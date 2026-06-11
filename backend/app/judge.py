from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from backend.app.extraction import ExtractedReceipt
from backend.app.openai_utils import create_openai_client, with_retry
from backend.app.retrieval import RetrievalResult, RetrievalService
from backend.app.settings import Settings


class CitedClause(BaseModel):
    doc_id: str
    section: str
    quoted_text: str


class JudgedVerdict(BaseModel):
    verdict: Literal["compliant", "flagged", "rejected"]
    reasoning: str
    cited_clauses: list[CitedClause] = Field(default_factory=list)
    model_confidence: float = Field(ge=0.0, le=1.0)


class JudgmentOutcome(BaseModel):
    verdict: Literal["compliant", "flagged", "rejected"]
    reasoning: str
    cited_clauses: list[CitedClause] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    retrieval_similarity: float = Field(ge=0.0, le=1.0)
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    issues: list[str] = Field(default_factory=list)


JUDGE_SYSTEM_PROMPT = (
    "You are an expense pre-review judge. "
    "You must decide one verdict: compliant, flagged, or rejected. "
    "Use only provided extracted receipt fields, trip context, and retrieved policy chunks. "
    "Judge only what is explicitly present; never speculate or invent facts (no invented client-hosting, approvals, "
    "alternative-rate availability, or missing context assumptions). "
    "Any citation must be a verbatim quote from one of the retrieved chunks. "
    "Alcoholic drinks must be checked against the alcohol policy independently of the meal cap. If the trip is solo (one traveler, no other Northwind employees listed, or the trip purpose says solo) and the meal contains alcohol, flag the alcohol portion as non-reimbursable and cite the alcohol clause, even when the meal total is under the per-person cap. Non-alcoholic drinks are part of the meal total. Do not assume client hosting or apply any hosting cap unless the receipt names external attendees. "
    "If attendees are missing and amount is within per-person meal cap, treat as a solo meal by default. "
    "For meals, evaluate both per-person cap and tip policy; any tip above allowed percent of PRE-TAX subtotal is "
    "non-reimbursable for the excess portion. "
    "For lodging, caps are PER NIGHT on room rate excluding tax; compare per-night room rate to the city/tier cap and "
    "never compare full-stay total to a per-night cap. "
    "Require approval/justification only when amount actually exceeds the applicable cap. "
    "Use flagged only for genuine evidence-based ambiguity, not theoretical possibilities."
)


