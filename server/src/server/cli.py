"""CLI entry.

Usage examples:
  - `uv run server` → start FastAPI dev server
  - `uv run server dev` → same as above
  - `uv run server ingest --connector email --path data/enterprise-bench/`
  - `uv run server status`
  - `uv run server discover --connector all --path data/enterprise-bench` (dry-run)
  - `uv run server resolve --limit 200 --source-type email`
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import typer
import uvicorn

from server.config import settings
from server.connectors import (  # side-effect import populates registry
    CONNECTOR_REGISTRY,
    get_connector,
)
from server.db import get_supabase


cli = typer.Typer(add_completion=False, no_args_is_help=False)


@cli.command("dev")
def cmd_dev() -> None:
    uvicorn.run(
        "server.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )


@cli.command("ingest")
def cmd_ingest(
    connector: str = typer.Option(..., help="Connector name or 'all'"),
    path: Path = typer.Option(Path("data/enterprise-bench"), exists=False),
    batch_size: int = typer.Option(500, help="Batch size for upserts"),
):
    supabase = get_supabase()
    if connector == "all":
        order = [
            "email",
            "crm",       # umbrella: customer, product, sale, client
            "hr_record",
            "invoice_pdf",
            "it_ticket",
            "document",
        ]
        total = 0
        for name in order:
            cls = CONNECTOR_REGISTRY.get(name) or get_connector(name)
            inst = cls()
            written = inst.ingest(path, supabase, batch_size=batch_size)
            typer.echo(f"[{name}] written: {written}")
            total += written
        typer.echo(f"total written: {total}")
        return
    cls = CONNECTOR_REGISTRY.get(connector) or get_connector(connector)
    inst = cls()
    written = inst.ingest(path, supabase, batch_size=batch_size)
    typer.echo(f"[{connector}] written: {written}")


@cli.command("status")
def cmd_status() -> None:
    supabase = get_supabase()
    types: dict[str, int] = {}
    page, page_size = 0, 1000
    while True:
        res = (
            supabase.table("source_records")
            .select("source_type")
            .range(page * page_size, (page + 1) * page_size - 1)
            .execute()
        )
        for row in res.data:
            t = row["source_type"]
            types[t] = types.get(t, 0) + 1
        if len(res.data) < page_size:
            break
        page += 1
    for t, c in sorted(types.items()):
        typer.echo(f"{t}: {c}")
    typer.echo(f"total: {sum(types.values())}")


@cli.command("discover")
def cmd_discover(
    connector: str = typer.Option(..., help="Connector name or 'all'"),
    path: Path = typer.Option(Path("data/enterprise-bench"), exists=False),
    sample: int = typer.Option(3, help="Show first N normalized IDs as sample"),
):
    def run_one(name: str) -> None:
        cls = CONNECTOR_REGISTRY.get(name) or get_connector(name)
        inst = cls()
        count = 0
        samples: list[str] = []
        for raw in inst.discover(path):
            count += 1
            if len(samples) < sample:
                rec = inst.normalize(raw)
                samples.append(f"{rec.id} :: {rec.content_hash[:12]}")
        typer.echo(f"[{name}] discovered={count}")
        for s in samples:
            typer.echo(f"  - {s}")

    if connector == "all":
        for name in ["email", "crm", "hr_record", "invoice_pdf"]:
            run_one(name)
        return
    run_one(connector)


# ---------------------------------------------------------------------------
# Resolver: source_records → entities + facts
# ---------------------------------------------------------------------------


def _entity_id(entity_type: str, canonical_name: str) -> str:
    """Deterministic entity ID from type + normalized name.

    Lets the resolver upsert the same logical entity idempotently across
    multiple source_records that mention it.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", canonical_name.lower()).strip("-") or "unnamed"
    return f"{entity_type}:{slug}"


def _persist_entity(
    db,
    candidate,
    matched_id: str | None,
) -> str:
    """Upsert an entity row and return its id.

    If matched_id is set, returns it (assumed: existing row in DB; we don't
    overwrite — Tier-1/Tier-2 already confirmed the match).
    Otherwise creates a deterministic-ID entity, merging aliases on conflict.
    """
    # Only trust matched_id for tiers that resolve same-entity. Tier-4 "context"
    # produces relationship hints (person → company by domain) which would
    # incorrectly merge a person into a company. Caller passes None for those.
    if matched_id:
        return matched_id

    eid = _entity_id(candidate.entity_type, candidate.canonical_name)
    aliases = list({candidate.canonical_name})
    for hard_id_field in ("email", "emp_id", "tax_id", "domain", "product_id"):
        if v := candidate.attrs.get(hard_id_field):
            aliases.append(str(v).lower())

    db.table("entities").upsert(
        {
            "id": eid,
            "entity_type": candidate.entity_type,
            "canonical_name": candidate.canonical_name,
            "aliases": aliases,
            "attrs": candidate.attrs,
            "provenance": [candidate.source_id] if candidate.source_id else [],
        },
        on_conflict="id",
    ).execute()
    return eid


