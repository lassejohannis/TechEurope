"""CLI entry.

Usage examples:
  - `uv run server` → start FastAPI dev server
  - `uv run server dev` → same as above
  - `uv run server ingest --connector email --path data/enterprise-bench/`
  - `uv run server status`
  - `uv run server discover --connector all --path data/enterprise-bench` (dry-run)
  - `uv run server resolve --limit 200 --source-type email`
  - `uv run server reprocess` (re-derive needs_refresh facts)
"""

from __future__ import annotations

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
from server.vfs_paths import segment_from_type, slugify_name


cli = typer.Typer(add_completion=False, no_args_is_help=False)


# Resolver-internal type aliases. The DB ontology uses "organization" while
# extractor/cascade internals still emit "company".
_ENTITY_TYPE_ALIASES = {
    "company": "organization",
}


def _canonical_entity_type(entity_type: str) -> str:
    return _ENTITY_TYPE_ALIASES.get(entity_type, entity_type)


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
            "crm",           # umbrella: customer, product, sale, client
            "hr_record",
            "invoice_pdf",
            "it_ticket",
            "document",
            "collaboration",
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


@cli.command("gemini-stats")
def cmd_gemini_stats() -> None:
    """Print process-wide Gemini call/cap/cooldown stats."""
    import json as _json

    from server.gemini_budget import get_budget

    typer.echo(_json.dumps(get_budget().stats(), indent=2, default=str))


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
    slug = slugify_name(canonical_name)
    etype = _canonical_entity_type(entity_type)
    return f"{etype}:{slug}"


def _persist_entity(
    db,
    candidate,
    matched_id: str | None,
) -> str | None:
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

    canonical_entity_type = _canonical_entity_type(candidate.entity_type)
    eid = _entity_id(canonical_entity_type, candidate.canonical_name)
    entity_segment = segment_from_type(canonical_entity_type)
    base_slug = slugify_name(candidate.canonical_name)
    base_path = f"/{entity_segment}/{base_slug}"

    existing_res = (
        db.table("entities")
        .select("id, attrs, embedding")
        .eq("id", eid)
        .limit(1)
        .execute()
    )
    existing = existing_res.data[0] if existing_res.data else None
    has_embedding = bool(existing) and existing.get("embedding") is not None

    attrs = dict(candidate.attrs or {})
    existing_vfs_path = (
        (existing.get("attrs") or {}).get("vfs_path")
        if isinstance(existing, dict)
        else None
    )

    if isinstance(existing_vfs_path, str) and existing_vfs_path.strip():
        attrs["vfs_path"] = existing_vfs_path.strip()
    else:
        suffix = 1
        vfs_path = base_path
        while True:
            path_res = (
                db.table("entities")
                .select("id")
                .eq("entity_type", canonical_entity_type)
                .filter("attrs->>vfs_path", "eq", vfs_path)
                .limit(1)
                .execute()
            )
            taken = bool(path_res.data) and str(path_res.data[0]["id"]) != eid
            if not taken:
                attrs["vfs_path"] = vfs_path
                break
            suffix += 1
            vfs_path = f"{base_path}-{suffix}"

    aliases = list({candidate.canonical_name})
    for hard_id_field in ("email", "emp_id", "tax_id", "domain", "product_id"):
        if v := candidate.attrs.get(hard_id_field):
            aliases.append(str(v).lower())

    # Organization-specific alias seeding so that "Inazuma", "Inazuma.co",
    # "Inazuma Corp", "inazuma.com" all converge on the same entity via
    # Tier 2 alias-match. Without these the same company gets a fresh
    # entity per source-type-mapping.
    if canonical_entity_type == "organization":
        from server.db import normalize_for_embedding
        aliases.append(normalize_for_embedding(candidate.canonical_name))
        if "@" in candidate.canonical_name:
            aliases.append(candidate.canonical_name.split("@", 1)[1].lower().strip())
        for fld in ("domain", "website", "url", "homepage"):
            v = candidate.attrs.get(fld)
            if isinstance(v, str) and v.strip():
                aliases.append(v.strip().lower())

    # Build Tier-A name embedding only if this entity is new — re-runs of
    # resolve must not re-call Gemini for entities that already have one.
    embedding = None if has_embedding else _build_tier_a_embedding(candidate)

    # entities.entity_type is the writable column on this schema (renamed
    # from `type` in migration 003).
    row: dict[str, object] = {
        "id": eid,
        "entity_type": canonical_entity_type,
        "canonical_name": candidate.canonical_name,
        "aliases": aliases,
        "attrs": attrs,
        "provenance": [candidate.source_id] if candidate.source_id else [],
    }
    if embedding is not None:
        row["embedding"] = embedding

    try:
        db.table("entities").upsert(row, on_conflict="id").execute()
    except Exception as exc:
        # DB-side ontology guards can reject unknown/unapproved entity types.
        if "not approved" in str(exc):
            return None
        raise
    return eid


