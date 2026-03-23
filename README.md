# claude-code-autoresearch

**Turn [Claude Code](https://docs.anthropic.com/en/docs/claude-code) into a relentless self-improvement engine.**

Based on [Karpathy's autoresearch](https://github.com/karpathy/autoresearch) — constraint + mechanical metric + autonomous iteration = compounding gains.

[![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill-blue?style=flat&logo=anthropic&logoColor=white)](https://docs.anthropic.com/en/docs/claude-code)
[![Based on Karpathy's Autoresearch](https://img.shields.io/badge/Based%20on-Karpathy's%20Autoresearch-orange?style=flat&logo=github&logoColor=white)](https://github.com/karpathy/autoresearch)
[![MIT License](https://img.shields.io/badge/License-MIT-green?style=flat&logo=github&logoColor=white)](LICENSE)

---

_"Set the GOAL → Claude runs the LOOP → You wake up to results"_

_You don't need AGI. You need a goal, a metric, and a loop that never quits._

---

## What It Does

Give it a file to optimize, a way to measure quality, and a goal. Then walk away.

Claude will **modify → test → score → keep winners → discard losers → repeat** — indefinitely, without pausing for permission.

```
  ┌─────────────────────────────────────────────────────┐
  │                    THE LOOP                         │
  │                                                     │
  │   1. Review current state + git history + log       │
  │   2. Pick ONE change based on what worked           │
  │   3. Make the change + git commit                   │
  │   4. Run verification (tests, benchmarks, scores)   │
  │   5. Score improved? → KEEP. Worse? → REVERT.       │
  │   6. Log result + repeat                            │
  │                                                     │
  │   Never stops unless you interrupt it.              │
  └─────────────────────────────────────────────────────┘
```

---

## Quick Start

**1. Install**

```bash
# Clone the repo
git clone https://github.com/mjenkinsx9/claude-code-autoresearch.git

# Copy the skill to your Claude Code skills directory
cp -r claude-code-autoresearch ~/.claude/skills/autoresearch
```

**2. Run**

```bash
/autoresearch
Goal: Improve my skill routing accuracy from 62% to 90%
```

**3. Walk Away**

Claude reads the skill, establishes a baseline, and starts iterating. One change at a time. Auto-revert on failure. Never asks for permission.

---

## Real Example: Email Skill Optimization

```
experiment    score    max_score    status    description
001          28/48    48          keep      baseline — original email skill
002          35/48    48          keep      added explicit CTA instruction  (+7)
003          33/48    48          discard   word limit broke tone
004          37/48    48          keep      restructured with progressive disclosure  (+2)
```

**Baseline** (001): 28/48 — CTA criterion fails 6/9 times, word limit fails 4/9.

**Experiment 002**: Add instruction: "Every email MUST end with exactly one specific call-to-action." → Score: 35/48. **KEEP.**

**Experiment 003**: Add word count constraint: "Keep emails under 150 words." → Score: 33/48. Tone regressed. **REVERT to 002.**

---

## Use Cases

| Goal | Eval Approach | Example |
|------|--------------|---------|
| Skill routing accuracy | Binary criteria judged by LLM | 62% → 90% routing accuracy |
| Test coverage | `npm test --coverage` parses to % | 72% → 85% coverage |
| API latency | Benchmark script outputs ms | 240ms → 180ms p99 |
| Code readability | LLM judges clarity + naming | Readability score improving |
| Email response rates | LLM judges CTA + tone | Yes-answers compound over runs |
| Bundle size | Build script outputs KB | 420KB → 310KB |

---

## The Three Components

| Component | What it is | Who creates | Who edits |
|-----------|-----------|-------------|-----------|
| **Target file** | Artifact being improved (skill, prompt, code, email copy) | User provides | Agent edits during experiments |
| **program.md** | Human-written instructions: goals, constraints, strategy | Human creates | Human edits (read-only for agent) |
| **Eval suite (`eval.json`)** | Binary yes/no questions scored out of N | Human + agent collaborate | Fixed during a run |

---

## Eval Modes

### Mechanical Mode — Bash Command Output (Default)

A shell command that outputs a parseable number. The loop maximizes it.

```bash
# Test coverage
npm test --coverage 2>&1 | grep "All files" | awk '{print $NF}'

# Operations per second
npm run bench 2>&1 | grep "ops/sec" | awk '{print $4}'

# Custom validation (exits 0 + outputs score)
./validate.sh  # → "Score: 72"
```

### Binary Eval Mode — LLM-Judged Criteria

A suite of yes/no criteria evaluated by an LLM. Maximizes yes-answers.

```json
{
  "criteria": [
    {"id": 1, "question": "Does the output follow the specified format?"},
    {"id": 2, "question": "Are all required sections present?"},
    {"id": 3, "question": "Is the output free of placeholder text?"},
    {"id": 4, "question": "Would the output be usable without further editing?"}
  ],
  "test_prompts": [
    "Create a project status report for a web redesign project that is 60% complete",
    "Generate a summary of key findings from a customer satisfaction survey"
  ]
}
```

Run via:
```bash
python scripts/eval_engine.py \
  --eval-config eval.json \
  --output-dir ./outputs/
```

---

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/autoresearch_loop.py` | Full autonomous experiment loop |
| `scripts/eval_engine.py` | Binary yes/no scoring against criteria |
| `scripts/generate_dashboard.py` | HTML dashboard from results.tsv |

---

## Critical Rules

| # | Rule | Why |
|---|------|-----|
| 1 | **One change per iteration** | Atomic changes. If it breaks, you know exactly why. |
| 2 | **Mechanical verification only** | No subjective "looks good." Use metrics. |
| 3 | **Automatic rollback** | Failed changes revert instantly. No debates. |
| 4 | **Simplicity wins** | Equal results + less code = KEEP. |
| 5 | **Git is memory** | Every kept change committed. Agent reads history to learn. |
| 6 | **Never pause mid-loop** | Once started, never ask for permission. The human may be asleep. |
| 7 | **When stuck, think harder** | Re-read files, combine near-misses, try radical changes. |
| 8 | **Guard against regressions** | Add `Guard: npm test` to prevent breaking existing behavior. |

---

## Common Mistakes

| Mistake | The fix |
|---------|--------|
| Asking the human mid-loop | The #1 failure. Once started, never pause. |
| Stacking multiple changes | You can't tell what helped. One at a time. |
| Vague eval criteria | "Is it good?" is useless. "Does it include a specific CTA?" is testable. |
| Forgetting to revert | If score doesn't improve, you MUST revert before next experiment. |
| Not logging failures | Failed experiments are data. Always log them. |

---

## Research Log — The Most Valuable Output

The `results.tsv` research log is worth more than the optimized file itself.

- The **optimized file** is a snapshot.
- The **log** is a map of the entire optimization landscape — what worked, what didn't, and why.
- When a better model comes along, hand it the log and it picks up exactly where you left off — skipping all the dead ends.

Always preserve `results.tsv`. Never delete or overwrite it.

---

## Repository Structure

```
claude-code-autoresearch/
├── README.md
├── LICENSE
├── SKILL.md                          ← Main skill (drop into .claude/skills/)
├── examples/
│   ├── skill-optimization.json       ← Eval config for SKILL.md files
│   ├── prompt-optimization.json      ← Eval config for prompt templates
│   └── code-optimization.json        ← Eval config for scripts
├── references/
│   ├── autonomous-loop-protocol.md   ← Full iteration protocol
│   ├── core-principles.md            ← 7 universal principles
│   ├── eval-criteria-guide.md        ← How to write binary criteria
│   ├── program-template.md           ← program.md template
│   ├── plan-workflow.md             ← Planning wizard protocol
│   ├── security-workflow.md         ← STRIDE + OWASP audit
│   └── results-logging.md           ← Results log management
└── scripts/
    ├── autoresearch_loop.py          ← Full autonomous loop
    ├── eval_engine.py               ← Binary yes/no scoring
    └── generate_dashboard.py        ← HTML results dashboard
```

---

## Credits

- **[Andrej Karpathy](https://github.com/karpathy)** — for [autoresearch](https://github.com/karpathy/autoresearch)
- **[Anthropic](https://anthropic.com/)** — for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and the skills system

---

## License

MIT — see [LICENSE](LICENSE).
