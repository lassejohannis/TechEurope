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


def get_ontology_dir(default: Path | None = None) -> Path | None:
    """Find the ontologies directory regardless of current working dir.

    Tries in order:
      1) provided default
      2) CWD/config/ontologies
      3) walk up from this file to find a parent containing config/ontologies
    """
    candidates: list[Path] = []
    if default is not None:
        candidates.append(default)
    candidates.append(Path.cwd() / "config/ontologies")
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidates.append(parent / "config/ontologies")
    for c in candidates:
        if c.exists() and c.is_dir():
            return c
    return None


def load_all(directory: Path | None = None) -> list[str]:
    loaded: list[str] = []
    dirpath = get_ontology_dir(directory or Path("config/ontologies"))
    if not dirpath:
        return loaded
    for path in sorted(dirpath.glob("*.yaml")):
        loaded.append(path.name)
    return loaded
