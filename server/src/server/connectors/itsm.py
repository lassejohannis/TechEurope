"""ITSM connector — reads IT_Service_Management/it_tickets.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from server.ingestion_models import ExtractionStatus, SourceRecord
from .base import BaseConnector


class ITSMConnector(BaseConnector):
    source_type = "it_ticket"

    def discover(self, path: Path) -> Iterator[dict]:
        base = Path(path)
        file = base if base.is_file() else base / "IT_Service_Management" / "it_tickets.json"
        with file.open(encoding="utf-8") as f:
            for row in json.load(f):
                yield row

    def normalize(self, raw: dict) -> SourceRecord:
        native_id = str(raw.get("id", ""))
        payload = {
            "ticket_id": raw.get("id"),
            "priority": raw.get("priority"),
            "raised_by_emp_id": raw.get("raised_by_emp_id"),
            "assigned_to_emp_id": raw.get("emp_id"),
            "assigned_date": raw.get("assigned_date"),
            "issue": raw.get("Issue", "")[:2000],
            "resolution": raw.get("Resolution", "")[:2000],
        }
        content_hash = self.make_content_hash(payload)
        return SourceRecord(
            id=self.make_id(native_id),
            source_type=self.source_type,
            source_uri="IT_Service_Management/it_tickets.json",
            source_native_id=native_id,
            payload=payload,
            content_hash=content_hash,
            extraction_status=ExtractionStatus.pending,
        )
