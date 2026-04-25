"""ITSM connector — reads IT_Service_Management/it_tickets.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from server.connectors.base import BaseConnector, SourceRecord


class ITSMConnector(BaseConnector):
    source_type = "it_ticket"

    def fetch(self, path: Path) -> Iterator[dict]:
        with open(path) as f:
            yield from json.load(f)

    def normalize(self, raw: dict) -> SourceRecord:
        payload = {
            "ticket_id": raw.get("id"),
            "priority": raw.get("priority"),
            "raised_by_emp_id": raw.get("raised_by_emp_id"),
            "assigned_to_emp_id": raw.get("emp_id"),
            "assigned_date": raw.get("assigned_date"),
            "issue": raw.get("Issue", "")[:2000],
            "resolution": raw.get("Resolution", "")[:2000],
        }
        content_hash = SourceRecord.hash_payload(payload)
        return SourceRecord(
            id=SourceRecord.make_id(self.source_type, content_hash),
            source_type=self.source_type,
            source_uri="IT_Service_Management/it_tickets.json",
            source_native_id=str(raw.get("id", "")),
            payload=payload,
            content_hash=content_hash,
            metadata={"method": "connector_ingest", "priority": raw.get("priority")},
        )
