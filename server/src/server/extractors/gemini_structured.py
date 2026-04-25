from __future__ import annotations

import json
import logging
from typing import Literal, Optional

from pydantic import BaseModel, Field

from server.config import settings

logger = logging.getLogger(__name__)


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


EmailFactPredicate = Literal[
    "mentions",
    "promised_to",
    "asked",
    "approved",
    "blocked",
    "owns_topic",
    "scheduled_with",
]


class ExtractedEmailFact(BaseModel):
    """LLM-mined relationship between two named entities in an email body."""

    subject_name: str = Field(description="Canonical name of the subject person")
    predicate: EmailFactPredicate
    object_name: Optional[str] = Field(default=None, description="Canonical name of the object person/topic")
    confidence: float = Field(ge=0.0, le=1.0)
    quote: str = Field(description="Literal verbatim quote from the email body")


class EmailFactsSchema(BaseModel):
    facts: list[ExtractedEmailFact] = Field(default_factory=list)


def extract_email_facts(
    body: str, sender_name: str, recipient_name: str
) -> list[ExtractedEmailFact]:
    """LLM mining of an email body for inter-person relationship facts.

    Returns an empty list when the API key is missing, the body is too short,
    or any error occurs (extraction must never block ingestion).
    """
    if not settings.gemini_api_key or not body or len(body.strip()) < 200:
        return []
    try:
        from google import genai  # type: ignore
    except Exception:
        return []
    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        schema = EmailFactsSchema.model_json_schema()
        prompt = (
            f"Extract explicit relationship facts from this email.\n"
            f"Sender: {sender_name}\nRecipient: {recipient_name}\n\n"
            f"Body:\n{body[:3000]}\n\n"
            "Rules:\n"
            "- Only emit facts that are explicitly stated in the email.\n"
            "- predicate must be one of: mentions, promised_to, asked, approved, "
            "blocked, owns_topic, scheduled_with.\n"
            "- subject_name is one of Sender/Recipient or another named person.\n"
            "- object_name is the named person or topic the predicate refers to.\n"
            "- quote is the literal verbatim sentence from the body.\n"
            "- confidence in [0,1] reflecting how unambiguous the statement is."
        )
        resp = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": schema,
            },
        )
        raw = getattr(resp, "text", None) or getattr(resp, "output_text", None) or "{}"
        data = json.loads(raw)
        return EmailFactsSchema.model_validate(data).facts
    except Exception as exc:
        logger.debug("extract_email_facts failed: %s", exc)
        return []


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
