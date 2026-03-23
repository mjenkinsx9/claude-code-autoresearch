# claude-code-autoresearch

Autonomous self-improvement loop for skills, prompts, plugins, code, and any text artifact with measurable output. Based on Karpathy's [autoresearch](https://github.com/karpathy/autoresearch) methodology.

## Overview

Give it a file to change, instructions on what to optimize, and a way to measure whether it got better. Then let it run — it modifies, tests, scores, keeps winners, discards losers, and repeats indefinitely.

## Quick Start

```bash
# Install into your Claude Code skills directory
# Place SKILL.md at ~/.claude/skills/autoresearch/SKILL.md (personal)
# or .claude/skills/autoresearch/SKILL.md (project)

# Run the loop
/autoresearch
Goal: Optimize my skill file

# Or with iteration limit
/loop 25 /autoresearch
Goal: Increase test coverage to 90%
```

## The Three Components

| Component | What it is | Who creates it | Who edits it |
|-----------|-----------|---------------|--------------|
| **Target file** | The artifact being improved (skill, prompt, code, email copy, etc.) | User provides | Agent edits during experiments |
| **program.md** | Human-written instructions guiding the agent's experiments | Human creates | Human edits (read-only) |
| **Eval suite (`eval.json`)** | Binary yes/no questions scored out of N to measure quality | Human + agent collaborate | Fixed during a run |

## How It Works

1. **Read the target file** — understand what you're optimizing
2. **Create the eval suite** — define binary yes/no criteria in `eval.json`
3. **Create `program.md`** — specify goals, constraints, and strategy
4. **Initialize and run** — establish baseline, then iterate
5. **Present results** — best version + `results.tsv` research log

## Eval Modes

### Mechanical Mode (Default)
A bash command that outputs a parseable number. Maximizes this number.

```bash
npm test --coverage | grep pct
npm run bench | grep "ops/sec"
```

### Binary Eval Mode (LLM-judged)
A suite of yes/no criteria judged by an LLM. Maximizes yes-answers.

```bash
python scripts/eval_engine.py \
  --eval-config eval.json \
  --output-dir ./outputs/
```

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/autoresearch_loop.py` | Full autonomous experiment loop |
| `scripts/eval_engine.py` | Binary yes/no scoring against criteria |
| `scripts/generate_dashboard.py` | HTML dashboard from results.tsv |

## Environment Notes

- **Claude Code**: Place in `~/.claude/skills/autoresearch/` (personal) or `.claude/skills/autoresearch/` (project)
- **Cowork**: Works in Cowork sessions via file snapshots
- Use git for versioning experiments

## Reference Files

- `references/autonomous-loop-protocol.md` — Full iteration protocol
- `references/eval-criteria-guide.md` — How to write effective binary criteria
- `references/program-template.md` — Template for program.md
- `references/plan-workflow.md` — Planning wizard protocol
- `references/security-workflow.md` — STRIDE + OWASP security audit
- `references/core-principles.md` — 7 universal principles
- `references/results-logging.md` — Results log management
