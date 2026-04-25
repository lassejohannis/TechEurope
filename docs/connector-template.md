# Writing a new connector (< 30 min)

A connector reads one external data source and yields `SourceRecord` objects that
the ingestion pipeline upserts into `source_records` (Supabase) and optionally
indexes in Neo4j.

## Minimal template

```python
# server/src/server/connectors/my_source.py
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from server.connectors.base import BaseConnector, SourceRecord


class MySourceConnector(BaseConnector):
    source_type = "my_source"          # used as prefix in SourceRecord.id

    def fetch(self, path: Path) -> Iterator[dict]:
        """Yield raw dicts — one per logical record."""
        import json
        with open(path) as f:
            yield from json.load(f)

    def normalize(self, raw: dict) -> SourceRecord:
        """Map a raw dict → SourceRecord."""
        native_id = str(raw.get("id", ""))
        payload = {
            "id":    raw.get("id"),
            "title": raw.get("title", ""),
            "body":  raw.get("body", "")[:4000],  # cap large text for jsonb
        }
        content_hash = SourceRecord.hash_payload(payload)
        return SourceRecord(
            id=SourceRecord.make_id(self.source_type, content_hash),
            source_type=self.source_type,
            source_uri=str(path),
            source_native_id=native_id,
            payload=payload,
            content_hash=content_hash,
            metadata={"method": "connector_ingest"},
        )
```

## Register it

Add one line to `server/src/server/connectors/__init__.py`:

```python
from server.connectors.my_source import MySourceConnector

REGISTRY = {
    ...
    "my_source": MySourceConnector,
}
```

## Run it

```bash
# dry-run (no DB writes)
uv run server ingest --connector my_source --path data/my_source/records.json --dry-run

# persist to Supabase
uv run server ingest --connector my_source --path data/my_source/records.json
```

## Rules

| Rule | Reason |
|------|--------|
| `payload` values must be JSON-serialisable | stored in Supabase `jsonb` column |
| Cap long text fields to ≤ 8 000 chars | prevents oversized payloads |
| `source_native_id` must be stable | used for dedup / linking |
| Never raise in `normalize()` | wrap in try/except and log, return `None` to skip |
| `fetch()` is a generator | keeps memory flat for large files |

## `SourceRecord` fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | `"{source_type}:{sha256[:24]}"` — globally unique |
| `source_type` | str | Matches connector `source_type` |
| `source_uri` | str | Relative path or URL to the source file |
| `source_native_id` | str | ID as it appears in the source system |
| `payload` | dict | All fields to store / search |
| `content_hash` | str | SHA-256 of canonical payload — used for dedup |
| `extraction_status` | str | `"pending"` by default |
| `metadata` | dict | Extra context (method, file size, etc.) |

## Directory connectors

If your source is a directory of files, handle it in `fetch()`:

```python
def fetch(self, path: Path) -> Iterator[dict]:
    if path.is_dir():
        for file in sorted(path.rglob("*.json")):
            yield from self._load_file(file)
    else:
        yield from self._load_file(path)
```

## Existing connectors for reference

| Connector | File | Source |
|-----------|------|--------|
| `email` | `email_mock.py` | `Enterprise_mail_system/emails.json` |
| `crm` | `crm_mock.py` | `CRM/` directory (clients/vendors/customers/sales) |
| `hr` | `hr_mock.py` | `Human_Resources/` (employees.json + resume CSV) |
| `itsm` | `itsm_mock.py` | `IT_Service_Management/it_tickets.json` |
| `document` | `document.py` | Any directory — PDF/DOCX/PPTX/HTML/CSV/MD via Docling |