def _build_tier_a_embedding(candidate) -> list[float] | None:
    """Use the per-type build_search_text helper + embed_text to mint Tier A."""
    from server.db import embed_text
    from server.resolver.cascade import _get_type_module

    type_mod = _get_type_module(candidate.entity_type)
    if type_mod is not None and hasattr(type_mod, "build_search_text"):
        text = type_mod.build_search_text(candidate.canonical_name, candidate.attrs)
    else:
        text = candidate.canonical_name
    try:
        return embed_text(text)
    except Exception as exc:
        # Embedding must never block resolver writes in local/dev envs where
        # GEMINI_API_KEY is missing or temporarily invalid.
        typer.echo(f"Embedding unavailable: {exc}")
        return None


def _persist_relationship_fact(
    db,
    subject_id: str,
    predicate: str,
    object_id: str,
    source_id: str,
    confidence: float,
) -> bool:
    """Write a Tier-4 relationship-hint fact directly (subject + object known)."""
    try:
        db.table("facts").insert(
            {
                "id": str(uuid.uuid4()),
                "subject_id": subject_id,
                "predicate": predicate,
                "object_id": object_id,
                "object_literal": None,
                "confidence": confidence,
                "source_id": source_id,
                "extraction_method": "rule",
            }
        ).execute()
        return True
    except Exception as exc:
        if "no_temporal_overlap" in str(exc) or "23P01" in str(exc):
            return False
        raise


