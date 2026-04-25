"""Convert our SourceRecord/Entity/Fact JSONL into Pioneer's NER format.

Pioneer's training endpoint wants:
    {"text": "...", "entities": [["span", "label"], ["span", "label"], ...]}

…not the GLiNER2 multi-task format we used previously. The fine-tuned
v1/v2/v3 likely under-performed because Pioneer's NER trainer half-rejected
that schema.

Reads:  data/training/pioneer_training.jsonl  (304 Gemini-labelled chunks)
Writes: data/training/pioneer_ner_v4.jsonl    (Pioneer NER format)

Per chunk: walks each canonical entity name (and aliases), finds every span
in the text, emits one [span, label] tuple per occurrence. Pioneer's GLiNER2
trains on character-span supervision, so each occurrence helps.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from server.extractors.schemas import TrainingPair  # noqa: E402

INPUT_PATH = ROOT.parent / "data" / "training" / "pioneer_training.jsonl"
OUTPUT_PATH = ROOT.parent / "data" / "training" / "pioneer_ner_v4.jsonl"
HOLDOUT_PATH = ROOT.parent / "data" / "training" / "pioneer_ner_v4_holdout.jsonl"


def find_spans(text: str, needle: str) -> list[int]:
    """Return all start indices where needle occurs (case-insensitive)."""
    if not needle:
        return []
    text_lower = text.lower()
    needle_lower = needle.lower()
    out: list[int] = []
    i = 0
    while True:
        idx = text_lower.find(needle_lower, i)
        if idx == -1:
            return out
        out.append(idx)
        i = idx + 1


def convert_pair(pair: TrainingPair) -> dict | None:
    """Build the Pioneer-NER row for one TrainingPair.

    For each entity, collect all surface forms (canonical_name + aliases),
    locate every occurrence in the text, emit one [span_text, type] per match.
    Skip entities with no occurrence (Gemini sometimes hallucinates names).
    """
    text = pair.text
    seen: set[tuple[int, int]] = set()  # (start, end) ranges already claimed
    entries: list[tuple[int, int, str, str]] = []

    for ent in pair.output.entities:
        surface_forms = [ent.canonical_name, *ent.aliases]
        for surface in surface_forms:
            if not surface or len(surface) < 2:
                continue
            for start in find_spans(text, surface):
                end = start + len(surface)
                # Skip if any overlap with an existing claim (longest-first wins).
                if any(not (end <= s or start >= e) for s, e in seen):
                    continue
                seen.add((start, end))
                # Pioneer's tuple uses the *exact* span as it appears in text.
                entries.append((start, end, text[start:end], ent.type))

    if not entries:
        return None

    # Pioneer's docs use [span_text, label] without offsets — sort by start so
    # the resulting list is reading-order-stable (helpful when reviewing).
    entries.sort()
    return {
        "text": text,
        "entities": [[e[2], e[3]] for e in entries],
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", default=str(INPUT_PATH))
    p.add_argument("--holdout", type=int, default=20, help="Reserve N rows for eval")
    args = p.parse_args()

    rows_in = [
        json.loads(line)
        for line in Path(args.input).read_text().splitlines()
        if line.strip()
    ]
    converted: list[dict] = []
    skipped = 0
    for r in rows_in:
        pair = TrainingPair.model_validate(r)
        out_row = convert_pair(pair)
        if out_row is None:
            skipped += 1
            continue
        converted.append(out_row)

    train = converted[: -args.holdout] if args.holdout else converted
    holdout = converted[-args.holdout :] if args.holdout else []

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w") as f:
        for r in train:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    if holdout:
        with HOLDOUT_PATH.open("w") as f:
            for r in holdout:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Stats
    from collections import Counter

    type_counts: Counter[str] = Counter()
    span_per_row: list[int] = []
    for r in converted:
        span_per_row.append(len(r["entities"]))
        for _, label in r["entities"]:
            type_counts[label] += 1

    print(f"input:    {len(rows_in)} rows")
    print(f"skipped:  {skipped} (no entity matched in text — Gemini hallucinations)")
    print(f"output:   {len(train)} train, {len(holdout)} holdout")
    print(f"avg spans/row: {sum(span_per_row) / max(1, len(span_per_row)):.1f}")
    print()
    print("entity-mention counts:")
    for t, n in type_counts.most_common():
        print(f"  {t:<14} {n}")
    print(f"\nwrote {OUTPUT_PATH}")
    if holdout:
        print(f"wrote {HOLDOUT_PATH}")


if __name__ == "__main__":
    main()
