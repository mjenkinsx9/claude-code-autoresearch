---
name: autoresearch
description: >-
  Use when a user wants an autonomous, measurable modify -> verify -> keep/discard loop for improving a skill, prompt, document, or code file. Runs with Claude Code, Hermes, or a custom agent command. Use for /autoresearch, /autoresearch-plan, /autoresearch-security, "iterate until the score improves", "run overnight", or similar measurable optimization requests.
version: 1.2.0
author: Mike Jenkins
license: MIT
argument-hint: "[plan|security|run] [goal or target]"
metadata:
  hermes:
    tags: [autoresearch, autonomous-iteration, evaluation, optimization, skills, prompts]
    related_skills: [systematic-debugging, test-driven-development]
---

# Autoresearch — Autonomous Goal-directed Iteration

Autoresearch is a controlled experiment loop:

modify -> verify -> score -> keep or discard -> log -> repeat

The loop is useful only when the target has a measurable objective. It is not a general "make it better" mode. Establish a baseline first, change one thing at a time, and keep only changes that improve the metric or tie the metric with a simpler target.

## When to Use

Use this skill when the user asks to:

- Run `/autoresearch`
- Run `/autoresearch-plan`
- Run `/autoresearch-security`
- Improve a skill, prompt, markdown file, or code file against a numeric metric
- Iterate autonomously until a score improves
- Run an overnight or bounded experiment loop
- Optimize against binary eval criteria
- Compare candidate changes with a keep/discard decision

Do not use this skill when:

- There is no mechanical or LLM-judged score
- The task touches production infrastructure or datacenter systems without explicit change approval
- The target is broad enough that one-change experiments cannot isolate cause and effect
- The user wants a one-off edit rather than a measured loop

## Subcommands and Modes

| Mode | Purpose |
|---|---|
| `/autoresearch` | Run the modify -> verify -> keep/discard loop |
| `/autoresearch-plan` | Interview for goal, scope, metric, direction, and verify command |
| `/autoresearch-security` | Run a STRIDE + OWASP + red-team audit loop |

In Hermes, these are skill triggers rather than native slash commands. If the user writes `/autoresearch`, load this skill and run the appropriate workflow.

## Backend Support

The Python scripts can call different agent CLIs.

Default behavior:

1. Try Claude Code CLI if `claude` is installed
2. Fall back to Hermes CLI if `hermes` is installed

Override with CLI flags:

```bash
python scripts/autoresearch_loop.py \
  --target target.md \
  --program program.md \
  --eval-config eval.json \
  --agent-backend hermes \
  --max-experiments 5
```

Supported backend flags:

| Backend | Command behavior |
|---|---|
| `auto` | Try `claude`, then `hermes` |
| `claude` | Run `claude -p <prompt> --output-format text` |
| `hermes` | Run `hermes chat -Q -q <prompt>` |
| `custom` | Run a user-supplied command template |

Useful environment variables:

```bash
export AUTORESEARCH_AGENT_BACKEND=hermes
export AUTORESEARCH_HERMES_MODEL=gpt-5.5

# Optional custom command. It must print the final response to stdout.
export AUTORESEARCH_AGENT_BACKEND=custom
export AUTORESEARCH_AGENT_CMD='my-agent-command --prompt-file {prompt_file} --model {model}'
```

Custom command placeholders:

- `{prompt_file}` — path to a temporary UTF-8 file containing the prompt
- `{prompt}` — shell-quoted prompt text
- `{model}` — shell-quoted model string

Prefer `{prompt_file}` for large prompts.

## Mandatory Baseline Gate

Do not start the loop until the baseline is real.

Checklist:

- [ ] The target file exists and is inside the allowed root
- [ ] The metric command or eval suite runs once successfully
- [ ] The baseline score is recorded
- [ ] The user has approved the scope of files the loop may edit
- [ ] A guard command is identified or explicitly omitted

If there is no baseline number, stop and create one first.

## Setup Phase

1. Read the target and surrounding context.
2. Define the goal as one quantifiable metric.
3. Define the editable scope as explicit files or patterns.
4. Define a guard command when regressions matter.
5. Create or confirm `program.md`.
6. Create or confirm `eval.json`.
7. Run the baseline.
8. Start the bounded or unbounded loop.

Minimal files:

