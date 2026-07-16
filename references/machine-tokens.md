# Machine-parseable helper tokens

`scripts/autoresearch_loop.py` prints `KEY=value` lines on stdout so harnesses
can drive keep/discard without scraping prose. Values are not localized.

## Common tokens

| Token | Where | Meaning |
|---|---|---|
| `STATUS` | baseline, score, fork, budget | `keep` \| `discard` \| `crash` \| `fork` \| `budget_exceeded` |
| `MODE` | baseline, score, fork, budget | Always `mechanical-no-headless` |
| `SCHEMA_VERSION` | baseline, score, fork, budget | Integer; currently `2` (also in `state.json`) |
| `OUTPUT_DIR` | baseline, score, fork, budget | Absolute path to results dir |
| `EXPERIMENT` | baseline, score, fork | `001`… or `fork-…` id |
| `PARENT` | baseline, score, fork | Parent experiment id (blank on baseline) |
| `DECISION` | baseline, score | Metric used for keep/discard this step |
| `BEST` | baseline, score, fork, budget | Current best decision score |
| `BEST_EXPERIMENT` | fork, budget | Best experiment id (fork parent / when budget blocks) |
| `DIRECTION` | baseline, score | `higher` or `lower` |
| `PUBLIC` | baseline, score | Public verify metric |
| `PRIVATE` | baseline, score | Present only if private verify is configured |
| `LINEAGE` | score, fork | Strategy tag when set |
| `SNAPSHOT` | baseline, score | Path to this experiment’s snapshot |
| `REVERTED` | baseline, score | `true` if target restored to best; else `false` |
| `BEST_SNAPSHOT` | score | Present when `REVERTED=true` |
| `CANDIDATES_DONE` | baseline, score, budget | Count of post-baseline scores already run (always printed) |
| `CANDIDATES_REMAINING` | baseline, score, budget | Remaining candidate slots (only when `--max-experiments` set) |
| `WALL_REMAINING_SECONDS` | baseline, score, budget | Remaining wall budget (only when `--max-wall-seconds` set) |

## Exit codes (`score`)

| Code | Meaning |
|---|---|
| 0 | `keep` or `discard` completed (discard still reverts targets) |
| 1 | `crash` (verify/private/guard failed; targets reverted) |
| 2 | `budget_exceeded` (no mutation by helper) |

## JSON alternatives

- `status --json` — full state + budget progress (`candidates_*`, wall fields, `schema_version`)
- `results --json` — TSV rows with numeric coercion (`score`/`decision_score`/… as numbers or `null`; `experiment`/`parent_experiment` as int or `null`)
- `best --json` — best score/snapshot + `schema_version`/`mode` + full candidate/wall budget fields (same progress keys as `status --json`)

## Example (`score` keep)

```text
STATUS=keep
MODE=mechanical-no-headless
SCHEMA_VERSION=2
OUTPUT_DIR=/path/to/autoresearch-results
EXPERIMENT=002
PARENT=001
DECISION=4
BEST=4
DIRECTION=higher
PUBLIC=4
SNAPSHOT=/path/to/snapshots/experiment_002_keep
REVERTED=false
CANDIDATES_DONE=1
CANDIDATES_REMAINING=4
```
