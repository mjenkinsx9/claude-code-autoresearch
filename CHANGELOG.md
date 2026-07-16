# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **`--metric NAME`** on the loop helper: extract `name: value` / `name = value` (last match wins). Prefer this over the last-number fallback.
- **Config seal** on `score`: changing verify/guard/metric/direction mid-run requires `--allow-config-change`.
- **Snapshot sandbox**: revert refuses `best_snapshot` paths outside `output_dir/snapshots/`; stores `best_snapshot_sha256` (optional `--strict-snapshots`).
- **Directory multi-file snapshots** with `manifest.json` + `--targets`; single-target uses the same layout.
- **Parent lineage** columns (`parent_experiment`, `lineage`); after discard/crash next parent is best keep; `fork` subcommand.
- **Budgets**: `--max-experiments` (candidates after baseline), `--max-wall-seconds`; score exits 2 with `BUDGET_EXCEEDED`.
- **JSON agent surface**: `status --json`, `results --json`, `best --json`.
- **Private verify**: `--private-verify-command` drives keep/discard while public score is still logged.
- **Eval hard-fail**: judgment count/id mismatches fail closed unless `--allow-partial-judgments`; scores are clamped so `total_yes <= max_score`.
- **Untrusted-output framing** in binary-eval judge prompts (`<UNTRUSTED_OUTPUT>` + ignore-instructions language).
- `references/eval-script-guide.md` and `examples/mechanical/*` frozen-eval samples.
- Atomic `state.json` writes (`state.json.tmp` + replace); UTF-8 I/O; process-group kill on verify/guard timeout (POSIX).

### Changed
- `--timeout` default is unset so score inherits the baseline timeout (default 120s only when neither CLI nor state set it).
- Metric regex extraction uses the **last** match when multiple matches exist (metric should be printed near the end of eval output).
- Architecture SVG documents active-harness + deterministic helpers (no headless backends).
- Protocol/results-logging aligned with parent lineage, budgets, and helper guard timing.

### Removed
- Stale `docs/superpowers/` 1.x scratch plan (already claimed removed in 2.0.0).

## [2.0.0] - 2026-06-17

**The no-headless rebuild.** Autoresearch now runs entirely inside your active
agent session — Claude Code, Codex, Gemini CLI, Pi, Hermes, or any harness that
can read files, edit files, and run commands. The helper scripts no longer shell
out to a model; they are deterministic only. This is a breaking change to the CLI
and the operating model, hence the major version bump.

### Changed
- **No-headless architecture.** The active harness session *is* the agent. The
  loop no longer spawns a second model through print/headless CLI mode
  (`claude -p`, `hermes chat`, Pi `-p`, or a custom backend). The model work
  happens in your existing session; the scripts only do verification, guard
  checks, snapshots, keep/discard, scoring, and logging.
- **Harness-agnostic.** Documented and supported across Claude Code, Codex,
  Gemini CLI, Pi, and Hermes instead of being Claude/Hermes-specific.
- **`autoresearch_loop.py` is now a subcommand-based state manager** —
  `baseline`, `score`, `run-verify`, and `status` — driving a deterministic
  mechanical keep/discard loop with an explicit best-snapshot in `state.json`.
- **`eval_engine.py` is harness-judged.** It emits a judge prompt
  (`--emit-prompt`) for the active session to answer, then scores the supplied
  JSON judgments (`--judgments-file`) — no model subprocess.
- **Renamed to `autoresearch-agent`** (repository, skill identity, and docs)
  from the former `claude-code-autoresearch` branding.
- Skill metadata bumped to `version: 2.0.0`; description and references rewritten
  around the no-headless contract.

### Added
- `AGENTS.md` — generic, harness-agnostic operating instructions.
- `tests/test_no_headless.py` — coverage asserting the loop never invokes a
  headless model command, alongside rebuilt loop/eval/dashboard smoke tests.
- `state.json` in the results layout — tracks the current best score and snapshot.
- This `CHANGELOG.md`.

### Removed
- Headless model subprocess orchestration. `scripts/agent_cli.py` is now only a
  compatibility notice that reports the migration path; the legacy backend
  adapter (`--agent-backend` / `--agent-command`) is gone.
- `docs/superpowers/` development-scratch implementation plan.

## [1.0] - 2026-03

Initial public release as `claude-code-autoresearch`: the autoresearch skill,
reference docs, and a stdlib-only Python runner that drove the loop through
headless model CLIs (Claude Code, Hermes, or a custom agent command).

[2.0.0]: https://github.com/mjenkinsx9/autoresearch-agent/releases/tag/2.0.0
[1.0]: https://github.com/mjenkinsx9/autoresearch-agent/releases/tag/1.0
