from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from server.models import SourceRecord, ExtractionStatus
from .base import BaseConnector


class EmailConnector(BaseConnector):
    source_type = "email"

    def discover(self, path: Path) -> Iterator[dict]:
        # Expected: single file emails.json with an array of records
        p = Path(path)
        file = p if p.is_file() else (p / "Enterprise_mail_system" / "emails.json")
        with file.open("r", encoding="utf-8") as f:
            data = json.load(f)
            for row in data:
                yield row

    def normalize(self, raw: dict) -> SourceRecord:
        native_id = str(raw.get("email_id") or raw.get("id"))
        record_id = self.make_id(native_id)
        payload = dict(raw)
        content_hash = self.make_content_hash(payload)
        return SourceRecord(
            id=record_id,
            source_type=self.source_type,
            source_uri=raw.get("source_uri"),
            source_native_id=native_id,
            payload=payload,
            content_hash=content_hash,
            extraction_status=ExtractionStatus.pending,
        )

