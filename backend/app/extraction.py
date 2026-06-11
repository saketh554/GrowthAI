from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path
from typing import Literal

import fitz
from pydantic import BaseModel, Field

from backend.app.openai_utils import create_openai_client, with_retry
from backend.app.settings import Settings


class ExtractedReceipt(BaseModel):
    vendor: str | None = None
    date: str | None = None
    amount: float | None = None
    currency: str | None = None
    category: str | None = None
    nights: int | None = None
    nightly_rate: float | None = None
    subtotal: float | None = None
    tip: float | None = None
    meal_type: str | None = None
    line_details: str | None = None
    attendees: list[str] | None = None


class ExtractionOutcome(BaseModel):
    extracted: ExtractedReceipt
    confidence: float
    for_human_review: bool
    source_type: Literal["pdf_text", "pdf_vision", "image_vision", "txt", "failed"]
    issues: list[str] = Field(default_factory=list)


SYSTEM_PROMPT = (
    "You extract one expense receipt into structured data. "
    "Return only values grounded in the provided content. "
    "If a field is missing or unclear, return null for that field. "
    "For lodging receipts, populate nights and nightly_rate (room rate per night, pre-tax). "
    "For meal receipts, populate subtotal (pre-tax food/drink subtotal before tax/tip) and tip."
)

DATE_PATTERNS = [
    ("%Y-%m-%d", re.compile(r"^\d{4}-\d{2}-\d{2}$")),
]

CATEGORY_SYNONYMS = {
    "travel": "Travel",
    "flight": "Travel",
    "airfare": "Travel",
    "lodging": "Lodging",
    "hotel": "Lodging",
    "transport": "Ground Transport",
    "transportation": "Ground Transport",
    "rideshare": "Ground Transport",
    "uber": "Ground Transport",
    "lyft": "Ground Transport",
    "meal": "Meal",
    "meals": "Meal",
    "food": "Meal",
    "conference": "Conference",
    "registration": "Conference",
}


