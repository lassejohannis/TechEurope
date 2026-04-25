from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

try:
    from server.ingestion_models import ExtractionStatus, SourceRecord
except ModuleNotFoundError:
    from server.models import ExtractionStatus, SourceRecord  # type: ignore[no-redef]
from .base import BaseConnector


class CollaborationConnector(BaseConnector):
    source_type = "collaboration"

    def discover(self, path: Path) -> Iterator[dict]:
        base = Path(path)
        root = base if base.is_dir() else base.parent
        file = root / "Collaboration_tools" / "conversations.json"
        with file.open("r", encoding="utf-8") as f:
            for row in json.load(f):
                yield row

    def normalize(self, raw: dict) -> SourceRecord:
        native_id = str(raw.get("conversation_id") or raw.get("id", ""))
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
