"""Document connector — Docling-based multi-format reader.

Supported formats (via Docling):
  PDF   — invoices, policy docs, resumes, contracts
  DOCX  — Word documents
  PPTX  — slide decks
  HTML  — web pages / exported reports
  CSV   — structured tables (fallback to stdlib csv)
  MD    — markdown files

Structured extraction (invoice / policy / resume schemas) runs on top of
Docling's plain-text output via Gemini + instructor.

Usage:
    connector = DocumentConnector()
    for record in connector.ingest(Path("data/enterprise-bench/Policy_Documents")):
        print(record.source_type, record.source_native_id)
"""

from __future__ import annotations

import csv
import json
import logging
import os
from pathlib import Path
from typing import Iterator

from server.connectors.base import BaseConnector, SourceRecord

logger = logging.getLogger(__name__)

# File extensions handled by Docling vs. native fallbacks
_DOCLING_EXTS = {".pdf", ".docx", ".pptx", ".html", ".htm", ".png", ".jpg", ".jpeg"}
_CSV_EXTS = {".csv"}
_TEXT_EXTS = {".txt", ".md"}

# Auto-detect document type from path patterns
_TYPE_HINTS = {
    "invoice": "invoice",
    "policy": "policy",
    "resume": "resume",
    "handbook": "policy",
    "contract": "contract",
    "report": "report",
}


def _detect_doc_type(path: Path) -> str:
    name = path.stem.lower()
    parent = path.parent.name.lower()
    for keyword, doc_type in _TYPE_HINTS.items():
        if keyword in name or keyword in parent:
            return doc_type
    return "document"


# ---------------------------------------------------------------------------
# Docling extraction
# ---------------------------------------------------------------------------

def _extract_with_docling(path: Path) -> dict:
    """Parse document with Docling. Falls back to pdfplumber for PDFs if unavailable."""
    try:
        from docling.document_converter import DocumentConverter
        converter = DocumentConverter()
        result = converter.convert(str(path))
        doc = result.document
        return {
            "text": doc.export_to_markdown(),
            "tables": [t.export_to_dataframe().to_dict() for t in doc.tables] if hasattr(doc, "tables") else [],
            "method": "docling",
        }
    except (ImportError, Exception) as exc:
        logger.debug("Docling unavailable (%s), falling back to pdfplumber", exc)
        return _extract_with_pdfplumber(path)


def _extract_with_pdfplumber(path: Path) -> dict:
    """Fallback PDF extraction via pdfplumber."""
    try:
        import pdfplumber
        text_parts = []
        tables = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                if t := page.extract_text():
                    text_parts.append(t)
                for table in (page.extract_tables() or []):
                    tables.append(table)
        return {"text": "\n".join(text_parts), "tables": tables, "method": "pdfplumber"}
    except Exception as exc:
        logger.warning("pdfplumber also failed for %s: %s", path, exc)
        return {"text": "", "tables": [], "method": "failed"}


def _extract_csv(path: Path) -> dict:
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return {
        "text": "\n".join(json.dumps(r) for r in rows[:50]),  # first 50 rows as text
        "rows": rows,
        "method": "csv_native",
    }


def _extract_text(path: Path) -> dict:
    return {"text": path.read_text(encoding="utf-8", errors="replace"), "method": "text_native"}


# ---------------------------------------------------------------------------
# Structured schema extraction via Gemini + instructor
# ---------------------------------------------------------------------------

