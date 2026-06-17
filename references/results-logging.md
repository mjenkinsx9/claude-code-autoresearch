# Results Logging Protocol

Track every iteration in a structured log. Enables pattern recognition and prevents repeating failed experiments.

## Log Format (TSV)

`scripts/autoresearch_loop.py` writes `autoresearch-results/results.tsv` automatically.

```tsv
experiment	score	max_score	best_score	status	description	timestamp	direction	verify_command	guard_command	snapshot
```

### Columns

| Column | Type | Description |
|---|---|---|
| experiment | string | Sequential experiment id, starting at `001` for baseline |
| score | number | Parsed metric for this candidate, blank if verify failed before parsing |
| max_score | number | Optional maximum score for binary eval compatibility; blank for mechanical metrics |
| best_score | number | Best known score after this row is processed |
| status | enum | `keep`, `discard`, or `crash` |
| description | string | One-sentence description of what was tried |
| timestamp | ISO datetime | When the row was written |
| direction | enum | `higher` or `lower` |
| verify_command | string | Actual verify command used |
| guard_command | string | Actual guard command used, if any |
| snapshot | path | Snapshot of the baseline/candidate file |

### Example

```tsv
experiment	score	max_score	best_score	status	description	timestamp	direction	verify_command	guard_command	snapshot
001	85.2		85.2	keep	baseline	2026-06-17T10:00:00	higher	./score.sh	npm test	autoresearch-results/snapshots/experiment_001_keep.md
002	87.1		87.1	keep	add auth edge cases	2026-06-17T10:05:00	higher	./score.sh	npm test	autoresearch-results/snapshots/experiment_002_keep.md
003	86.5		87.1	discard	refactor helpers	2026-06-17T10:10:00	higher	./score.sh	npm test	autoresearch-results/snapshots/experiment_003_discard.md
004			87.1	crash	guard failed: tests broke	2026-06-17T10:15:00	higher	./score.sh	npm test	autoresearch-results/snapshots/experiment_004_crash.md
```

When guard fails, the metric may have improved but the change is still reverted and logged as `crash`; the saved guard output under `autoresearch-results/runs/` explains why.

## Log Management

- Let `scripts/autoresearch_loop.py baseline` create the first row.
- Let `scripts/autoresearch_loop.py score` append after every candidate.
- Do not commit `autoresearch-results/` to git.
- Read the last 10-20 rows at the start of each iteration.
- Preserve the log; it is the research map for future agents.

## Summary Reporting

Every 10 iterations, or at bounded-loop completion, summarize:

```text
=== Autoresearch Progress ===
Baseline: 85.2 -> Current best: 92.1 (+6.9)
Keeps: 8 | Discards: 10 | Crashes: 2
Last 5: keep, discard, discard, keep, keep
```

## Metric Direction

Clarify at setup whether lower or higher is better:

- **Lower is better:** response time, bundle size, error count, LOC
- **Higher is better:** coverage, Lighthouse score, throughput, pass count

The helper stores direction in `state.json` and records it on each TSV row.
