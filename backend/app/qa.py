from __future__ import annotations

import re

from pydantic import BaseModel, Field

from backend.app.judge import CitedClause
from backend.app.openai_utils import create_openai_client, with_retry
from backend.app.retrieval import RetrievalResult, RetrievalService
from backend.app.settings import Settings


class QAResult(BaseModel):
    answer: str
    refused: bool
    refusal_reason: str | None = None
    cited_clauses: list[CitedClause] = Field(default_factory=list)


class QAService:
    def __init__(self, settings: Settings, retrieval: RetrievalService) -> None:
        self._settings = settings
        self._retrieval = retrieval
        self._client = create_openai_client(settings)

    _OUT_OF_SCOPE_PATTERNS = [
        r"\bweather\b",
        r"\bstock\b",
        r"\bbitcoin\b",
        r"\bsports?\b",
        r"\bmovie\b",
        r"\brecipe\b",
        r"\bprogramming\b",
        r"\bpython\b",
        r"\bjavascript\b",
        r"\bwho (is|was)\b",
        r"\bcapital of\b",
    ]

    def answer(self, question: str) -> QAResult:
        if self._is_out_of_scope(question):
            return QAResult(
                answer="I can't answer that because it is outside the policy library scope.",
                refused=True,
                refusal_reason="out_of_scope",
                cited_clauses=[],
            )

        retrieved = self._retrieval.retrieve(query=question, k=self._settings.retrieval_top_k)
        if not retrieved:
            return QAResult(
                answer="I can't find this in the policy library.",
                refused=True,
                refusal_reason="no_retrieval_results",
                cited_clauses=[],
            )

        max_similarity = max(item.similarity for item in retrieved)
        if max_similarity < self._settings.retrieval_min_similarity:
            return QAResult(
                answer="I can't find this in the policy library.",
                refused=True,
                refusal_reason="low_similarity",
                cited_clauses=[],
            )

        result = self._model_answer(question, retrieved)
        verified = self._verify_citations(result.cited_clauses, retrieved)
        if result.refused:
            return QAResult(
                answer=result.answer,
                refused=True,
                refusal_reason=result.refusal_reason or "model_refusal",
                cited_clauses=[],
            )
        if not verified:
            return QAResult(
                answer="I can't find enough grounded support in the policy library.",
                refused=True,
                refusal_reason="missing_grounded_citations",
                cited_clauses=[],
            )
        return QAResult(
            answer=result.answer,
            refused=False,
            refusal_reason=None,
            cited_clauses=verified,
        )

    def _model_answer(self, question: str, retrieved: list[RetrievalResult]) -> QAResult:
        chunks = []
        for item in retrieved:
            chunks.append(f"doc_id={item.doc_id}, section={item.section}\n{item.text}")
        completion = with_retry(
            lambda: self._client.beta.chat.completions.parse(
                model=self._settings.judge_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Answer policy-only questions using only the provided policy chunks. "
                            "If out of scope, refuse and set refused=true with refusal_reason='out_of_scope'. "
                            "If information is weak or missing, refuse with refusal_reason='insufficient_policy_support'. "
                            "If you answer, set refused=false and refusal_reason=null. "
                            "Any citation quote must be verbatim from a chunk."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Question: {question}\n\nPolicy chunks:\n" + "\n\n---\n\n".join(chunks),
                    },
                ],
                response_format=QAResult,
            ),
            settings=self._settings,
            op_name="qa",
        )
        return completion.choices[0].message.parsed

    @classmethod
    def _is_out_of_scope(cls, question: str) -> bool:
        lowered = question.lower()
        return any(re.search(pattern, lowered) is not None for pattern in cls._OUT_OF_SCOPE_PATTERNS)

    @staticmethod
    def _verify_citations(
        citations: list[CitedClause], retrieved: list[RetrievalResult]
    ) -> list[CitedClause]:
        def norm(v: str) -> str:
            v = v.replace("\u2013", "-").replace("\u2014", "-").lower()
            v = re.sub(r"[^a-z0-9$%./\- ]", " ", v)
            return re.sub(r"\s+", " ", v).strip()

        chunks = [(norm(i.text), norm(i.doc_id)) for i in retrieved]
        verified: list[CitedClause] = []
        for citation in citations:
            quote_tokens = [t for t in norm(citation.quoted_text).split(" ") if t]
            cited_doc = norm(citation.doc_id)
            if not quote_tokens:
                continue
            for chunk_text, chunk_doc in chunks:
                if cited_doc and cited_doc != chunk_doc:
                    continue
                if sum(1 for t in quote_tokens if t in chunk_text) / len(quote_tokens) >= 0.8:
                    verified.append(citation)
                    break
        return verified
