"""HTML report generator for the eval harness."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from server.eval.harness import EvalResult


def write_html_report(results: list[EvalResult], out: Path) -> None:
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    score_pct = int(passed / total * 100) if total else 0
    grade_color = "#22c55e" if score_pct >= 75 else "#ef4444"
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows = ""
    for r in results:
        icon = "✅" if r.passed else "❌"
        status_class = "pass" if r.passed else "fail"
        expected_facts_str = ", ".join(
            f"{f.get('predicate')}={f.get('object', '?')}" for f in r.expected_facts
        ) or "—"
        found_facts_str = ", ".join(
            f"{f.get('predicate')}={f.get('object', '?')}" for f in r.found_facts[:3]
        ) or "—"
        expected_sources = ", ".join(r.expected_sources) or "—"
        error_cell = f'<td class="error">{r.error}</td>' if r.error else "<td>—</td>"

        rows += f"""
        <tr class="{status_class}">
          <td>{icon}</td>
          <td class="question">{r.question}</td>
          <td>{r.expected_entity or "—"}</td>
          <td>{r.found_entity or "—"}</td>
          <td class="facts">{expected_facts_str}</td>
          <td class="facts">{found_facts_str}</td>
          <td>{expected_sources}</td>
          <td>{r.confidence:.2f} / {r.confidence_min:.2f}</td>
          <td>{r.latency_ms:.0f}ms</td>
          {error_cell}
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Qontext Eval Report — {ts}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: #0f172a; color: #e2e8f0; margin: 0; padding: 2rem; }}
    h1 {{ color: #f8fafc; margin-bottom: 0.25rem; }}
    .meta {{ color: #64748b; font-size: 0.875rem; margin-bottom: 2rem; }}
    .score {{ font-size: 3rem; font-weight: 700; color: {grade_color}; }}
    .score-label {{ font-size: 1rem; color: #94a3b8; margin-bottom: 2rem; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; }}
    th {{ background: #1e293b; color: #94a3b8; text-align: left;
          padding: 0.75rem 0.5rem; border-bottom: 1px solid #334155; }}
    td {{ padding: 0.6rem 0.5rem; border-bottom: 1px solid #1e293b; vertical-align: top; }}
    tr.pass td {{ background: #052e16; }}
    tr.fail td {{ background: #2d0707; }}
    tr:hover td {{ filter: brightness(1.2); }}
    .question {{ max-width: 240px; font-weight: 500; }}
    .facts {{ font-family: monospace; font-size: 0.75rem; color: #94a3b8; max-width: 160px; }}
    .error {{ color: #f87171; font-family: monospace; font-size: 0.75rem; }}
    .badge {{ display: inline-block; padding: 0.25rem 0.75rem; border-radius: 9999px;
              font-size: 0.75rem; font-weight: 600; background: #1e293b; margin-right: 0.5rem; }}
  </style>
</head>
<body>
  <h1>🔍 Qontext Eval Report</h1>
  <p class="meta">Generated {ts} · EnterpriseBench dataset · WS-8</p>
  <div class="score">{passed}/{total}</div>
  <div class="score-label">questions passed ({score_pct}%)</div>
  <span class="badge">{'🟢 PASS' if score_pct >= 75 else '🔴 FAIL'}</span>
  <span class="badge">avg latency {sum(r.latency_ms for r in results)/total:.0f}ms</span>
  <br><br>
  <table>
    <thead>
      <tr>
        <th></th>
        <th>Question</th>
        <th>Expected Entity</th>
        <th>Found Entity</th>
        <th>Expected Facts</th>
        <th>Found Facts</th>
        <th>Expected Sources</th>
        <th>Confidence</th>
        <th>Latency</th>
        <th>Error</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>"""

    out.write_text(html, encoding="utf-8")