```text
program.md        Human strategy, constraints, and scope
eval.json         Criteria and test prompts
target.md         File being optimized
autoresearch-results/results.tsv
```

## Eval Modes

### Mechanical Mode

A command produces a parseable score. The loop maximizes it.

Examples:

```bash
npm test -- --coverage
python benchmark.py
./validate.sh
```

Use this when the quality signal is objective: coverage, latency, throughput, line count, pass count, bundle size, or an explicit score.

### Binary Eval Mode

An agent judges yes/no criteria across test prompts. Score is:

criteria passed / total criteria

Example `eval.json`:

```json
{
  "criteria": [
    {"id": 1, "question": "Does the output follow the requested format?"},
    {"id": 2, "question": "Does it avoid placeholder text?"},
    {"id": 3, "question": "Would this be usable without more edits?"}
  ],
  "test_prompts": [
    "Summarize a 5-file PR into release notes",
    "Explain a failed CI run from a log excerpt"
  ]
}
```

Run the judge directly:

```bash
python scripts/eval_engine.py \
  --eval-config eval.json \
  --output-dir ./outputs/ \
  --agent-backend hermes
```

## Loop Protocol

For each experiment:

1. Review current target, recent git history, and `results.tsv`.
2. Pick one focused change.
3. Apply that single change.
4. Execute test prompts or mechanical verification.
5. Run the guard command if configured.
6. Score the result.
7. Decide:
   - Higher score -> keep
   - Same score with simpler target -> keep
   - Worse score -> revert
   - Crash or judge failure -> revert and log as crash
8. Append the result to `results.tsv`.
9. Repeat until interrupted, bounded count reached, or stuck threshold hit.

## Running the Script

Bounded smoke run:

```bash
python scripts/autoresearch_loop.py \
  --target target.md \
  --program program.md \
  --eval-config eval.json \
  --runs-per-experiment 1 \
  --max-experiments 2 \
  --agent-backend hermes
```

Notes:

- `--max-experiments 0` means unlimited.
- `--allowed-root` defaults to the current working directory.
- `.py` targets require `--allow-exec` because the loop rewrites and executes that file.
- Do not pass `--allow-exec` unless the sandbox and target are intentionally disposable.
- `--guard "<command>"` runs after every keep-eligible experiment (score improvement, or score tie with smaller file); if it exits non-zero the change is discarded.

## Security Mode

For `/autoresearch-security`, load `references/security-workflow.md`.

Use it for scoped audits against code that can be inspected and tested. Log findings with file paths, evidence, severity, and reproduction notes. Do not auto-fix broad security issues unless the user explicitly asks.

## Planning Mode

For `/autoresearch-plan`, load `references/plan-workflow.md`.

The output is a ready run configuration:

- Goal
- Scope
- Metric
- Direction
- Verify command
- Guard command
- Bounded or unbounded loop choice

Dry-run the verify command before declaring the plan ready.

## Reference Files

Load only when needed:

| File | When |
|---|---|
| `references/autonomous-loop-protocol.md` | Running the core loop |
| `references/plan-workflow.md` | Planning a run |
| `references/security-workflow.md` | Security audit mode |
| `references/core-principles.md` | Reviewing the seven principles |
| `references/results-logging.md` | Managing `results.tsv` |
| `references/eval-criteria-guide.md` | Writing binary criteria |
| `references/program-template.md` | Creating `program.md` |

## Common Pitfalls

1. Starting without a baseline.
   - Fix: run the metric first and record the score.

2. Stacking multiple changes.
   - Fix: one focused change per experiment.

3. Using subjective scoring.
   - Fix: write binary criteria or use a mechanical metric.

4. Forgetting to revert failures.
   - Fix: failed, worse, crashed, and judge-error runs revert to the prior kept state.

5. Running on a live production path.
   - Fix: copy targets into a disposable branch or workspace before starting.

6. Assuming Claude Code is required.
   - Fix: use `--agent-backend hermes` or a custom command template.

## Verification Checklist

- [ ] `python scripts/autoresearch_loop.py --help` shows `--agent-backend`
- [ ] `python scripts/eval_engine.py --help` shows `--agent-backend`
- [ ] A custom backend smoke test completes a bounded run
- [ ] Hermes can load the skill with `skill_view autoresearch`
- [ ] The Library catalog includes `autoresearch`
