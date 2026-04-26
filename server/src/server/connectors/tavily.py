"""Tavily web-search connector — entity-enrichment partner.

Brings external evidence (press releases, news, product pages, public profiles)
into the Memory as `source_records` of `source_type='web_search'`. Each hit
goes through the same SourceRecord → infer-mapping → engine pipeline as
Email/CRM/HR — same provenance (URL + scrape_timestamp), same bi-temporal
validity. That's the Generality demonstration in 30 seconds.

Use via `cli.py:cmd_enrich_entity` which derives the search query from an
existing entity's canonical_name and tags every hit's payload with
`triggered_by_entity_id`. The CLI handles auto-bootstrapping the
`web_search` mapping if it doesn't exist yet.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import httpx
from supabase import Client

from server.config import settings
from server.connectors.base import BaseConnector
from server.ingestion_models import ExtractionStatus, SourceRecord

logger = logging.getLogger(__name__)


class TavilySearchConnector(BaseConnector):
    source_type = "web_search"

    #: Tavily Search API endpoint (overridable via env in the future).
    ENDPOINT = "https://api.tavily.com/search"

    def __init__(self) -> None:
        self._query: str | None = None
        self._triggered_by: str | None = None
        self._max_results: int = 10

    # ------------------------------------------------------------------
    # BaseConnector API — `discover(path)` not used for Tavily; we expose
    # `ingest_query()` instead. The abstract method is kept satisfied with
    # a tiny shim so the registry import doesn't blow up.
    # ------------------------------------------------------------------

    def discover(self, path: Path) -> Iterator[dict]:
        """Path-based ingest is not supported for Tavily.

        File-based callers can pass a JSON `{"query": "..."}` and we'll
        run that, but the canonical entry point is `ingest_query()`.
        """
        if path is None or not Path(path).exists():
            raise NotImplementedError(
                "TavilySearchConnector is query-driven, not path-driven. "
                "Use ingest_query(query, supabase) instead."
            )
        import json as _json
        data = _json.loads(Path(path).read_text())
        query = data.get("query") or ""
        if not query:
            return iter(())
        yield from self._fetch(query, max_results=self._max_results)

    def normalize(self, raw: dict) -> SourceRecord:
        url = raw.get("url") or ""
        title = raw.get("title") or url
        native_id = url or title
        payload: dict[str, Any] = {
            "query": raw.get("_query"),
            "triggered_by_entity_id": raw.get("_triggered_by"),
            "url": url,
            "title": title,
            "content": raw.get("content") or "",
            "raw_content": raw.get("raw_content"),
            "score": raw.get("score"),
            "published_date": raw.get("published_date"),
            "scraped_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        return SourceRecord(
            id=self.make_id(native_id),
            source_type=self.source_type,
            source_uri=url or None,
            source_native_id=native_id,
            payload=payload,
            content_hash=self.make_content_hash(payload),
            extraction_status=ExtractionStatus.pending,
        )

    # ------------------------------------------------------------------
    # Query-driven entry point used by `cli.cmd_enrich_entity`.
    # ------------------------------------------------------------------

    def ingest_query(
        self,
        query: str,
        supabase: Client,
        *,
        triggered_by_entity_id: str | None = None,
        max_results: int = 10,
        batch_size: int = 50,
        seed_path: Path | None = None,
    ) -> int:
        """Hit Tavily for `query`, persist results as source_records.

        Returns count of records actually written (idempotent via the
        BaseConnector content_hash diff). Mirrors `BaseConnector.ingest()`
        but skips its `discover(path)` step.

        If `seed_path` is set, the connector reads results from a JSON
        file ({"query", "results": [...]}) instead of hitting the live
        API. Useful for reproducible demos when no API key is available.
        """
        rows: list[dict[str, Any]] = []
        written = 0

        if seed_path is not None:
            iterator = self._fetch_from_seed(
                seed_path, fallback_query=query,
                triggered_by_entity_id=triggered_by_entity_id,
            )
        else:
            if not settings.tavily_api_key:
                raise RuntimeError(
                    "TAVILY_API_KEY not configured. Set it in server/.env, "
                    "or pass --seed for offline demos."
                )
            iterator = self._fetch(
                query,
                max_results=max_results,
                triggered_by_entity_id=triggered_by_entity_id,
            )

        for raw in iterator:
            record = self.normalize(raw)
            rows.append(record.model_dump(exclude_none=True))
            if len(rows) >= batch_size:
                written += self._upsert_batch(supabase, rows)
                rows.clear()
        if rows:
            written += self._upsert_batch(supabase, rows)
        return written

    def _fetch_from_seed(
        self,
        seed_path: Path,
        *,
        fallback_query: str,
        triggered_by_entity_id: str | None = None,
    ) -> Iterator[dict]:
        """Read pre-recorded Tavily results from a JSON seed file."""
        import json as _json
        data = _json.loads(Path(seed_path).read_text())
        query = data.get("query") or fallback_query
        for hit in data.get("results", []) or []:
            if not isinstance(hit, dict):
                continue
            yield {**hit, "_query": query, "_triggered_by": triggered_by_entity_id}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _fetch(
        self,
        query: str,
        *,
        max_results: int = 10,
        triggered_by_entity_id: str | None = None,
    ) -> Iterator[dict]:
        body = {
            "query": query,
            "search_depth": "advanced",
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
        }
        # Tavily accepts the API key in the request body too — keeps it
        # consistent with their official examples and avoids header/auth
        # variance across endpoints.
        body["api_key"] = settings.tavily_api_key

        try:
            resp = httpx.post(self.ENDPOINT, json=body, timeout=30.0)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("Tavily query failed (%s): %s", query, exc)
            return

        data = resp.json() or {}
        for hit in data.get("results", []) or []:
            if not isinstance(hit, dict):
                continue
            yield {
                **hit,
                "_query": query,
                "_triggered_by": triggered_by_entity_id,
            }
