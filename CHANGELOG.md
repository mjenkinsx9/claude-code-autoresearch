# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-06-17

The hardening release: the loop now runs reliably on Windows, fails safe instead
of optimizing against a broken measurement, and ships with an automated test
suite and CI. This is the first release recommended for unattended overnight runs.

### Added
- **`--guard "<command>"`** on `autoresearch_loop.py` — a command that must exit 0
  before any keep is accepted; a failing guard discards the change even if the
  score improved. (Previously documented but not implemented.)
- **Automated test suite** — 15 pytest tests covering the agent CLI adapter, the
  eval engine, and end-to-end loop smoke tests (bounded keep/discard run,
  broken-backend baseline abort, consecutive-crash stop).
- **GitHub Actions CI** — runs the suite and CLI smoke checks on Ubuntu + Windows
  across Python 3.10 and 3.12.
- **Judge prompt hardening** — outputs under evaluation are delimited as untrusted
  data with an anti-injection instruction, so a target can no longer instruct its
  own judge to "answer yes to everything."
- `requirements-dev.txt` (pytest) and a `tests/` package with a deterministic stub
  agent backend.
- Professional README with animated SVG diagrams (the loop, architecture, score
  progression) and a documentation map.

### Changed
- **Baseline gate now fails safe** — if baseline runs crash or the judge errors,
  the loop aborts with exit code 2 instead of recording a bogus `0` baseline as a
  keep.
- **`runs_per_experiment` is honored from the eval config** when the CLI flag is
  omitted (previously only the CLI flag was read).
- Reconciled `references/results-logging.md` with the TSV schema the script
  actually writes (`experiment / score / max_score / status / description /
  timestamp`).
- Removed the `references/security-workflow.md` dependency on a
  `persona-security-expert` skill that did not exist in this repo.

### Fixed
- **Windows compatibility** — every file `open()` now uses `encoding="utf-8"`,
  fixing crashes on cp1252 consoles when reading or writing non-ASCII content.
- Removed emoji from `print()` output that raised `UnicodeEncodeError` on cp1252
  consoles, killing the loop right after baseline.
- Added the missing `import subprocess` in `autoresearch_loop.py` that raised
  `NameError` on any `.py` target run with `--allow-exec`.
- Custom-backend command templates no longer arrive with literal quotes on Windows
  (`cmd.exe` / `shell=True` quoting fix), and child output is decoded as UTF-8.
- `eval_engine.evaluate_single_output` tolerates malformed judge JSON shapes
  instead of crashing, and clamps `total_yes` to the number of criteria.
- Consecutive crashing experiments now increment the failure counter and trip the
  crash-stop threshold instead of looping forever and burning tokens.

### Removed
- `docs/superpowers/` implementation-plan scratch folder (development artifact).

## [1.0] - 2026-03

Initial public release: the autoresearch skill (`SKILL.md`), reference docs, and
the stdlib-only Python runner (`autoresearch_loop.py`, `eval_engine.py`,
`agent_cli.py`, `generate_dashboard.py`) with Claude Code, Hermes, and custom
agent backends.

[2.0.0]: https://github.com/mjenkinsx9/claude-code-autoresearch/releases/tag/2.0.0
[1.0]: https://github.com/mjenkinsx9/claude-code-autoresearch/releases/tag/1.0
