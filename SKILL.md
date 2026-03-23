---
name: autoresearch
description: >-
  Autonomous goal-directed iteration engine — modify, verify, keep/discard, repeat.
  Subcommands: /autoresearch (run the loop), /autoresearch-plan (interactive config
  wizard), /autoresearch-security (STRIDE + OWASP security audit). Use for iterating
  on measurable outcomes until interrupted or a goal is reached.
version: 1.1.0
generated-status: failed
verified-at: '2026-03-16T19:07:48.819Z'
verification-score: 83
---

# Autoresearch — Autonomous Goal-directed Iteration

Inspired by [Karpathy's autoresearch](https://github.com/karpathy/autoresearch). Applies constraint-driven autonomous iteration to ANY work — not just ML research.

**Core idea:** You are an autonomous agent. Modify -> Verify -> Keep/Discard -> Repeat.

## AUTONOMOUS OPERATION

> **Once the experiment loop begins, do NOT pause to ask the human for permission, confirmation, or whether to continue.** The human may be asleep or away. You run indefinitely until manually stopped. If you run out of ideas, re-read the target, combine near-misses, try radical changes, or simplify.

## The Three Components

Every autoresearch run has exactly three parts. Do not confuse them:

| Component | What it is | Who creates it | Who edits it |
|-----------|-----------|---------------|--------------|
| **Target file** | The artifact being improved (skill, prompt, code, email copy, etc.) | User provides | Agent edits during experiments |
| **program.md** | Human-written instructions guiding the agent's experiments — constraints, strategy, goals | Human creates | Human edits (agent reads only) |
| **Eval suite (`eval.json`)** | Binary yes/no questions scored out of N to measure quality | Human + agent collaborate | Fixed during a run |

The target file is your `train.py`. The `program.md` is your research org code. The eval suite is your `val_bpb` metric. These map directly to Karpathy's architecture.

## Quick Start

When the user invokes this skill, follow this sequence immediately — do not ask clarifying questions unless the target file is genuinely ambiguous:

**Step 1: Read the Target File** — The user tells you what to optimize. Read it completely. This is your baseline.

**Step 2: Create the Eval Suite (DO THIS IMMEDIATELY)** — Define 4-8 binary yes/no evaluation criteria with the user. Each criterion must be: Binary (yes/no, no gray area), Specific, Machine-readable (another LLM can judge from output alone), and Non-gameable. Write them into `eval.json`:
```json
{
  "criteria": [
    {"id": 1, "question": "Does the output follow the specified format?"},
    {"id": 2, "question": "Are all required sections present?"},
    {"id": 3, "question": "Is the output free of placeholder text?"},
    {"id": 4, "question": "Would the output be usable without further editing?"}
  ],
  "test_prompts": [
    "A realistic input the target would receive",
    "A different realistic input",
    "An edge case or challenging input"
  ]
}
```
Aim for 4-8 criteria and 3-5 test prompts. Score = total yes / (criteria × prompts × runs).

**Step 3: Create `program.md`** — Write instructions specifying what the target does, what success looks like, constraints (don't change X), and experimentation strategy. Use `references/program-template.md` as a starting point.

**Step 4: Initialize and Run** — Create `results.tsv` with the header row. Run the target as-is to establish the baseline score (experiment 001). Start the experiment loop — either via `python ${CLAUDE_SKILL_DIR}/scripts/autoresearch_loop.py` (automated) or manually with the loop below.

**Step 5: Present Results** — When the user returns or the loop is stopped, present: the best version of the target file, the research log (`results.tsv` — the most valuable artifact), and a brief summary: experiments run, starting vs final score, the 2-3 changes that moved the needle most.

## Subcommands

| Subcommand | Purpose |
|------------|---------|
| `/autoresearch` | Run the autonomous loop (default) |
| `/autoresearch-plan` | Interactive wizard to build Scope, Metric, Direction & Verify from a Goal |
| `/autoresearch-security` | Autonomous security audit: STRIDE threat model + OWASP Top 10 + red-team |

### /autoresearch-security — Autonomous Security Audit

Load: `references/security-workflow.md` for full protocol.

STRIDE threat model + OWASP Top 10 + red-team adversarial analysis. Iteratively tests vulnerability vectors, logs findings with code evidence, generates structured report in `security/` folder. Supports `--diff`, `--fix`, and `--fail-on` flags.

### /autoresearch-plan — Goal -> Configuration Wizard

Load: `references/plan-workflow.md` for full protocol.

Interactive wizard that converts a plain-language goal into a validated, ready-to-execute autoresearch configuration (Scope, Metric, Direction, Verify). Dry-runs the verify command before accepting.

## When to Activate

- User invokes `/autoresearch` -> run the loop
- User invokes `/autoresearch-plan` -> run the planning wizard
- User invokes `/autoresearch-security` -> run the security audit
- User says "help me set up autoresearch", "plan an autoresearch run" -> run the planning wizard
- User says "security audit", "threat model", "OWASP", "STRIDE", "find vulnerabilities", "red-team" -> run the security audit
- User says "work autonomously", "iterate until done", "keep improving", "run overnight" -> run the loop
- Any task requiring repeated iteration cycles with measurable outcomes -> run the loop

## Forge Observability Integration

> **Cowork support:** Works in Cowork sessions via file snapshots. Results save to the workspace folder.

At the start of any autoresearch run, call the `forge_run_start` MCP tool:
```
forge_run_start(skill_name: "autoresearch", phase: "<subcommand>")
```

At the end of any run, call `forge_run_end` with the stored run_id:
```
forge_run_end(run_id: "<from start>", outcome: "success"|"failure", summary: "<iterations completed, metric change>")
```

## Optional: Controlled Loop Count

By default, autoresearch loops **forever** until manually interrupted. Users can specify a **loop count** using Claude Code's built-in `/loop` command.

**Unlimited (default):**
```
/autoresearch
Goal: Increase test coverage to 90%
```

**Bounded (N iterations):**
```
/loop 25 /autoresearch
Goal: Increase test coverage to 90%
```

### Behavior with Loop Count

When a loop count is specified:
- Claude runs exactly N iterations through the autoresearch loop
- After iteration N, Claude prints a **final summary** with baseline -> current best, keeps/discards/crashes
- If the goal is achieved before N iterations, Claude prints early completion and stops
- All other rules (atomic changes, mechanical verification, auto-rollback) still apply

## Eval Modes

The autoresearch loop supports two evaluation modes. Choose the one that fits your metric:

### Mechanical Mode (Default)

A bash command that outputs a parseable number. The loop maximizes this number.

**Examples:**
- `npm test --coverage | grep pct` — extracts a percentage
- `npm run bench | grep "ops/sec"` — extracts a performance metric
- `./validate.sh` — script that exits 0 for pass, outputs a score

**Setup:** Define the command and how to parse the number from its output.

### Binary Eval Mode (LLM-judged)

A suite of yes/no criteria judged by an LLM. The loop maximizes yes-answers across all criteria.

**Architecture (from Karpathy's design):**

| Karpathy | This Skill | Purpose |
|---|---|---|
| `train.py` | **Target file** | The artifact being improved |
| `program.md` | **program.md** | Human-written agent instructions |
| `val_bpb` | **Binary eval suite** | Yes/no questions scored out of N |

**Eval scoring:** Score = (total yes answers) / (criteria_count × runs × prompts)

**Setup:**
1. Create `eval.json` with binary criteria and test prompts
2. Create `program.md` with experiment instructions
3. Run via `python ${CLAUDE_SKILL_DIR}/scripts/autoresearch_loop.py`

See `${CLAUDE_SKILL_DIR}/references/eval-criteria-guide.md` for writing effective binary criteria.

## Python Eval Infrastructure

The Binary Eval Mode uses three scripts:

### eval_engine.py

Scores outputs against binary criteria using an LLM as judge.

```bash
python ${CLAUDE_SKILL_DIR}/scripts/eval_engine.py \
  --eval-config eval.json \
  --output-dir ./outputs/ \
  --results-file ./results.json
```

**Parameters:**
- `--eval-config`: JSON with `criteria` (array of `{question}`) and `test_prompts`
- `--output-dir`: Directory containing output files to evaluate, OR
- `--output`: Inline text to evaluate
- `--model`: Judge model (default: sonnet)
- `--verbose`: Print detailed progress
- `--results-file`: Path to save results JSON

### autoresearch_loop.py

Orchestrates the full autonomous loop.

```bash
python ${CLAUDE_SKILL_DIR}/scripts/autoresearch_loop.py \
  --target path/to/target.md \
  --program path/to/program.md \
  --eval-config eval.json \
  --runs-per-experiment 5 \
  --output-dir ./autoresearch-results/
```

**Parameters:**
- `--target`: Path to target file to optimize
- `--program`: Path to program.md instructions
- `--eval-config`: Path to eval config JSON
- `--runs-per-experiment`: Number of test runs per experiment (default: 5)
- `--output-dir`: Directory for results and snapshots
- `--experiment-model`: Model for generating experiments (default: opus)
- `--execution-model`: Model for executing target (default: sonnet)
- `--eval-model`: Model for evaluation judging (default: sonnet)
- `--max-experiments`: Max experiments (0 = infinite, default: 0)

The loop creates:
- `snapshots/`: Kept and discarded snapshots of the target
- `backups/`: Full backups before each experiment
- `runs/`: Per-experiment output files
- `results.tsv`: Experiment log

### generate_dashboard.py

Creates an HTML dashboard from results.tsv.

```bash
python ${CLAUDE_SKILL_DIR}/scripts/generate_dashboard.py \
  --results ./autoresearch-results/results.tsv \
  --output ./autoresearch-results/dashboard.html \
  --title "Autoresearch: Skill Optimization"
```

## Setup Phase (Do Once)

1. **Read all in-scope files** for full context before any modification
2. **Define the goal** — What does "better" mean? Extract or ask for a mechanical metric:
   - Code: tests pass, build succeeds, performance benchmark improves
   - Content: word count target hit, SEO score improves, readability score
   - Design: lighthouse score, accessibility audit passes
   - If no metric exists -> define one with user, or use simplest proxy (e.g. "compiles without errors")
3. **Define scope constraints** — Which files can you modify? Which are read-only?
4. **Define guard (optional)** — A command that must ALWAYS pass for a change to be kept. Use this to prevent regressions while optimizing the main metric (e.g., `npm test` must pass while optimizing benchmark time). If not specified, no guard is enforced.
   - **Validate the guard command at setup:** Run it once on the current codebase. If it exits non-zero, the guard is broken — warn the user and help them fix it before starting the loop.
   - **If the command doesn't exist** (e.g., `npm run typecheck` but the script isn't in package.json), either find an equivalent (e.g., `npx tsc --noEmit`) or warn that no guard will be enforced. Log the actual command that will run — not the originally specified one.
5. **Create a results log** — Track every iteration (see `references/results-logging.md`)
6. **Establish baseline** — Run verification on current state AND guard (if set). Record as iteration #0. **The baseline verify command must produce a parseable metric number.** If it does not, abort — do not start the loop with a broken verification system.
7. **Confirm and go** — Show user the setup, get confirmation, then BEGIN THE LOOP

## The Loop

Read `references/autonomous-loop-protocol.md` for full protocol details.

```
LOOP (FOREVER or N times):
  1. Review: Read current state + git history + results log
  2. Ideate: Pick next change based on goal, past results, what hasn't been tried
  3. Modify: Make ONE focused change to in-scope files
  4. Commit: Git commit the change (before verification)
  5. Verify: Run the mechanical metric (tests, benchmarks, scores)
  6. Guard: If guard is set, run the guard command
  7. Decide:
     - IMPROVED + guard passed (or no guard) -> Keep commit, log "keep", advance
     - IMPROVED + guard FAILED -> Revert, then try to rework the optimization
       (max 2 attempts) so it improves the metric WITHOUT breaking the guard.
       Never modify guard/test files — adapt the implementation instead.
       If still failing -> log "discard (guard failed)" and move on
     - SAME/WORSE -> Git revert, log "discard"
     - CRASHED -> Try to fix (max 3 attempts), else log "crash" and move on
  8. Log: Record result in results log
  9. Repeat: Go to step 1.
     - If unbounded: NEVER STOP. NEVER ASK "should I continue?"
     - If bounded (N): Stop after N iterations, print final summary
```

## Critical Rules

1. **Loop until done** — Unbounded: loop until interrupted. Bounded: loop N times then summarize.
2. **Read before write** — Always understand full context before modifying
3. **One change per iteration** — Atomic changes. If it breaks, you know exactly why
4. **Mechanical verification only** — No subjective "looks good". Use metrics
5. **Automatic rollback** — Failed changes revert instantly. No debates
6. **Simplicity wins** — Equal results + less code = KEEP. Tiny improvement + ugly complexity = DISCARD
7. **Git is memory** — Every kept change committed. Agent reads history to learn patterns
8. **When stuck, think harder** — Re-read files, re-read goal, combine near-misses, try radical changes. Don't ask for help unless truly blocked by missing access/permissions

## Common Mistakes

| Mistake | Why it matters |
|---------|---------------|
| **Asking the human mid-loop** | The #1 failure. Once started, never pause for confirmation. |
| **Stacking multiple changes** | You can't tell what helped. One change per experiment. |
| **Vague eval criteria** | "Is it good?" is useless. "Does it include a specific next step?" is testable. |
| **Forgetting to revert** | If score doesn't improve, you MUST revert before the next experiment. |
| **Not logging failures** | Failed experiments are data. Always log them. |

## The Research Log (Most Valuable Output)

The research log (`results.tsv` + version history of the target) is more valuable than the improved file itself. The improved file is a snapshot. The log is a map of the entire optimization landscape — what worked, what didn't, and why. When a better model comes along, you hand it the log and it picks up exactly where you left off, skipping all the dead ends.

Always preserve the research log. Never delete or overwrite `results.tsv`.

## Principles Reference

See `references/core-principles.md` for the 7 generalizable principles from autoresearch.

## Adapting to Different Domains

| Domain | Metric | Scope | Verify Command | Guard |
|--------|--------|-------|----------------|-------|
| Backend code | Tests pass + coverage % | `src/**/*.ts` | `npm test` | -- |
| Frontend UI | Lighthouse score | `src/components/**` | `npx lighthouse` | `npm test` |
| ML training | val_bpb / loss | `train.py` | `uv run train.py` | -- |
| Blog/content | Word count + readability | `content/*.md` | Custom script | -- |
| Performance | Benchmark time (ms) | Target files | `npm run bench` | `npm test` |
| Refactoring | Tests pass + LOC reduced | Target module | `npm test && wc -l` | `npm run typecheck` |
| Security | OWASP + STRIDE coverage + findings | API/auth/middleware | `/autoresearch-security` | -- |

Adapt the loop to your domain. The PRINCIPLES are universal; the METRICS are domain-specific.

## Reference Files

Read only when the specific subcommand or feature requires it. Do not load all at once.

| File | Read When |
|------|-----------|
| [references/autonomous-loop-protocol.md](references/autonomous-loop-protocol.md) | Running `/autoresearch` core loop — full iteration protocol |
| [references/plan-workflow.md](references/plan-workflow.md) | Running `/autoresearch-plan` — interactive config wizard |
| [references/security-workflow.md](references/security-workflow.md) | Running `/autoresearch-security` — STRIDE + OWASP audit |
| [references/core-principles.md](references/core-principles.md) | Need to review the 7 universal principles |
| [references/results-logging.md](references/results-logging.md) | Setting up or managing the iteration results log |
| [references/eval-criteria-guide.md](references/eval-criteria-guide.md) | Writing binary eval criteria for Binary Eval Mode |
| [references/program-template.md](references/program-template.md) | Creating program.md for Binary Eval Mode experiments |

## Example Eval Configs

Example eval configurations are in `examples/`:
- [examples/skill-optimization.json](examples/skill-optimization.json) — For optimizing SKILL.md files
- [examples/prompt-optimization.json](examples/prompt-optimization.json) — For optimizing prompt templates
- [examples/code-optimization.json](examples/code-optimization.json) — For optimizing code scripts
