from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator, Iterable

from server.ingestion_models import SourceRecord, ExtractionStatus
from .base import BaseConnector


class CRMConnector(BaseConnector):
    source_type = "crm"  # umbrella; per-record source_type field will be specialized

    def _iter_file(self, file: Path) -> Iterable[dict]:
        with file.open("r", encoding="utf-8") as f:
            data = json.load(f)
            for row in data:
                yield row

    def discover(self, path: Path) -> Iterator[dict]:
        base = Path(path)
        root = base if base.is_dir() else base.parent
        crm_dir = root / "Customer_Relation_Management"
        # customers
        for row in self._iter_file(crm_dir / "customers.json"):
            row["__source_type"] = "customer"
            row["__native_id"] = str(row.get("customer_id"))
            yield row
        # products
        for row in self._iter_file(crm_dir / "products.json"):
            row["__source_type"] = "product"
            row["__native_id"] = str(row.get("product_id"))
            yield row
        # sales (volume)
        for row in self._iter_file(crm_dir / "sales.json"):
            row["__source_type"] = "sale"
            row["__native_id"] = str(row.get("sales_record_id"))
            yield row
        # clients (B2B)
        biz_dir = root / "Business_and_Management"
        clients_file = biz_dir / "clients.json"
        if clients_file.exists():
            for row in self._iter_file(clients_file):
                row["__source_type"] = "client"
                row["__native_id"] = str(row.get("client_id"))
                yield row

    def normalize(self, raw: dict) -> SourceRecord:
        per_type = raw.get("__source_type", "unknown")
        native_id = str(raw.get("__native_id"))
        # stable id per leaf type for idempotency
        record_id = f"{per_type}:{self.make_id(native_id).split(':',1)[1]}"
        payload = {k: v for k, v in raw.items() if not k.startswith("__")}
        content_hash = self.make_content_hash(payload)
        return SourceRecord(
            id=record_id,
            source_type=per_type,
            source_uri=None,
            source_native_id=native_id,
            payload=payload,
            content_hash=content_hash,
            extraction_status=ExtractionStatus.pending,
        )

