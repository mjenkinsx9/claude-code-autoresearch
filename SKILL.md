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

**Core idea:** You are an autonomous agent. Modify -> Verify -> Keep/Discard -> Repeat.

## Subcommands

| Subcommand | Purpose |
|------------|---------|
| `/autoresearch` | Run the autonomous loop (default) |
| `/autoresearch-plan` | Interactive wizard: Goal -> Scope, Metric, Direction, Verify |
| `/autoresearch-security` | STRIDE + OWASP + red-team security audit |

### /autoresearch-security
Load `references/security-workflow.md` for full protocol. Iteratively tests vulnerability vectors, logs findings with code evidence, generates report in `security/` folder.

### /autoresearch-plan
Load `references/plan-workflow.md`. Converts plain-language goal into validated configuration. Dry-runs verify command before accepting.

## When to Activate

- `/autoresearch` → run the loop
- `/autoresearch-plan` or "help me set up autoresearch" → run planning wizard
- `/autoresearch-security` or "security audit"/"threat model"/"OWASP"/"STRIDE"/"find vulnerabilities" → run security audit
- "work autonomously"/"iterate until done"/"keep improving"/"run overnight" → run the loop
- Any task requiring repeated iteration cycles with measurable outcomes → run the loop

## Forge Observability Integration

```
forge_run_start(skill_name: "autoresearch", phase: "<subcommand>")
forge_run_end(run_id: "<from start>", outcome: "success"|"failure", summary: "<summary>")
```

## Loop Count Control

**Unlimited (default):** Runs until interrupted.
**Bounded:** Use `/loop N /autoresearch` for exactly N iterations, then prints final summary.

## Eval Modes

### Mechanical Mode (Default)
Bash command outputs a parseable number. Loop maximizes this number.

**Examples:** `npm test --coverage | grep pct`, `npm run bench | grep "ops/sec"`, `./validate.sh`

### Binary Eval Mode (LLM-judged)
Suite of yes/no criteria judged by LLM. Score = (total yes) / (criteria × runs × prompts).

**Setup:** Create `eval.json` with criteria, create `program.md` with instructions, run via `python ${CLAUDE_SKILL_DIR}/scripts/autoresearch_loop.py`. See `references/eval-criteria-guide.md`.

## Python Infrastructure

### eval_engine.py
Scores outputs against binary criteria.
```bash
python ${CLAUDE_SKILL_DIR}/scripts/eval_engine.py --eval-config eval.json --output-dir ./outputs/ --results-file ./results.json
```

### autoresearch_loop.py
Orchestrates the full loop. Creates `snapshots/`, `backups/`, `runs/`, `results.tsv`.
```bash
python ${CLAUDE_SKILL_DIR}/scripts/autoresearch_loop.py --target target.md --program program.md --eval-config eval.json
```

### generate_dashboard.py
Creates HTML dashboard from results.tsv.

---

## ⛔ BASELINE GATE — STOP. READ THIS FIRST.

```
╔═══════════════════════════════════════════════════════════════════╗
║  ⛔ MANDATORY BASELINE REQUIREMENT — CANNOT BE SKIPPED            ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  THE AUTONOMOUS LOOP IS DISABLED UNTIL YOU COMPLETE THIS:        ║
║                                                                   ║
║  □ Run your verify command RIGHT NOW                             ║
║  □ Capture the NUMERIC output (e.g., "73", "2.5", "0.81")        ║
║  □ Write this number down as your BASELINE                       ║
║                                                                   ║
║  ✅ IF you have a numeric baseline → Proceed to Setup Phase      ║
║  ❌ IF no numeric output → ABORT. Fix verify command first.      ║
║                                                                   ║
║  THE LOOP WILL NOT START WITHOUT A BASELINE NUMBER.              ║
║  This is not optional. This is not a suggestion.                 ║
╚═══════════════════════════════════════════════════════════════════╝
```

**Before reading any further:** Do you have a baseline number?
- **YES** → Continue to Setup Phase below
- **NO** → Stop. Run your verify command. Get a number. Then continue.

---

## Setup Phase (Complete ALL Before Loop)

