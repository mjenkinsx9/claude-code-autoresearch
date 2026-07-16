# Results Logging Protocol

Track every iteration in a structured log. Enables pattern recognition and prevents repeating failed experiments.

## Log Format (TSV)

`scripts/autoresearch_loop.py` writes `autoresearch-results/results.tsv` automatically.

```tsv
experiment	score	max_score	best_score	private_score	decision_score	status	description	timestamp	direction	verify_command	guard_command	snapshot	parent_experiment	lineage
```

### Columns

| Column | Type | Description |
|---|---|---|
| experiment | string | Sequential experiment id, starting at `001` for baseline |
| score | number | Public/parsed metric for this candidate (blank if parse failed) |
| max_score | number | Optional known maximum; blank when unknown |
| best_score | number | Best known **decision** score after this row |
| private_score | number | Private/held-out metric when configured; else blank |
| decision_score | number | Metric used for keep/discard this row (private if set, else public) |
| status | enum | `keep`, `discard`, `crash`, or `fork` (lineage marker; does not count toward `--max-experiments`) |
| description | string | One-sentence description of what was tried |
| timestamp | ISO datetime | When the row was written |
| direction | enum | `higher` or `lower` |
| verify_command | string | Public verify command used |
| guard_command | string | Guard command used, if any |
| snapshot | path | Snapshot directory (or legacy file) for this experiment |
| parent_experiment | string | Parent experiment id (blank for baseline); after discard, next parent is best keep |
| lineage | string | Optional strategy tag |

### Example

Parent and lineage show search structure after discards:

| experiment | score | best_score | status | parent | lineage | description |
|---|---|---|---|---|---|---|
| 001 | 3 | 3 | keep | (none) | | baseline |
| 002 | 4 | 4 | keep | 001 | exploit | append text |
| 003 | 1 | 4 | discard | 002 | exploit | shorter |
| 004 | 5 | 5 | keep | 002 | explore | after discard (parent is best keep) |

Notes:

- After `discard`/`crash`, the helper sets the next parent to **best_experiment**, not the failed id.
- Snapshots live under `autoresearch-results/snapshots/experiment_NNN_status/` with `manifest.json` + `files/`.
- Do not commit `autoresearch-results/`.
