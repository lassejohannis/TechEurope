"""Gemini extractor — baseline + fallback for the cascade.

Shares the same prompt + schema as the WS-3 training-pair generator
(server/scripts/gen_pioneer_training.py); the synthetic data and the
production extractor must agree on shape.
"""

from __future__ import annotations

from typing import Any

from google import genai
from google.genai import types as genai_types

from server.config import settings
from server.extractors.schemas import ExtractionResult


def _gemini_schema(model_cls: type) -> dict[str, Any]:
    """Pydantic JSON schema, stripped of fields Gemini rejects.

    Gemini's response_schema validator chokes on `additionalProperties` and
    `$defs/$ref` indirection. We inline refs and drop the bits it doesn't like.
    """
    schema = model_cls.model_json_schema()
    defs = schema.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"].split("/")[-1]
                return resolve(defs[ref])
            return {
                k: resolve(v)
                for k, v in node.items()
                if k not in {"additionalProperties", "title", "default"}
            }
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    return resolve(schema)


_RESPONSE_SCHEMA = _gemini_schema(ExtractionResult)

EXTRACTION_PROMPT = """You extract a typed knowledge graph from a single enterprise text chunk.

Return entities and facts strictly following the schema. Rules:
- canonical_name: the person/customer/product/etc. name as it should appear in a directory.
- aliases: alternate spellings or short forms seen in the text.
- attributes: only what the text supports. Don't invent values.
- Fact subject must reference an entity emitted in this same response (use the same id).
- Fact predicate is a snake_case verb-phrase like "reports_to", "account_manager_of",
  "renewal_date", "located_in", "title", "department".
- object_type=entity when object is another entity id; otherwise string/date/number/bool.
- confidence in [0,1]: 1.0 only if explicitly stated, 0.7-0.9 if strongly implied,
  0.5 if speculative.
- Skip facts you would have to invent. Empty arrays are fine.

Use entity ids of the form "{type}:{slug}" where slug is lowercase-hyphenated canonical_name."""


def _client() -> genai.Client:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    return genai.Client(api_key=settings.gemini_api_key)


_MENTION_SCHEMA = {
    "type": "object",
    "properties": {
        "names": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["names"],
}

_MENTION_PROMPT = (
    "You receive the body of an enterprise email. "
    "List the full names of any *third-party people* mentioned in the text "
    "(exclude the sender and recipient — only people referenced in passing). "
    "Return JSON: {\"names\": [\"Full Name\", ...]}. "
    "If no third parties are named, return {\"names\": []}."
)


def extract_mentions(text: str) -> list[str]:
    """Return names of people mentioned in an email body (third parties only).

    Raises RuntimeError when GEMINI_API_KEY is unset so callers can distinguish
    'unavailable' from 'succeeded with zero mentions'.
    """
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    if not text.strip():
        return []
    import json as _json
    resp = _client().models.generate_content(
        model=settings.gemini_model,
        contents=[text],
        config=genai_types.GenerateContentConfig(
            system_instruction=_MENTION_PROMPT,
            response_mime_type="application/json",
            response_schema=_MENTION_SCHEMA,
            temperature=0.1,
        ),
    )
    if not resp.text:
        return []
    data = _json.loads(resp.text)
    return [str(n).strip() for n in data.get("names", []) if str(n).strip()]


def extract(text: str, source_type: str = "unknown", model: str | None = None) -> ExtractionResult:
    resp = _client().models.generate_content(
        model=model or settings.gemini_model,
        contents=[f"source_type: {source_type}\n\n----\n{text}"],
        config=genai_types.GenerateContentConfig(
            system_instruction=EXTRACTION_PROMPT,
            response_mime_type="application/json",
            response_schema=_RESPONSE_SCHEMA,
            temperature=0.2,
        ),
    )
    if not resp.text:
        return ExtractionResult(entities=[], facts=[])
    return ExtractionResult.model_validate_json(resp.text)
