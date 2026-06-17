# Autoresearch Agent verification

Last verified: pending current PR

## Scenario 1 — CLI help exposes no-headless commands

Input:

```bash
python3 scripts/autoresearch_loop.py --help
python3 scripts/eval_engine.py --help
```

Expected result:

- `autoresearch_loop.py` help includes `baseline`, `score`, and `run-verify`.
- `eval_engine.py` help includes `--emit-prompt`, `--judgments-file`, and no agent backend flags.

## Scenario 2 — Mechanical baseline and score keep/discard

Input:

```bash
python3 scripts/autoresearch_loop.py baseline \
  --target target.txt \
  --verify-command 'python3 score.py target.txt' \
  --direction higher

python3 scripts/autoresearch_loop.py score \
  --target target.txt \
  --description 'candidate change'
```

Expected result:

- Baseline writes `autoresearch-results/state.json`.
- Score writes `results.tsv`.
- Improved score is kept.
- Worse score is reverted to the best snapshot.

## Scenario 3 — Guard failure reverts

Input:

```bash
python3 scripts/autoresearch_loop.py baseline \
  --target target.txt \
  --verify-command 'python3 score.py target.txt' \
  --direction higher \
  --guard-command './guard.sh'

python3 scripts/autoresearch_loop.py score \
  --target target.txt \
  --description 'guard failing change'
```

Expected result:

- If verify improves but guard exits non-zero, status is `crash`.
- Target reverts to the best snapshot.
- Guard output is saved under `autoresearch-results/runs/`.

## Scenario 4 — Binary eval emits prompt and scores supplied judgments

Input:

```bash
python3 scripts/eval_engine.py \
  --eval-config eval.json \
  --output 'sample output' \
  --emit-prompt

python3 scripts/eval_engine.py \
  --eval-config eval.json \
  --output 'sample output' \
  --judgments '{"outputs":[{"output_id":"sample","scores":[{"criterion":1,"question":"Does it work?","passed":true,"evidence":"yes"}]}]}'
```

Expected result:

- The first command prints a judge prompt for the active harness.
- The second command prints `Score:` without calling any model CLI.

## Scenario 5 — Legacy headless adapter is disabled

Input:

```bash
python3 scripts/agent_cli.py
```

Expected result:

- Command exits non-zero.
- Output explains that headless agent invocation has been removed.
