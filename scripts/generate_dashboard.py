#!/usr/bin/env python3
"""Generate a small HTML dashboard from autoresearch results.tsv."""

from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from pathlib import Path
from typing import Any


def parse_number(value: str | None) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_results(results_path: str) -> list[dict[str, Any]]:
    path = Path(results_path)
    if not path.exists():
        raise SystemExit(f"Error: results file not found: {results_path}")

    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            row = dict(row)
            row["score_num"] = parse_number(row.get("score"))
            row["best_score_num"] = parse_number(row.get("best_score"))
            row["max_score_num"] = parse_number(row.get("max_score"))
            if row["score_num"] is not None and row["max_score_num"]:
                row["score_pct"] = round(row["score_num"] / row["max_score_num"] * 100, 1)
            else:
                row["score_pct"] = None
            rows.append(row)
    return rows


def safe_json(value: Any) -> str:
    return json.dumps(value).replace("<", "\\u003c")


def generate_html(results: list[dict[str, Any]], title: str) -> str:
    if not results:
        return "<html><body><h1>No results</h1></body></html>"

    kept = sum(1 for r in results if r.get("status") == "keep")
    discarded = sum(1 for r in results if r.get("status") == "discard")
    crashed = sum(1 for r in results if r.get("status") == "crash")
    latest = results[-1]
    direction = latest.get("direction") or "higher"
    numeric_scores = [r["score_num"] for r in results if r.get("score_num") is not None and r.get("status") != "crash"]
    if numeric_scores:
        best_score = max(numeric_scores) if direction == "higher" else min(numeric_scores)
    else:
        best_score = None

    rows = []
    for row in results:
        status = html.escape(row.get("status", ""))
        rows.append(
            "<tr>"
            f"<td>{html.escape(row.get('experiment', ''))}</td>"
            f"<td>{html.escape(row.get('parent_experiment', '') or '')}</td>"
            f"<td><span class='status {status}'>{status}</span></td>"
            f"<td>{html.escape(row.get('score', ''))}</td>"
            f"<td>{html.escape(row.get('private_score', '') or '')}</td>"
            f"<td>{html.escape(row.get('best_score', ''))}</td>"
            f"<td>{html.escape(row.get('lineage', '') or '')}</td>"
            f"<td>{html.escape(row.get('description', ''))}</td>"
            f"<td>{html.escape(row.get('timestamp', ''))}</td>"
            "</tr>"
        )

    chart_data = [
        {"experiment": r.get("experiment"), "score": r.get("score_num"), "status": r.get("status")}
        for r in results
    ]

    best_text = "n/a" if best_score is None else (str(int(best_score)) if float(best_score).is_integer() else f"{best_score:.6g}")
    title_escaped = html.escape(title)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title_escaped}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 2rem; background: #101120; color: #f4f4f5; }}
.card {{ background: #181a2f; border: 1px solid #2c2f4a; border-radius: 12px; padding: 1rem; margin: 1rem 0; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 1rem; }}
.stat {{ font-size: 2rem; font-weight: 700; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: .65rem; border-bottom: 1px solid #2c2f4a; text-align: left; vertical-align: top; }}
th {{ color: #a5b4fc; }}
.status {{ border-radius: 999px; padding: .15rem .5rem; font-size: .8rem; }}
.status.keep {{ background: #064e3b; color: #a7f3d0; }}
.status.discard {{ background: #4c1d1d; color: #fecaca; }}
.status.crash {{ background: #451a03; color: #fed7aa; }}
canvas {{ width: 100%; max-height: 320px; background: #0b0c18; border-radius: 8px; }}
</style>
</head>
<body>
<h1>{title_escaped}</h1>
<div class="stats">
  <div class="card"><div>Experiments</div><div class="stat">{len(results)}</div></div>
  <div class="card"><div>Best score</div><div class="stat">{best_text}</div><div>{html.escape(direction)} is better</div></div>
  <div class="card"><div>Kept</div><div class="stat">{kept}</div></div>
  <div class="card"><div>Discarded</div><div class="stat">{discarded}</div></div>
  <div class="card"><div>Crashed</div><div class="stat">{crashed}</div></div>
</div>
<div class="card"><canvas id="chart" width="1000" height="320"></canvas></div>
<div class="card">
<table>
<thead><tr><th>Experiment</th><th>Parent</th><th>Status</th><th>Score</th><th>Private</th><th>Best</th><th>Lineage</th><th>Description</th><th>Timestamp</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
</div>
<script>
const data = {safe_json(chart_data)};
const canvas = document.getElementById('chart');
const ctx = canvas.getContext('2d');
const scores = data.map(d => d.score).filter(v => typeof v === 'number');
if (scores.length) {{
  const min = Math.min(...scores);
  const max = Math.max(...scores);
  const pad = 40;
  const w = canvas.width, h = canvas.height;
  ctx.strokeStyle = '#4f46e5';
  ctx.lineWidth = 2;
  ctx.beginPath();
  data.forEach((d, i) => {{
    if (typeof d.score !== 'number') return;
    const x = pad + (i / Math.max(1, data.length - 1)) * (w - pad * 2);
    const y = h - pad - ((d.score - min) / Math.max(1e-9, max - min)) * (h - pad * 2);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }});
  ctx.stroke();
  data.forEach((d, i) => {{
    if (typeof d.score !== 'number') return;
    const x = pad + (i / Math.max(1, data.length - 1)) * (w - pad * 2);
    const y = h - pad - ((d.score - min) / Math.max(1e-9, max - min)) * (h - pad * 2);
    ctx.fillStyle = d.status === 'keep' ? '#22c55e' : d.status === 'crash' ? '#f97316' : '#ef4444';
    ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI * 2); ctx.fill();
  }});
  ctx.fillStyle = '#cbd5e1';
  ctx.fillText('max ' + max, 8, pad);
  ctx.fillText('min ' + min, 8, h - pad);
}} else {{
  ctx.fillStyle = '#cbd5e1';
  ctx.fillText('No numeric scores yet', 40, 80);
}}
</script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an HTML dashboard from autoresearch results.tsv")
    parser.add_argument("--results", required=True, help="Path to results.tsv")
    parser.add_argument("--output", default="dashboard.html", help="Output HTML file path")
    parser.add_argument("--title", default="Autoresearch Agent Results", help="Dashboard title")
    args = parser.parse_args()

    results = load_results(args.results)
    output = generate_html(results, args.title)
    Path(args.output).write_text(output, encoding="utf-8")
    print(f"Dashboard written to {args.output}")
    if results:
        direction = (results[-1].get("direction") or "higher")
        non_crash = [r["score_num"] for r in results if r.get("status") != "crash" and r.get("score_num") is not None]
        if non_crash:
            best = max(non_crash) if direction == "higher" else min(non_crash)
            print(f"Best score: {best} ({direction} is better)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
