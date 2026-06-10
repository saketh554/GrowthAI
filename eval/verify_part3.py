from __future__ import annotations

from pathlib import Path

from backend.app.extraction import ExtractionService
from backend.app.settings import Settings


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    settings = Settings()
    assert_true(bool(settings.openai_api_key), "OPENAI_API_KEY is required for Part 3 verification.")

    extraction = ExtractionService(settings)

    sample_pdf = Path("./data/submissions/01_clean_denver/receipts/01_united_airlines.pdf")
    assert_true(sample_pdf.exists(), f"Sample PDF missing: {sample_pdf}")
    pdf_outcome = extraction.extract_receipt(str(sample_pdf))
    assert_true(pdf_outcome.source_type in {"pdf_text", "pdf_vision"}, "Unexpected PDF source type.")
    assert_true(pdf_outcome.extracted.amount is not None, "PDF extraction missing amount.")
    assert_true(bool(pdf_outcome.extracted.vendor), "PDF extraction missing vendor.")

    synthetic_txt = Path("./data/part3_synthetic_receipt.txt")
    synthetic_txt.write_text(
        "Vendor: Metro Diner\nDate: 2025-06-10\nAmount: 28.50 USD\nCategory: meal\nDetails: team lunch\n",
        encoding="utf-8",
    )
    try:
        txt_outcome = extraction.extract_receipt(str(synthetic_txt))
        assert_true(txt_outcome.source_type == "txt", "Unexpected TXT source type.")
        assert_true(txt_outcome.extracted.amount is not None, "TXT extraction missing amount.")
        assert_true(bool(txt_outcome.extracted.vendor), "TXT extraction missing vendor.")
    finally:
        if synthetic_txt.exists():
            synthetic_txt.unlink()

    missing_outcome = extraction.extract_receipt("./data/does_not_exist.pdf")
    assert_true(missing_outcome.source_type == "failed", "Missing file should fail gracefully.")
    assert_true(missing_outcome.for_human_review, "Missing file should be marked for human review.")

    print("Part 3 verification passed.")
    print(f"PDF source type: {pdf_outcome.source_type}, confidence={pdf_outcome.confidence}")
    print(f"TXT source type: {txt_outcome.source_type}, confidence={txt_outcome.confidence}")
    print(f"Missing-file handling: {missing_outcome.issues[0]}")


if __name__ == "__main__":
    main()
