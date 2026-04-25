from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

try:
    from supabase import create_client, Client  # type: ignore
except Exception:  # pragma: no cover - import guard for local dev w/o deps
    Client = Any  # type: ignore


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def upsert_to_db(client: Client, ontology: dict[str, Any]) -> None:
    entity_types = ontology.get("entity_types") or {}
    edge_types = ontology.get("edge_types") or {}

    if entity_types:
        rows = [
            {"id": key, "config": cfg} for key, cfg in entity_types.items()
        ]
        client.table("entity_type_config").upsert(rows, on_conflict="id").execute()

    if edge_types:
        rows = [
            {"id": key, "config": cfg} for key, cfg in edge_types.items()
        ]
        client.table("edge_type_config").upsert(rows, on_conflict="id").execute()


def load_all(directory: Path = Path("config/ontologies")) -> list[str]:
    loaded: list[str] = []
    if not directory.exists():
        return loaded
    for path in sorted(directory.glob("*.yaml")):
        loaded.append(path.name)
    return loaded

