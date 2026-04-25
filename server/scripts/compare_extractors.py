"""Pioneer vs. Gemini comparison eval (WS-3, Task 5).

Runs both extractors on a held-out fixture set, writes per-chunk diffs to
data/training/comparison.json. Frontend renders this in WS-6.

Until the Pioneer fine-tune lands (see docs/ws3-pioneer-finetune.md),
the pioneer column is reported as unavailable — comparison still produces
the Gemini-side baseline so the harness is testable today.

Usage:
    uv run python server/scripts/compare_extractors.py
    uv run python server/scripts/compare_extractors.py --fixtures path/to/fixtures.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from server.extractors import gemini as gemini_extractor  # noqa: E402
from server.extractors import pioneer as pioneer_extractor  # noqa: E402
from server.extractors.schemas import ExtractionResult  # noqa: E402

DEFAULT_FIXTURES = ROOT.parent / "data" / "training" / "fixtures.jsonl"
TRAINING_PATH = ROOT.parent / "data" / "training" / "pioneer_training.jsonl"
OUTPUT_PATH = ROOT.parent / "data" / "training" / "comparison.json"


def build_fixtures(n: int = 10) -> list[dict]:
    """Hold the last `n` rows of pioneer_training.jsonl out for eval.

    Quick-and-dirty: the held-out rows must NOT be re-fed to the fine-tune.
    Reserve the trailing slice in your training run instead.
    """
    if not TRAINING_PATH.exists():
        raise SystemExit(
            f"No training file at {TRAINING_PATH}. Run gen_pioneer_training.py first."
        )
    rows = TRAINING_PATH.read_text().splitlines()
    return [json.loads(r) for r in rows[-n:]]


def diff_result(a: ExtractionResult, b: ExtractionResult) -> dict:
    a_ents = {e.id for e in a.entities}
    b_ents = {e.id for e in b.entities}
    a_predicates = {(f.subject, f.predicate) for f in a.facts}
    b_predicates = {(f.subject, f.predicate) for f in b.facts}
    return {
        "entities_only_in_a": sorted(a_ents - b_ents),
        "entities_only_in_b": sorted(b_ents - a_ents),
        "shared_entities": len(a_ents & b_ents),
        "predicates_only_in_a": [list(p) for p in sorted(a_predicates - b_predicates)],
        "predicates_only_in_b": [list(p) for p in sorted(b_predicates - a_predicates)],
        "shared_predicates": len(a_predicates & b_predicates),
    }


def run(args: argparse.Namespace) -> None:
    if args.fixtures:
        fixtures = [json.loads(line) for line in Path(args.fixtures).read_text().splitlines()]
    else:
        fixtures = build_fixtures(n=args.n)

    rows: list[dict] = []
    for i, fx in enumerate(fixtures):
        text = fx["text"]
        src_type = fx.get("source_record_id", "").split(":", 1)[0] or "unknown"
        gold = ExtractionResult.model_validate(fx["output"])

        t0 = time.perf_counter()
        try:
            gem = gemini_extractor.extract(text, source_type=src_type)
            gem_err = None
        except Exception as exc:  # noqa: BLE001
            gem = ExtractionResult(entities=[], facts=[])
            gem_err = str(exc)
        gem_ms = round((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        try:
            pio = pioneer_extractor.extract(text, source_type=src_type)
            pio_err = None
        except Exception as exc:  # noqa: BLE001
            pio = None
            pio_err = str(exc)
        pio_ms = round((time.perf_counter() - t0) * 1000)

        rows.append(
            {
                "chunk_id": fx.get("chunk_id"),
                "source_record_id": fx.get("source_record_id"),
                "text_preview": text[:240],
                "gemini": {
                    "entities": [e.model_dump() for e in gem.entities],
                    "facts": [f.model_dump() for f in gem.facts],
                    "latency_ms": gem_ms,
                    "error": gem_err,
                    "vs_gold": diff_result(gold, gem),
                },
                "pioneer": (
                    None
                    if pio is None
                    else {
                        "entities": [e.model_dump() for e in pio.entities],
                        "facts": [f.model_dump() for f in pio.facts],
                        "latency_ms": pio_ms,
                        "error": pio_err,
                        "vs_gold": diff_result(gold, pio),
                    }
                ),
                "pioneer_available": pioneer_extractor.AVAILABLE,
            }
        )
        print(f"  [{i + 1}/{len(fixtures)}] gemini={gem_ms}ms pioneer={'-' if pio is None else f'{pio_ms}ms'}")

    summary = {
        "n": len(rows),
        "pioneer_available": pioneer_extractor.AVAILABLE,
        "gemini_avg_ms": round(sum(r["gemini"]["latency_ms"] for r in rows) / max(1, len(rows))),
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2, default=str))
    print(f"wrote {OUTPUT_PATH}  ({summary})")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fixtures", help="JSONL of held-out fixtures (default: tail of training file).")
    p.add_argument("--n", type=int, default=10, help="Number of fixtures when auto-selecting.")
    args = p.parse_args()
    run(args)


if __name__ == "__main__":
    main()