def _extract_structured(text: str, doc_type: str) -> dict:
    """Use Gemini + instructor to pull structured fields from document text."""
    if not text.strip():
        return {}
    try:
        import instructor
        from pydantic import BaseModel
        from google import genai

        client = instructor.from_genai(
            genai.Client(api_key=os.environ.get("GEMINI_API_KEY", "")),
            mode=instructor.Mode.GENAI_TOOLS,
        )

        if doc_type == "invoice":
            class InvoiceSchema(BaseModel):
                invoice_number: str | None = None
                customer_id: str | None = None
                customer_name: str | None = None
                total_amount: str | None = None
                currency: str | None = None
                issue_date: str | None = None
                due_date: str | None = None
                line_items: list[dict] = []

            result = client.chat.completions.create(
                model="gemini-2.0-flash",
                response_model=InvoiceSchema,
                messages=[{"role": "user", "content": f"Extract invoice fields:\n{text[:3000]}"}],
            )
            return result.model_dump()

        elif doc_type == "resume":
            class ResumeSchema(BaseModel):
                name: str | None = None
                email: str | None = None
                skills: list[str] = []
                current_role: str | None = None
                years_experience: int | None = None
                education: list[str] = []

            result = client.chat.completions.create(
                model="gemini-2.0-flash",
                response_model=ResumeSchema,
                messages=[{"role": "user", "content": f"Extract resume fields:\n{text[:3000]}"}],
            )
            return result.model_dump()

        elif doc_type == "policy":
            class PolicySchema(BaseModel):
                title: str | None = None
                category: str | None = None
                effective_date: str | None = None
                key_rules: list[str] = []
                applies_to: str | None = None

            result = client.chat.completions.create(
                model="gemini-2.0-flash",
                response_model=PolicySchema,
                messages=[{"role": "user", "content": f"Extract policy fields:\n{text[:3000]}"}],
            )
            return result.model_dump()

    except Exception as exc:
        logger.debug("Structured extraction skipped for %s: %s", doc_type, exc)
    return {}


# ---------------------------------------------------------------------------
# Connector
# ---------------------------------------------------------------------------

class DocumentConnector(BaseConnector):
    """Multi-format document connector using Docling + Gemini structured extraction."""

    source_type = "document"

    def __init__(self, extract_structured: bool = False):
        # Structured extraction costs Gemini API calls — opt-in
        self.extract_structured = extract_structured

    def fetch(self, path: Path) -> Iterator[dict]:
        """Yield raw extraction dicts. Path can be file or directory."""
        if path.is_dir():
            for ext in (*_DOCLING_EXTS, *_CSV_EXTS, *_TEXT_EXTS):
                for file in sorted(path.rglob(f"*{ext}")):
                    yield from self._process_file(file)
        elif path.is_file():
            yield from self._process_file(path)

    def _process_file(self, path: Path) -> Iterator[dict]:
        ext = path.suffix.lower()
        logger.debug("Processing %s", path)
        try:
            if ext in _DOCLING_EXTS:
                extracted = _extract_with_docling(path)
            elif ext in _CSV_EXTS:
                extracted = _extract_csv(path)
            elif ext in _TEXT_EXTS:
                extracted = _extract_text(path)
            else:
                return

            doc_type = _detect_doc_type(path)
            structured = {}
            if self.extract_structured and extracted.get("text"):
                structured = _extract_structured(extracted["text"], doc_type)

            yield {
                "_path": str(path),
                "_doc_type": doc_type,
                "_ext": ext,
                "text": extracted.get("text", ""),
                "tables": extracted.get("tables", []),
                "rows": extracted.get("rows", []),
                "structured": structured,
                "extraction_method": extracted.get("method", "unknown"),
            }
        except Exception as exc:
            logger.warning("Failed to process %s: %s", path, exc)

    def normalize(self, raw: dict) -> SourceRecord:
        path = Path(raw["_path"])
        doc_type = raw["_doc_type"]

        payload = {
            "file_name": path.name,
            "doc_type": doc_type,
            "extension": raw["_ext"],
            "text": raw.get("text", "")[:8000],  # cap for jsonb
            "structured": raw.get("structured", {}),
            "table_count": len(raw.get("tables", [])),
            "row_count": len(raw.get("rows", [])),
            "extraction_method": raw.get("extraction_method"),
        }

        content_hash = SourceRecord.hash_payload(payload)
        return SourceRecord(
            id=SourceRecord.make_id(f"doc_{doc_type}", content_hash),
            source_type=f"doc_{doc_type}",
            source_uri=str(path),
            source_native_id=path.stem,
            payload=payload,
            content_hash=content_hash,
            metadata={
                "method": raw.get("extraction_method", "docling"),
                "doc_type": doc_type,
                "file_size_bytes": path.stat().st_size if path.exists() else 0,
            },
        )
