"""Generate synthetic training pairs for Pioneer fine-tune (WS-3, Task 2).

Reads chunks from data/enterprise-bench/, asks Gemini for structured
(entities, facts) extraction, writes one TrainingPair per line to
data/training/pioneer_training.jsonl.

Idempotent: re-running skips chunks already present in the output JSONL.

Usage:
    uv run python server/scripts/gen_pioneer_training.py --target 300
    uv run python server/scripts/gen_pioneer_training.py --domains emails,employees --target 100
    uv run python server/scripts/gen_pioneer_training.py --dry-run --target 5
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from collections.abc import Iterator
from pathlib import Path

from google import genai
from google.genai import types as genai_types

# Make `server.*` importable when running this script directly.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from server.config import settings  # noqa: E402
from server.extractors.gemini import _RESPONSE_SCHEMA  # noqa: E402
from server.extractors.schemas import ExtractionResult, TrainingPair  # noqa: E402

DATA_ROOT = ROOT.parent / "data" / "enterprise-bench"
OUTPUT_PATH = ROOT.parent / "data" / "training" / "pioneer_training.jsonl"


# --------------------------------------------------------------------------- #
# Chunk loaders — each yields (chunk_id, source_record_id, source_type, text) #
# --------------------------------------------------------------------------- #

Chunk = tuple[str, str, str, str]


def _chunk_id(prefix: str, content: str) -> str:
    return f"{prefix}:{hashlib.sha256(content.encode()).hexdigest()[:16]}"


def load_emails(limit: int | None = None) -> Iterator[Chunk]:
    path = DATA_ROOT / "Enterprise_mail_system" / "emails.json"
    data = json.loads(path.read_text())
    for i, e in enumerate(data):
        if limit and i >= limit:
            break
        text = (
            f"From: {e['sender_name']} <{e['sender_email']}>\n"
            f"To: {e['recipient_name']} <{e['recipient_email']}>\n"
            f"Date: {e['date']}\n"
            f"Subject: {e['subject']}\n\n"
            f"{e['body']}"
        )
        yield _chunk_id("email", e["email_id"]), f"email:{e['email_id']}", "email", text


def load_employees(limit: int | None = None) -> Iterator[Chunk]:
    path = DATA_ROOT / "Human_Resource_Management" / "Employees" / "employees.json"
    data = json.loads(path.read_text())
    for i, emp in enumerate(data):
        if limit and i >= limit:
            break
        # The bench uses a free-form `description` plus structured fields.
        text = emp.get("description", "")
        if not text:
            continue
        yield _chunk_id("employee", emp["index"]), f"hr_record:{emp['index']}", "hr_record", text


def load_customer_support(limit: int | None = None) -> Iterator[Chunk]:
    path = DATA_ROOT / "Customer_Relation_Management" / "Customer Support" / "customer_support_chats.json"
    if not path.exists():
        return
    data = json.loads(path.read_text())
    for i, item in enumerate(data):
        if limit and i >= limit:
            break
        text = json.dumps(item, ensure_ascii=False, indent=2)[:4000]
        cid = item.get("id") or item.get("chat_id") or str(i)
        yield _chunk_id("support", str(cid)), f"ticket:{cid}", "ticket", text


def load_sales(limit: int | None = None) -> Iterator[Chunk]:
    path = DATA_ROOT / "Customer_Relation_Management" / "sales.json"
    if not path.exists():
        return
    data = json.loads(path.read_text())
    for i, item in enumerate(data):
        if limit and i >= limit:
            break
        text = json.dumps(item, ensure_ascii=False, indent=2)[:4000]
        sid = item.get("id") or item.get("invoice_id") or str(i)
        yield _chunk_id("sales", str(sid)), f"sales_record:{sid}", "sales_record", text


def load_collaboration(limit: int | None = None) -> Iterator[Chunk]:
    """Conversations are one big JSON; flatten into per-conversation chunks."""
    path = DATA_ROOT / "Collaboration_tools" / "conversations.json"
    if not path.exists():
        return
    data = json.loads(path.read_text())
    items = data if isinstance(data, list) else list(data.values())
    for i, item in enumerate(items):
        if limit and i >= limit:
            break
        text = json.dumps(item, ensure_ascii=False)[:4000]
        cid = str(item.get("id") or item.get("conversation_id") or i)
        yield _chunk_id("chat", cid), f"chat_message:{cid}", "chat_message", text


LOADERS = {
    "emails": load_emails,
    "employees": load_employees,
    "support": load_customer_support,
    "sales": load_sales,
    "chat": load_collaboration,
}


# --------------------------------------------------------------------------- #
# Gemini extraction                                                           #
# --------------------------------------------------------------------------- #

EXTRACTION_PROMPT = """You extract a typed knowledge graph from a single enterprise text chunk.

