"""WS-8 Eval Harness — runs demo questions against the live search API.

Usage:
    uv run server-eval                     # runs all questions, writes report.html
    uv run server-eval --out /tmp/out.html # custom output path
    uv run server-eval --dry-run           # validate question format only (no DB)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_QUESTIONS_PATH = Path(__file__).parent / "questions.yaml"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class EvalQuestion:
    question: str
    expected_entity: str | None
    expected_facts: list[dict]
    expected_sources: list[str]
    confidence_min: float


@dataclass
class EvalResult:
    question: str
    status: str          # PASS | FAIL | SKIP | ERROR
    expected_entity: str | None
    found_entity: str | None
    expected_facts: list[dict]
    found_facts: list[dict]
    expected_sources: list[str]
    found_sources: list[str]
    confidence: float
    confidence_min: float
    latency_ms: float
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


# ---------------------------------------------------------------------------
# Question loader
# ---------------------------------------------------------------------------

def load_questions(path: Path = _QUESTIONS_PATH) -> list[EvalQuestion]:
    try:
        import yaml  # type: ignore
        loader = yaml.safe_load
    except ImportError:
        # Fallback: minimal YAML parser for our simple format
        def loader(text):  # type: ignore
            raise RuntimeError("PyYAML not installed — run: uv add pyyaml")

    with open(path) as f:
        raw = loader(f.read())

    return [
        EvalQuestion(
            question=q["question"],
            expected_entity=q.get("expected_entity"),
            expected_facts=q.get("expected_facts") or [],
            expected_sources=q.get("expected_sources") or [],
            confidence_min=float(q.get("confidence_min", 0.7)),
        )
        for q in raw
    ]


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

def _evaluate(q: EvalQuestion, search_fn) -> EvalResult:
    t0 = time.monotonic()
    try:
        results = search_fn(q.question, k=5)
    except Exception as exc:
        return EvalResult(
            question=q.question,
            status="ERROR",
            expected_entity=q.expected_entity,
            found_entity=None,
            expected_facts=q.expected_facts,
            found_facts=[],
            expected_sources=q.expected_sources,
            found_sources=[],
            confidence=0.0,
            confidence_min=q.confidence_min,
            latency_ms=(time.monotonic() - t0) * 1000,
            error=str(exc),
        )

    latency_ms = (time.monotonic() - t0) * 1000

    if not results:
        return EvalResult(
            question=q.question, status="FAIL",
            expected_entity=q.expected_entity, found_entity=None,
            expected_facts=q.expected_facts, found_facts=[],
            expected_sources=q.expected_sources, found_sources=[],
            confidence=0.0, confidence_min=q.confidence_min,
            latency_ms=latency_ms,
        )

    top = results[0]
    # results is list[SearchResult] with .entity and .score
    entity = getattr(top, "entity", None)
    found_entity = entity.canonical_name if entity else None
    found_facts = [
        {"predicate": f.predicate, "object": f.object_literal or f.object_id}
        for f in (entity.facts if entity else [])
    ]
    found_sources = list({f.source_id for f in (entity.facts if entity else [])})
    confidence = float(getattr(top, "score", 0.0))

    # Pass conditions
    entity_ok = (q.expected_entity is None) or (found_entity == q.expected_entity)
    confidence_ok = confidence >= q.confidence_min

    # Check expected facts present in found facts
    facts_ok = True
    for ef in q.expected_facts:
        match = any(
            ff.get("predicate") == ef.get("predicate")
            for ff in found_facts
        )
        if not match:
            facts_ok = False
            break

    status = "PASS" if (entity_ok and confidence_ok) else "FAIL"

    return EvalResult(
        question=q.question,
        status=status,
        expected_entity=q.expected_entity,
        found_entity=found_entity,
        expected_facts=q.expected_facts,
        found_facts=found_facts,
        expected_sources=q.expected_sources,
        found_sources=found_sources,
        confidence=confidence,
        confidence_min=q.confidence_min,
        latency_ms=latency_ms,
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_eval(search_fn=None, questions_path: Path = _QUESTIONS_PATH) -> list[EvalResult]:
    """Run all eval questions. search_fn(query, k) -> list[SearchResult]."""
    if search_fn is None:
        from server.api.search import run_hybrid_search
        from server.db import get_db
        db = get_db()
        search_fn = lambda q, k=5: run_hybrid_search(q, k=k, db=db)  # noqa: E731

    questions = load_questions(questions_path)
    results = []
    for q in questions:
        print(f"  [{q.question[:60]}]", end=" ", flush=True)
        result = _evaluate(q, search_fn)
        icon = "✅" if result.passed else "❌"
        print(f"{icon}  ({result.latency_ms:.0f}ms)")
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="WS-8 Eval Harness")
    parser.add_argument("--out", default="eval_report.html", help="Output HTML path")
    parser.add_argument("--dry-run", action="store_true", help="Validate questions only, no DB")
    parser.add_argument("--json", action="store_true", help="Print JSON results to stdout")
    args = parser.parse_args()

    if args.dry_run:
        questions = load_questions()
        print(f"✅ {len(questions)} questions loaded and valid.")
        for q in questions:
            print(f"   - {q.question}")
        sys.exit(0)

    print(f"\n🔍 Running eval harness ({_QUESTIONS_PATH.name})...\n")
    results = run_eval()

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    score_pct = int(passed / total * 100) if total else 0
    print(f"\n{'='*50}")
    print(f"Score: {passed}/{total} ({score_pct}%)")
    print(f"{'='*50}\n")

    if args.json:
        import dataclasses
        print(json.dumps([dataclasses.asdict(r) for r in results], indent=2, default=str))
    else:
        from server.eval.reporter import write_html_report
        out = Path(args.out)
        write_html_report(results, out)
        print(f"📄 Report written to: {out.resolve()}")

    sys.exit(0 if score_pct >= 75 else 1)


if __name__ == "__main__":
    main()