def _persist_fact(
    db,
    pf,
    name_to_id: dict[tuple[str, str], str],
    source_id: str,
) -> bool:
    subject_key = (_canonical_entity_type(pf.subject_key[0]), pf.subject_key[1])
    subject_id = name_to_id.get(subject_key)
    if not subject_id:
        return False

    object_id: str | None = None
    object_literal = pf.object_literal
    if pf.object_key is not None:
        object_key = (_canonical_entity_type(pf.object_key[0]), pf.object_key[1])
        object_id = name_to_id.get(object_key)
        if not object_id:
            # Object entity wasn't extracted from this record — store as literal
            # so the fact still carries the reference.
            object_literal = {"name": pf.object_key[1], "type": object_key[0]}
    if object_id is None and object_literal is None:
        return False

    # Skip self-loops (Pioneer occasionally emits "X has_price X" on noisy text).
    if object_id is not None and object_id == subject_id:
        return False

    try:
        payload = {
            "id": str(uuid.uuid4()),
            "subject_id": subject_id,
            "predicate": pf.predicate,
            "object_id": object_id,
            "object_literal": object_literal,
            "confidence": pf.confidence,
            "source_id": source_id,
            # Optional metadata columns differ across DB revisions; keep core
            # fields stable so resolver can operate against older schemas.
        }
        db.table("facts").insert(payload).execute()
        return True
    except Exception as exc:
        # Pioneer/Gemini occasionally emit predicates not yet in edge_type_config.
        # Auto-register them as approved (consistent with the autonomous-ontology
        # promise) and retry once.
        if "edge_type_config" in str(exc) or "facts_predicate_fk" in str(exc):
            try:
                db.table("edge_type_config").upsert(
                    {
                        "id": pf.predicate,
                        "config": {
                            "description": "Auto-registered from free-text extraction",
                            "auto_proposed": True,
                        },
                        "approval_status": "approved",
                        "auto_proposed": True,
                    },
                    on_conflict="id",
                ).execute()
                db.table("facts").insert(payload).execute()
                return True
            except Exception:
                return False
        if "not approved" in str(exc):
            return False
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
    llm_extract: bool = typer.Option(True, help="Mine free-text payload fields via Pioneer/Gemini for relationship facts"),
) -> None:
    """Walk source_records → resolve → upsert entities + facts.

    Idempotent: deterministic entity IDs (`{type}:{slug}`) mean re-running on
    the same records is safe.
    """
    from server.resolver.cascade import resolve as cascade_resolve
    from server.resolver.extract import extract_candidates
    from server.ontology.engine import apply_mapping

    db = get_supabase()
    q = db.table("source_records").select("id, source_type, payload")
    if source_type:
        q = q.eq("source_type", source_type)
    res = q.range(offset, offset + limit - 1).execute()
    records = res.data or []

    typer.echo(f"processing {len(records)} source_records …")

    # Cache approved mapping configs once per source_type — avoids 28k DB
    # roundtrips when running over the full corpus.
    mapping_cache: dict[str, dict | None] = {}

    def _mapping_for(stype: str) -> dict | None:
        if stype not in mapping_cache:
            r = (
                db.table("source_type_mapping")
                .select("config, status")
                .eq("source_type", stype)
                .limit(1)
                .execute()
            )
            row = (r.data or [None])[0]
            if row and row.get("status") == "approved":
                mapping_cache[stype] = row.get("config") or {}
            else:
                mapping_cache[stype] = None
        return mapping_cache[stype]
    stats = {
        "records": 0,
        "candidates": 0,
        "entities_created": 0,
        "entities_merged": 0,
        "entities_inboxed": 0,
        "facts": 0,
        "skipped_no_mapping": 0,
    }

    from server.gemini_budget import get_budget

    for rec in records:
        if get_budget().in_cooldown():
            typer.echo("gemini cooldown active — stopping early")
            break
        stats["records"] += 1

        cfg = _mapping_for(rec.get("source_type") or "")
        if cfg is None:
            # Backward-compatible fallback: keep resolver functional for
            # source_types that don't have an approved source_type_mapping yet.
            candidates, pending_facts = extract_candidates(rec, llm_extract=llm_extract)
        else:
            candidates, pending_facts = apply_mapping(rec, cfg)
        if not candidates and not pending_facts:
            continue
        stats["candidates"] += len(candidates)

        # Resolve every candidate, building name → id map for facts.
        name_to_id: dict[tuple[str, str], str] = {}
        for cand in candidates:
            result = cascade_resolve(cand, db)
            # Cascade returns matched_id for same-type merges (T1/T2/T3/T3.5).
            # For inbox-action results matched_id points to the *other side*
            # of the pending pair — the candidate itself must still be persisted
            # as a new entity so a human can decide if they're duplicates.
            if result.action == "inbox":
                entity_id = _persist_entity(db, cand, None)  # force new
                if not entity_id:
                    continue
                canonical_type = _canonical_entity_type(cand.entity_type)
                name_to_id[(canonical_type, cand.canonical_name)] = entity_id
                from server.resolver.cascade import write_pending_inbox

                write_pending_inbox(cand, result, db)
                stats["entities_inboxed"] += 1
            else:
                # Tier-4 "context" matches are relationship hints (e.g. email-domain
                # → employer) — they must NOT collapse a person entity into a
                # company. Only same-type tiers are safe to merge by ID.
                same_type_match = result.matched_id if result.tier in (
                    "hard_id", "alias", "embedding", "pioneer"
                ) else None
                entity_id = _persist_entity(db, cand, same_type_match)
                if not entity_id:
                    continue
                canonical_type = _canonical_entity_type(cand.entity_type)
                name_to_id[(canonical_type, cand.canonical_name)] = entity_id

                if same_type_match:
                    stats["entities_merged"] += 1
                else:
                    stats["entities_created"] += 1

            # T4 cross-type hint → write an extra fact directly (e.g. works_at
            # when a person's email domain matches an existing company).
            if result.relationship_hint:
                predicate, _target_type, target_id = result.relationship_hint
                if _persist_relationship_fact(
                    db, entity_id, predicate, target_id, rec["id"], result.confidence
                ):
                    stats.setdefault("relationship_hints", 0)
                    stats["relationship_hints"] += 1

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


@cli.command("resolve-conflicts")
def cmd_resolve_conflicts(
    limit: int = typer.Option(200, help="Max pending fact_resolutions to process"),
) -> None:
    """Walk pending fact_resolutions and apply the 4-tier auto-resolution cascade.

    Tiers: cross-confirmation → authority (trust_weight × confidence) →
    confidence → recency. Whichever tier produces a clear winner wins; the
    rest stay 'pending' for the human inbox.
    """
    from server.resolver.auto_resolve import auto_resolve_disputed_facts

    db = get_supabase()
    stats = auto_resolve_disputed_facts(db, limit=limit)
    typer.echo("done:")
    for k, v in stats.items():
        typer.echo(f"  {k}: {v}")


