#!/usr/bin/env python3
"""
Autoresearch Results Dashboard Generator

Reads results.tsv and generates an interactive HTML dashboard showing
experiment history, scores, and trends.

Usage:
    python generate_dashboard.py --results path/to/results.tsv --output dashboard.html
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from datetime import datetime


def load_results(results_path: str) -> list[dict]:
    """Load results from TSV file."""
    results = []
    with open(results_path) as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            try:
                row["score"] = int(row["score"])
                row["max_score"] = int(row["max_score"])
            except (ValueError, KeyError) as e:
                print(f"Warning: Skipping malformed row: {row} ({e})", file=sys.stderr)
                continue
            row["score_pct"] = round(row["score"] / row["max_score"] * 100, 1) if row["max_score"] > 0 else 0
            results.append(row)
    return results


def generate_html(results: list[dict], title: str = "Autoresearch Results") -> str:
    """Generate the dashboard HTML."""
    if not results:
        return "<html><body><h1>No results yet</h1></body></html>"

    max_score = results[0]["max_score"]
    non_crash_results = [r for r in results if r["status"] != "crash"]
    best_score = max(r["score"] for r in non_crash_results) if non_crash_results else 0
    best_pct = round(best_score / max_score * 100, 1) if max_score > 0 else 0
    total_experiments = len(results)
    keeps = sum(1 for r in results if r["status"] == "keep")
    discards = sum(1 for r in results if r["status"] == "discard")
    crashes = sum(1 for r in results if r["status"] == "crash")

    # Running best score for chart
    running_best = []
    current_best = 0
    for r in results:
        if r["status"] == "keep":
            current_best = r["score"]
        running_best.append(current_best)

    results_json = json.dumps(results)
    running_best_json = json.dumps(running_best)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f0f23; color: #e0e0e0; min-height: 100vh; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
        h1 {{ font-size: 28px; margin-bottom: 8px; color: #fff; }}
        .subtitle {{ color: #888; margin-bottom: 24px; font-size: 14px; }}

        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 32px; }}
        .stat-card {{ background: #1a1a3e; border-radius: 12px; padding: 20px; border: 1px solid #2a2a5e; }}
        .stat-label {{ font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }}
        .stat-value {{ font-size: 32px; font-weight: 700; }}
        .stat-value.green {{ color: #4ade80; }}
        .stat-value.blue {{ color: #60a5fa; }}
        .stat-value.red {{ color: #f87171; }}
        .stat-value.yellow {{ color: #facc15; }}

        .chart-container {{ background: #1a1a3e; border-radius: 12px; padding: 24px; border: 1px solid #2a2a5e; margin-bottom: 32px; }}
        .chart-title {{ font-size: 16px; font-weight: 600; margin-bottom: 16px; }}
        canvas {{ width: 100% !important; height: 300px !important; }}

        .table-container {{ background: #1a1a3e; border-radius: 12px; padding: 24px; border: 1px solid #2a2a5e; overflow-x: auto; }}
        .table-title {{ font-size: 16px; font-weight: 600; margin-bottom: 16px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
        th {{ text-align: left; padding: 12px 16px; border-bottom: 2px solid #2a2a5e; color: #888; font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 1px; }}
        td {{ padding: 10px 16px; border-bottom: 1px solid #1f1f4f; }}
        tr:hover {{ background: #22224a; }}

        .badge {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }}
        .badge-keep {{ background: #064e3b; color: #4ade80; }}
        .badge-discard {{ background: #4a1d1d; color: #f87171; }}
        .badge-crash {{ background: #4a3b1d; color: #facc15; }}

        .score-bar {{ display: flex; align-items: center; gap: 8px; }}
        .score-bar-track {{ flex: 1; height: 8px; background: #2a2a5e; border-radius: 4px; overflow: hidden; }}
        .score-bar-fill {{ height: 100%; border-radius: 4px; transition: width 0.3s; }}
        .score-bar-fill.high {{ background: #4ade80; }}
        .score-bar-fill.mid {{ background: #facc15; }}
        .score-bar-fill.low {{ background: #f87171; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 {title}</h1>
        <div class="subtitle">Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · {total_experiments} experiments</div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Best Score</div>
                <div class="stat-value green">{best_score}/{max_score}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Best %</div>
                <div class="stat-value blue">{best_pct}%</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Experiments</div>
                <div class="stat-value">{total_experiments}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Kept / Discarded / Crashed</div>
                <div class="stat-value"><span class="green">{keeps}</span> / <span class="red">{discards}</span> / <span class="yellow">{crashes}</span></div>
            </div>
        </div>

        <div class="chart-container">
            <div class="chart-title">Score Progression</div>
            <canvas id="scoreChart"></canvas>
        </div>

        <div class="table-container">
            <div class="table-title">Experiment Log</div>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Score</th>
                        <th>Progress</th>
                        <th>Status</th>
                        <th>Description</th>
                        <th>Time</th>
                    </tr>
                </thead>
                <tbody id="resultsBody"></tbody>
            </table>
        </div>
    </div>

    <script>
        const results = {results_json};
        const runningBest = {running_best_json};
        const maxScore = {max_score};

        // Populate table
        const tbody = document.getElementById('resultsBody');
        results.forEach((r, i) => {{
            const pct = r.max_score > 0 ? (r.score / r.max_score * 100).toFixed(1) : 0;
            const barClass = pct >= 80 ? 'high' : pct >= 50 ? 'mid' : 'low';
            const badgeClass = r.status === 'keep' ? 'badge-keep' : r.status === 'crash' ? 'badge-crash' : 'badge-discard';
            const ts = r.timestamp ? new Date(r.timestamp).toLocaleTimeString() : '';

            tbody.innerHTML += `
                <tr>
                    <td>${{r.experiment}}</td>
                    <td>${{r.score}}/${{r.max_score}}</td>
                    <td>
                        <div class="score-bar">
                            <div class="score-bar-track">
                                <div class="score-bar-fill ${{barClass}}" style="width:${{pct}}%"></div>
                            </div>
                            <span>${{pct}}%</span>
                        </div>
                    </td>
                    <td><span class="badge ${{badgeClass}}">${{r.status}}</span></td>
                    <td>${{r.description.replace(/</g, '&lt;').replace(/>/g, '&gt;')}}</td>
                    <td>${{ts}}</td>
                </tr>
            `;
        }});

        // Simple chart using canvas
        const canvas = document.getElementById('scoreChart');
        const ctx = canvas.getContext('2d');
        const dpr = window.devicePixelRatio || 1;
        canvas.width = canvas.offsetWidth * dpr;
        canvas.height = 300 * dpr;
        ctx.scale(dpr, dpr);

        const w = canvas.offsetWidth;
        const h = 300;
        const pad = {{ top: 20, right: 20, bottom: 40, left: 50 }};
        const plotW = w - pad.left - pad.right;
        const plotH = h - pad.top - pad.bottom;

        // Draw axes
        ctx.strokeStyle = '#2a2a5e';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(pad.left, pad.top);
        ctx.lineTo(pad.left, h - pad.bottom);
        ctx.lineTo(w - pad.right, h - pad.bottom);
        ctx.stroke();

        // Y-axis labels
        ctx.fillStyle = '#888';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'right';
        for (let i = 0; i <= 4; i++) {{
            const val = Math.round(maxScore * i / 4);
            const y = h - pad.bottom - (plotH * i / 4);
            ctx.fillText(val.toString(), pad.left - 8, y + 4);
            ctx.strokeStyle = '#1f1f4f';
            ctx.beginPath();
            ctx.moveTo(pad.left, y);
            ctx.lineTo(w - pad.right, y);
            ctx.stroke();
        }}

        if (results.length > 1) {{
            const xStep = plotW / (results.length - 1);

            // Score dots and lines
            ctx.strokeStyle = '#60a5fa';
            ctx.lineWidth = 2;
            ctx.beginPath();
            results.forEach((r, i) => {{
                const x = pad.left + i * xStep;
                const y = h - pad.bottom - (r.score / maxScore * plotH);
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }});
            ctx.stroke();

            // Running best line
            ctx.strokeStyle = '#4ade80';
            ctx.lineWidth = 2;
            ctx.setLineDash([5, 5]);
            ctx.beginPath();
            runningBest.forEach((score, i) => {{
                const x = pad.left + i * xStep;
                const y = h - pad.bottom - (score / maxScore * plotH);
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }});
            ctx.stroke();
            ctx.setLineDash([]);

            // Dots colored by status
            results.forEach((r, i) => {{
                const x = pad.left + i * xStep;
                const y = h - pad.bottom - (r.score / maxScore * plotH);
                ctx.beginPath();
                ctx.arc(x, y, 4, 0, Math.PI * 2);
                ctx.fillStyle = r.status === 'keep' ? '#4ade80' : r.status === 'crash' ? '#facc15' : '#f87171';
                ctx.fill();
            }});

            // Legend
            ctx.font = '11px sans-serif';
            ctx.fillStyle = '#60a5fa';
            ctx.fillText('● Score', w - 180, pad.top + 10);
            ctx.fillStyle = '#4ade80';
            ctx.fillText('--- Best', w - 110, pad.top + 10);
        }}

        // X-axis label
        ctx.fillStyle = '#888';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Experiment', w / 2, h - 8);
    </script>
</body>
</html>"""

    return html


def main():
    parser = argparse.ArgumentParser(description="Autoresearch Results Dashboard")
    parser.add_argument("--results", required=True, help="Path to results.tsv")
    parser.add_argument("--output", default="dashboard.html", help="Output HTML file path")
    parser.add_argument("--title", default="Autoresearch Results", help="Dashboard title")
    args = parser.parse_args()

    if not os.path.exists(args.results):
        print(f"Error: results file '{args.results}' not found")
        sys.exit(1)

    results = load_results(args.results)
    html = generate_html(results, args.title)

    with open(args.output, "w") as f:
        f.write(html)

    print(f"Dashboard generated: {args.output}")
    print(f"Experiments: {len(results)}")
    if results:
        best = max(r["score"] for r in results if r["status"] != "crash")
        print(f"Best score: {best}/{results[0]['max_score']}")


if __name__ == "__main__":
    main()
