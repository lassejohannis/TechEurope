"""CLI entry.

Usage examples:
  - `uv run server` → start FastAPI dev server
  - `uv run server dev` → same as above
  - `uv run server ingest --connector email --path data/enterprise-bench/`
  - `uv run server status`
  - `uv run server discover --connector all --path data/enterprise-bench` (dry-run)
"""

from __future__ import annotations

import uvicorn
import typer
from pathlib import Path

from server.config import settings
from server.db import get_supabase
from server.connectors import CONNECTOR_REGISTRY, get_connector  # side-effect import populates registry


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


def main() -> None:
    import sys
    if len(sys.argv) == 1:
        # backward-compatible default: start dev server
        return cmd_dev()
    cli()


if __name__ == "__main__":
    main()
