"""CRM connector — reads clients, vendors, customers, sales (HubSpot-shape mock)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from server.connectors.base import BaseConnector, SourceRecord


class CRMConnector(BaseConnector):
    """Reads all CRM files from a directory: clients, vendors, customers, sales."""

    source_type = "crm_contact"

    _FILE_MAP = {
        "clients.json": "crm_client",
        "vendors.json": "crm_vendor",
        "customers.json": "crm_customer",
        "sales.json": "crm_sale",
        "products.json": "crm_product",
    }

    def fetch(self, path: Path) -> Iterator[dict]:
        """Path may be a directory (scans all CRM files) or a single JSON file."""
        if path.is_dir():
            for filename, record_type in self._FILE_MAP.items():
                target = path / filename
                if target.exists():
                    yield from self._load_file(target, record_type)
        else:
            record_type = self._FILE_MAP.get(path.name, "crm_record")
            yield from self._load_file(path, record_type)

    def _load_file(self, path: Path, record_type: str) -> Iterator[dict]:
        with open(path) as f:
            data = json.load(f)
        for record in (data if isinstance(data, list) else []):
            yield {"_record_type": record_type, "_source_file": str(path), **record}

    def normalize(self, raw: dict) -> SourceRecord:
        record_type = raw.pop("_record_type", "crm_record")
        source_file = raw.pop("_source_file", "crm")

        # Pick best native ID per record type
        native_id = (
            raw.get("client_id")
            or raw.get("customer_id")
            or raw.get("product_id")
            or str(raw.get("sales_record_id", ""))
            or raw.get("id", "")
        )

        payload = {k: v for k, v in raw.items()}
        content_hash = SourceRecord.hash_payload(payload)
        return SourceRecord(
            id=SourceRecord.make_id(record_type, content_hash),
            source_type=record_type,
            source_uri=source_file,
            source_native_id=native_id,
            payload=payload,
            content_hash=content_hash,
            metadata={"method": "connector_ingest"},
        )