- [ ] **Step 1: Read Context** — Read all in-scope files. Success: Can summarize each.
- [ ] **Step 2: Define Goal** — What does "better" mean? Success: SINGLE quantifiable metric.
- [ ] **Step 3: Define Scope** — Which files can be modified? Success: Explicit paths/patterns.
- [ ] **Step 4: Define Guard (optional)** — Command that must ALWAYS pass. Success: Guard identified OR "no guard" declared. **Validate guard by running once.**
- [ ] **Step 5: Create Results Log** — Success: Log file exists with header.
- [ ] **Step 6: Confirm Baseline** — Record the numeric baseline you captured above. Success: Baseline is a NUMBER written to results log as iteration #0.
- [ ] **Step 7: Confirm and Go** — Success: User confirms → BEGIN LOOP.

## The Loop

Read `references/autonomous-loop-protocol.md` for full details.

```
LOOP (FOREVER or N times):
  1. Review: Read current state + git history + results log
  2. Ideate: Pick next change based on goal, past results, unexplored areas
  3. Modify: Make ONE focused change to in-scope files
  4. Commit: Git commit the change (before verification)
  5. Verify: Run the mechanical metric
  6. Guard: If guard is set, run it
  7. Decide:
     - IMPROVED + guard passed (or no guard) → Keep commit, log "keep"
     - IMPROVED + guard FAILED → Revert, rework optimization (max 2 attempts) to improve WITHOUT breaking guard. If still failing → "discard (guard failed)"
     - SAME/WORSE → Git revert, log "discard"
     - CRASHED → Try to fix (max 3 attempts), else log "crash"
  8. Log: Record result with MANDATORY information gain:
     - **Novelty score (0-1):** How different from previous attempts?
     - **Lesson learned:** One sentence capturing key insight
     - **Negative results:** If discarded, document WHY it failed
  9. Repeat: Go to step 1. (Unbounded: NEVER STOP. Bounded: Stop after N.)
```

## Stuck Recovery Protocol

After **3 consecutive discards**, activate:

### Step 1: Diagnose
- Review last 5 log entries. Same failure mode or different?
- Check if metric plateaued (5+ iterations, no improvement)
- **Check novelty scores:** Recent novelty < 0.3 = rut.

### Step 2: Apply Strategy (in order)

| Strategy | When | Action |
|----------|------|--------|
| Invert | All recent changes were additions | Remove something |
| Simplify | Added complexity | Simplest possible change |
| Pivot | Same approach failing | Completely different approach |
| Backtrack | Regressed from baseline | Revert to last good, try different path |
| Expand Scope | Scope exhausted | Request expansion OR declare completion |

### Step 3: Escalation
If 5+ consecutive failures after recovery: Log "STUCK: exhaustion detected", document learnings, request human input OR switch subtask.

## Critical Rules

1. **Loop until done** — Unbounded: until interrupted. Bounded: N iterations then summarize.
2. **Read before write** — Understand context before modifying.
3. **One change per iteration** — Atomic. If breaks, you know why.
4. **Mechanical verification only** — No subjective "looks good".
5. **Automatic rollback** — Failed changes revert instantly.
6. **Simplicity wins** — Equal results + less code = KEEP. Tiny gain + ugly complexity = DISCARD.
7. **Git is memory** — Every kept change committed.
8. **When stuck, think harder** — Re-read, combine near-misses, try radical changes. Don't ask for help unless blocked.
9. **Track learning** — Every iteration records what was learned. Information gain compounds.

## Domain Adaptation

| Domain | Metric | Scope | Verify | Guard |
|--------|--------|-------|--------|-------|
| Backend | Tests + coverage | `src/**/*.ts` | `npm test` | -- |
| Frontend | Lighthouse score | `src/components/**` | `npx lighthouse` | `npm test` |
| ML | val_bpb / loss | `train.py` | `uv run train.py` | -- |
| Performance | Benchmark time | Target files | `npm run bench` | `npm test` |
| Refactoring | Tests + LOC | Target module | `npm test && wc -l` | `npm run typecheck` |
| Security | OWASP + STRIDE | API/auth/middleware | `/autoresearch-security` | -- |

## Reference Files (Load Only When Needed)

| File | When |
|------|------|
| references/autonomous-loop-protocol.md | Running `/autoresearch` core loop |
| references/plan-workflow.md | Running `/autoresearch-plan` |
| references/security-workflow.md | Running `/autoresearch-security` |
| references/core-principles.md | Reviewing 7 universal principles |
| references/results-logging.md | Managing results log |
| references/eval-criteria-guide.md | Writing binary eval criteria |
| references/program-template.md | Creating program.md |

## Example Eval Configs

- `examples/skill-optimization.json` — Optimizing SKILL.md files
- `examples/prompt-optimization.json` — Optimizing prompt templates
- `examples/code-optimization.json` — Optimizing code scripts
