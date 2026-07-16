---
name: autoresearch
version: 2.0.0
description: >-
  Run a no-headless, measurable modify -> verify -> keep/discard loop for improving a skill, prompt, document, or code file. Use for /autoresearch, /autoresearch-plan, /autoresearch-security, "iterate until the score improves", "run overnight", or similar optimization requests. The active harness does the agent work; helper scripts only run deterministic scoring, guard checks, snapshots, and logs.
author: Mike Jenkins
license: MIT
argument-hint: "[plan|security|run] [goal or target]"
metadata:
  tags: [autoresearch, autonomous-iteration, evaluation, optimization, no-headless, skills, prompts]
---

# Autoresearch Agent — No-headless Autonomous Iteration

Autoresearch Agent is a controlled experiment loop:

```text
modify -> verify -> score -> keep or discard -> log -> repeat
```

The active harness session is the agent. Do **not** spawn another model through print/headless CLI mode. This skill is meant to work inside Claude Code, Codex, Gemini CLI, Pi, Hermes, or any agent runtime that can read files, edit files, and run commands.

Helper scripts are deterministic only:

- `scripts/autoresearch_loop.py` — `baseline` / `score` / `run-verify` / `status` / `results` / `best` / `fork`
- `scripts/eval_engine.py` — emit judge prompts and score harness-supplied JSON judgments
- `scripts/generate_dashboard.py` — HTML from `results.tsv` (decision best, not public spikes)
- `scripts/agent_cli.py` — compatibility notice; legacy headless invocation is disabled

## When to Use

Use this skill when the user asks to:

- Run `/autoresearch`
- Run `/autoresearch-plan`
- Run `/autoresearch-security`
- Improve a skill, prompt, markdown file, or code file against a measurable score
- Iterate autonomously until a score improves
- Run a bounded or overnight experiment loop
- Optimize against binary eval criteria
- Compare candidate changes with a keep/discard decision

Do not use this skill when:

- There is no mechanical or harness-judged score
- The task touches production infrastructure without explicit approval
- The editable target is too broad for one-change experiments
- The user wants a one-off edit rather than a measured loop

## Mandatory No-headless Rule

Never run a second LLM via headless/print commands for autoresearch. In particular, do not build the loop around commands such as model CLI print modes. The current harness is already the model runtime.

Allowed:

- Use the active harness's normal file, shell, search, and edit tools.
- Run deterministic local commands such as tests, benchmarks, linters, parsers, and the helper scripts.
- Ask the active harness to judge outputs directly in-session, then record JSON judgments.

Not allowed:

- Shelling out to another model to generate experiments.
- Shelling out to another model to execute prompts.
- Shelling out to another model to judge outputs.

## Subcommands and Modes

| Mode | Purpose |
|---|---|
| `/autoresearch` | Run the modify -> verify -> keep/discard loop in the active harness |
| `/autoresearch-plan` | Create a validated run plan: goal, scope, metric, verify, guard, bounds |
| `/autoresearch-security` | Run a STRIDE + OWASP + red-team audit loop |

If the harness does not support slash commands, treat these as plain-text triggers and follow the matching workflow.

## Mandatory Baseline Gate

Do not start iterating until the baseline is real.

Checklist:

- [ ] Target file exists and is inside the allowed root
- [ ] Editable scope is explicit
- [ ] Verify command runs successfully
- [ ] Metric parses to a single number, or binary eval criteria are ready
- [ ] Direction is known: higher or lower is better
- [ ] Guard command is identified or explicitly omitted
- [ ] Baseline is recorded in `autoresearch-results/results.tsv`

Mechanical baseline command:

```bash
python scripts/autoresearch_loop.py baseline \
  --target target.md \
  --verify-command './score.sh' \
  --metric Score \
  --direction higher \
  --guard-command 'npm test' \
  --max-experiments 10
```

Prefer `--metric NAME` so the helper extracts the last `NAME: value` line. Use `--metric-regex` for custom patterns.

**Sealed fields** (mid-run change requires `--allow-config-change`): verify, private-verify, guard, metric, metric-regex, direction, cwd, targets.

## Core Loop Protocol

For each experiment:

1. Prefer `status --json` + last TSV rows (context diet); re-read targets after rollbacks.
2. Pick exactly one focused change.
3. Apply only that change.
4. Run scoring:

   ```bash
   python scripts/autoresearch_loop.py score \
     --target target.md \
     --description 'short description of this one change'
   ```

5. Interpret result:
   - `KEEP` — decision metric improved, or exact tie with **smaller total target bytes**.
   - `DISCARD` — helper reverted to best snapshot; next parent is best keep.
   - `CRASH` — verify/guard/private-verify failed; helper reverted.
   - Exit code **2** + `BUDGET_EXCEEDED` — stop; do not keep editing.
6. Append observations if useful.
7. Repeat until budget exhausted, user interrupts, or a stop rule triggers.

## Advanced Helper Surface

