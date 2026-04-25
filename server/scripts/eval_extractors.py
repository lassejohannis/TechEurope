"""Proper extractor benchmark with a fresh holdout + per-type P/R/F1.

Stages
------
1. `--build-gold`  → samples N fresh chunks from EnterpriseBench (chunk_ids
   that are NOT already in pioneer_training.jsonl, so no leakage), labels
   each with Gemini 2.5 Pro, writes data/training/eval_holdout.jsonl.
   Slow (Gemini Pro is rate-limited); run once.

2. (default)        → reads eval_holdout.jsonl, runs v1 + v3 + Gemini-Flash-Lite
   over each chunk, computes precision/recall/F1 per entity type AND per
   predicate. Matches by (type, canonical_name normalized) — lenient enough
   to allow GLiNER2's "Ravi" vs Gemini's "Ravi Kumar" to count when the
   text only uses the short form.

   Writes data/training/eval_v2.json + prints a summary table.

Usage
-----
    # one-time gold labelling
    uv run python scripts/eval_extractors.py --build-gold --n 30 --gold-model gemini-2.5-pro

    # benchmark all models over the gold set (re-runnable, no Gemini-Pro calls)
    uv run python scripts/eval_extractors.py
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # so we can import gen_pioneer_training

from google import genai  # noqa: E402
from google.genai import types as genai_types  # noqa: E402

from server.config import settings  # noqa: E402
from server.extractors import gemini as gemini_extractor  # noqa: E402
from server.extractors.gemini import _RESPONSE_SCHEMA  # noqa: E402
from server.extractors.pioneer import _call_pioneer  # noqa: E402
from server.extractors.prompt import EXTRACTION_PROMPT  # noqa: E402
from server.extractors.schemas import ExtractionResult, TrainingPair  # noqa: E402

# Reuse the chunk loaders from the training-pair generator. They yield
# (chunk_id, source_record_id, source_type, text).
from gen_pioneer_training import LOADERS  # noqa: E402

TRAINING_PATH = ROOT.parent / "data" / "training" / "pioneer_training.jsonl"
GOLD_PATH = ROOT.parent / "data" / "training" / "eval_holdout.jsonl"
OUTPUT_PATH = ROOT.parent / "data" / "training" / "eval_v2.json"


# --------------------------------------------------------------------------- #
# Stage 1: build gold                                                         #
# --------------------------------------------------------------------------- #


def _taken_chunk_ids() -> set[str]:
    if not TRAINING_PATH.exists():
        return set()
    return {
        json.loads(line)["chunk_id"]
        for line in TRAINING_PATH.read_text().splitlines()
        if line.strip()
    }


def sample_fresh_chunks(n: int, taken: set[str], domains: list[str], seed: int = 42) -> list[tuple]:
    """Round-robin across domains, skipping anything already in training."""
    rng = random.Random(seed)
    pool: dict[str, list[tuple]] = {}
    for d in domains:
        loader = LOADERS.get(d)
        if not loader:
            continue
        # Pull every chunk the loader can yield (no limit) so we can pick from later indices.
        candidates = [c for c in loader(limit=None) if c[0] not in taken]
        rng.shuffle(candidates)
        pool[d] = candidates

    out: list[tuple] = []
    per = n // max(1, len(pool)) + 1
    for d, candidates in pool.items():
        out.extend(candidates[:per])
    rng.shuffle(out)
    return out[:n]


def label_with_gemini_pro(client: genai.Client, model: str, source_type: str, text: str) -> ExtractionResult:
    resp = client.models.generate_content(
        model=model,
        contents=[f"source_type: {source_type}\n\n----\n{text}"],
        config=genai_types.GenerateContentConfig(
            system_instruction=EXTRACTION_PROMPT,
            response_mime_type="application/json",
            response_schema=_RESPONSE_SCHEMA,
            temperature=0.1,
        ),
    )
    if not resp.text:
        return ExtractionResult(entities=[], facts=[])
    return ExtractionResult.model_validate_json(resp.text)


def build_gold(args: argparse.Namespace) -> None:
    taken = _taken_chunk_ids()
    domains = args.domains.split(",")
    chunks = sample_fresh_chunks(args.n, taken, domains, seed=args.seed)
    print(f"sampled {len(chunks)} fresh chunks (skipped {len(taken)} taken)\n")

    if not settings.gemini_api_key:
        sys.exit("GEMINI_API_KEY missing — cannot label gold.")
    client = genai.Client(api_key=settings.gemini_api_key)

    GOLD_PATH.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    failed = 0
    with GOLD_PATH.open("w") as f:
        for i, (chunk_id, source_record_id, source_type, text) in enumerate(chunks):
            try:
                gold = label_with_gemini_pro(client, args.gold_model, source_type, text)
            except Exception as exc:  # noqa: BLE001
                # Most likely 429 — Pro tier is tight; pause and retry once.
                print(f"  [{i + 1}/{len(chunks)}] err: {str(exc)[:80]}; sleeping 30s and retrying...")
                time.sleep(30)
                try:
                    gold = label_with_gemini_pro(client, args.gold_model, source_type, text)
                except Exception as exc2:  # noqa: BLE001
                    print(f"  [{i + 1}/{len(chunks)}] FINAL FAIL: {str(exc2)[:80]}")
                    failed += 1
                    continue
            row = TrainingPair(
                source_record_id=source_record_id,
                chunk_id=chunk_id,
                text=text,
                output=gold,
            )
            f.write(row.model_dump_json() + "\n")
            written += 1
            print(f"  [{i + 1}/{len(chunks)}] {chunk_id} → {len(gold.entities)}E/{len(gold.facts)}F")
            if args.delay > 0:
                time.sleep(args.delay)

    print(f"\nwrote {GOLD_PATH}  written={written} failed={failed}")


# --------------------------------------------------------------------------- #
# Stage 2: benchmark                                                          #
# --------------------------------------------------------------------------- #


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def _entity_keys(result: ExtractionResult) -> set[tuple[str, str]]:
    """Match entities by (type, normalized canonical_name)."""
    return {(e.type, _norm(e.canonical_name)) for e in result.entities}


def _entity_keys_by_type(result: ExtractionResult) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for e in result.entities:
        out[e.type].add(_norm(e.canonical_name))
    return out


def _predicate_keys(result: ExtractionResult) -> set[tuple[str, str, str]]:
    """Match facts by (subject_type, predicate, object_norm).

    Reads subject_type from the entity id prefix; object_norm is the
    object id stripped to its slug, or the literal value normalized.
    """
    type_by_id = {e.id: e.type for e in result.entities}
    keys: set[tuple[str, str, str]] = set()
    for f in result.facts:
        subj_type = type_by_id.get(f.subject) or f.subject.split(":", 1)[0]
        if f.object_type == "entity":
            obj_id = str(f.object)
            obj_key = obj_id.split(":", 1)[-1]
        else:
            obj_key = _norm(str(f.object))
        keys.add((subj_type, f.predicate, obj_key))
    return keys


def _predicate_keys_by_type(result: ExtractionResult) -> dict[str, set]:
    """Group keys by predicate string for per-predicate metrics."""
    out: dict[str, set] = defaultdict(set)
    for k in _predicate_keys(result):
        _subj_type, predicate, _ = k
        out[predicate].add(k)
    return out


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def evaluate_one(gold: ExtractionResult, pred: ExtractionResult) -> dict:
    g_ent = _entity_keys(gold)
    p_ent = _entity_keys(pred)
    e_tp = len(g_ent & p_ent)
    e_fp = len(p_ent - g_ent)
    e_fn = len(g_ent - p_ent)
    e_p, e_r, e_f1 = prf(e_tp, e_fp, e_fn)

    g_pred = _predicate_keys(gold)
    p_pred = _predicate_keys(pred)
    p_tp = len(g_pred & p_pred)
    p_fp = len(p_pred - g_pred)
    p_fn = len(g_pred - p_pred)
    p_p, p_r, p_f1 = prf(p_tp, p_fp, p_fn)

    # Per-entity-type breakdown
    g_by_type = _entity_keys_by_type(gold)
    p_by_type = _entity_keys_by_type(pred)
    per_type: dict[str, dict] = {}
    for t in set(g_by_type) | set(p_by_type):
        tp = len(g_by_type[t] & p_by_type[t])
        fp = len(p_by_type[t] - g_by_type[t])
        fn = len(g_by_type[t] - p_by_type[t])
        per_type[t] = {"tp": tp, "fp": fp, "fn": fn}

    # Per-predicate breakdown
    g_by_pred = _predicate_keys_by_type(gold)
    p_by_pred = _predicate_keys_by_type(pred)
    per_pred: dict[str, dict] = {}
    for pr in set(g_by_pred) | set(p_by_pred):
        tp = len(g_by_pred[pr] & p_by_pred[pr])
        fp = len(p_by_pred[pr] - g_by_pred[pr])
        fn = len(g_by_pred[pr] - p_by_pred[pr])
        per_pred[pr] = {"tp": tp, "fp": fp, "fn": fn}

    return {
        "entity": {"tp": e_tp, "fp": e_fp, "fn": e_fn, "p": e_p, "r": e_r, "f1": e_f1},
        "predicate": {"tp": p_tp, "fp": p_fp, "fn": p_fn, "p": p_p, "r": p_r, "f1": p_f1},
        "per_type": per_type,
        "per_predicate": per_pred,
    }


def aggregate(per_chunk: list[dict], key: str) -> dict:
    """Sum TP/FP/FN over chunks, then compute micro P/R/F1."""
    tp = sum(c[key]["tp"] for c in per_chunk)
    fp = sum(c[key]["fp"] for c in per_chunk)
    fn = sum(c[key]["fn"] for c in per_chunk)
    p, r, f1 = prf(tp, fp, fn)
    return {"tp": tp, "fp": fp, "fn": fn, "p": p, "r": r, "f1": f1}


def aggregate_per_type(per_chunk: list[dict], key: str = "per_type") -> dict[str, dict]:
    sums: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    for c in per_chunk:
        for t, counts in c[key].items():
            for k in counts:
                sums[t][k] += counts[k]
    out: dict[str, dict] = {}
    for t, s in sums.items():
        p, r, f1 = prf(s["tp"], s["fp"], s["fn"])
        out[t] = {**s, "p": p, "r": r, "f1": f1}
    return out


def benchmark(args: argparse.Namespace) -> None:
    if not GOLD_PATH.exists():
        sys.exit(f"No gold set at {GOLD_PATH}. Run --build-gold first.")
    gold_rows = [json.loads(l) for l in GOLD_PATH.read_text().splitlines() if l.strip()]
    print(f"gold chunks: {len(gold_rows)}\n")

    pioneer_versions = dict(spec.split("=", 1) for spec in args.pioneer.split(","))
    use_gemini = args.gemini_model and settings.gemini_api_key

    runs: dict[str, list[dict]] = {name: [] for name in pioneer_versions}
    if use_gemini:
        runs[f"gemini:{args.gemini_model}"] = []

    for i, row in enumerate(gold_rows):
        text = row["text"]
        gold = ExtractionResult.model_validate(row["output"])
        msg = f"  [{i + 1}/{len(gold_rows)}]"

        for name, uuid in pioneer_versions.items():
            try:
                pred = _call_pioneer(uuid, text)
                metrics = evaluate_one(gold, pred)
                runs[name].append(metrics)
                msg += f"  {name}=eF1:{metrics['entity']['f1']:.2f}"
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {name} err: {str(exc)[:60]}")
                runs[name].append({
                    "entity": {"tp": 0, "fp": 0, "fn": len({(e.type, _norm(e.canonical_name)) for e in gold.entities}), "p": 0.0, "r": 0.0, "f1": 0.0},
                    "predicate": {"tp": 0, "fp": 0, "fn": 0, "p": 0.0, "r": 0.0, "f1": 0.0},
                    "per_type": {},
                    "per_predicate": {},
                })

        if use_gemini:
            name = f"gemini:{args.gemini_model}"
            try:
                pred = gemini_extractor.extract(text, source_type="unknown", model=args.gemini_model)
                metrics = evaluate_one(gold, pred)
                runs[name].append(metrics)
                msg += f"  flash=eF1:{metrics['entity']['f1']:.2f}"
            except Exception as exc:  # noqa: BLE001
                print(f"  ! gemini err: {str(exc)[:60]}")
                runs[name].append({
                    "entity": {"tp": 0, "fp": 0, "fn": 0, "p": 0.0, "r": 0.0, "f1": 0.0},
                    "predicate": {"tp": 0, "fp": 0, "fn": 0, "p": 0.0, "r": 0.0, "f1": 0.0},
                    "per_type": {},
                    "per_predicate": {},
                })
            if args.delay > 0:
                time.sleep(args.delay)

        print(msg)

    # Summaries
    summary = {}
    for name, per_chunk in runs.items():
        if not per_chunk:
            continue
        summary[name] = {
            "entity_micro": aggregate(per_chunk, "entity"),
            "predicate_micro": aggregate(per_chunk, "predicate"),
            "per_type": aggregate_per_type(per_chunk, "per_type"),
            "per_predicate": aggregate_per_type(per_chunk, "per_predicate"),
        }

    print("\n========== Entity micro-F1 (case-insensitive canonical_name match) ==========")
    print(f"{'model':<40} {'TP':>5} {'FP':>5} {'FN':>5} {'P':>7} {'R':>7} {'F1':>7}")
    for name, s in summary.items():
        e = s["entity_micro"]
        print(f"{name:<40} {e['tp']:>5} {e['fp']:>5} {e['fn']:>5} {e['p']:>7.1%} {e['r']:>7.1%} {e['f1']:>7.1%}")

    print("\n========== Predicate micro-F1 (subject_type, predicate, object) ==========")
    print(f"{'model':<40} {'TP':>5} {'FP':>5} {'FN':>5} {'P':>7} {'R':>7} {'F1':>7}")
    for name, s in summary.items():
        e = s["predicate_micro"]
        print(f"{name:<40} {e['tp']:>5} {e['fp']:>5} {e['fn']:>5} {e['p']:>7.1%} {e['r']:>7.1%} {e['f1']:>7.1%}")

    print("\n========== Per-entity-type F1 (best model only) ==========")
    best = max(summary, key=lambda n: summary[n]["entity_micro"]["f1"])
    print(f"  showing: {best}")
    print(f"  {'type':<14} {'TP':>4} {'FP':>4} {'FN':>4} {'P':>7} {'R':>7} {'F1':>7}")
    for t, s in sorted(summary[best]["per_type"].items(), key=lambda kv: -kv[1]["tp"] - kv[1]["fn"]):
        print(f"  {t:<14} {s['tp']:>4} {s['fp']:>4} {s['fn']:>4} {s['p']:>7.1%} {s['r']:>7.1%} {s['f1']:>7.1%}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps({"summary": summary, "n_chunks": len(gold_rows)}, indent=2))
    print(f"\nwrote {OUTPUT_PATH}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build-gold", action="store_true")
    p.add_argument("--n", type=int, default=30)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--domains",
        default="emails,employees,support,sales,chat",
        help="Comma-separated subset of: emails,employees,support,sales,chat",
    )
    p.add_argument("--gold-model", default="gemini-2.5-pro")
    p.add_argument("--gemini-model", default="gemini-2.5-flash-lite",
                   help="Production-side Gemini for the comparison column. Empty to skip.")
    p.add_argument(
        "--pioneer",
        default="v1=d79f2191-9bcd-46b0-9d78-b13aacc1f1d8,v3=6f7451f9-cfac-48e8-b5e6-0bb970a8b45b",
        help="Comma-separated name=uuid pairs for Pioneer model versions.",
    )
    p.add_argument("--delay", type=float, default=4.0)
    args = p.parse_args()

    if args.build_gold:
        build_gold(args)
    else:
        benchmark(args)


if __name__ == "__main__":
    main()