def _persist_fact(
    db,
    pf,
    name_to_id: dict[tuple[str, str], str],
    source_id: str,
) -> bool:
    subject_id = name_to_id.get(pf.subject_key)
    if not subject_id:
        return False

    object_id: str | None = None
    object_literal = pf.object_literal
    if pf.object_key is not None:
        object_id = name_to_id.get(pf.object_key)
        if not object_id:
            # Object entity wasn't extracted from this record — store as literal
            # so the fact still carries the reference.
            object_literal = {"name": pf.object_key[1], "type": pf.object_key[0]}
    if object_id is None and object_literal is None:
        return False

    try:
        db.table("facts").insert(
            {
                "id": str(uuid.uuid4()),
                "subject_id": subject_id,
                "predicate": pf.predicate,
                "object_id": object_id,
                "object_literal": object_literal,
                "confidence": pf.confidence,
                "source_id": source_id,
                "extraction_method": pf.extraction_method,
            }
        ).execute()
        return True
    except Exception as exc:
        # `no_temporal_overlap` GIST exclusion fires when (subject, predicate)
        # is already asserted with overlapping validity — that's expected when
        # the same person/company appears in many source records. Treat as a
        # silent dedup and continue.
        if "no_temporal_overlap" in str(exc) or "23P01" in str(exc):
            return False
        raise


@cli.command("resolve")
def cmd_resolve(
    limit: int = typer.Option(200, help="Max source_records to process"),
    source_type: str | None = typer.Option(None, help="Filter by source_type"),
    offset: int = typer.Option(0, help="Skip the first N records"),
    verbose: bool = typer.Option(False, help="Log every entity decision"),
) -> None:
    """Walk source_records → resolve → upsert entities + facts.

    Idempotent: deterministic entity IDs (`{type}:{slug}`) mean re-running on
    the same records is safe.
    """
    from server.resolver.cascade import resolve as cascade_resolve
    from server.resolver.extract import extract_candidates

    db = get_supabase()
    q = db.table("source_records").select("id, source_type, payload")
    if source_type:
        q = q.eq("source_type", source_type)
    res = q.range(offset, offset + limit - 1).execute()
    records = res.data or []

    typer.echo(f"processing {len(records)} source_records …")

    stats = {
        "records": 0,
        "candidates": 0,
        "entities_created": 0,
        "entities_merged": 0,
        "entities_inboxed": 0,
        "facts": 0,
    }

    for rec in records:
        stats["records"] += 1
        candidates, pending_facts = extract_candidates(rec)
        stats["candidates"] += len(candidates)

        # Resolve every candidate, building name → id map for facts.
        name_to_id: dict[tuple[str, str], str] = {}
        for cand in candidates:
            result = cascade_resolve(cand, db)
            # Tier-4 "context" matches are relationship hints (e.g. email-domain
            # → employer) — they must NOT collapse a person entity into a
            # company. Only same-type tiers are safe to merge by ID.
            same_type_match = result.matched_id if result.tier in (
                "hard_id", "alias", "embedding", "pioneer"
            ) else None
            entity_id = _persist_entity(db, cand, same_type_match)
            name_to_id[(cand.entity_type, cand.canonical_name)] = entity_id

            if same_type_match:
                stats["entities_merged"] += 1
            elif result.action == "inbox":
                stats["entities_inboxed"] += 1
            else:
                stats["entities_created"] += 1

            if verbose:
                typer.echo(
                    f"  {cand.entity_type:10} {cand.canonical_name[:30]:30} → "
                    f"{entity_id} ({result.tier}, {result.action})"
                )

        # Persist pending facts now that all entities for this record are known.
        for pf in pending_facts:
            if _persist_fact(db, pf, name_to_id, rec["id"]):
                stats["facts"] += 1

    typer.echo("done:")
    for k, v in stats.items():
        typer.echo(f"  {k}: {v}")


def main() -> None:
    import sys
    if len(sys.argv) == 1:
        # backward-compatible default: start dev server
        return cmd_dev()
    cli()


if __name__ == "__main__":
    main()
