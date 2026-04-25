"""Run two (or more) Pioneer fine-tune versions over the same holdout chunks.

Reuses the last 10 rows of pioneer_training.jsonl as fixtures, calls each
model UUID, writes data/training/pioneer_versions.json and prints a
comparison summary.

Usage:
    uv run python scripts/compare_pioneer_versions.py \
        v1=d79f2191-9bcd-46b0-9d78-b13aacc1f1d8 \
        v3=6f7451f9-cfac-48e8-b5e6-0bb970a8b45b
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from server.config import settings  # noqa: E402
from server.extractors.pioneer import (  # noqa: E402
    ENTITY_TYPES,
    PIONEER_ENDPOINT,
    RELATION_TYPES,
    _parse_response,
)
from server.extractors.schemas import ExtractionResult  # noqa: E402

TRAINING_PATH = ROOT.parent / "data" / "training" / "pioneer_training.jsonl"
OUTPUT_PATH = ROOT.parent / "data" / "training" / "pioneer_versions.json"


def parse_versions(args: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for a in args:
        if "=" not in a:
            sys.exit(f"bad arg {a!r}, expected name=uuid")
        name, uuid = a.split("=", 1)
        out[name] = uuid
    if not out:
        sys.exit("at least one name=uuid required")
    return out


def call_pioneer(model_uuid: str, text: str) -> tuple[ExtractionResult | None, int, str | None]:
    body = {
        "model": model_uuid,
        "messages": [{"role": "user", "content": text}],
        "schema": {"entities": ENTITY_TYPES, "relations": RELATION_TYPES},
        "include_confidence": True,
        "include_spans": True,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.pioneer_api_key}",
    }
    t0 = time.perf_counter()
    try:
        resp = httpx.post(PIONEER_ENDPOINT, headers=headers, json=body, timeout=30.0)
        resp.raise_for_status()
        result = _parse_response(resp.json())
        ms = round((time.perf_counter() - t0) * 1000)
        return result, ms, None
    except Exception as exc:  # noqa: BLE001
        ms = round((time.perf_counter() - t0) * 1000)
        return None, ms, str(exc)


def diff_against_gold(gold: ExtractionResult, pred: ExtractionResult) -> dict:
    g_ents = {e.id for e in gold.entities}
    p_ents = {e.id for e in pred.entities}
    g_pred = {(f.subject, f.predicate) for f in gold.facts}
    p_pred = {(f.subject, f.predicate) for f in pred.facts}
    return {
        "shared_entities": len(g_ents & p_ents),
        "gold_entity_recall": round(len(g_ents & p_ents) / max(1, len(g_ents)), 3),
        "shared_predicates": len(g_pred & p_pred),
        "extra_entities": len(p_ents - g_ents),
    }


def main() -> None:
    versions = parse_versions(sys.argv[1:])
    fixtures = [json.loads(l) for l in TRAINING_PATH.read_text().splitlines()[-10:]]
    print(f"versions: {list(versions.keys())}  ·  fixtures: {len(fixtures)}\n")

    rows: list[dict] = []
    summary = {name: {"latency_ms": [], "entities": 0, "facts": 0, "errors": 0,
                      "shared_entities": 0, "shared_predicates": 0,
                      "gold_entities_total": 0, "gold_predicates_total": 0}
               for name in versions}

    for i, fx in enumerate(fixtures):
        text = fx["text"]
        gold = ExtractionResult.model_validate(fx["output"])
        row = {"chunk_id": fx["chunk_id"], "text_preview": text[:160]}
        msg = f"  [{i + 1}/{len(fixtures)}]"

        for name, uuid in versions.items():
            pred, ms, err = call_pioneer(uuid, text)
            s = summary[name]
            s["latency_ms"].append(ms)
            if pred is None:
                s["errors"] += 1
                row[name] = {"error": err, "latency_ms": ms}
                msg += f"  {name}=ERR({ms}ms)"
                continue
            d = diff_against_gold(gold, pred)
            s["entities"] += len(pred.entities)
            s["facts"] += len(pred.facts)
            s["shared_entities"] += d["shared_entities"]
            s["shared_predicates"] += d["shared_predicates"]
            s["gold_entities_total"] += len({e.id for e in gold.entities})
            s["gold_predicates_total"] += len({(f.subject, f.predicate) for f in gold.facts})
            row[name] = {
                "entities": len(pred.entities),
                "facts": len(pred.facts),
                "latency_ms": ms,
                "shared_entities": d["shared_entities"],
                "shared_predicates": d["shared_predicates"],
                "extra_entities": d["extra_entities"],
            }
            msg += f"  {name}: {len(pred.entities)}E/{len(pred.facts)}F ({ms}ms)"

        print(msg)
        rows.append(row)

    print("\n--- summary ---")
    print(f"{'metric':<26} " + " ".join(f"{n:>14}" for n in versions))
    print(f"{'errors':<26} " + " ".join(f"{summary[n]['errors']:>14d}" for n in versions))
    print(f"{'avg latency (ms)':<26} " + " ".join(
        f"{round(sum(summary[n]['latency_ms']) / max(1, len(summary[n]['latency_ms']))):>14d}" for n in versions
    ))
    print(f"{'entities total':<26} " + " ".join(f"{summary[n]['entities']:>14d}" for n in versions))
    print(f"{'facts total':<26} " + " ".join(f"{summary[n]['facts']:>14d}" for n in versions))
    print(f"{'gold-entity recall':<26} " + " ".join(
        f"{summary[n]['shared_entities'] / max(1, summary[n]['gold_entities_total']):>14.1%}" for n in versions
    ))
    print(f"{'gold-predicate match':<26} " + " ".join(
        f"{summary[n]['shared_predicates'] / max(1, summary[n]['gold_predicates_total']):>14.1%}" for n in versions
    ))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps({"versions": versions, "rows": rows, "summary": summary}, indent=2))
    print(f"\nwrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