@cli.command("reprocess")
def cmd_reprocess(
    limit: int = typer.Option(500, help="Max stale source records to reprocess"),
) -> None:
    """Re-derive facts for source_records whose facts are marked needs_refresh.

    Finds source_records linked to needs_refresh facts, re-runs the resolver
    on them, and inserts fresh facts. Idempotent: deterministic entity IDs
    mean repeated runs are safe.
    """
    from server.resolver.cascade import resolve as cascade_resolve
    from server.resolver.extract import extract_candidates

    db = get_supabase()

    stale = (
        db.table("facts")
        .select("source_id")
        .eq("status", "needs_refresh")
        .limit(limit)
        .execute()
    )
    source_ids = list({r["source_id"] for r in (stale.data or []) if r.get("source_id")})

    if not source_ids:
        typer.echo("no stale facts found")
        return

    typer.echo(f"found {len(source_ids)} stale source records")

    records: list[dict] = []
    _chunk = 50
    for i in range(0, len(source_ids), _chunk):
        chunk = source_ids[i : i + _chunk]
        res = db.table("source_records").select("id, source_type, payload").in_("id", chunk).execute()
        records.extend(res.data or [])

    typer.echo(f"reprocessing {len(records)} records …")

    # Reset needs_refresh → active before reinserting so GIST dedup works correctly
    for i in range(0, len(source_ids), _chunk):
        chunk = source_ids[i : i + _chunk]
        db.table("facts").update({"status": "active"}).in_("source_id", chunk).eq(
            "status", "needs_refresh"
        ).execute()

    stats = {"records": 0, "facts": 0}
    for rec in records:
        stats["records"] += 1
        candidates, pending_facts = extract_candidates(rec)
        name_to_id: dict[tuple[str, str], str] = {}
        for cand in candidates:
            result = cascade_resolve(cand, db)
            same_type_match = (
                result.matched_id
                if result.tier in ("hard_id", "alias", "embedding", "pioneer")
                else None
            )
            entity_id = _persist_entity(db, cand, same_type_match)
            name_to_id[(cand.entity_type, cand.canonical_name)] = entity_id
        for pf in pending_facts:
            if _persist_fact(db, pf, name_to_id, rec["id"]):
                stats["facts"] += 1

    typer.echo("done:")
    for k, v in stats.items():
        typer.echo(f"  {k}: {v}")


@cli.command("backfill-embeddings")
def cmd_backfill_embeddings(
    tier: str = typer.Option("A", help="A = name embedding, B = inference embedding"),
    limit: int = typer.Option(500, help="Max entities to process this run"),
    batch: int = typer.Option(50, help="Batch size for embedding API calls"),
) -> None:
    """Backfill embeddings for entities that don't have one yet.

    Tier A: name + key-attrs embedding (cheap, used by Hybrid Search Stage 1).
    Tier B: inference text from neighbouring facts (expensive, hot entities only).
    """
    from server.db import embed_text
    from server.gemini_budget import get_budget
    from server.resolver.cascade import _get_type_module

    if tier not in ("A", "B"):
        raise typer.BadParameter("tier must be 'A' or 'B'")

    db = get_supabase()
    column = "embedding" if tier == "A" else "inference_embedding"
    res = (
        db.table("entities")
        .select("id, entity_type, canonical_name, attrs")
        .is_(column, "null")
        .limit(limit)
        .execute()
    )
    rows = res.data or []
    typer.echo(f"backfilling {len(rows)} entities (tier={tier}) …")

    written = 0
    skipped = 0
    for i, row in enumerate(rows, 1):
        if get_budget().in_cooldown():
            typer.echo("gemini cooldown active — stopping early")
            break
        if tier == "A":
            type_mod = _get_type_module(row["entity_type"])
            if type_mod is not None and hasattr(type_mod, "build_search_text"):
                text = type_mod.build_search_text(row["canonical_name"], row.get("attrs") or {})
            else:
                text = row["canonical_name"]
        else:
            from server.resolver.embed import build_inference_text
            text = build_inference_text(row["id"], db)

        vec = embed_text(text)
        if vec is None:
            skipped += 1
            continue

        update: dict[str, object] = {column: vec}
        if tier == "B":
            update["inference_needs_refresh"] = False
        db.table("entities").update(update).eq("id", row["id"]).execute()
        written += 1

        if i % batch == 0:
            typer.echo(f"  {i}/{len(rows)} (written={written}, skipped={skipped})")

    typer.echo(f"done: written={written}, skipped={skipped}")