def _normalize_for_match(value: str) -> str:
    value = value.replace("\u2013", "-").replace("\u2014", "-")
    value = value.lower()
    value = re.sub(r"[^a-z0-9$%./\- ]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _tokens(value: str) -> list[str]:
    return [t for t in _normalize_for_match(value).split(" ") if t]


class JudgmentService:
    def __init__(self, settings: Settings, retrieval: RetrievalService) -> None:
        self._settings = settings
        self._retrieval = retrieval
        self._client = create_openai_client(settings)

    def judge_line_item(
        self,
        extracted: ExtractedReceipt,
        extraction_confidence: float,
        trip_context: str,
    ) -> JudgmentOutcome:
        query = self._build_query(extracted, trip_context)
        retrieved = self._retrieve_for_judgment(extracted=extracted, trip_context=trip_context, base_query=query)
        if not retrieved:
            return JudgmentOutcome(
                verdict="flagged",
                reasoning="No relevant policy chunks were retrieved; requires human review.",
                cited_clauses=[],
                confidence=0.1,
                retrieval_similarity=0.0,
                extraction_confidence=extraction_confidence,
                issues=["no policy chunks retrieved"],
            )

        try:
            judged = self._judge_with_model(extracted, trip_context, retrieved)
        except Exception as exc:
            return JudgmentOutcome(
                verdict="flagged",
                reasoning="Judgment model failed; requires human review.",
                cited_clauses=[],
                confidence=0.1,
                retrieval_similarity=max(item.similarity for item in retrieved),
                extraction_confidence=extraction_confidence,
                issues=[f"judgment failed: {exc}"],
            )

        verified_citations, invalid_count = self._verify_citations(judged.cited_clauses, retrieved)
        retrieval_similarity = max(item.similarity for item in retrieved)
        issues: list[str] = []
        verdict = judged.verdict
        reasoning = judged.reasoning

        if invalid_count > 0:
            issues.append(f"removed {invalid_count} non-verbatim citation(s)")

        if verdict != "flagged" and not verified_citations:
            issues.append("missing valid citation support for non-flagged verdict")
            verdict = "flagged"
            reasoning = "Insufficient citation support after verification; routed for human review."

        verdict, reasoning, lodging_issue = self._apply_lodging_guardrail(
            extracted=extracted,
            verdict=verdict,
            reasoning=reasoning,
            retrieved=retrieved,
        )
        if lodging_issue:
            issues.append(lodging_issue)

        if retrieval_similarity < self._settings.retrieval_min_similarity:
            issues.append("retrieval similarity below threshold")
            verdict = "flagged"

        if extraction_confidence < 0.55:
            issues.append("low extraction confidence")
            verdict = "flagged"

        confidence = self._compose_confidence(
            extraction_confidence=extraction_confidence,
            retrieval_similarity=retrieval_similarity,
            model_confidence=judged.model_confidence,
            issue_count=len(issues),
        )

        return JudgmentOutcome(
            verdict=verdict,
            reasoning=reasoning,
            cited_clauses=verified_citations,
            confidence=confidence,
            retrieval_similarity=retrieval_similarity,
            extraction_confidence=extraction_confidence,
            issues=issues,
        )

    @classmethod
    def _apply_lodging_guardrail(
        cls,
        extracted: ExtractedReceipt,
        verdict: Literal["compliant", "flagged", "rejected"],
        reasoning: str,
        retrieved: list[RetrievalResult],
    ) -> tuple[Literal["compliant", "flagged", "rejected"], str, str | None]:
        if (extracted.category or "").lower() != "lodging":
            return verdict, reasoning, None
        if extracted.nightly_rate is None:
            return verdict, reasoning, None

        nightly_cap = cls._extract_lodging_nightly_cap(retrieved)
        if nightly_cap is None:
            return verdict, reasoning, None

        if extracted.nightly_rate <= nightly_cap + 0.01 and verdict == "rejected":
            nights_text = (
                f" across {extracted.nights} night(s)" if extracted.nights is not None else ""
            )
            return (
                "flagged",
                (
                    f"The extracted nightly room rate (${extracted.nightly_rate:.2f}) is within the inferred "
                    f"nightly cap (${nightly_cap:.2f}){nights_text}, so rejection is "
                    "not justified. Routed for human confirmation."
                ),
                "lodging guardrail prevented over-cap rejection",
            )
        return verdict, reasoning, None

    @staticmethod
    def _build_query(extracted: ExtractedReceipt, trip_context: str) -> str:
        category = (extracted.category or "unknown").strip().lower()
        amount_text = f"{extracted.amount:.2f}" if extracted.amount is not None else "unknown"
        meal_type = (extracted.meal_type or "n/a").strip().lower()
        city = JudgmentService._infer_policy_city(trip_context=trip_context, line_details=extracted.line_details)

        rule_focus = "general reimbursability, documentation requirements, and approval exceptions"
        if category == "lodging":
            rule_focus = "lodging city tier, nightly cap, mandatory tax inclusion, and exception documentation"
        elif category == "meal":
            rule_focus = "meal per-person caps, alcohol exclusions, and attendee/context requirements"
        elif category in {"ground transport", "travel"}:
            rule_focus = "transport eligibility, fare class limits, and reimbursable ground/air expense rules"
        elif category == "conference":
            rule_focus = "conference registration eligibility, approval requirements, and reimbursable add-ons"

        facts = [
            f"category={category}",
            f"amount_usd={amount_text}",
            f"currency={(extracted.currency or 'unknown').upper()}",
            f"meal_type={meal_type}",
            f"nights={extracted.nights if extracted.nights is not None else 'unknown'}",
            f"nightly_rate={extracted.nightly_rate if extracted.nightly_rate is not None else 'unknown'}",
            f"city={city or 'unknown'}",
        ]
        return (
            "Retrieve governing Northwind policy clauses for expense judgment. "
            f"Rule focus: {rule_focus}. "
            f"Facts: {'; '.join(facts)}. "
            "Prefer explicit cap/threshold clauses over examples, definitions, and related-doc sections. "
            "Do not rely on vendor names or narrative trip-purpose wording for retrieval ranking."
        )

    def _retrieve_for_judgment(
        self,
        extracted: ExtractedReceipt,
        trip_context: str,
        base_query: str,
    ) -> list[RetrievalResult]:
        top_k = self._settings.retrieval_top_k
        expanded_k = max(top_k * 2, 12)
        merged: list[RetrievalResult] = self._retrieval.retrieve(query=base_query, k=expanded_k)

        category = (extracted.category or "").lower()
        city = self._infer_policy_city(trip_context=trip_context, line_details=extracted.line_details) or ""
        if category in {"ground transport", "travel", "air travel"}:
            merged.extend(
                self._retrieval.retrieve(
                    query="rideshare airport transfer ground transportation reimbursable standard service policy",
                    k=expanded_k,
                )
            )
            merged.extend(
                self._retrieval.retrieve(
                    query="air travel reimbursement commercial passenger flight business purpose policy scope",
                    k=expanded_k,
                )
            )
        if category in {"lodging", "hotel accommodation", "accommodation", "hotel stay"}:
            merged.extend(
                self._retrieval.retrieve(
                    query=f"city tier rate caps lodging per night cap {city}".strip(),
                    k=expanded_k,
                )
            )
        if category == "meal":
            merged.extend(
                self._retrieval.retrieve(
                    query="alcohol not reimbursable solo travel meal per person cap breakfast lunch dinner tip",
                    k=expanded_k,
                )
            )

        deduped: list[RetrievalResult] = []
        seen: set[str] = set()
        for item in merged:
            if item.chunk_id in seen:
                continue
            seen.add(item.chunk_id)
            deduped.append(item)

        ranked = sorted(
            deduped,
            key=lambda row: (
                self._category_signal_score(category, row),
                row.similarity,
            ),
            reverse=True,
        )
        return ranked[:top_k]

    @staticmethod
    def _category_signal_score(category: str, row: RetrievalResult) -> float:
        text = f"{row.section} {row.text}".lower()
        score = 0.0
        if "related documents" in text:
            score -= 0.5
        if category in {"ground transport", "travel", "air travel"}:
            if any(token in text for token in ("rideshare", "uber", "lyft", "airport transfer", "ground transportation")):
                score += 0.4
            if any(token in text for token in ("air travel", "commercial passenger flight", "seat selection")):
                score += 0.3
        if category in {"lodging", "hotel accommodation", "accommodation", "hotel stay"}:
            if any(token in text for token in ("tier", "city", "per night", "lodging", "hotel", "rate caps")):
                score += 0.4
        if category == "meal":
            if any(tok in text for tok in ("alcohol", "alcoholic", "per person", "meal cap", "tip")):
                score += 0.4
        return score

    @staticmethod
    def _infer_policy_city(trip_context: str, line_details: str | None) -> str | None:
        known_cities = [
            "Boston",
            "New York",
            "San Francisco",
            "Washington",
            "Los Angeles",
            "Seattle",
            "Chicago",
            "Denver",
            "Atlanta",
            "Austin",
            "Dallas",
            "Houston",
            "Miami",
            "Portland",
            "San Diego",
            "Toronto",
            "Amsterdam",
            "Berlin",
            "London",
            "Zurich",
            "Tokyo",
            "Singapore",
        ]
        haystack = f"{trip_context or ''} {line_details or ''}".lower()
        for city in known_cities:
            if city.lower() in haystack:
                return city
        return None

    def _judge_with_model(
        self,
        extracted: ExtractedReceipt,
        trip_context: str,
        retrieved: list[RetrievalResult],
    ) -> JudgedVerdict:
        context_blocks = []
        for item in retrieved:
            context_blocks.append(
                (
                    f"doc_id={item.doc_id}, section={item.section}, similarity={item.similarity:.4f}\n"
                    f"{item.text}"
                )
            )
        completion = with_retry(
            lambda: self._client.beta.chat.completions.parse(
                model=self._settings.judge_model,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            "Extracted receipt (JSON-like):\n"
                            f"{extracted.model_dump_json(indent=2)}\n\n"
                            f"Trip context:\n{trip_context}\n\n"
                            "Retrieved policy chunks:\n"
                            + "\n\n---\n\n".join(context_blocks)
                        ),
                    },
                ],
                response_format=JudgedVerdict,
            ),
            settings=self._settings,
            op_name="judgment",
        )
        return completion.choices[0].message.parsed

    @staticmethod
    def _verify_citations(
        citations: list[CitedClause], retrieved: list[RetrievalResult]
    ) -> tuple[list[CitedClause], int]:
        chunks = [
            (_normalize_for_match(item.text), _normalize_for_match(item.doc_id))
            for item in retrieved
        ]
        verified: list[CitedClause] = []
        invalid_count = 0
        for citation in citations:
            quote_tokens = _tokens(citation.quoted_text)
            cited_doc = _normalize_for_match(citation.doc_id)
            if not quote_tokens:
                invalid_count += 1
                continue
            matched = False
            for chunk_text, chunk_doc in chunks:
                if cited_doc and cited_doc != chunk_doc:
                    continue
                hits = sum(1 for tok in quote_tokens if tok in chunk_text)
                if hits / len(quote_tokens) >= 0.8:
                    matched = True
                    break
            if matched:
                verified.append(citation)
            else:
                invalid_count += 1
        return verified, invalid_count

    @staticmethod
    def _extract_lodging_nightly_cap(retrieved: list[RetrievalResult]) -> float | None:
        cap_matches: list[float] = []
        cap_pattern = re.compile(r"\$([0-9]+(?:\.[0-9]{1,2})?)\s*(?:/|per)\s*night", re.IGNORECASE)
        for item in retrieved:
            for matched in cap_pattern.findall(item.text):
                try:
                    cap_matches.append(float(matched))
                except ValueError:
                    continue
        if not cap_matches:
            return None
        return min(cap_matches)

    @staticmethod
    def _compose_confidence(
        extraction_confidence: float,
        retrieval_similarity: float,
        model_confidence: float,
        issue_count: int,
    ) -> float:
        base = (0.35 * extraction_confidence) + (0.35 * retrieval_similarity) + (0.30 * model_confidence)
        penalty = min(0.4, issue_count * 0.08)
        return max(0.05, min(0.95, base - penalty))
