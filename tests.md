# Autoresearch Agent verification

Last verified: 2026-07-16 (P1 polish: dashboard decision best, eval integrity, docs)

Automated source of truth: `python3 -m pytest tests/ -q`

## Scenario 1 — CLI help surfaces

```bash
python3 scripts/autoresearch_loop.py --help
python3 scripts/autoresearch_loop.py baseline --help
python3 scripts/autoresearch_loop.py score --help
python3 scripts/eval_engine.py --help
```

Expected:

- Top-level loop help lists: `baseline`, `score`, `run-verify`, `status`, `results`, `best`, `fork`
- `baseline --help` includes `--metric`, `--max-experiments`, `--targets`, `--private-verify-command`
- `score --help` includes `--allow-config-change`, `--strict-snapshots`
- Eval help includes `--emit-prompt`, `--judgments-file`, `--allow-partial-judgments`; no agent backend

## Scenario 2 — Mechanical keep / discard

```bash
python3 scripts/autoresearch_loop.py baseline \
  --target target.txt \
  --verify-command 'python3 score.py target.txt' \
  --metric Score \
  --direction higher \
  --max-experiments 10

python3 scripts/autoresearch_loop.py score \
  --target target.txt \
  --description 'candidate change'
```

Expected: KEEP on improve, DISCARD reverts; `state.json` has UTC `created_at` and `best_snapshot_sha256`.

## Scenario 3 — Guard / private / multi-target / budget / parent

Covered by pytest modules (preferred over manual):

| Module | What it proves |
|---|---|
| `test_no_headless.py` | Core keep/discard + eval + agent_cli |
| `test_integrity.py` | Metric name, seal, snapshot escape, UTF-8, cwd seal |
| `test_lineage_multitarget.py` | Parent after discard; multi-file restore |
| `test_budgets_json.py` | max_experiments; max_wall keep/expired; JSON CLI |
| `test_private_metric.py` | Private decision KEEP/DISCARD; fork |
| `test_snapshot_sandbox.py` | Artifact escape; strict hash; sealed targets |
| `test_eval_engine.py` | Overcount, duplicate ids, output count, untrusted tags |
| `test_dashboard.py` | Decision best ≠ public spike; lower direction |
| `test_meta_self_improve.py` | End-to-end Score improves with real CLI |
| `test_mechanical_examples.py` | Shipped hello-length, constrained-compress, multitarget-api via real loop |

## Scenario 4 — Binary eval

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

Expected: untrusted framing in prompt; `Score: 1/1`; overcount exits non-zero.

## Scenario 5 — Headless adapter disabled

```bash
python3 scripts/agent_cli.py
```

Expected: non-zero exit; message that headless invocation was removed.
