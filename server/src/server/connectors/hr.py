from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from server.models import SourceRecord, ExtractionStatus
from .base import BaseConnector


class HRConnector(BaseConnector):
    source_type = "hr_record"

    def discover(self, path: Path) -> Iterator[dict]:
        base = Path(path)
        root = base if base.is_dir() else base.parent
        file = root / "Human_Resource_Management" / "Employees" / "employees.json"
        with file.open("r", encoding="utf-8") as f:
            data = json.load(f)
            for row in data:
                yield row

    def normalize(self, raw: dict) -> SourceRecord:
        native_id = str(raw.get("emp_id") or raw.get("email") or raw.get("index"))
        payload = dict(raw)
        record_id = self.make_id(native_id)
        content_hash = self.make_content_hash(payload)
        return SourceRecord(
            id=record_id,
            source_type=self.source_type,
            source_uri=None,
            source_native_id=native_id,
            payload=payload,
            content_hash=content_hash,
            extraction_status=ExtractionStatus.pending,
        )

