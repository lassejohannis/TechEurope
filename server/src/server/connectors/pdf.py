from __future__ import annotations

from pathlib import Path
from typing import Iterator

try:
    import pdfplumber  # type: ignore
except Exception:  # pragma: no cover
    pdfplumber = None

from server.ingestion_models import SourceRecord, ExtractionStatus
from .base import BaseConnector


class InvoicePDFConnector(BaseConnector):
    source_type = "invoice_pdf"

    def discover(self, path: Path) -> Iterator[dict]:
        # path is a directory tree — recursive search lets us find
        # `Customer_Relation_Management/Customer_orders/invoice_*.pdf`
        # under the EnterpriseBench root.
        p = Path(path)
        for pdf in p.rglob("invoice_*.pdf"):
            stem = pdf.stem  # invoice_<customer_id>_<...>
            parts = stem.split("_")
            customer_id = parts[1] if len(parts) > 1 else None
            yield {"file": pdf, "customer_id": customer_id}

    def normalize(self, raw: dict) -> SourceRecord:
        # Ingest stays "dumb": just extract raw text + filename metadata.
        # Gemini/Pioneer extraction happens later in the autonomous mapping
        # pipeline like every other source type.
        file: Path = raw["file"]
        customer_id = raw.get("customer_id")
        text = ""
        if pdfplumber:
            with pdfplumber.open(file) as doc:
                for page in doc.pages:
                    text += page.extract_text() or ""
        payload = {
            "customer_id": customer_id,
            "file_name": file.name,
            "text": text,
        }
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