| Feature | How |
|---|---|
| Multi-file targets | `--targets a.py b.py` (snapshotted/reverted together; sealed) |
| Private / holdout metric | `--private-verify-command '...'` — **decision** score; public still logged |
| Budgets | `--max-experiments N`, `--max-wall-seconds S` at baseline |
| JSON for harnesses | `status --json` (includes `candidates_done` / `candidates_remaining` / `budget_exhausted`), `results --json --last N`, `best --json` |
| Fork from best | `fork --lineage name` (does not reseal verify/metric) |
| Strict snapshots | `--strict-snapshots` on score — fail closed on hash mismatch |
| Instructions | `--instructions path-or-text` stored in state for the harness to re-read |

Multi-target example:

```bash
python scripts/autoresearch_loop.py baseline \
  --targets features.py model.py \
  --verify-command 'python evaluate.py' \
  --metric Score \
  --direction higher \
  --max-experiments 20
```

## Mechanical Eval Mode

Use this when a command can produce a numeric metric.

Examples:

```bash
npm test -- --coverage
python benchmark.py
./validate.sh
```

Dry-run a candidate verify command before using it (include private verify when planned):

```bash
python scripts/autoresearch_loop.py run-verify \
  --verify-command './score.sh' \
  --private-verify-command './score_holdout.sh' \
  --metric Score \
  --guard-command 'npm test'
```

Metric requirements:

- Outputs or exposes one parseable number (print the metric **last**; progress on stderr)
- Prefer `--metric Name` or `--metric-regex` over the last-number fallback
- Deterministic enough for keep/discard decisions
- Fast enough to run every iteration
- Has clear direction: `higher` or `lower`

## Harness-judged Binary Eval Mode

Use this for prompts, skills, and documents where quality must be judged against binary yes/no criteria.

1. Generate outputs from the target using the active harness.
2. Emit a judge prompt:

   ```bash
   python scripts/eval_engine.py \
     --eval-config eval.json \
     --output-dir ./outputs \
     --emit-prompt \
     --prompt-file ./autoresearch-results/judge-prompt.md
   ```

3. The active harness reads the prompt and writes judgments JSON.
4. Score the judgments:

   ```bash
   python scripts/eval_engine.py \
     --eval-config eval.json \
     --output-dir ./outputs \
     --judgments-file ./autoresearch-results/judgments.json \
     --results-file ./autoresearch-results/eval-results.json
   ```

## Planning Mode

For `/autoresearch-plan`, load `references/plan-workflow.md`.

The output must include:

- Goal
- Editable scope
- Metric
- Direction
- Verify command
- Guard command or explicit omission
- Baseline value
- Bounded or unbounded loop choice

Dry-run verify and guard before declaring the plan ready.

## Security Mode

For `/autoresearch-security`, load `references/security-workflow.md`.

Use it for scoped audits against code that can be inspected and tested. Log findings with file paths, evidence, severity, and reproduction notes. Do not auto-fix broad security issues unless the user explicitly asks.

## Reference Files

Load only when needed:

| File | When |
|---|---|
| `references/autonomous-loop-protocol.md` | Running the core loop |
| `references/plan-workflow.md` | Planning a run |
| `references/security-workflow.md` | Security audit mode (harness conventions, not CLI product) |
| `references/core-principles.md` | Reviewing the principles |
| `references/results-logging.md` | Managing `results.tsv` |
| `references/eval-script-guide.md` | Writing frozen mechanical evaluate scripts |
| `references/eval-criteria-guide.md` | Writing binary criteria |
| `references/program-template.md` | Creating `program.md` |
| `examples/mechanical/` | Minimal mechanical metric examples |

## Stop Rules

Stop and report instead of continuing when:

- Verify command is invalid or flaky after three repair attempts
- Guard fails on the baseline
- The same failure mode repeats five times
- The next improvement requires changing unapproved files
- The target touches production or secrets unexpectedly
- Mechanical budget exhausted (`BUDGET_EXCEEDED` / exit 2)
- The harness-bounded experiment count is reached

Do **not** treat “never stop” as absolute — budgets and safety stop rules win.

## Common Pitfalls

1. Starting without a baseline.
   - Fix: run the baseline command and record the score.
2. Stacking multiple changes.
   - Fix: one focused change per experiment.
3. Using subjective scoring without criteria.
   - Fix: write binary criteria or use a mechanical metric.
4. Forgetting to revert failures.
   - Fix: let `autoresearch_loop.py score` do keep/discard and rollback.
5. Running a model CLI as a subprocess.
   - Fix: keep all agent work in the active harness session.
6. Letting the agent edit `evaluate.py`.
   - Fix: freeze the scorer; only mutate the target.
7. Expecting prose “Max experiments: 10” without `--max-experiments`.
   - Fix: set budgets on baseline for mechanical enforcement.

## Verification Checklist

- [ ] `python scripts/autoresearch_loop.py --help` shows `baseline`, `score`, `run-verify`, `status`, `results`, `best`, `fork`
- [ ] `baseline --help` includes `--metric`, `--max-experiments`, `--targets`, `--private-verify-command`
- [ ] `score --help` includes `--allow-config-change`, `--strict-snapshots`
- [ ] `python scripts/eval_engine.py --help` does not require an agent backend
- [ ] `python3 -m pytest tests/ -q` passes
- [ ] Binary eval can emit a prompt and score supplied judgments
- [ ] `scripts/agent_cli.py` reports that headless invocation is disabled
