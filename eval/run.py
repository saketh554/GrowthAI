from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from backend.app.extraction import ExtractionService
from backend.app.judge import JudgmentOutcome, JudgmentService
from backend.app.qa import QAService, QAResult
from backend.app.retrieval import RetrievalService
from backend.app.settings import Settings


def _normalize(value: str) -> str:
    value = value.replace("\u2013", "-").replace("\u2014", "-").lower()
    value = re.sub(r"[^a-z0-9$%./ -]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


class LineItemExpectation(BaseModel):
    receipt_path: str
    expected_verdict: Literal["compliant", "flagged", "rejected"] | None = None
    expected_policy_doc: str | None = None
    key_clause: str | None = None
    trip_context: str | None = None


class QAExpectation(BaseModel):
    question: str
    expected_refused: bool | None = None
    out_of_scope: bool = False


class ExpectedOutcomes(BaseModel):
    line_items: list[LineItemExpectation] = Field(default_factory=list)
    qa: list[QAExpectation] = Field(default_factory=list)


class MetricCounter:
    def __init__(self) -> None:
        self.correct = 0
        self.total = 0

    def add(self, condition: bool) -> None:
        self.total += 1
        if condition:
            self.correct += 1

    def rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.correct / self.total

    def format(self) -> str:
        if self.total == 0:
            return "n/a"
        return f"{self.correct}/{self.total} ({self.rate():.1%})"


def _load_expected(path: Path) -> ExpectedOutcomes:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ExpectedOutcomes.model_validate(payload)


def _infer_trip_context(receipt_path: Path) -> str:
    for parent in [receipt_path.parent, *receipt_path.parents]:
        employee_info = parent / "employee_info.json"
        if employee_info.exists():
            payload = json.loads(employee_info.read_text(encoding="utf-8"))
            return str(payload.get("trip_purpose", ""))
    return ""


def _doc_match(expected_doc: str, actual_docs: list[str]) -> bool:
    expected = _normalize(expected_doc)
    if not expected:
        return False
    for doc_id in actual_docs:
        doc = _normalize(doc_id)
        if doc == expected or doc.startswith(expected) or expected in doc:
            return True
    return False


def _quote_matches_key_clause(citations: list[str], key_clause: str) -> bool:
    expected = _normalize(key_clause)
    if not expected:
        return False
    return any(expected in _normalize(quote) for quote in citations)


def _print_metric_table(
    verdict_accuracy: MetricCounter,
    retrieval_quality: MetricCounter,
    citation_correctness: MetricCounter,
    qa_refusal_accuracy: MetricCounter,
    out_of_scope_refusal_rate: MetricCounter,
) -> None:
    rows = [
        ("verdict accuracy", verdict_accuracy.format()),
        ("retrieval quality (expected doc in top-k)", retrieval_quality.format()),
        ("citation correctness", citation_correctness.format()),
        ("qa refusal accuracy", qa_refusal_accuracy.format()),
        ("out-of-scope refusal rate", out_of_scope_refusal_rate.format()),
    ]
    metric_width = max(len(name) for name, _ in rows) + 2
    print("\nMetrics")
    print("-" * (metric_width + 22))
    print(f"{'metric'.ljust(metric_width)}value")
    print("-" * (metric_width + 22))
    for name, value in rows:
        print(f"{name.ljust(metric_width)}{value}")
    print("-" * (metric_width + 22))


def _evaluate_line_items(
    expected: ExpectedOutcomes,
    extraction: ExtractionService,
    judge: JudgmentService,
) -> tuple[MetricCounter, MetricCounter, MetricCounter]:
    verdict_accuracy = MetricCounter()
    retrieval_quality = MetricCounter()
    citation_correctness = MetricCounter()

    if expected.line_items:
        print("Line-item cases")
    for case in expected.line_items:
        receipt = Path(case.receipt_path)
        if not receipt.exists():
            raise FileNotFoundError(f"receipt not found for evaluation: {case.receipt_path}")

        trip_context = case.trip_context or _infer_trip_context(receipt)
        extraction_outcome = extraction.extract_receipt(str(receipt))
        outcome: JudgmentOutcome = judge.judge_line_item(
            extracted=extraction_outcome.extracted,
            extraction_confidence=extraction_outcome.confidence,
            trip_context=trip_context,
        )

        if case.expected_verdict is not None:
            verdict_accuracy.add(outcome.verdict == case.expected_verdict)

        if case.expected_policy_doc:
            query = judge._build_query(extraction_outcome.extracted, trip_context)  # noqa: SLF001
            retrieved = judge._retrieve_for_judgment(  # noqa: SLF001
                extracted=extraction_outcome.extracted,
                trip_context=trip_context,
                base_query=query,
            )
            retrieval_quality.add(
                _doc_match(case.expected_policy_doc, [item.doc_id for item in retrieved])
            )

        if outcome.verdict != "flagged":
            quote_texts = [item.quoted_text for item in outcome.cited_clauses]
            if case.key_clause:
                citation_correctness.add(_quote_matches_key_clause(quote_texts, case.key_clause))
            else:
                citation_correctness.add(len(quote_texts) > 0)

        print(
            f"- {case.receipt_path}: verdict={outcome.verdict}, "
            f"citations={len(outcome.cited_clauses)}, retrieval_similarity={outcome.retrieval_similarity:.3f}"
        )

    return verdict_accuracy, retrieval_quality, citation_correctness


def _evaluate_qa(expected: ExpectedOutcomes, qa_service: QAService) -> tuple[MetricCounter, MetricCounter]:
    qa_refusal_accuracy = MetricCounter()
    out_of_scope_refusal_rate = MetricCounter()

    if expected.qa:
        print("\nQA cases")
    for case in expected.qa:
        result: QAResult = qa_service.answer(case.question)
        if case.expected_refused is not None:
            qa_refusal_accuracy.add(result.refused == case.expected_refused)
        if case.out_of_scope:
            out_of_scope_refusal_rate.add(result.refused)
        print(f"- {case.question!r}: refused={result.refused}, reason={result.refusal_reason}")

    return qa_refusal_accuracy, out_of_scope_refusal_rate


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Part 8 evaluation harness.")
    parser.add_argument(
        "--expected",
        type=Path,
        required=True,
        help="Path to expected-outcomes JSON file.",
    )
    args = parser.parse_args()

    if not args.expected.exists():
        raise FileNotFoundError(f"expected file not found: {args.expected}")

    settings = Settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required to run eval harness.")

    expected = _load_expected(args.expected)
    extraction = ExtractionService(settings)
    retrieval_for_judge = RetrievalService(settings)
    retrieval_for_judge.build_index_if_missing()
    judge = JudgmentService(settings, retrieval_for_judge)
    qa_service = QAService(settings, retrieval_for_judge)

    print(f"Loaded expected file: {args.expected}")
    print(
        f"Cases: line_items={len(expected.line_items)}, qa={len(expected.qa)}, "
        f"retrieval_top_k={settings.retrieval_top_k}"
    )

    verdict_accuracy, retrieval_quality, citation_correctness = _evaluate_line_items(
        expected=expected,
        extraction=extraction,
        judge=judge,
    )
    qa_refusal_accuracy, out_of_scope_refusal_rate = _evaluate_qa(expected, qa_service)

    _print_metric_table(
        verdict_accuracy=verdict_accuracy,
        retrieval_quality=retrieval_quality,
        citation_correctness=citation_correctness,
        qa_refusal_accuracy=qa_refusal_accuracy,
        out_of_scope_refusal_rate=out_of_scope_refusal_rate,
    )


if __name__ == "__main__":
    main()