@cli.command("reembed")
def cmd_reembed(
    tier: str = typer.Option("B", help="A = name, B = inference (default)"),
    limit: int = typer.Option(200, help="Max entities per run"),
    fact_threshold: int = typer.Option(3, help="Tier B only: min fact-count to qualify as 'hot'"),
) -> None:
    """Re-embed entities flagged inference_needs_refresh=true.

    Tier B is the default; Tier A re-embed is rare (only when normalize logic
    changes). Idempotent — picks the next batch of stale entities each run.
    """
    from server.db import embed_text
    from server.gemini_budget import get_budget
    from server.resolver.cascade import _get_type_module
    from server.resolver.embed import build_inference_text

    if tier not in ("A", "B"):
        raise typer.BadParameter("tier must be 'A' or 'B'")

    db = get_supabase()
    if tier == "B":
        # Hot-entity filter: run an RPC-free heuristic by counting facts in Python.
        res = (
            db.table("entities")
            .select("id, entity_type, canonical_name, attrs")
            .eq("inference_needs_refresh", True)
            .limit(limit)
            .execute()
        )
        candidates = res.data or []
        # Filter to hot entities (>= fact_threshold facts as subject).
        hot = []
        for row in candidates:
            count_res = (
                db.table("facts")
                .select("id", count="exact")
                .eq("subject_id", row["id"])
                .is_("valid_to", "null")
                .execute()
            )
            if (count_res.count or 0) >= fact_threshold:
                hot.append(row)
        rows = hot
    else:
        res = (
            db.table("entities")
            .select("id, entity_type, canonical_name, attrs")
            .is_("embedding", "null")
            .limit(limit)
            .execute()
        )
        rows = res.data or []

    typer.echo(f"reembedding {len(rows)} entities (tier={tier}) …")
    written = skipped = 0
    for i, row in enumerate(rows, 1):
        if get_budget().in_cooldown():
            typer.echo("gemini cooldown active — stopping early")
            break
        if tier == "B":
            text = build_inference_text(row["id"], db)
        else:
            type_mod = _get_type_module(row["entity_type"])
            if type_mod is not None and hasattr(type_mod, "build_search_text"):
                text = type_mod.build_search_text(row["canonical_name"], row.get("attrs") or {})
            else:
                text = row["canonical_name"]

        vec = embed_text(text)
        if vec is None:
            skipped += 1
            continue

        col = "inference_embedding" if tier == "B" else "embedding"
        update: dict[str, object] = {col: vec}
        if tier == "B":
            update["inference_needs_refresh"] = False
        db.table("entities").update(update).eq("id", row["id"]).execute()
        written += 1

        if i % 25 == 0:
            typer.echo(f"  {i}/{len(rows)}")

    typer.echo(f"done: written={written}, skipped={skipped}")


# ---------------------------------------------------------------------------
# Agent tokens (WS-API #14)
# ---------------------------------------------------------------------------

token_cli = typer.Typer(help="Manage agent_tokens for MCP / programmatic API access")
cli.add_typer(token_cli, name="token")


@token_cli.command("issue")
def cmd_token_issue(
    name: str = typer.Argument(..., help="Human-readable label for this token"),
    scopes: str = typer.Option("read", help="Comma-separated scopes: read,write,admin"),
) -> None:
    from server.auth.tokens import issue_token

    scope_list = [s.strip() for s in scopes.split(",") if s.strip()]
    token_id, full_token = issue_token(name, scope_list)
    typer.echo(f"id:     {token_id}")
    typer.echo(f"scopes: {','.join(scope_list)}")
    typer.echo(f"token:  {full_token}")
    typer.echo("⚠  Save this token now — it won't be shown again.")


@token_cli.command("list")
def cmd_token_list() -> None:
    from server.auth.tokens import list_tokens

    rows = list_tokens()
    if not rows:
        typer.echo("(no tokens)")
        return
    for r in rows:
        status = "revoked" if r.get("revoked_at") else "active"
        typer.echo(
            f"{r['id']}  [{status}]  {r['name']}  scopes={','.join(r.get('scopes') or [])}"
        )


