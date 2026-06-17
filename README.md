# autoresearch-agent

**A no-headless, harness-agnostic autoresearch loop for Claude Code, Codex, Gemini CLI, Pi, Hermes, and other agent runtimes.**

Based on [Karpathy's autoresearch](https://github.com/karpathy/autoresearch): constraint + metric + autonomous iteration = compounding gains.

The important design choice: **the agent runs inside your active harness session.** `autoresearch-agent` does not shell out to paid or limited print/headless model commands. The helper scripts are deterministic only: verification, guard checks, snapshots, keep/discard, scoring, and dashboards.

---

## What It Does

Give the active agent:

1. a target file or scoped file set,
2. a measurable metric,
3. a verify command,
4. an optional guard command,
5. and permission to iterate.

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

1. Establish a baseline:

```bash
python scripts/autoresearch_loop.py baseline \
  --target target.md \
  --verify-command './score.sh' \
  --metric-regex 'Score: ([0-9.]+)' \
  --direction higher \
  --guard-command 'npm test'
```

2. Ask the active harness to run autoresearch:

```text
/autoresearch
Goal: Improve target.md score.
Target: target.md
Verify: ./score.sh
Metric regex: Score: ([0-9.]+)
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

The helper keeps improvements, reverts regressions to the best snapshot, and appends `autoresearch-results/results.tsv`.

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

---

## Helper Scripts

| Script | Purpose | Calls an LLM? |
|---|---|---|
| `scripts/autoresearch_loop.py` | Mechanical verify/guard/snapshot/keep-discard state manager | No |
| `scripts/eval_engine.py` | Emits binary-eval judge prompts and scores supplied judgments | No |
| `scripts/generate_dashboard.py` | Builds an HTML dashboard from `results.tsv` | No |
| `scripts/agent_cli.py` | Compatibility notice for the removed headless adapter | No |

---

## Results Layout

```text
autoresearch-results/
├── state.json                     # current best score/snapshot
├── results.tsv                    # experiment log
├── snapshots/                     # kept/discarded/crashed candidate files
└── runs/
    └── experiment_002/
        ├── verify.txt             # verify command output
        └── guard.txt              # guard command output, if configured
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
├── SKILL.md
├── examples/
│   ├── code-optimization.json
│   ├── prompt-optimization.json
│   └── skill-optimization.json
├── references/
│   ├── autonomous-loop-protocol.md
│   ├── core-principles.md
│   ├── eval-criteria-guide.md
│   ├── plan-workflow.md
│   ├── program-template.md
│   ├── results-logging.md
│   └── security-workflow.md
├── scripts/
│   ├── agent_cli.py
│   ├── autoresearch_loop.py
│   ├── eval_engine.py
│   └── generate_dashboard.py
└── tests.md
```

---

## License

MIT — see [LICENSE](LICENSE).
