#!/usr/bin/env python3
"""
Autoresearch Agent loop helper — no-headless state manager.

This script never invokes an LLM CLI. The active harness (Claude Code, Codex,
Gemini CLI, Pi, Hermes, or another agent) performs the thinking and file edits
inside its normal interactive/session context. This helper does only the
repeatable, deterministic work:

- run the mechanical verify command
- extract a numeric metric
- run an optional guard command
- snapshot candidates and kept versions
- keep improvements or revert regressions
- append results.tsv

Typical flow:

    python scripts/autoresearch_loop.py baseline \
      --target target.md \
      --verify-command './score.sh' \
      --metric Score \
      --direction higher

    # active agent makes exactly one change to target.md

    python scripts/autoresearch_loop.py score \
      --target target.md \
      --description 'tightened routing examples'
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_TIMEOUT = 120

RESULTS_HEADER = [
    "experiment",
    "score",
    "max_score",
    "best_score",
    "status",
    "description",
    "timestamp",
    "direction",
    "verify_command",
    "guard_command",
    "snapshot",
]


@dataclass
class CommandResult:
    command: str
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def combined_output(self) -> str:
        return "\n".join(part for part in (self.stdout, self.stderr) if part)


def run_shell_command(command: str, cwd: str | None = None, timeout: int | None = None) -> CommandResult:
    """Run a user-supplied verification or guard command."""
    if timeout is None:
        timeout = DEFAULT_TIMEOUT
    # start_new_session enables process-group kill on timeout (POSIX).
    kwargs: dict[str, Any] = {
        "args": command,
        "shell": True,
        "cwd": cwd,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
    }
    if os.name != "nt":
        kwargs["start_new_session"] = True

    try:
        process = subprocess.Popen(**kwargs)
    except OSError as exc:
        return CommandResult(command, 127, "", str(exc))

    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return CommandResult(command, process.returncode, stdout or "", stderr or "")
    except subprocess.TimeoutExpired:
        _kill_process_tree(process)
        try:
            stdout, stderr = process.communicate(timeout=1)
        except (subprocess.TimeoutExpired, ValueError, OSError):
            stdout, stderr = "", ""
        return CommandResult(
            command,
            124,
            stdout or "",
            (stderr or "") + ("" if not stderr else "\n") + f"command timed out after {timeout}s",
        )


def _kill_process_tree(process: subprocess.Popen[str]) -> None:
    """Best-effort kill of the process and its children."""
    try:
        if os.name != "nt" and process.pid:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                process.kill()
        else:
            process.kill()
    except (ProcessLookupError, PermissionError, OSError):
        pass
    try:
        process.wait(timeout=1)
    except (subprocess.TimeoutExpired, ProcessLookupError, OSError):
        try:
            if os.name != "nt" and process.pid:
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except (ProcessLookupError, PermissionError, OSError):
            pass


def ensure_target_allowed(target: Path, allowed_root: Path) -> Path:
    target = target.resolve()
    allowed_root = allowed_root.resolve()
    try:
        target.relative_to(allowed_root)
    except ValueError:
        raise SystemExit(
            f"ERROR: --target {target} is not under --allowed-root {allowed_root}. "
            "Pass --allowed-root to widen the sandbox if intentional."
        )
    if not target.exists():
        raise SystemExit(f"ERROR: --target {target} does not exist.")
    if not target.is_file():
        raise SystemExit(f"ERROR: --target {target} is not a file.")
    return target


def make_dirs(output_dir: Path) -> dict[str, Path]:
    paths = {
        "output": output_dir,
        "snapshots": output_dir / "snapshots",
        "runs": output_dir / "runs",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def state_path(output_dir: Path) -> Path:
    return output_dir / "state.json"


def results_path(output_dir: Path) -> Path:
    return output_dir / "results.tsv"


def load_state(output_dir: Path) -> dict[str, Any]:
    path = state_path(output_dir)
    if not path.exists():
        raise SystemExit(
            f"ERROR: no autoresearch state found at {path}. "
            "Run the 'baseline' command first."
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: corrupt state.json at {path}: {exc}") from exc


def save_state(output_dir: Path, state: dict[str, Any]) -> None:
    path = state_path(output_dir)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def sanitize_tsv_field(value: Any) -> str:
    s = "" if value is None else str(value)
    return "".join(" " if ch in ("\t", "\n", "\r") else ch for ch in s if ch in ("\t", "\n", "\r") or ord(ch) >= 32).strip()


def append_results(output_dir: Path, row: dict[str, Any]) -> None:
    path = results_path(output_dir)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=RESULTS_HEADER, delimiter="\t", extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow({key: sanitize_tsv_field(row.get(key, "")) for key in RESULTS_HEADER})


def resolve_metric_spec(
    metric_regex: str | None = None,
    metric_name: str | None = None,
) -> tuple[str | None, str | None]:
    """Return (regex, name) used for extraction. Regex wins over name."""
    if metric_regex:
        return metric_regex, None
    if metric_name:
        return None, metric_name
    return None, None


def metric_from_output(
    output: str,
    metric_regex: str | None = None,
    metric_name: str | None = None,
) -> float:
    """Extract a numeric metric from command output.

    Preference order:
    1. ``metric_regex`` (first capture group when present; last match if multiple)
    2. ``metric_name`` (case-insensitive ``name: value`` / ``name = value``; last match)
    3. Last number in the combined output (legacy fallback)
    """
    regex, name = resolve_metric_spec(metric_regex=metric_regex, metric_name=metric_name)
    if regex:
        matches = list(re.finditer(regex, output, re.MULTILINE | re.DOTALL))
        if not matches:
            raise ValueError(f"metric regex did not match: {regex!r}")
        match = matches[-1]
        raw = match.group(1) if match.groups() else match.group(0)
    elif name:
        pattern = (
            rf"(?im)(?:^|\b){re.escape(name)}\s*[:=]\s*"
            rf"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)"
        )
        matches = list(re.finditer(pattern, output))
        if not matches:
            raise ValueError(f"metric name {name!r} not found in verify output")
        raw = matches[-1].group(1)
    else:
        numbers = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", output)
        if not numbers:
            raise ValueError("no number found in verify output")
        raw = numbers[-1]
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"extracted metric is not numeric: {raw!r}") from exc


def format_score(score: float | None) -> str:
    if score is None:
        return ""
    if float(score).is_integer():
        return str(int(score))
    return f"{score:.6g}"


def is_improvement(score: float, best_score: float, direction: str) -> bool:
    if direction == "higher":
        return score > best_score
    if direction == "lower":
        return score < best_score
    raise ValueError(f"unsupported direction: {direction}")


def is_tie(score: float, best_score: float) -> bool:
    return score == best_score


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def snapshot_target(target: Path, snapshots_dir: Path, experiment: int, status: str) -> Path:
    suffix = target.suffix or ".txt"
    destination = snapshots_dir / f"experiment_{experiment:03d}_{status}{suffix}"
    shutil.copy2(target, destination)
    return destination


def ensure_snapshot_allowed(snapshot: Path, snapshots_dir: Path) -> Path:
    snapshot = snapshot.resolve()
    snapshots_dir = snapshots_dir.resolve()
    try:
        snapshot.relative_to(snapshots_dir)
    except ValueError:
        raise SystemExit(
            f"ERROR: best_snapshot {snapshot} is not under snapshots dir {snapshots_dir}. "
            "Refusing to revert from a path outside the run sandbox."
        )
    if not snapshot.exists():
        raise SystemExit(f"ERROR: best_snapshot {snapshot} does not exist.")
    if not snapshot.is_file():
        raise SystemExit(f"ERROR: best_snapshot {snapshot} is not a file.")
    return snapshot


def revert_to_snapshot(
    target: Path,
    snapshot: str,
    snapshots_dir: Path,
    *,
    expected_sha256: str | None = None,
    strict_snapshots: bool = False,
) -> None:
    snap_path = ensure_snapshot_allowed(Path(snapshot), snapshots_dir)
    if expected_sha256:
        actual = file_sha256(snap_path)
        if actual != expected_sha256:
            msg = (
                f"snapshot hash mismatch for {snap_path}: "
                f"expected {expected_sha256}, got {actual}"
            )
            if strict_snapshots:
                raise SystemExit(f"ERROR: {msg}")
            print(f"WARNING: {msg}", file=sys.stderr)
    shutil.copy2(snap_path, target)


def resolve_timeout(args: argparse.Namespace, state: dict[str, Any] | None = None) -> int:
    if getattr(args, "timeout", None) is not None:
        return int(args.timeout)
    if state is not None and state.get("timeout") is not None:
        return int(state["timeout"])
    return DEFAULT_TIMEOUT


def run_verify(
    args: argparse.Namespace,
    verify_command: str,
    metric_regex: str | None,
    metric_name: str | None = None,
) -> tuple[CommandResult, float | None, str | None]:
    result = run_shell_command(verify_command, cwd=args.cwd, timeout=args.timeout)
    if not result.ok:
        return result, None, f"verify command exited {result.returncode}"
    try:
        score = metric_from_output(result.combined_output, metric_regex=metric_regex, metric_name=metric_name)
        return result, score, None
    except ValueError as exc:
        return result, None, str(exc)


def run_guard(args: argparse.Namespace, guard_command: str | None) -> tuple[CommandResult | None, str | None]:
    if not guard_command:
        return None, None
    result = run_shell_command(guard_command, cwd=args.cwd, timeout=args.timeout)
    if result.ok:
        return result, None
    return result, f"guard command exited {result.returncode}"


def command_output_file(output_dir: Path, experiment: int, name: str, result: CommandResult | None) -> None:
    if result is None:
        return
    run_dir = output_dir / "runs" / f"experiment_{experiment:03d}"
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / f"{name}.txt"
    path.write_text(
        f"$ {result.command}\n"
        f"exit={result.returncode}\n\n"
        f"--- stdout ---\n{result.stdout}\n\n"
        f"--- stderr ---\n{result.stderr}\n",
        encoding="utf-8",
    )


def _cli_config_overrides(args: argparse.Namespace, state: dict[str, Any]) -> list[str]:
    """Return human-readable list of sealed fields the CLI is trying to change."""
    changes: list[str] = []
    if args.verify_command is not None and args.verify_command != state.get("verify_command"):
        changes.append("verify_command")
    if args.direction is not None and args.direction != state.get("direction"):
        changes.append("direction")
    if args.metric_regex is not None and (args.metric_regex or "") != (state.get("metric_regex") or ""):
        changes.append("metric_regex")
    if getattr(args, "metric", None) is not None and (args.metric or "") != (state.get("metric") or ""):
        changes.append("metric")
    if args.guard_command is not None and (args.guard_command or "") != (state.get("guard_command") or ""):
        changes.append("guard_command")
    return changes


def cmd_baseline(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    paths = make_dirs(output_dir)
    target = ensure_target_allowed(
        Path(args.target),
        Path(args.allowed_root).resolve() if args.allowed_root else Path.cwd().resolve(),
    )
    args.cwd = args.cwd or str(Path.cwd())
    args.timeout = resolve_timeout(args)

    if state_path(output_dir).exists() and not args.force:
        raise SystemExit(f"ERROR: {state_path(output_dir)} already exists. Pass --force to replace the baseline.")

    metric_name = args.metric or None
    metric_regex = args.metric_regex or None
    if not metric_name and not metric_regex:
        print(
            "WARNING: no --metric or --metric-regex set; using last-number fallback. "
            "Prefer --metric Score (or similar) so progress logs cannot steal the metric.",
            file=sys.stderr,
        )

    verify_result, score, verify_error = run_verify(args, args.verify_command, metric_regex, metric_name)
    command_output_file(output_dir, 1, "verify", verify_result)
    if verify_error:
        print(f"ERROR: invalid baseline verify result: {verify_error}", file=sys.stderr)
        print(verify_result.combined_output[-1000:], file=sys.stderr)
        return 1

    guard_result, guard_error = run_guard(args, args.guard_command)
    command_output_file(output_dir, 1, "guard", guard_result)
    if guard_error:
        print(f"ERROR: baseline guard failed: {guard_error}", file=sys.stderr)
        if guard_result:
            print(guard_result.combined_output[-1000:], file=sys.stderr)
        return 1

    snapshot = snapshot_target(target, paths["snapshots"], 1, "keep")
    state = {
        "target": str(target),
        "direction": args.direction,
        "verify_command": args.verify_command,
        "guard_command": args.guard_command or "",
        "metric": metric_name or "",
        "metric_regex": metric_regex or "",
        "cwd": args.cwd or "",
        "timeout": args.timeout,
        "best_score": score,
        "best_size": target.stat().st_size,
        "best_snapshot": str(snapshot),
        "best_snapshot_sha256": file_sha256(snapshot),
        "best_experiment": 1,
        "last_experiment": 1,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "mode": "mechanical-no-headless",
    }
    save_state(output_dir, state)
    append_results(output_dir, {
        "experiment": "001",
        "score": format_score(score),
        "best_score": format_score(score),
        "status": "keep",
        "description": args.description or "baseline",
        "timestamp": datetime.now().isoformat(),
        "direction": args.direction,
        "verify_command": args.verify_command,
        "guard_command": args.guard_command or "",
        "snapshot": str(snapshot),
    })
    print(f"Baseline recorded: {format_score(score)} ({args.direction} is better)")
    print(f"Snapshot: {snapshot}")
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    paths = make_dirs(output_dir)
    state = load_state(output_dir)
    target = ensure_target_allowed(
        Path(args.target or state["target"]),
        Path(args.allowed_root).resolve() if args.allowed_root else Path.cwd().resolve(),
    )

    overrides = _cli_config_overrides(args, state)
    if overrides and not getattr(args, "allow_config_change", False):
        raise SystemExit(
            "ERROR: sealed config change refused for: "
            + ", ".join(overrides)
            + ". Re-run with --allow-config-change if intentional."
        )

    experiment = int(state.get("last_experiment", 1)) + 1
    direction = args.direction if args.direction is not None else state["direction"]
    verify_command = args.verify_command if args.verify_command is not None else state["verify_command"]
    guard_command = args.guard_command if args.guard_command is not None else state.get("guard_command", "")
    metric_regex = args.metric_regex if args.metric_regex is not None else state.get("metric_regex", "")
    metric_regex = metric_regex or None
    metric_name = args.metric if getattr(args, "metric", None) is not None else state.get("metric", "")
    metric_name = metric_name or None
    args.cwd = args.cwd if args.cwd is not None else (state.get("cwd") or None)
    args.timeout = resolve_timeout(args, state)

    verify_result, score, verify_error = run_verify(args, verify_command, metric_regex, metric_name)
    command_output_file(output_dir, experiment, "verify", verify_result)

    status = "discard"
    reason = args.description or f"experiment {experiment:03d}"
    guard_result: CommandResult | None = None
    candidate_snapshot_status = "discard"

    if verify_error:
        status = "crash"
        reason = f"{reason} — verify failed: {verify_error}"
        candidate_snapshot_status = "crash"
    else:
        guard_result, guard_error = run_guard(args, guard_command)
        command_output_file(output_dir, experiment, "guard", guard_result)
        if guard_error:
            status = "crash"
            reason = f"{reason} — guard failed: {guard_error}"
            candidate_snapshot_status = "crash"
        else:
            best_score = float(state["best_score"])
            current_size = target.stat().st_size
            best_size = int(state.get("best_size", current_size))
            if is_improvement(float(score), best_score, direction):
                status = "keep"
                candidate_snapshot_status = "keep"
            elif is_tie(float(score), best_score) and current_size < best_size:
                status = "keep"
                candidate_snapshot_status = "keep"
                reason = f"{reason} — tie on score, simpler target"
            else:
                status = "discard"
                candidate_snapshot_status = "discard"

    snapshot = snapshot_target(target, paths["snapshots"], experiment, candidate_snapshot_status)

    if status == "keep" and score is not None:
        state.update({
            "best_score": score,
            "best_size": target.stat().st_size,
            "best_snapshot": str(snapshot),
            "best_snapshot_sha256": file_sha256(snapshot),
            "best_experiment": experiment,
        })
    else:
        try:
            revert_to_snapshot(
                target,
                state["best_snapshot"],
                paths["snapshots"],
                expected_sha256=state.get("best_snapshot_sha256") or None,
                strict_snapshots=bool(getattr(args, "strict_snapshots", False)),
            )
        except SystemExit:
            raise
        except OSError as exc:
            raise SystemExit(f"ERROR: failed to revert target to best snapshot: {exc}") from exc

    state.update({
        "last_experiment": experiment,
        "updated_at": datetime.now().isoformat(),
        "target": str(target),
        "direction": direction,
        "verify_command": verify_command,
        "guard_command": guard_command or "",
        "metric": metric_name or "",
        "metric_regex": metric_regex or "",
        "cwd": args.cwd or "",
        "timeout": args.timeout,
    })
    save_state(output_dir, state)

    append_results(output_dir, {
        "experiment": f"{experiment:03d}",
        "score": format_score(score),
        "best_score": format_score(float(state["best_score"])),
        "status": status,
        "description": reason,
        "timestamp": datetime.now().isoformat(),
        "direction": direction,
        "verify_command": verify_command,
        "guard_command": guard_command or "",
        "snapshot": str(snapshot),
    })

    print(f"Experiment {experiment:03d}: {status.upper()}")
    print(f"Score: {format_score(score)} | Best: {format_score(float(state['best_score']))} | Direction: {direction}")
    print(f"Snapshot: {snapshot}")
    if status != "keep":
        print(f"Reverted target to best snapshot: {state['best_snapshot']}")
    return 0 if status != "crash" else 1


def cmd_run_verify(args: argparse.Namespace) -> int:
    args.timeout = resolve_timeout(args)
    metric_name = getattr(args, "metric", None) or None
    metric_regex = args.metric_regex or None
    verify_result, score, verify_error = run_verify(args, args.verify_command, metric_regex, metric_name)
    print(f"Verify exit: {verify_result.returncode}")
    if verify_error:
        print(f"Metric: INVALID ({verify_error})")
        print(verify_result.combined_output[-1000:])
        return 1
    print(f"Metric: {format_score(score)}")
    if args.guard_command:
        guard_result, guard_error = run_guard(args, args.guard_command)
        print(f"Guard exit: {guard_result.returncode if guard_result else 'skipped'}")
        if guard_error:
            print(guard_result.combined_output[-1000:] if guard_result else "")
            return 1
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    state = load_state(output_dir)
    print(f"Target: {state['target']}")
    print(f"Mode: {state.get('mode', 'unknown')}")
    print(f"Best: {format_score(float(state['best_score']))} ({state['direction']} is better), experiment {state['best_experiment']:03d}")
    print(f"Best snapshot: {state['best_snapshot']}")
    if state.get("metric"):
        print(f"Metric name: {state['metric']}")
    path = results_path(output_dir)
    if path.exists():
        rows = path.read_text(encoding="utf-8").splitlines()[-6:]
        print("\nRecent results:")
        print("\n".join(rows))
    return 0


def add_common(
    parser: argparse.ArgumentParser,
    require_verify: bool = False,
    require_target: bool = False,
    require_direction: bool = False,
) -> None:
    parser.add_argument("--target", required=require_target, help="Path to the file the active harness is optimizing")
    parser.add_argument("--output-dir", default="./autoresearch-results/", help="Directory for state, snapshots, runs, and results.tsv")
    parser.add_argument("--verify-command", required=require_verify, default=None, help="Command that prints/exposes the numeric metric")
    parser.add_argument(
        "--metric",
        default=None,
        help="Metric name to extract (e.g. Score, accuracy). Matches 'name: value' / 'name = value'; last match wins.",
    )
    parser.add_argument(
        "--metric-regex",
        default=None,
        help="Regex for extracting the metric (overrides --metric). Last match wins; first capture group is used when present.",
    )
    parser.add_argument("--direction", choices=("higher", "lower"), required=require_direction, default=None, help="Whether higher or lower metric values are better")
    parser.add_argument("--guard-command", default=None, help="Optional command that must exit 0 for a change to be kept")
    parser.add_argument("--cwd", default=None, help="Working directory for verify and guard commands")
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help=f"Timeout in seconds for verify and guard commands (default: inherit from state or {DEFAULT_TIMEOUT})",
    )
    parser.add_argument("--allowed-root", default=None, help="Restrict target paths to this root (default: current working directory)")
    parser.add_argument("--description", default="", help="Short description of this baseline or candidate change")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="No-headless autoresearch state manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    baseline = subparsers.add_parser("baseline", help="Run verify/guard once and establish the baseline")
    add_common(baseline, require_verify=True, require_target=True, require_direction=True)
    baseline.add_argument("--force", action="store_true", help="Replace an existing state.json baseline")
    baseline.set_defaults(func=cmd_baseline)

    score = subparsers.add_parser("score", help="Score the active harness's current candidate and keep/discard it")
    add_common(score, require_verify=False)
    score.add_argument(
        "--allow-config-change",
        action="store_true",
        help="Allow changing sealed verify/guard/metric/direction settings mid-run",
    )
    score.add_argument(
        "--strict-snapshots",
        action="store_true",
        help="Hard-fail if best snapshot content hash does not match state",
    )
    score.set_defaults(func=cmd_score)

    run_verify_parser = subparsers.add_parser("run-verify", help="Dry-run a verify command and optional guard")
    add_common(run_verify_parser, require_verify=True)
    run_verify_parser.set_defaults(func=cmd_run_verify)

    status = subparsers.add_parser("status", help="Show current autoresearch state")
    status.add_argument("--output-dir", default="./autoresearch-results/")
    status.set_defaults(func=cmd_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
