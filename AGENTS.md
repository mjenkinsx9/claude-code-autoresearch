# Autoresearch Agent — Repository Instructions

Use these instructions for Claude Code, Codex, Gemini CLI, Pi, Hermes, and any other agent harness working in this repository.

## Core Rule: No Headless Model Commands

Do not run a second LLM through print/headless CLI mode for autoresearch work. The active harness session is the agent runtime.

Do not build workflows around commands such as Claude `-p`, Pi `-p`, or equivalent model CLI print/headless modes. Use local deterministic commands only for tests, scoring, guard checks, snapshots, and logs.

## How Autoresearch Should Run

1. The active harness reads goals, `status --json` / recent `results.tsv` rows, and target files.
2. The active harness makes exactly one focused change.
3. Run deterministic helpers:
   - `python scripts/autoresearch_loop.py baseline ...` (`--metric`, optional `--max-experiments`, `--targets`, `--private-verify-command`).
   - `python scripts/autoresearch_loop.py score ...` after each candidate change.
   - `python scripts/eval_engine.py --emit-prompt ...` to prepare binary-eval prompts for the active harness.
4. Keep, discard, crash, or budget exceeded come from helper output — parse `STATUS=` / `EXPERIMENT=` / `DECISION=` / `BEST=` (and exit 2 for budget). Do not invent keep/discard.
5. Failed candidates are reverted by the helper to the best snapshot (multi-file sets included).

## Development Commands

Run these before committing changes:

```bash
git diff --check
python3 -m py_compile scripts/*.py tests/*.py
python3 -m pytest tests/ -q
```

## Code Guidelines

- Keep helper scripts deterministic and model-free.
- Prefer explicit, parseable command output over prose.
- Preserve backward-compatible CLI help where practical, but do not preserve behavior that invokes model subprocesses.
- Keep `README.md`, `SKILL.md`, `tests.md`, and reference docs aligned when changing workflow semantics.
- Add or update tests for loop, eval, dashboard, and migration behavior.

## Documentation Guidelines

- Use the project name `autoresearch-agent`.
- Describe Claude Code, Codex, Gemini CLI, Pi, Hermes, and similar tools as active harnesses, not subprocess backends.
- If adding harness-specific notes, keep the generic no-headless contract first.

## Git Hygiene

- Do not commit `autoresearch-results/`, snapshots, caches, or local virtualenvs.
- Keep experiments on feature branches.
- Include validation output in PR descriptions.
