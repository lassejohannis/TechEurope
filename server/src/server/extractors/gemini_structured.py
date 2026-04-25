from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

from server.config import settings


class InvoiceLineItem(BaseModel):
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total: Optional[float] = None


class InvoiceSchema(BaseModel):
    invoice_number: Optional[str] = None
    date: Optional[str] = None
    total: Optional[float] = None
    currency: Optional[str] = None
    customer_id: Optional[str] = None
    line_items: list[InvoiceLineItem] = Field(default_factory=list)


def gemini_extract_invoice(text: str) -> InvoiceSchema:
    """Extract invoice fields using Gemini structured output.

    Falls back to an empty schema if API key/library not available.
    """
    if not settings.gemini_api_key:
        return InvoiceSchema()
    try:
        from google import genai  # type: ignore
    except Exception:
        return InvoiceSchema()
    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        schema = InvoiceSchema.model_json_schema()
        resp = client.models.generate_content(
            model=settings.gemini_model,
            contents=text,
            config={
                "response_mime_type": "application/json",
                "response_schema": schema,
            },
        )
        # google-genai responses typically expose .text or .output_text
        raw = getattr(resp, "text", None) or getattr(resp, "output_text", None) or "{}"
        import json

        data = json.loads(raw)
        return InvoiceSchema.model_validate(data)
    except Exception:
        # Be robust: never break ingestion due to extractor errors.
        return InvoiceSchema()
