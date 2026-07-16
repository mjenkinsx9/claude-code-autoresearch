# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **`--metric NAME`** on the loop helper: extract `name: value` / `name = value` (last match wins). Prefer this over the last-number fallback.
- **Config seal** on `score`: changing verify/guard/metric/direction/private-verify/**cwd**/**targets**/**max-score** mid-run requires `--allow-config-change`.
- **Snapshot sandbox**: revert refuses paths outside `snapshots/`; artifact paths cannot escape the bundle; stores `best_snapshot_sha256` with working `--strict-snapshots`.
- **Directory multi-file snapshots** with `manifest.json` + `--targets`.
- **Parent lineage** (`parent_experiment`, `lineage`); after discard next parent is best keep; `fork` subcommand.
- **Budgets**: `--max-experiments`, `--max-wall-seconds` (UTC-aware `created_at`); score exits 2 with `BUDGET_EXCEEDED`.
- **JSON agent surface**: `status --json`, `results --json`, `best --json`.
- **Private verify**: `--private-verify-command` drives keep/discard; dashboard **decision best** uses `best_score` / private, not public spikes.
- **Eval hard-fail**: overcount, duplicate criterion ids, judgment count ≠ outputs unless `--allow-partial-judgments`; untrusted delimiter neutralization.
- `references/eval-script-guide.md` and `examples/mechanical/*` frozen-eval samples.
- Atomic `state.json` writes; UTF-8 I/O; process-group kill on timeout (POSIX).

### Changed
- `--timeout` default is unset so score inherits baseline timeout (else 120s).
- Metric regex uses the **last** match (print metric near end of eval output).
- Architecture SVG: active harness + deterministic helpers (no headless backends).
- Docs (README, SKILL, protocol, program-template, security-workflow, tests.md) aligned with budgets, seal, multi-target, and stop rules.

### Fixed
- `--max-score` must be finite and `>= 0` (negative known maxima rejected on baseline and sealed score updates).
- Free-text machine tokens (`DESCRIPTION`, `LINEAGE`) are single-line (tabs/newlines collapsed) so values with whitespace cannot split `KEY=value` parsers.
- Negative `--max-experiments` / `--max-wall-seconds` are rejected on baseline (they previously stored and immediately tripped `BUDGET_EXCEEDED` on every score).
- `status --json` / `best --json` coerce `best_score` and experiment ids to numbers (and unlimited budgets to `null`) so stringy legacy `state.json` values do not break harness parsers.
- `--timeout` must be `>= 1` second; `0`/`-1` no longer become a confusing immediate command timeout.
- `run-verify` emits machine tokens (`STATUS=ok|invalid`, `PUBLIC`/`PRIVATE`/`DECISION`, `MODE`, `SCHEMA_VERSION`) so harness dry-runs match the score/baseline parse surface.
- `--parent-experiment` rejects non-integers and values `< 1` with a clean error (no traceback); zero-padded ids like `001` still work.
- `eval_engine.py` creates missing parent directories for `--prompt-file` and `--results-file` (nested harness paths no longer fail with `FileNotFoundError`).
- `generate_dashboard.py` creates missing parent directories for `--output` (nested report paths no longer fail with `FileNotFoundError`).
- Metric extraction rejects non-finite values (`nan` / `inf`) so a permissive `--metric-regex` cannot keep/discard or log invalid scores.
- Seal **`max_score`**: mid-run `--max-score` changes require `--allow-config-change` (same value is a no-op; was previously ignored silently).
- Fresh `baseline` rotates an orphan `results.tsv` when `state.json` is missing (not only on `--force`), so leftover logs no longer produce duplicate `001` rows.
- `eval_engine` rejects empty `criteria` / `test_prompts` and criteria missing `question`, so harnesses cannot record vacuous `0/0` scores from a broken config.
- `results --last 0` returns no rows (was treated as unlimited); negative `--last` is rejected. Avoids Python’s `seq[-0:]` full-slice trap.
- Dashboard chart path starts at the first numeric decision score (not index 0), so leading `fork`/blank-score rows no longer skip `moveTo` and break the trajectory line.
- `fork` experiment ids use microsecond stamps (+ counter) so multiple forks in the same second no longer share one `fork-…` id in `results.tsv`.
- `best --json` includes `schema_version`, `mode`, and full wall/candidate budget fields (parity with `status --json`); plain `best` prints wall budget when capped.
- `baseline --force` rotates `results.tsv` with microsecond-unique names and a counter so a second force in the same second never clobbers a prior `results.prev.*.tsv` archive.
- `baseline` / `score` always print `CANDIDATES_DONE` (and `CANDIDATES_REMAINING` / `WALL_REMAINING_SECONDS` when capped) so harnesses can stop without a separate `status` call; same tokens as `budget_exceeded`.
- `results --json` coerces score / decision columns and experiment ids to numbers (`null` when blank), matching `status --json` / `best --json` instead of leaving TSV strings.
- Wall-clock budgets no longer false-expire when host is west of UTC (aware UTC timestamps; naive legacy parsed as local).
- Strict snapshot hash comparison for directory snapshots; multi-target subset no longer silently shrinks sealed scope.
- Score **ties** use `math.isclose` so float noise (e.g. `0.1+0.2` vs `0.3`) no longer blocks size-based simplification or spuriously counts as improvement.
- `run-verify` dry-runs `--private-verify-command` when set and prints the decision metric (private vs public).
- `status --json` includes `candidates_done`, `candidates_remaining`, and `budget_exhausted` for harness stop checks.
- Plain `status` prints budget progress (`Budget: N/M candidates used`) plus lineage/next parent.
- `status` / `status --json` report wall-clock `wall_elapsed_seconds` / `wall_remaining_seconds` when `--max-wall-seconds` is set.
- Pytest smokes `examples/mechanical/hello-length`, `constrained-compress`, and `multitarget-api` through the real loop helper.
- `results.tsv` **`decision_score`** column: metric used for keep/discard (private when configured); dashboard table shows a Decision column.
- `fork` appends a `status=fork` audit row to `results.tsv` (does not consume candidate budget).
- `score` / `baseline` print machine-parseable tokens: `STATUS=`, `EXPERIMENT=`, `PARENT=`, `DECISION=`, `BEST=`, `DIRECTION=`, `PUBLIC=` / `PRIVATE=` / `LINEAGE=` (exit 0 keep/discard, 1 crash, 2 budget with `STATUS=budget_exceeded`).
- `fork` prints `STATUS=fork` (+ PARENT/LINEAGE/BEST); `best --json` includes budget progress fields.
- `score`/`baseline` emit `SNAPSHOT=` and `REVERTED=true|false` (plus `BEST_SNAPSHOT=` when reverted); CI runs `py_compile` under bash so Windows globs expand.
- `state.json` / tokens include `schema_version` (2) and `MODE=mechanical-no-headless`; score/baseline print `OUTPUT_DIR=`.
- Budget refusal prints full token block (`BEST=`, `CANDIDATES_*`, wall remaining); `references/machine-tokens.md` documents the parse surface.
- `fork` emits full shared token set (`MODE`, `SCHEMA_VERSION`, `OUTPUT_DIR`, `BEST_EXPERIMENT`, `SNAPSHOT`, `REVERTED=false`).
- Auto-migrate `results.tsv` headers when new columns are added so mid-run helper upgrades stay parseable.
- `baseline --force` rotates `results.tsv` to `results.prev.<timestamp>.tsv` so experiment ids restart without duplicate rows.

### Removed
- Confirmed absence of stale `docs/superpowers/` scratch plan.

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
