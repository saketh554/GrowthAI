from __future__ import annotations

from collections import Counter
from pathlib import Path

from backend.app.extraction import ExtractionService
from backend.app.settings import Settings


def main() -> None:
    settings = Settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for bulk extraction verification.")

    base = Path("./data/submissions")
    receipts = sorted(base.glob("*/receipts/*.pdf"))
    if not receipts:
        raise RuntimeError("No sample PDF receipts found under ./data/submissions.")

    service = ExtractionService(settings)
    source_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()
    total = len(receipts)
    high_conf = 0
    missing_core = 0
    failed = 0

    for receipt in receipts:
        outcome = service.extract_receipt(str(receipt))
        source_counter[outcome.source_type] += 1
        if outcome.extracted.category:
            category_counter[outcome.extracted.category] += 1
        if outcome.confidence >= 0.75:
            high_conf += 1
        if (
            not outcome.extracted.vendor
            or outcome.extracted.amount is None
            or not outcome.extracted.currency
            or not outcome.extracted.date
        ):
            missing_core += 1
        if outcome.source_type == "failed":
            failed += 1

    print("Part 3 bulk verification completed.")
    print(f"Receipts processed: {total}")
    print(f"High-confidence extractions (>=0.75): {high_conf}/{total}")
    print(f"Missing core fields (vendor/date/amount/currency): {missing_core}/{total}")
    print(f"Failures: {failed}/{total}")
    print(f"Source type breakdown: {dict(source_counter)}")
    print(f"Top categories: {category_counter.most_common(5)}")

    if failed > 0:
        raise AssertionError("At least one receipt failed extraction.")


if __name__ == "__main__":
    main()
