"""CLI entry: `uv run server` starts the FastAPI dev server.

Sub-commands
------------
serve   — start the FastAPI dev server (default)
ingest  — run a connector and upsert records into Supabase

Examples
--------
    uv run server serve
    uv run server ingest --connector email \\
        --path data/enterprise-bench/Enterprise_mail_system/emails.json
    uv run server ingest --connector document \\
        --path data/enterprise-bench/Policy_Documents --structured
    uv run server ingest --connector hr \\
        --path data/enterprise-bench/Human_Resources --dry-run
"""

from __future__ import annotations

import sys


def _serve() -> None:
    import uvicorn
    from server.config import settings
    uvicorn.run(
        "server.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )


def _ingest(
    connector: str,
    path: str,
    *,
    structured: bool = False,
    dry_run: bool = False,
    batch_size: int = 100,
) -> None:
    """Run a named connector and upsert results into Supabase."""
    from pathlib import Path
    from server.connectors import REGISTRY

    if connector not in REGISTRY:
        print(f"Unknown connector '{connector}'. Available: {', '.join(REGISTRY)}")
        sys.exit(1)

    target = Path(path)
    if not target.exists():
        print(f"Path not found: {target}")
        sys.exit(1)

    connector_cls = REGISTRY[connector]
    # DocumentConnector accepts extract_structured kwarg; others ignore extra kwargs
    try:
        instance = connector_cls(extract_structured=structured)  # type: ignore[call-arg]
    except TypeError:
        instance = connector_cls()

    records = list(instance.ingest(target))
    print(f"[{connector}] {len(records)} records extracted from {target}")

    if dry_run:
        for r in records[:5]:
            print(f"  {r.id}  {r.source_type}  {r.source_native_id}")
        if len(records) > 5:
            print(f"  … and {len(records) - 5} more")
        print("[dry-run] nothing persisted")
        return

    from server.db import get_supabase
    db = get_supabase()

    inserted = skipped = 0
    batch: list[dict] = []

    def _flush(batch: list[dict]) -> tuple[int, int]:
        resp = (
            db.table("source_records")
            .upsert(batch, on_conflict="content_hash", ignore_duplicates=True)
            .execute()
        )
        ins = len(resp.data) if resp.data else 0
        return ins, len(batch) - ins

    for rec in records:
        batch.append({
            "id": rec.id,
            "source_type": rec.source_type,
            "source_uri": rec.source_uri,
            "source_native_id": rec.source_native_id,
            "payload": rec.payload,
            "content_hash": rec.content_hash,
            "extraction_status": rec.extraction_status,
            "metadata": rec.metadata,
        })
        if len(batch) >= batch_size:
            i, s = _flush(batch)
            inserted += i
            skipped += s
            batch = []

    if batch:
        i, s = _flush(batch)
        inserted += i
        skipped += s

    print(f"[{connector}] inserted={inserted} skipped(duplicate)={skipped}")


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] == "serve":
        _serve()
        return

    if args[0] == "ingest":
        import argparse
        p = argparse.ArgumentParser(prog="server ingest")
        p.add_argument("--connector", required=True, help="Connector name: email|crm|hr|itsm|document")
        p.add_argument("--path", required=True, help="File or directory to ingest")
        p.add_argument("--structured", action="store_true", help="Enable Gemini structured extraction (document connector only)")
        p.add_argument("--dry-run", action="store_true", help="Print records without persisting")
        p.add_argument("--batch-size", type=int, default=100, help="Upsert batch size (default 100)")
        ns = p.parse_args(args[1:])
        _ingest(
            ns.connector,
            ns.path,
            structured=ns.structured,
            dry_run=ns.dry_run,
            batch_size=ns.batch_size,
        )
        return

    print(f"Unknown sub-command '{args[0]}'. Usage: server [serve|ingest]")
    sys.exit(1)


if __name__ == "__main__":
    main()
