from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Iterator, List

from supabase import Client

from server.models import SourceRecord


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class BaseConnector(ABC):
    source_type: str

    @abstractmethod
    def discover(self, path: Path) -> Iterator[dict]:
        """Yield raw records discovered under path (file or directory)."""

    @abstractmethod
    def normalize(self, raw: dict) -> SourceRecord:
        """Convert raw dict into a normalized SourceRecord (id, hashes set)."""

    def _upsert_batch(self, supabase: Client, rows: List[Dict[str, Any]]) -> int:
        if not rows:
            return 0
        ids = [r["id"] for r in rows]
        # fetch existing hashes
        existing = (
            supabase.table("source_records")
            .select("id, content_hash")
            .in_("id", ids)
            .execute()
            .data
        )
        existing_map = {r["id"]: r["content_hash"] for r in existing}
        to_write = [r for r in rows if existing_map.get(r["id"]) != r["content_hash"]]
        if not to_write:
            return 0
        # use upsert on changed/new rows only
        supabase.table("source_records").upsert(to_write, on_conflict="id").execute()
        return len(to_write)

    def ingest(self, path: Path, supabase: Client, batch_size: int = 500) -> int:
        """Batched UPSERT into source_records. Returns count of rows written.

        Idempotent by content_hash: only new or changed rows are written.
        """
        buffer: List[Dict[str, Any]] = []
        written = 0
        for raw in self.discover(path):
            record = self.normalize(raw)
            row = record.model_dump()
            buffer.append(row)
            if len(buffer) >= batch_size:
                written += self._upsert_batch(supabase, buffer)
                buffer.clear()
        if buffer:
            written += self._upsert_batch(supabase, buffer)
        return written

    # Helpers for connectors
    def make_id(self, native_id: str) -> str:
        return f"{self.source_type}:{sha256_hex(native_id)}"

    def make_content_hash(self, payload: dict) -> str:
        return sha256_hex(canonical_json(payload))

