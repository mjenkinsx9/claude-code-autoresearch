# Autoresearch skill verification

Last verified: 2026-05-18

## Scenario 1 — CLI help exposes agent backend controls

Input:

```bash
python3 scripts/autoresearch_loop.py --help
python3 scripts/eval_engine.py --help
```

Expected result:

- Both commands exit 0.
- Both help pages include `--agent-backend`.
- Both help pages include `--agent-command`.

Verified on 2026-05-18.

## Scenario 2 — Custom backend smoke test completes a bounded run

Input:

```bash
python3 scripts/autoresearch_loop.py \
  --target target.md \
  --program program.md \
  --eval-config eval.json \
  --runs-per-experiment 1 \
  --max-experiments 2 \
  --agent-backend custom \
  --agent-command 'python3 agent_stub.py {prompt_file}'
```

Expected result:

- The baseline runs.
- One generated experiment runs.
- `results.tsv` is written.
- The process exits 0.

Verified on 2026-05-18.

## Scenario 3 — Eval engine can judge through a custom backend

Input:

```bash
python3 scripts/eval_engine.py \
  --eval-config eval.json \
  --output 'sample output' \
  --agent-backend custom \
  --agent-command 'python3 agent_stub.py {prompt_file}'
```

Expected result:

- Command exits 0.
- Output contains `Score:`.
- No Claude CLI dependency is required.

Verified on 2026-05-18.

## Scenario 4 — Hermes discovery from The-Library

Input:

```bash
hermes skills list
```

and direct skill load through the Hermes skill tool.

Expected result:

- `autoresearch` appears as an enabled local skill.
- `skill_view autoresearch` loads the copy from The-Library.

Verified on 2026-05-18.

## Scenario 5 — Hermes backend adapter smoke test

Input:

```bash
python3 - <<'PY'
from scripts.agent_cli import run_agent_prompt
result = run_agent_prompt(
    'Respond with exactly this text and nothing else: HERMES_BACKEND_OK',
    backend='hermes',
    timeout=180,
)
assert result.ok
assert 'HERMES_BACKEND_OK' in result.stdout
PY
```

Expected result:

- Command exits 0.
- Backend is `hermes`.
- Stdout contains `HERMES_BACKEND_OK`.

Verified on 2026-05-18.