@token_cli.command("revoke")
def cmd_token_revoke(token_id: str) -> None:
    from server.auth.tokens import revoke_token

    if revoke_token(token_id):
        typer.echo(f"revoked {token_id}")
    else:
        typer.echo(f"no such token: {token_id}", err=True)
        raise typer.Exit(code=1)

@cli.command("infer-source-mappings")
def cmd_infer_source_mappings(
    sample_size: int = typer.Option(5, help="Sample records per source_type for inference"),
    holdout_size: int = typer.Option(3, help="Held-out records used for validation"),
    auto_approve: bool = typer.Option(
        True,
        help="Approve mappings even if they would normally route to the inbox",
    ),
    only: str | None = typer.Option(None, help="Run only for this source_type"),
) -> None:
    """For every source_type without an approved mapping, ask Gemini to design one.

    Validates each proposal on a held-out sample and (by default) writes it
    straight to ``source_type_mapping`` as ``status='approved'`` so the engine
    picks it up immediately. New entity/edge types referenced by the proposal
    are upserted into the type configs as ``approved`` so the FK trigger
    accepts them.
    """
    from server.ontology.propose import (
        infer_source_mapping,
        persist_proposal,
        should_auto_approve,
        validate_proposal,
    )

    db = get_supabase()

    # Discover candidate source_types from source_records (paginate; default
    # postgrest cap is 1000 rows so we'd otherwise miss minority types).
    if only:
        distinct_types = [only]
    else:
        seen: set[str] = set()
        page, page_size = 0, 1000
        while True:
            res = (
                db.table("source_records")
                .select("source_type")
                .range(page * page_size, (page + 1) * page_size - 1)
                .execute()
            )
            rows = res.data or []
            for r in rows:
                if r.get("source_type"):
                    seen.add(r["source_type"])
            if len(rows) < page_size:
                break
            page += 1
        distinct_types = sorted(seen)

    typer.echo(f"source_types in scope: {distinct_types}")

    for stype in distinct_types:
        existing = (
            db.table("source_type_mapping")
            .select("status")
            .eq("source_type", stype)
            .limit(1)
            .execute()
        )
        if existing.data and existing.data[0].get("status") == "approved":
            typer.echo(f"  {stype}: already approved — skip")
            continue

        sample_res = (
            db.table("source_records")
            .select("id, source_type, payload")
            .eq("source_type", stype)
            .limit(sample_size + holdout_size)
            .execute()
        )
        records = sample_res.data or []
        if len(records) < 2:
            typer.echo(f"  {stype}: only {len(records)} records — skip")
            continue
        sample = records[:sample_size]
        holdout = records[sample_size : sample_size + holdout_size] or sample[-1:]

        typer.echo(f"  {stype}: inferring mapping (samples={len(sample)}, holdout={len(holdout)}) …")
        proposal = infer_source_mapping(stype, sample, db)
        if proposal is None:
            typer.echo("    ✗ inference returned None (likely budget/api)")
            continue

        stats = validate_proposal(proposal, holdout)
        typer.echo(
            f"    validation: ents={stats['entities_total']} facts={stats['facts_total']} "
            f"entity_rate={stats['entity_rate']:.2f} fact_rate={stats['fact_rate']:.2f}"
        )

        # Auto-approve every type/predicate the mapping actually references.
        # We can't trust `proposal.new_entity_types` / `new_edge_types` alone:
        # the LLM frequently uses a predicate (e.g. `has_skill`) inside
        # `facts[].predicate` without declaring it. Walk the config instead
        # so the resolver can never hit a "type X not approved" trigger.
        # Honest gate: even when --auto-approve is on (default), only flip the
        # mapping to approved if the validator actually scored it. A 0/0 mapping
        # belongs in the human inbox, not silently approved.
        gated_auto = auto_approve and should_auto_approve(proposal, stats)

        if gated_auto:
            from server.ontology.engine import FORBIDDEN_ENTITY_TYPES

            def _is_real_entity_type(t: str | None) -> bool:
                """Block scalar pseudo-types (string, number, ...) from becoming approved."""
                return bool(t) and t.strip().lower() not in FORBIDDEN_ENTITY_TYPES

            referenced_entity_types: set[str] = set()
            referenced_edges: set[str] = set()
            for spec in proposal.entities or []:
                if _is_real_entity_type(spec.type):
                    referenced_entity_types.add(spec.type)
            for spec in proposal.facts or []:
                if _is_real_entity_type(spec.subject_type):
                    referenced_entity_types.add(spec.subject_type)
                if _is_real_entity_type(spec.object_type):
                    referenced_entity_types.add(spec.object_type)
                if spec.predicate:
                    referenced_edges.add(spec.predicate)
            for self_declared in proposal.new_entity_types or []:
                if _is_real_entity_type(self_declared):
                    referenced_entity_types.add(self_declared)
            for self_declared in proposal.new_edge_types or []:
                if self_declared:
                    referenced_edges.add(self_declared)

            def _approve(table: str, ids: set[str]) -> None:
                if not ids:
                    return
                # Don't override explicitly rejected rows — only flip pending /
                # missing into approved.
                existing = (
                    db.table(table)
                    .select("id, approval_status")
                    .in_("id", list(ids))
                    .execute()
                )
                rejected = {
                    r["id"]
                    for r in (existing.data or [])
                    if r.get("approval_status") == "rejected"
                }
                for tid in ids:
                    if tid in rejected:
                        continue
                    db.table(table).upsert(
                        {
                            "id": tid,
                            "config": {
                                "description": f"Auto-approved by infer-source-mappings for {stype}",
                                "auto_proposed": True,
                            },
                            "approval_status": "approved",
                            "auto_proposed": True,
                        },
                        on_conflict="id",
                    ).execute()

            _approve("entity_type_config", referenced_entity_types)
            _approve("edge_type_config", referenced_edges)

        status = persist_proposal(
            proposal,
            db,
            sample_ids=[r["id"] for r in sample],
            validation_stats=stats,
            auto_approve=gated_auto,
        )
        typer.echo(f"    → {status}")

    typer.echo("done.")
