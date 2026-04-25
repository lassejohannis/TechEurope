"""BaseConnector — shared contract for all ingestion connectors.

Every connector is stateless, pulls raw data, normalizes to SourceRecord,
and pushes to Supabase. No business logic lives here.
"""

from __future__ import annotations

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)


@dataclass
class SourceRecord:
    """Normalized unit of ingestion — maps 1:1 to the source_records DB table."""

    id: str                    # deterministic: "{source_type}:{sha256_prefix}"
    source_type: str           # "email" | "crm_contact" | "hr_record" | "it_ticket" | "document" | ...
    source_uri: str            # file path or API endpoint
    source_native_id: str      # original ID from the source system
    payload: dict              # full parsed content (stored as jsonb)
    content_hash: str          # sha256 of canonical payload — drives idempotency
    extraction_status: str = "pending"
    metadata: dict = field(default_factory=dict)

    @staticmethod
    def make_id(source_type: str, content_hash: str) -> str:
        return f"{source_type}:{content_hash[:24]}"

    @staticmethod
    def hash_payload(payload: dict) -> str:
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode()).hexdigest()


class BaseConnector(ABC):
    """Stateless connector interface. Implement fetch() + normalize()."""

    source_type: str  # must be set on each subclass

    @abstractmethod
    def fetch(self, path: Path) -> Iterator[dict]:
        """Yield raw records from the data source."""

    @abstractmethod
    def normalize(self, raw: dict) -> SourceRecord:
        """Convert a raw record to a SourceRecord."""

    def ingest(self, path: Path) -> Iterator[SourceRecord]:
        """Full pipeline: fetch → normalize → yield SourceRecord."""
        for raw in self.fetch(path):
            try:
                yield self.normalize(raw)
            except Exception as exc:
                logger.warning("Skipping record in %s: %s", path, exc)

    def persist(self, records: Iterator[SourceRecord], db) -> dict:
        """Upsert all records into Supabase. Returns stats dict."""
        inserted = updated = skipped = 0
        for rec in records:
            row = {
                "id": rec.id,
                "source_type": rec.source_type,
                "source_uri": rec.source_uri,
                "source_native_id": rec.source_native_id,
                "payload": rec.payload,
                "content_hash": rec.content_hash,
                "extraction_status": rec.extraction_status,
            }
            existing = db.table("source_records").select("id,content_hash").eq("id", rec.id).execute()
            if existing.data:
                if existing.data[0]["content_hash"] == rec.content_hash:
                    skipped += 1
                else:
                    db.table("source_records").update(row).eq("id", rec.id).execute()
                    updated += 1
            else:
                db.table("source_records").insert(row).execute()
                inserted += 1

        return {"inserted": inserted, "updated": updated, "skipped": skipped}
