from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from backend.app.extraction import ExtractionService
from backend.app.judge import JudgmentService
from backend.app.retrieval import RetrievalService
from backend.app.settings import Settings


def main() -> None:
    settings = Settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for Part 4 bulk verification.")

    base = Path("./data/submissions")
    submission_dirs = sorted([path for path in base.iterdir() if path.is_dir()])
    if not submission_dirs:
        raise RuntimeError("No submission directories found under ./data/submissions.")

    retrieval = RetrievalService(settings)
    retrieval.build_index_if_missing()
    extraction = ExtractionService(settings)
    judge = JudgmentService(settings, retrieval)

    verdict_counter: Counter[str] = Counter()
    source_counter: Counter[str] = Counter()
    issue_counter: Counter[str] = Counter()
    total = 0
    failures = 0
    non_flagged = 0
    non_flagged_with_citations = 0
    confidence_sum = 0.0
    retrieval_sum = 0.0

    for submission_dir in submission_dirs:
        employee_info_path = submission_dir / "employee_info.json"
        if not employee_info_path.exists():
            continue
        employee_info = json.loads(employee_info_path.read_text(encoding="utf-8"))
        trip_context = employee_info.get("trip_purpose", "")

        receipts_dir = submission_dir / "receipts"
        for receipt_path in sorted(receipts_dir.glob("*.pdf")):
            total += 1
            extraction_outcome = extraction.extract_receipt(str(receipt_path))
            judgment = judge.judge_line_item(
                extracted=extraction_outcome.extracted,
                extraction_confidence=extraction_outcome.confidence,
                trip_context=trip_context,
            )

            source_counter[extraction_outcome.source_type] += 1
            verdict_counter[judgment.verdict] += 1
            confidence_sum += judgment.confidence
            retrieval_sum += judgment.retrieval_similarity

            if extraction_outcome.source_type == "failed":
                failures += 1

            if judgment.verdict != "flagged":
                non_flagged += 1
                if judgment.cited_clauses:
                    non_flagged_with_citations += 1

            for issue in judgment.issues:
                issue_counter[issue] += 1

    if total == 0:
        raise RuntimeError("No receipt files were processed.")

    avg_confidence = confidence_sum / total
    avg_retrieval_similarity = retrieval_sum / total
    citation_coverage = (
        non_flagged_with_citations / non_flagged if non_flagged > 0 else 1.0
    )

    print("Part 4 bulk verification completed.")
    print(f"Receipts judged: {total}")
    print(f"Extraction source breakdown: {dict(source_counter)}")
    print(f"Verdict breakdown: {dict(verdict_counter)}")
    print(f"Average final confidence: {avg_confidence:.4f}")
    print(f"Average retrieval similarity: {avg_retrieval_similarity:.4f}")
    print(
        f"Citation coverage for non-flagged verdicts: {non_flagged_with_citations}/{non_flagged} "
        f"({citation_coverage:.2%})"
    )
    print(f"Top issues: {issue_counter.most_common(5)}")
    print(f"Extraction failures: {failures}/{total}")

    if failures > 0:
        raise AssertionError("At least one receipt failed extraction.")
    if citation_coverage < 1.0:
        raise AssertionError("Found non-flagged verdicts without valid citations.")


if __name__ == "__main__":
    main()
