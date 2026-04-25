"""Email connector — reads Enterprise_mail_system/emails.json (Gmail-shape mock)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from server.connectors.base import BaseConnector, SourceRecord


class EmailConnector(BaseConnector):
    source_type = "email"

    def fetch(self, path: Path) -> Iterator[dict]:
        with open(path) as f:
            records = json.load(f)
        yield from (records if isinstance(records, list) else records.values())

    def normalize(self, raw: dict) -> SourceRecord:
        payload = {
            "email_id": raw["email_id"],
            "thread_id": raw.get("thread_id"),
            "date": raw.get("date"),
            "sender_email": raw["sender_email"],
            "sender_name": raw.get("sender_name"),
            "sender_emp_id": raw.get("sender_emp_id"),
            "recipient_email": raw.get("recipient_email"),
            "recipient_name": raw.get("recipient_name"),
            "recipient_emp_id": raw.get("recipient_emp_id"),
            "subject": raw.get("subject", ""),
            "body": raw.get("body", ""),
            "importance": raw.get("importance", "normal"),
            "category": raw.get("category"),
        }
        content_hash = SourceRecord.hash_payload(payload)
        return SourceRecord(
            id=SourceRecord.make_id(self.source_type, content_hash),
            source_type=self.source_type,
            source_uri="Enterprise_mail_system/emails.json",
            source_native_id=raw["email_id"],
            payload=payload,
            content_hash=content_hash,
            metadata={"method": "connector_ingest", "thread_id": raw.get("thread_id")},
        )
