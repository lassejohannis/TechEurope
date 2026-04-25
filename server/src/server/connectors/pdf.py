from __future__ import annotations

from pathlib import Path
from typing import Iterator

try:
    import pdfplumber  # type: ignore
except Exception:  # pragma: no cover
    pdfplumber = None

from server.models import SourceRecord, ExtractionStatus
from server.extractors.gemini_structured import gemini_extract_invoice
from server.utils.normalize import parse_currency, parse_date_iso
from .base import BaseConnector


class InvoicePDFConnector(BaseConnector):
    source_type = "invoice_pdf"

    def discover(self, path: Path) -> Iterator[dict]:
        # path is a directory containing invoice_*.pdf
        p = Path(path)
        for pdf in p.glob("invoice_*.pdf"):
            stem = pdf.stem  # invoice_<customer_id>_<...>
            parts = stem.split("_")
            customer_id = parts[1] if len(parts) > 1 else None
            yield {"file": pdf, "customer_id": customer_id}

    def normalize(self, raw: dict) -> SourceRecord:
        file: Path = raw["file"]
        customer_id = raw.get("customer_id")
        text = ""
        if pdfplumber:
            with pdfplumber.open(file) as doc:
                for page in doc.pages:
                    text += page.extract_text() or ""
        structured = gemini_extract_invoice(text)
        # Normalize basic numeric/date fields if present
        data = structured.model_dump()
        if "total" in data:
            data["total"] = parse_currency(data.get("total"))
        if "date" in data:
            data["date"] = parse_date_iso(data.get("date"))
        if isinstance(data.get("line_items"), list):
            for li in data["line_items"]:
                if isinstance(li, dict):
                    for k in ("quantity", "unit_price", "total"):
                        if k in li:
                            li[k] = parse_currency(li.get(k))
        payload = {"customer_id": customer_id, "text": text, **data}
        native_id = f"{customer_id}:{file.name}"
        record_id = self.make_id(native_id)
        content_hash = self.make_content_hash(payload)
        return SourceRecord(
            id=record_id,
            source_type=self.source_type,
            source_uri=str(file),
            source_native_id=native_id,
            payload=payload,
            content_hash=content_hash,
            extraction_status=ExtractionStatus.pending,
        )
