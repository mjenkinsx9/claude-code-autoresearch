# Results Logging Protocol

Track every iteration in a structured log. Enables pattern recognition and prevents repeating failed experiments.

## Log Format (TSV)

There are two TSV schemas depending on how you run autoresearch. Pick the one
that matches your mode — the dashboard (`scripts/generate_dashboard.py`) only
parses the script schema.

### Script schema (written by `scripts/autoresearch_loop.py`)

`autoresearch-results/results.tsv`:

```tsv
experiment	score	max_score	status	description	timestamp
001	28	48	keep	baseline — original target file	2026-06-10T08:00:00
002	35	48	keep	added explicit CTA instruction	2026-06-10T08:14:02
003	33	48	discard	word limit broke tone	2026-06-10T08:31:40
```

| Column | Type | Description |
|--------|------|-------------|
| experiment | string | Zero-padded sequential number (001, 002, ...) |
| score | int | Total yes answers across all runs and criteria |
| max_score | int | criteria × test prompts × runs per experiment |
| status | enum | `keep`, `discard`, `crash` |
| description | string | One-sentence description of what was tried |
| timestamp | string | ISO 8601 |

### Manual-loop schema (agent-driven loops without the Python runner)

`autoresearch-results.tsv` in the working directory:

```tsv
iteration	commit	metric	delta	guard	status	description
```

| Column | Type | Description |
|--------|------|-------------|
| iteration | int | Sequential counter starting at 0 (baseline) |
| commit | string | Short git hash (7 chars), "-" if reverted |
| metric | float | Measured value from verification |
| delta | float | Change from previous best (negative = improved for "lower is better") |
| guard | enum | `pass`, `fail`, or `-` (no guard configured) |
| status | enum | `baseline`, `keep`, `discard`, `crash` |
| description | string | One-sentence description of what was tried |

### Example (manual-loop schema)

```tsv
iteration	commit	metric	delta	guard	status	description
0	a1b2c3d	85.2	0.0	pass	baseline	initial state -- test coverage 85.2%
1	b2c3d4e	87.1	+1.9	pass	keep	add tests for auth middleware edge cases
2	-	86.5	-0.6	-	discard	refactor test helpers (broke 2 tests)
3	-	0.0	0.0	-	crash	add integration tests (DB connection failed)
4	-	88.9	+1.8	fail	discard	inline hot-path functions (guard: 3 tests broke)
5	c3d4e5f	88.3	+1.2	pass	keep	add tests for error handling in API routes
6	d4e5f6g	89.0	+0.7	pass	keep	add boundary value tests for validators
```

**Note:** When guard fails, the metric may have improved but the change is still discarded. The guard column makes this visible in the log so the agent can learn which optimization approaches tend to cause regressions.

## Log Management

- Create at setup (iteration 0 = baseline)
- Append after EVERY iteration (including crashes)
- Do NOT commit this file to git (add to .gitignore)
- Read last 10-20 entries at start of each iteration for context
- Use to detect patterns: what kind of changes tend to succeed?

## Summary Reporting

Every 10 iterations (or at loop completion in bounded mode), print a brief summary:

```
=== Autoresearch Progress (iteration 20) ===
Baseline: 85.2% -> Current best: 92.1% (+6.9%)
Keeps: 8 | Discards: 10 | Crashes: 2
Last 5: keep, discard, discard, keep, keep
```

## Metric Direction

Clarify at setup whether lower or higher is better:
- **Lower is better:** val_bpb, response time (ms), bundle size (KB), error count
- **Higher is better:** test coverage (%), lighthouse score, throughput (req/s)

Record direction in first line of results log as a comment:
```
# metric_direction: higher_is_better
```