@cli.command("mcp-stdio")
def cmd_mcp_stdio() -> None:
    """Run the MCP server over stdio (for Claude Desktop / mcp-cli)."""
    from server.mcp.stdio import run

    run()


@cli.command("link-reports-to")
def cmd_link_reports_to(
    dry_run: bool = typer.Option(False, help="Print matches without writing"),
) -> None:
    """Resolve reports_to_emp_id literal facts → manages entity-to-entity facts in Postgres.

    Run after all HR records have been resolved:
      uv run server resolve --source-type hr_record
    """
    db = get_supabase()

    res = (
        db.table("facts")
        .select("id, subject_id, object_literal")
        .eq("predicate", "reports_to_emp_id")
        .is_("valid_to", "null")
        .eq("status", "live")
        .execute()
    )
    literal_facts = res.data or []
    typer.echo(f"found {len(literal_facts)} reports_to_emp_id facts")

    linked = skipped = already_exists = 0
    for fact in literal_facts:
        employee_id = fact["subject_id"]
        manager_emp_id = str(fact.get("object_literal") or "").strip()
        if not manager_emp_id:
            skipped += 1
            continue

        mgr_res = (
            db.table("entities")
            .select("id, canonical_name")
            .eq("entity_type", "person")
            .filter("attrs->>emp_id", "eq", manager_emp_id)
            .limit(1)
            .execute()
        )
        if not mgr_res.data:
            mgr_res = (
                db.table("entities")
                .select("id, canonical_name")
                .eq("entity_type", "person")
                .contains("aliases", [manager_emp_id.lower()])
                .limit(1)
                .execute()
            )
        if not mgr_res.data:
            skipped += 1
            continue

        manager_id = mgr_res.data[0]["id"]
        manager_name = mgr_res.data[0]["canonical_name"]

        if dry_run:
            typer.echo(f"  {manager_name} manages → {employee_id}")
            linked += 1
            continue

        try:
            db.table("facts").insert(
                {
                    "id": str(uuid.uuid4()),
                    "subject_id": manager_id,
                    "predicate": "manages",
                    "object_id": employee_id,
                    "confidence": 0.99,
                    "source_id": fact["id"],
                    "extraction_method": "rule",
                    "derivation": "rule:reports_to_emp_id_resolve",
                }
            ).execute()
            linked += 1
        except Exception as exc:
            if "no_temporal_overlap" in str(exc) or "23P01" in str(exc):
                already_exists += 1
            else:
                typer.echo(f"  error {manager_id} → {employee_id}: {exc}")

    typer.echo(f"linked: {linked}  already_exists: {already_exists}  skipped: {skipped}")


def main() -> None:
    import sys
    if len(sys.argv) == 1:
        # backward-compatible default: start dev server
        return cmd_dev()
    cli()


if __name__ == "__main__":
    main()
