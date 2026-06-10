from __future__ import annotations

from pathlib import Path

from backend.app.extraction import ExtractionService
from backend.app.judge import JudgmentService
from backend.app.retrieval import RetrievalService
from backend.app.settings import Settings


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    settings = Settings()
    assert_true(bool(settings.openai_api_key), "OPENAI_API_KEY is required for Part 4 verification.")

    retrieval = RetrievalService(settings)
    retrieval.build_index_if_missing()
    extraction = ExtractionService(settings)
    judge = JudgmentService(settings, retrieval)

    samples = [
        (
            "./data/submissions/01_clean_denver/receipts/04_dinner_mercantile.pdf",
            "Client review trip in Denver with business meals and travel expenses.",
        ),
        (
            "./data/submissions/04_alcohol_solo_travel/receipts/05_dinner_franklin.pdf",
            "Solo carrier research trip in Austin with no client entertainment attendees.",
        ),
    ]

    for path, trip_context in samples:
        receipt = Path(path)
        assert_true(receipt.exists(), f"Missing sample receipt: {path}")
        extraction_outcome = extraction.extract_receipt(path)
        judgment = judge.judge_line_item(
            extracted=extraction_outcome.extracted,
            extraction_confidence=extraction_outcome.confidence,
            trip_context=trip_context,
        )
        assert_true(
            judgment.verdict in {"compliant", "flagged", "rejected"},
            f"Unexpected verdict for {path}: {judgment.verdict}",
        )
        assert_true(
            0.0 <= judgment.confidence <= 1.0,
            f"Confidence out of range for {path}: {judgment.confidence}",
        )
        if judgment.verdict != "flagged":
            assert_true(
                len(judgment.cited_clauses) > 0,
                f"Non-flagged verdict missing citations for {path}",
            )
        print(
            {
                "receipt": path,
                "verdict": judgment.verdict,
                "confidence": round(judgment.confidence, 4),
                "citations": len(judgment.cited_clauses),
                "issues": judgment.issues,
            }
        )

    print("Part 4 verification passed.")


if __name__ == "__main__":
    main()
