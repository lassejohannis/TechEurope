# Connector Template

Goal: A new engineer can build a connector in ~30 minutes. Use this as a checklist.

## Skeleton

```python
# server/src/server/connectors/my_connector.py
from __future__ import annotations
from pathlib import Path
from typing import Iterator

from server.models import SourceRecord, ExtractionStatus
from server.connectors.base import BaseConnector

class MyConnector(BaseConnector):
    source_type = "my_source"

    def discover(self, path: Path) -> Iterator[dict]:
        # yield raw dicts from files/dirs under `path`
        ...

    def normalize(self, raw: dict) -> SourceRecord:
        native_id = str(raw["id"])  # pick a stable native id
        payload = {...}              # minimal normalized shape
        return SourceRecord(
            id=self.make_id(native_id),
            source_type=self.source_type,
            source_uri=raw.get("uri"),
            source_native_id=native_id,
            payload=payload,
            content_hash=self.make_content_hash(payload),
            extraction_status=ExtractionStatus.pending,
        )
```

## Register

The registry auto-imports known modules (`email`, `crm`, `hr`, `pdf`). For a new file, either:
- Add an import to `server/src/server/connectors/__init__.py`, or
- Use the registry programmatically in code paths that instantiate your connector.

## Idempotenz

- `id = f"{source_type}:{sha256(native_id)}"` — stable across runs
- `content_hash = sha256(canonical_json(payload))` — only changed rows are upserted
- The base `ingest()` function batches and only writes new/changed rows.

## Test Loop (3 steps)

1) Dry-run locally
```bash
uv run python -c "from server.connectors.my_connector import MyConnector; print('OK')"
```

2) Ingest small sample
```bash
uv run server ingest --connector my_source --path data/enterprise-bench/
```

3) Re-run (idempotent)
```bash
uv run server ingest --connector my_source --path data/enterprise-bench/
# counts unchanged; written=0 if no changes
```

## Notes
- Keep `payload` reasonably small but complete enough for downstream extraction.
- Preserve useful relation hints (e.g. `thread_id`, `reports_to`) in `payload` — WS‑2 will use them to create edges/facts.
- Do not add use-case semantics into the connector; it only normalizes.
- Use batches of ~500 for large files.

