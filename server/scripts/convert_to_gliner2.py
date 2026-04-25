"""Convert our SourceRecord/Entity/Fact JSONL into GLiNER2 training format.

Our extraction pipeline emits typed entities + facts per the data-model.md spec.
GLiNER2 expects: entities grouped by type (list of strings), relations as
{predicate: {head, tail}}.

This script reads data/training/pioneer_training.jsonl and writes
data/training/gliner2_training.jsonl, ready to upload to Pioneer.

Usage:
    uv --directory server run python scripts/convert_to_gliner2.py
    uv --directory server run python scripts/convert_to_gliner2.py --holdout 10
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from server.extractors.schemas import ExtractionResult, TrainingPair  # noqa: E402

INPUT_PATH = ROOT.parent / "data" / "training" / "pioneer_training.jsonl"
OUTPUT_PATH = ROOT.parent / "data" / "training" / "gliner2_training.jsonl"
HOLDOUT_PATH = ROOT.parent / "data" / "training" / "gliner2_holdout.jsonl"

# Plain-English descriptions for each entity type. Pioneer/GLiNER2 use these
# to bootstrap the schema; better descriptions = better fine-tune.
ENTITY_DESCRIPTIONS: dict[str, str] = {
    "person": "Full name of an employee, customer contact, or other individual",
    "customer": "External customer organization or company",
    "product": "Product, service, or offering",
    "org_unit": "Internal department, team, or organizational unit",
    "process": "Business process, workflow, or procedure",
    "policy": "Company policy, rule, or guideline",
    "project": "Internal project, initiative, or program",
    "task": "Specific task, action item, or assignment",
    "ticket": "Support ticket, incident, or service request",
    "vendor": "External supplier or vendor organization",
    "repo": "Software repository or codebase",
}


def convert_pair(pair: TrainingPair) -> dict | None:
    """One TrainingPair → one GLiNER2 JSONL row. Returns None if empty."""
    out: ExtractionResult = pair.output

    # Build entities-by-type using canonical_name (drop ids; GLiNER2 wants strings).
    by_type: dict[str, set[str]] = defaultdict(set)
    id_to_name: dict[str, str] = {}
    for ent in out.entities:
        by_type[ent.type].add(ent.canonical_name)
        id_to_name[ent.id] = ent.canonical_name

    entities = {t: sorted(names) for t, names in by_type.items() if names}
    descriptions = {t: ENTITY_DESCRIPTIONS.get(t, t.replace("_", " ")) for t in entities}

    # Relations: only facts where object_type == "entity" and both sides resolve.
    relations: list[dict] = []
    for fact in out.facts:
        if fact.object_type != "entity":
            continue
        head = id_to_name.get(fact.subject)
        tail = id_to_name.get(str(fact.object))
        if head and tail:
            relations.append({fact.predicate: {"head": head, "tail": tail}})

    # Skip empty rows — GLiNER2 won't learn from a chunk with no entities.
    if not entities:
        return None

    row: dict = {
        "input": pair.text,
        "output": {
            "entities": entities,
            "entity_descriptions": descriptions,
        },
    }
    if relations:
        row["output"]["relations"] = relations
    return row


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--holdout",
        type=int,
        default=10,
        help="Reserve the last N rows as eval holdout (written to gliner2_holdout.jsonl).",
    )
    p.add_argument("--input", default=str(INPUT_PATH))
    args = p.parse_args()

    rows_in = [json.loads(line) for line in Path(args.input).read_text().splitlines() if line.strip()]
    converted = []
    for row in rows_in:
        pair = TrainingPair.model_validate(row)
        out_row = convert_pair(pair)
        if out_row:
            converted.append(out_row)

    skipped = len(rows_in) - len(converted)
    holdout = converted[-args.holdout :] if args.holdout else []
    train = converted[: -args.holdout] if args.holdout else converted

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w") as f:
        for r in train:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    if holdout:
        with HOLDOUT_PATH.open("w") as f:
            for r in holdout:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Quick stats
    type_counts: dict[str, int] = defaultdict(int)
    rel_counts: dict[str, int] = defaultdict(int)
    for r in converted:
        for t, names in r["output"]["entities"].items():
            type_counts[t] += len(names)
        for rel in r["output"].get("relations", []):
            for k in rel:
                rel_counts[k] += 1

    print(f"input rows: {len(rows_in)}  → converted: {len(converted)}  (skipped {skipped} empty)")
    print(f"train: {len(train)}  holdout: {len(holdout)}")
    print("\nentity counts (total mentions across all rows):")
    for t, n in sorted(type_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {t:<12} {n}")
    print("\ntop relations:")
    for r, n in sorted(rel_counts.items(), key=lambda kv: -kv[1])[:20]:
        print(f"  {r:<28} {n}")
    print(f"\nwrote {OUTPUT_PATH}")
    if holdout:
        print(f"wrote {HOLDOUT_PATH}")


if __name__ == "__main__":
    main()
