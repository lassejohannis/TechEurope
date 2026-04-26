"""Pioneer (Fastino) fine-tuned extractor — Free-Text-Mining Hot-Path.

Calls the GLiNER2 model trained in `docs/ws3-pioneer-finetune.md`. The model
UUIDs sit in `data/training/pioneer_versions.json` (v1, v3 — ~706ms p50 vs
Gemini's ~4800ms on the same chunks). Auth via `X-API-Key` header (matches
`scripts/pioneer_pipeline.py` which is the proven training/labeling driver).

Failure mode is graceful: when Pioneer is not configured, the API is
unreachable, or parsing fails, `extract()` returns None and the caller
(`engine._llm_free_text_facts`) falls back to Gemini.

Endpoint shape — Pioneer's chat-completions style API expects:
    POST /v1/chat/completions  (override via PIONEER_INFERENCE_ENDPOINT env)
    {
        "model": "<uuid>",
        "messages": [{"role": "user", "content": <text>}],
        "schema": {"entities": [...], "relations": [...]},
        "include_confidence": true,
        "include_spans": true,
    }
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

import httpx

from server.config import settings
from server.extractors.schemas import Entity, ExtractionResult, Fact

logger = logging.getLogger(__name__)


# Default inference endpoint. Override via env if Pioneer's actual route
# differs from `<API>/v1/chat/completions` — we keep the constant exposed so
# `compare_pioneer_versions.py` can still import it.
_API_BASE = os.environ.get("PIONEER_API_BASE", "https://api.pioneer.ai")
PIONEER_ENDPOINT: str = os.environ.get(
    "PIONEER_INFERENCE_ENDPOINT", f"{_API_BASE}/v1/chat/completions"
)


# ---------------------------------------------------------------------------
# Approved-types pulled from DB so Pioneer obeys the same ontology that
# everything else in the system does. lru_cached at module level so the
# DB roundtrip happens once per process.
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _approved_entity_types() -> tuple[str, ...]:
    try:
        from server.db import get_supabase
        rows = (
            get_supabase()
            .table("entity_type_config")
            .select("id")
            .eq("approval_status", "approved")
            .execute()
            .data
            or []
        )
        types = tuple(r["id"] for r in rows if r.get("id"))
        if types:
            return types
    except Exception as exc:
        logger.debug("could not load approved entity types from DB: %s", exc)
    # Conservative default: the four seed primitives.
    return ("person", "organization", "document", "communication")


@lru_cache(maxsize=1)
def _approved_edge_types() -> tuple[str, ...]:
    try:
        from server.db import get_supabase
        rows = (
            get_supabase()
            .table("edge_type_config")
            .select("id")
            .eq("approval_status", "approved")
            .execute()
            .data
            or []
        )
        types = tuple(r["id"] for r in rows if r.get("id"))
        if types:
            return types
    except Exception as exc:
        logger.debug("could not load approved edge types from DB: %s", exc)
    return ("works_at", "reports_to", "participant_in", "authored", "mentions")


# Module-level constants the comparison scripts import. Computed lazily so
# importing `pioneer` doesn't open a DB connection at import time.
def __getattr__(name: str):
    if name == "ENTITY_TYPES":
        return _approved_entity_types()
    if name == "RELATION_TYPES":
        return _approved_edge_types()
    raise AttributeError(name)


#: True when both API key and model id are configured. Cascade and engine
#: code branches on this to decide whether to even attempt a call.
AVAILABLE: bool = bool(settings.pioneer_api_key and settings.pioneer_model_id)


# Per-source-type entity-type whitelist for Pioneer extraction.
# Source-Types not listed here get the full approved set. Listed types get
# only their declared subset — keeps "person" out of policy-doc / invoice /
# CRM scans where NER consistently confuses common nouns for people.
_SOURCE_TYPE_LABEL_WHITELIST: dict[str, set[str]] = {
    "doc_policy":  {"organization", "document"},
    "invoice_pdf": {"organization", "product", "price"},
    "customer":    {"organization", "person"},
    "client":      {"organization", "person"},
    "product":     {"product", "organization", "price"},
    "sale":        {"product", "organization", "price"},
    # email, collaboration, hr_record, it_ticket: NOT listed → all approved types
}


def extract(text: str, source_type: str = "unknown") -> ExtractionResult | None:
    """Extract entities + facts from a free-text chunk via Pioneer GLiNER2.

    Returns None when Pioneer is not configured, the API call fails, or the
    response cannot be parsed. Caller should fall back to Gemini in that
    case (`engine._llm_free_text_facts` does this).
    """
    if not (settings.pioneer_api_key and settings.pioneer_model_id):
        return None
    if not text or len(text.strip()) < 20:
        return None

    approved_e = _approved_entity_types()
    allow = _SOURCE_TYPE_LABEL_WHITELIST.get(source_type)
    entity_labels = [t for t in approved_e if (not allow) or t in allow]

    body = {
        "model": settings.pioneer_model_id,
        "messages": [{"role": "user", "content": text}],
        "schema": {
            "entities": entity_labels,
            "relations": list(_approved_edge_types()),
        },
        "include_confidence": True,
        "include_spans": True,
    }
    headers = {
        "X-API-Key": settings.pioneer_api_key,
        "Content-Type": "application/json",
    }
    try:
        resp = httpx.post(PIONEER_ENDPOINT, headers=headers, json=body, timeout=30.0)
        resp.raise_for_status()
        return _parse_response(resp.json())
    except Exception as exc:
        logger.debug("pioneer.extract failed (will fall back to Gemini): %s", exc)
        return None


def _parse_response(data: dict) -> ExtractionResult | None:
    """Translate Pioneer GLiNER2 chat-completions response → ExtractionResult.

    Real Pioneer response shape (verified live against api.pioneer.ai):

        {"choices": [{"message": {"content": "{
            \"entities\": {
                \"person\":       [{\"text\": \"Jane\", \"confidence\": 0.9, \"start\": 6, \"end\": 10}, ...],
                \"organization\": [...],
                ...
            },
            \"relation_extraction\": {
                \"reports_to\": [{\"head\": {\"text\": \"Jane\", ...}, \"tail\": {\"text\": \"Bob\", ...}}, ...],
                ...
            }
        }"}}]}

    Entities are keyed by type, relations by predicate. Each item has a
    text span (`text`, `start`, `end`) and a confidence. The parser is
    tolerant of older flat-list shapes too in case Pioneer changes the
    response again.
    """
    if not isinstance(data, dict):
        return None

    payload: Any = data
    # Unwrap chat-completions envelope.
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(msg, dict):
            content = msg.get("content")
            if isinstance(content, str):
                import json as _json
                try:
                    payload = _json.loads(content)
                except Exception:
                    return None
            elif isinstance(content, dict):
                payload = content
    if not isinstance(payload, dict):
        return None

    raw_entities = payload.get("entities")
    raw_relations = payload.get("relation_extraction") or payload.get("relations") or payload.get("facts")

    entities: list[Entity] = []
    seen_ids: set[str] = set()
    # Index from span text → entity id so relations can resolve their
    # head/tail back to the entities we actually emit.
    text_to_id: dict[str, str] = {}

    def _add_entity(etype: str, item: dict) -> str | None:
        canonical = (item.get("canonical_name") or item.get("name") or item.get("text") or "").strip()
        if not canonical:
            return None
        eid = item.get("id") or f"{etype}:{_slug(canonical)}"
        if eid in seen_ids:
            return eid
        seen_ids.add(eid)
        entities.append(
            Entity(
                id=eid,
                type=etype,  # type: ignore[arg-type]
                canonical_name=canonical,
                aliases=list(item.get("aliases") or []),
                attributes={
                    k: v for k, v in item.items()
                    if k in ("start", "end", "confidence")
                },
            )
        )
        text_to_id[canonical.lower()] = eid
        return eid

    if isinstance(raw_entities, dict):
        # GLiNER2 dict-keyed-by-type shape
        for etype, items in raw_entities.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict):
                    _add_entity(str(etype).lower(), item)
    elif isinstance(raw_entities, list):
        # legacy flat-list shape
        for item in raw_entities:
            if isinstance(item, dict):
                etype = (item.get("type") or item.get("label") or "person").strip().lower()
                _add_entity(etype, item)

    facts: list[Fact] = []

    def _resolve_endpoint(endpoint: Any) -> tuple[str, str | None]:
        """Return (canonical_text, entity_id_if_known)."""
        if isinstance(endpoint, dict):
            txt = (endpoint.get("text") or endpoint.get("name") or "").strip()
            return txt, text_to_id.get(txt.lower())
        if isinstance(endpoint, str):
            return endpoint.strip(), text_to_id.get(endpoint.strip().lower())
        return "", None

    if isinstance(raw_relations, dict):
        # GLiNER2 dict-keyed-by-predicate shape
        for predicate, items in raw_relations.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                head_text, head_id = _resolve_endpoint(item.get("head"))
                tail_text, tail_id = _resolve_endpoint(item.get("tail"))
                if not head_text or not tail_text or not predicate:
                    continue
                # Use entity ids when both endpoints resolved; otherwise
                # store as plain text so the engine downstream can still
                # look up canonical entities by name.
                subject = head_id or head_text
                obj_raw = tail_id or tail_text
                obj_type = "entity" if (head_id and tail_id) else "string"
                confidence = float(item.get("confidence") or 0.85)
                try:
                    facts.append(
                        Fact(
                            subject=subject,
                            predicate=str(predicate),
                            object=obj_raw,
                            object_type=obj_type,  # type: ignore[arg-type]
                            confidence=max(0.0, min(1.0, confidence)),
                        )
                    )
                except Exception:
                    continue
    elif isinstance(raw_relations, list):
        # legacy flat-list (old comparison.json shape)
        for f in raw_relations:
            if not isinstance(f, dict):
                continue
            subject = (f.get("subject") or f.get("head") or "").strip()
            predicate = (f.get("predicate") or f.get("relation") or "").strip()
            obj_raw = f.get("object") if "object" in f else f.get("tail")
            if not subject or not predicate or obj_raw is None:
                continue
            obj_type = f.get("object_type")
            if obj_type is None:
                obj_type = "entity" if isinstance(obj_raw, str) and ":" in obj_raw else "string"
            confidence = float(f.get("confidence") or 0.85)
            try:
                facts.append(
                    Fact(
                        subject=subject,
                        predicate=predicate,
                        object=obj_raw,
                        object_type=obj_type,  # type: ignore[arg-type]
                        confidence=max(0.0, min(1.0, confidence)),
                    )
                )
            except Exception:
                continue

    return ExtractionResult(entities=entities, facts=facts)


def extract_and_match(candidate, db) -> "Any | None":
    """Cascade Tier 3.5 hook — explicit roadmap stub.

    The current Pioneer integration handles free-text fact-mining
    (see `extract` above + `engine._llm_free_text_facts`). Entity
    disambiguation against the existing DB via Pioneer is a Day-2
    item; cascade.py wraps this call in try/except so returning None
    here is safe.
    """
    return None


def _slug(value: str) -> str:
    import re
    s = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return s or "unnamed"
