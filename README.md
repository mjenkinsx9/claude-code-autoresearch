# autoresearch-agent

[![Release](https://img.shields.io/badge/release-2.0.0-brightgreen?style=flat)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE)

**A no-headless, harness-agnostic autoresearch loop for Claude Code, Codex, Gemini CLI, Pi, Hermes, and other agent runtimes.**

Based on [Karpathy's autoresearch](https://github.com/karpathy/autoresearch): constraint + metric + autonomous iteration = compounding gains.

The important design choice: **the agent runs inside your active harness session.** `autoresearch-agent` does not shell out to paid or limited print/headless model commands. The helper scripts are deterministic only: verification, guard checks, snapshots, keep/discard, scoring, and dashboards.

Architecture overview: [assets/architecture.svg](assets/architecture.svg).

---

## What It Does

Give the active agent:

1. a target file or multi-file set (`--target` / `--targets`),
2. a measurable metric (`--metric` or `--metric-regex`),
3. a verify command (optional private/held-out verify),
4. an optional guard command,
5. optional budgets (`--max-experiments`, `--max-wall-seconds`),
6. and permission to iterate.

Then the active harness follows the loop:

```text
read state -> make ONE change -> run verify -> run guard -> score -> keep/discard -> log -> repeat
```

The model work happens in your existing Claude Code/Codex/Gemini/Pi/Hermes session. The scripts do not invoke another model.

---

## Install

```bash
git clone https://github.com/mjenkinsx9/autoresearch-agent.git
```

### Agent Skills-compatible harnesses

Copy or symlink this directory into the skill location for your harness.

Examples:

```bash
# Claude Code
mkdir -p ~/.claude/skills
cp -R autoresearch-agent ~/.claude/skills/autoresearch

# Pi
mkdir -p ~/.pi/agent/skills
cp -R autoresearch-agent ~/.pi/agent/skills/autoresearch

# Hermes
mkdir -p ~/.hermes/skills/autoresearch
cp -R autoresearch-agent/* ~/.hermes/skills/autoresearch/

# Codex / Gemini CLI / other harnesses
# Use this repo as a local instruction pack and run the Python helper scripts
# from the project being optimized.
```

---

## Quick Start: Mechanical Metric

1. Establish a baseline (prefer a **named** metric and a mechanical budget):

```bash
python scripts/autoresearch_loop.py baseline \
  --target target.md \
  --verify-command './score.sh' \
  --metric Score \
  --direction higher \
  --guard-command 'npm test' \
  --max-experiments 10
```

Prefer `--metric Score` (parses the last `Score: <number>` line) over a bare last-number fallback. Use `--metric-regex` when you need a custom pattern. Print the metric **last**; put progress on stderr.

`--max-experiments` counts **candidate** scores after baseline. When exhausted, `score` exits **2** with `BUDGET_EXCEEDED` and does not mutate targets. Optional: `--max-wall-seconds`.

2. Ask the active harness to run autoresearch:

```text
/autoresearch
Goal: Improve target.md score.
Target: target.md
Verify: ./score.sh
Metric: Score
Direction: higher
Guard: npm test
Max experiments: 10
```

3. For each candidate change, the active harness runs:

```bash
python scripts/autoresearch_loop.py score \
  --target target.md \
  --description 'short description of the one change'
```

The helper keeps improvements, reverts regressions to the best snapshot, and appends `autoresearch-results/results.tsv`. Mid-run changes to sealed fields (verify/guard/metric/direction/private-verify/cwd/targets) require `--allow-config-change`.

To restart a run in the same output dir: `baseline ... --force` (replaces `state.json` and rotates the old TSV to a unique `results.prev.<timestamp>.tsv` — never overwrites a prior archive).

Machine-readable status:

```bash
python scripts/autoresearch_loop.py status --json
python scripts/autoresearch_loop.py results --json --last 10
python scripts/autoresearch_loop.py best --json
```

Each `score` also prints parseable tokens on stdout, e.g. `STATUS=keep`, `EXPERIMENT=002`, `DECISION=1.5`, `BEST=1.5`. Budget blocks print `STATUS=budget_exceeded` and exit 2. Full token list: [`references/machine-tokens.md`](references/machine-tokens.md).

---

## Quick Start: Multi-target + private metric

```bash
# Snapshot/revert several files together
python scripts/autoresearch_loop.py baseline \
  --targets features.py model.py \
  --verify-command 'python evaluate.py' \
  --metric Score \
  --direction higher \
  --max-experiments 20

# Optional held-out decision metric (keep/discard uses private; public still logged)
python scripts/autoresearch_loop.py baseline \
  --target prompt.md \
  --verify-command 'python eval_public.py' \
  --private-verify-command 'python eval_private.py' \
  --metric Score \
  --direction higher
```

After a discard, the next experiment’s parent is the **best keep** (not the failed id). Fork without resealing metrics:

```bash
python scripts/autoresearch_loop.py fork \
  --output-dir ./autoresearch-results/ \
  --lineage explore-alt \
  --description 'try a different strategy from best'
```

---

## Quick Start: Harness-judged Binary Eval

For prompts, skills, and documents where quality is not naturally numeric, use binary criteria. The helper emits a judge prompt for the active harness instead of calling a model subprocess.

```bash
python scripts/eval_engine.py \
  --eval-config examples/prompt-optimization.json \
  --output-dir ./outputs \
  --emit-prompt \
  --prompt-file ./autoresearch-results/judge-prompt.md
```

The active harness reads the prompt, writes JSON judgments, then scores them:

```bash
python scripts/eval_engine.py \
  --eval-config examples/prompt-optimization.json \
  --output-dir ./outputs \
  --judgments-file ./autoresearch-results/judgments.json \
  --results-file ./autoresearch-results/eval-results.json
```

Judgments hard-fail on overcount, duplicate criterion ids, or judgment count ≠ outputs unless `--allow-partial-judgments`. Outputs are wrapped as untrusted data in the judge prompt.

---

## Helper Scripts

| Script | Purpose | Calls an LLM? |
|---|---|---|
| `scripts/autoresearch_loop.py` | Mechanical verify/guard/snapshot/keep-discard; budgets; lineage; multi-target; private verify; JSON status; fork | No |
| `scripts/eval_engine.py` | Emits binary-eval judge prompts and scores supplied judgments | No |
| `scripts/generate_dashboard.py` | Builds an HTML dashboard from `results.tsv` (decision best, not public spikes) | No |
| `scripts/agent_cli.py` | Compatibility notice for the removed headless adapter | No |

Subcommands on the loop helper: `baseline`, `score`, `run-verify`, `status`, `results`, `best`, `fork`.

See `references/eval-script-guide.md` and `examples/mechanical/` for frozen-eval patterns.

---

## Results Layout

```text
autoresearch-results/
├── state.json                     # best score/snapshot, sealed config, budgets
├── results.tsv                    # experiment log (parent, lineage, private_score)
├── snapshots/                     # experiment_NNN_status/ + manifest.json
└── runs/
    └── experiment_002/
        ├── verify.txt
        ├── private_verify.txt     # if private verify configured
        └── guard.txt
```

Generate a dashboard:

```bash
python scripts/generate_dashboard.py \
  --results autoresearch-results/results.tsv \
  --output autoresearch-results/dashboard.html
```

---

## The Three Core Files

| File | What it is | Who edits it |
|---|---|---|
| **Target** | Artifact being improved: skill, prompt, code, docs, copy | Active agent during experiments |
| **program.md** | Human strategy, constraints, scope, and success notes | Human / active agent during setup |
| **eval.json** | Binary criteria and test prompts for harness-judged evals | Fixed during a run |

Keep **evaluate.py** frozen when possible — the agent should not rewrite the scorer.

---

## Critical Rules

| # | Rule | Why |
|---|---|---|
| 1 | **No headless model commands** | The loop must work inside any active harness without spawning a second paid/limited model process. |
| 2 | **One change per iteration** | Isolate cause and effect. |
| 3 | **Real baseline first** | Without a baseline, keep/discard has no meaning. |
| 4 | **Mechanical verification where possible** | Use numbers, not vibes. |
| 5 | **Guard regressions** | A metric can improve while behavior breaks. |
| 6 | **Automatic rollback** | Worse, crashed, or guard-failing candidates revert to the best snapshot. |
| 7 | **Preserve the log** | `results.tsv` is the research map for future agents. |
| 8 | **Stop on budgets / stop rules** | Prefer `--max-experiments` / `--max-wall-seconds`; do not ignore production/secrets stop rules. |

---

## Common Harness Notes

- **Claude Code:** load the skill and run the loop in the active session; do not use print/headless mode.
- **Codex:** keep the active Codex session in charge of edits and tool calls; use helper scripts only for deterministic scoring.
- **Gemini CLI:** run the skill/protocol in the active CLI session; use helper scripts for verify/guard/logging.
- **Pi:** install under `~/.pi/agent/skills` or load as a local skill; use Pi tools for edits and commands.
- **Hermes:** install as a Hermes skill; Hermes remains the active agent rather than a subprocess backend.

---

## Repository Structure

```text
autoresearch-agent/
├── README.md
├── AGENTS.md
├── CHANGELOG.md
├── SKILL.md
├── assets/
│   └── architecture.svg
├── examples/
│   ├── code-optimization.json
│   ├── prompt-optimization.json
│   ├── skill-optimization.json
│   └── mechanical/
│       ├── hello-length/
│       ├── constrained-compress/
│       └── multitarget-api/
├── references/
│   ├── autonomous-loop-protocol.md
│   ├── core-principles.md
│   ├── eval-criteria-guide.md
│   ├── eval-script-guide.md
│   ├── plan-workflow.md
│   ├── program-template.md
│   ├── results-logging.md
│   └── security-workflow.md
├── scripts/
│   ├── agent_cli.py
│   ├── autoresearch_loop.py
│   ├── eval_engine.py
│   └── generate_dashboard.py
├── tests/
└── tests.md
```

---

## License

MIT — see [LICENSE](LICENSE).