class ExtractionService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = create_openai_client(settings)

    def extract_receipt(self, receipt_path: str) -> ExtractionOutcome:
        path = Path(receipt_path)
        if not path.exists():
            return self._failed(f"receipt not found: {receipt_path}")

        suffix = path.suffix.lower()
        try:
            if suffix == ".txt":
                text = path.read_text(encoding="utf-8")
                extracted = self._extract_from_text(text, path.name)
                return self._finalize(extracted, source_type="txt")

            if suffix == ".pdf":
                text = self._pdf_text(path)
                if text.strip():
                    extracted = self._extract_from_text(text, path.name)
                    return self._finalize(extracted, source_type="pdf_text")
                image_bytes = self._pdf_page_image(path)
                extracted = self._extract_from_image(image_bytes, "image/png", path.name)
                issues = ["pdf has no text layer; used vision fallback"]
                return self._finalize(extracted, source_type="pdf_vision", issues=issues)

            if suffix in {".jpg", ".jpeg", ".png"}:
                mime = mimetypes.guess_type(path.name)[0] or "image/png"
                extracted = self._extract_from_image(path.read_bytes(), mime, path.name)
                return self._finalize(extracted, source_type="image_vision")

            return self._failed(f"unsupported receipt format: {suffix or 'unknown'}")
        except Exception as exc:  # graceful request path
            return self._failed(f"failed to extract receipt: {exc}")

    def _extract_from_text(self, text: str, filename: str) -> ExtractedReceipt:
        completion = with_retry(
            lambda: self._client.beta.chat.completions.parse(
                model=self._settings.extraction_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Filename: {filename}\n\nReceipt text:\n{text}",
                    },
                ],
                response_format=ExtractedReceipt,
            ),
            settings=self._settings,
            op_name="extraction_text",
        )
        return completion.choices[0].message.parsed

    def _extract_from_image(self, image_bytes: bytes, mime: str, filename: str) -> ExtractedReceipt:
        data_uri = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('utf-8')}"
        completion = with_retry(
            lambda: self._client.beta.chat.completions.parse(
                model=self._settings.extraction_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Filename: {filename}. Extract the receipt fields."},
                            {"type": "image_url", "image_url": {"url": data_uri}},
                        ],
                    },
                ],
                response_format=ExtractedReceipt,
            ),
            settings=self._settings,
            op_name="extraction_image",
        )
        return completion.choices[0].message.parsed

    @staticmethod
    def _pdf_text(path: Path) -> str:
        doc = fitz.open(path)
        try:
            return "\n".join(page.get_text("text") for page in doc)
        finally:
            doc.close()

    @staticmethod
    def _pdf_page_image(path: Path) -> bytes:
        doc = fitz.open(path)
        try:
            page = doc[0]
            pix = page.get_pixmap()
            return pix.tobytes("png")
        finally:
            doc.close()

    def _finalize(
        self,
        extracted: ExtractedReceipt,
        source_type: Literal["pdf_text", "pdf_vision", "image_vision", "txt"],
        issues: list[str] | None = None,
    ) -> ExtractionOutcome:
        extracted = self._normalize_extracted(extracted)
        issue_list = list(issues or [])
        missing = []
        if not extracted.vendor:
            missing.append("vendor missing")
        if not extracted.date:
            missing.append("date missing")
        if extracted.amount is None:
            missing.append("amount missing")
        if not extracted.currency:
            missing.append("currency missing")
        if not extracted.category:
            missing.append("category missing")
        issue_list.extend(missing)

        if extracted.currency and extracted.currency.upper() not in {"USD", "$"}:
            issue_list.append(f"foreign currency detected: {extracted.currency}")

        confidence = 0.9 - (0.15 * len(missing))
        if source_type in {"pdf_vision", "image_vision"}:
            confidence -= 0.05
        if any(issue.startswith("foreign currency") for issue in issue_list):
            confidence = min(confidence, 0.35)
        confidence = max(0.05, min(0.95, confidence))
        for_human_review = confidence < 0.55 or bool(issue_list)

        return ExtractionOutcome(
            extracted=extracted,
            confidence=confidence,
            for_human_review=for_human_review,
            source_type=source_type,
            issues=issue_list,
        )

    def _normalize_extracted(self, extracted: ExtractedReceipt) -> ExtractedReceipt:
        vendor = extracted.vendor.strip() if extracted.vendor else None
        if vendor:
            vendor = re.sub(r"\s+", " ", vendor)

        currency = extracted.currency.strip().upper() if extracted.currency else None
        if currency in {"$", "US$", "USDOLLAR", "US DOLLAR"}:
            currency = "USD"

        category = extracted.category.strip().lower() if extracted.category else None
        normalized_category = CATEGORY_SYNONYMS.get(category, extracted.category)
        if normalized_category:
            normalized_category = normalized_category.strip()

        date = extracted.date.strip() if extracted.date else None
        normalized_date = date
        if date:
            cleaned = re.sub(r"\s+", " ", date).strip()
            parsed = self._try_parse_date(cleaned)
            normalized_date = parsed if parsed else cleaned

        meal_type = extracted.meal_type.strip().lower() if extracted.meal_type else None
        if meal_type in {"bf", "brkfst"}:
            meal_type = "breakfast"
        elif meal_type in {"lnch"}:
            meal_type = "lunch"
        elif meal_type in {"dnr"}:
            meal_type = "dinner"

        line_details = extracted.line_details.strip() if extracted.line_details else None
        attendees = [name.strip() for name in (extracted.attendees or []) if name.strip()] or None
        details_text = (line_details or "").lower()

        nights = extracted.nights if (extracted.nights is not None and extracted.nights > 0) else None
        if nights is None and line_details:
            nights = self._parse_nights_from_text(line_details)

        nightly_rate = extracted.nightly_rate if extracted.nightly_rate is not None else None
        if nightly_rate is None and line_details:
            nightly_rate = self._parse_nightly_rate_from_text(line_details)
        if nightly_rate is None and nights and extracted.amount is not None:
            nightly_rate = round(float(extracted.amount) / float(nights), 2)

        subtotal = extracted.subtotal if extracted.subtotal is not None else None
        tip = extracted.tip if extracted.tip is not None else None
        if "meal" in (normalized_category or "").lower() or meal_type is not None:
            if subtotal is None and line_details:
                subtotal = self._parse_subtotal_from_text(line_details)
            if tip is None and line_details:
                tip = self._parse_tip_from_text(line_details)

        return ExtractedReceipt(
            vendor=vendor,
            date=normalized_date,
            amount=extracted.amount,
            currency=currency,
            category=normalized_category,
            nights=nights,
            nightly_rate=nightly_rate,
            subtotal=subtotal,
            tip=tip,
            meal_type=meal_type,
            line_details=line_details,
            attendees=attendees,
        )

    @staticmethod
    def _parse_nights_from_text(text: str) -> int | None:
        match = re.search(r"\bnights?\s*[:\-]?\s*(\d{1,2})\b", text, re.IGNORECASE)
        if match:
            value = int(match.group(1))
            return value if value > 0 else None
        alt = re.search(r"\b(\d{1,2})\s+nights?\b", text, re.IGNORECASE)
        if alt:
            value = int(alt.group(1))
            return value if value > 0 else None
        return None

    @staticmethod
    def _parse_nightly_rate_from_text(text: str) -> float | None:
        room_line = re.search(
            r"\broom\b[^$]{0,40}\$?\s*(\d+(?:\.\d{1,2})?)",
            text,
            re.IGNORECASE,
        )
        if room_line:
            return float(room_line.group(1))
        per_night = re.search(
            r"\$?\s*(\d+(?:\.\d{1,2})?)\s*(?:/|per)\s*night\b",
            text,
            re.IGNORECASE,
        )
        if per_night:
            return float(per_night.group(1))
        return None

    @staticmethod
    def _parse_subtotal_from_text(text: str) -> float | None:
        match = re.search(r"\bsubtotal\b[^$]{0,20}\$?\s*(\d+(?:\.\d{1,2})?)", text, re.IGNORECASE)
        if match:
            return float(match.group(1))
        return None

    @staticmethod
    def _parse_tip_from_text(text: str) -> float | None:
        match = re.search(r"\btip\b[^$]{0,20}\$?\s*(\d+(?:\.\d{1,2})?)", text, re.IGNORECASE)
        if match:
            return float(match.group(1))
        return None

    @staticmethod
    def _try_parse_date(raw: str) -> str | None:
        from datetime import datetime

        known_formats = [
            "%Y-%m-%d",
            "%b %d, %Y",
            "%B %d, %Y",
            "%a, %b %d, %Y",
            "%m/%d/%Y",
            "%m-%d-%Y",
        ]
        for fmt in known_formats:
            try:
                return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def _failed(self, message: str) -> ExtractionOutcome:
        return ExtractionOutcome(
            extracted=ExtractedReceipt(line_details=message),
            confidence=0.05,
            for_human_review=True,
            source_type="failed",
            issues=[message],
        )
