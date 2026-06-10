from __future__ import annotations

import re

from openai import OpenAI
from pydantic import BaseModel, Field

from backend.app.judge import CitedClause
from backend.app.retrieval import RetrievalResult, RetrievalService
from backend.app.settings import Settings


class QAResult(BaseModel):
    answer: str
    refused: bool
    cited_clauses: list[CitedClause] = Field(default_factory=list)


class QAService:
    def __init__(self, settings: Settings, retrieval: RetrievalService) -> None:
        self._settings = settings
        self._retrieval = retrieval
        self._client = OpenAI(api_key=settings.openai_api_key)

    def answer(self, question: str) -> QAResult:
        retrieved = self._retrieval.retrieve(query=question, k=self._settings.retrieval_top_k)
        if not retrieved:
            return QAResult(
                answer="I can't find this in the policy library.",
                refused=True,
                cited_clauses=[],
            )

        max_similarity = max(item.similarity for item in retrieved)
        if max_similarity < self._settings.retrieval_min_similarity:
            return QAResult(
                answer="I can't find this in the policy library.",
                refused=True,
                cited_clauses=[],
            )

        result = self._model_answer(question, retrieved)
        verified = self._verify_citations(result.cited_clauses, retrieved)
        if not verified:
            return QAResult(
                answer="I can't find enough grounded support in the policy library.",
                refused=True,
                cited_clauses=[],
            )
        return QAResult(answer=result.answer, refused=result.refused, cited_clauses=verified)

    def _model_answer(self, question: str, retrieved: list[RetrievalResult]) -> QAResult:
        chunks = []
        for item in retrieved:
            chunks.append(f"doc_id={item.doc_id}, section={item.section}\n{item.text}")
        completion = self._client.beta.chat.completions.parse(
            model=self._settings.judge_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Answer policy-only questions using only the provided policy chunks. "
                        "If out of scope, refuse and set refused=true. "
                        "Any citation quote must be verbatim from a chunk."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nPolicy chunks:\n" + "\n\n---\n\n".join(chunks),
                },
            ],
            response_format=QAResult,
        )
        return completion.choices[0].message.parsed

    @staticmethod
    def _verify_citations(
        citations: list[CitedClause], retrieved: list[RetrievalResult]
    ) -> list[CitedClause]:
        normalized_chunks = [re.sub(r"\s+", " ", item.text).strip().lower() for item in retrieved]
        verified: list[CitedClause] = []
        for citation in citations:
            quote = re.sub(r"\s+", " ", citation.quoted_text).strip().lower()
            if quote and any(quote in chunk for chunk in normalized_chunks):
                verified.append(citation)
        return verified