Return entities and facts strictly following the schema. Rules:
- canonical_name: the person/customer/product/etc. name as it should appear in a directory.
- aliases: alternate spellings or short forms seen in the text.
- attributes: only what the text supports (e.g. for a person: email, title, department; for a customer: industry, location). Don't invent values.
- Fact subject must reference an entity emitted in this same response (use the same id you assigned).
- Fact predicate is a snake_case verb-phrase like "reports_to", "account_manager_of", "renewal_date", "located_in", "title", "department".
- object_type=entity when object is another entity id; otherwise string/date/number/bool.
- confidence in [0,1]: 1.0 only if explicitly stated, 0.7-0.9 if strongly implied, 0.5 if speculative.
- Skip facts you would have to invent. Empty arrays are fine.

Use entity ids of the form "{type}:{slug}" where slug is lowercase-hyphenated canonical_name.

The source_type of the input is provided so you can pick reasonable predicates."""


def build_client() -> genai.Client:
    if not settings.gemini_api_key:
        raise SystemExit(
            "GEMINI_API_KEY is empty. Copy server/.env.example to server/.env and set it."
        )
    return genai.Client(api_key=settings.gemini_api_key)


async def extract(
    client: genai.Client,
    model: str,
    source_type: str,
    text: str,
) -> ExtractionResult | None:
    """Call Gemini with structured output. Returns None on failure."""
    try:
        resp = await asyncio.to_thread(
            client.models.generate_content,
            model=model,
            contents=[
                f"source_type: {source_type}\n\n----\n{text}",
            ],
            config=genai_types.GenerateContentConfig(
                system_instruction=EXTRACTION_PROMPT,
                response_mime_type="application/json",
                response_schema=_RESPONSE_SCHEMA,
                temperature=0.2,
            ),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  ! gemini error: {exc}", file=sys.stderr)
        return None

    raw = resp.text
    if not raw:
        return None
    try:
        return ExtractionResult.model_validate_json(raw)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! parse error: {exc}", file=sys.stderr)
        return None


# --------------------------------------------------------------------------- #
# Driver                                                                      #
# --------------------------------------------------------------------------- #


def load_seen(out_path: Path) -> set[str]:
    if not out_path.exists():
        return set()
    seen = set()
    for line in out_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            seen.add(json.loads(line)["chunk_id"])
        except Exception:  # noqa: BLE001
            continue
    return seen


def gather_chunks(domains: list[str], per_domain: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    for d in domains:
        loader = LOADERS.get(d)
        if not loader:
            print(f"  ! unknown domain: {d}", file=sys.stderr)
            continue
        chunks.extend(loader(limit=per_domain))
    return chunks


async def run(args: argparse.Namespace) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    seen = load_seen(OUTPUT_PATH)
    domains = args.domains.split(",")
    per_domain = max(1, args.target // len(domains)) + 5  # small buffer for skips
    chunks = gather_chunks(domains, per_domain)
    todo = [c for c in chunks if c[0] not in seen][: args.target]

    print(f"chunks total={len(chunks)} already_done={len(seen) & {c[0] for c in chunks}.__len__()} todo={len(todo)}")
    if not todo:
        print("nothing to do.")
        return

    if args.dry_run:
        for c in todo[:5]:
            print(f"  - {c[0]}  ({c[2]})  {c[3][:120]!r}")
        print(f"... and {max(0, len(todo) - 5)} more (dry run; no calls made)")
        return

    client = build_client()
    sem = asyncio.Semaphore(args.concurrency)
    written = 0
    failed = 0
    lock = asyncio.Lock()

    async def worker(chunk: Chunk) -> None:
        nonlocal written, failed
        chunk_id, src_id, src_type, text = chunk
        async with sem:
            result = await extract(client, args.model, src_type, text)
        if result is None:
            failed += 1
            return
        pair = TrainingPair(
            source_record_id=src_id,
            chunk_id=chunk_id,
            text=text,
            output=result,
        )
        async with lock:
            with OUTPUT_PATH.open("a") as f:
                f.write(pair.model_dump_json() + "\n")
            written += 1
            if written % 10 == 0:
                print(f"  written={written} failed={failed} ({written + failed}/{len(todo)})")

    await asyncio.gather(*(worker(c) for c in todo))
    print(f"done. written={written} failed={failed} → {OUTPUT_PATH}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--target", type=int, default=300, help="Total pairs to produce.")
    p.add_argument(
        "--domains",
        default="emails,employees,support,sales,chat",
        help="Comma-separated subset of: emails,employees,support,sales,chat",
    )
    p.add_argument("--model", default=settings.gemini_model)
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--dry-run", action="store_true", help="Print samples, no API calls.")
    args = p.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
