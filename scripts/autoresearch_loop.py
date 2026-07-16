#!/usr/bin/env python3
"""
Autoresearch Agent loop helper — no-headless state manager.

This script never invokes an LLM CLI. The active harness performs thinking and
file edits. This helper does deterministic verify/guard/snapshot/keep-discard.

Typical flow:

    python scripts/autoresearch_loop.py baseline \\
      --target target.md \\
      --verify-command './score.sh' \\
      --metric Score \\
      --direction higher

    python scripts/autoresearch_loop.py score \\
      --target target.md \\
      --description 'one focused change'
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_TIMEOUT = 120
MAX_SCOPED_FILES = 10
MAX_TOTAL_BYTES_WARN = 500 * 1024
BUDGET_EXIT_CODE = 2
# Float comparison for metric ties / non-improvements (benchmark noise).
TIE_REL_TOL = 1e-9
TIE_ABS_TOL = 1e-12


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Timezone-aware UTC timestamp for state/TSV (always includes offset)."""
    return utc_now().isoformat()


def parse_timestamp(value: str) -> datetime:
    """Parse ISO timestamps into UTC.

    Aware values are converted to UTC. Naive values (legacy) are interpreted as
    *local* wall-clock time, then converted to UTC — never treated as UTC.
    Trailing ``Z`` is accepted as ``+00:00``.
    """
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        local_tz = datetime.now().astimezone().tzinfo
        dt = dt.replace(tzinfo=local_tz)
    return dt.astimezone(timezone.utc)

RESULTS_HEADER = [
    "experiment",
    "score",
    "max_score",
    "best_score",
    "private_score",
    "decision_score",
    "status",
    "description",
    "timestamp",
    "direction",
    "verify_command",
    "guard_command",
    "snapshot",
    "parent_experiment",
    "lineage",
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
    if timeout is None:
        timeout = DEFAULT_TIMEOUT
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


def sanitize_artifact_relpath(path_value: str | Path) -> Path:
    normalized = str(path_value).replace("\\", "/")
    parts = Path(normalized).parts
    safe: list[str] = []
    for part in parts:
        if part in ("", ".", "/"):
            continue
        if part == "..":
            continue
        if not safe and ":" in part:
            part = part.replace(":", "_")
        safe.append(part)
    if not safe:
        return Path("unnamed_file")
    return Path(*safe)


def resolve_targets(args: argparse.Namespace, state: dict[str, Any] | None, allowed_root: Path) -> list[Path]:
    if getattr(args, "targets", None):
        raw = list(args.targets)
    elif getattr(args, "target", None):
        raw = [args.target]
    elif state:
        if state.get("targets"):
            raw = list(state["targets"])
        elif state.get("target"):
            raw = [state["target"]]
        else:
            raise SystemExit("ERROR: no target in state; pass --target or --targets")
    else:
        raise SystemExit("ERROR: provide --target or --targets")
    if len(raw) > MAX_SCOPED_FILES:
        raise SystemExit(f"ERROR: too many targets ({len(raw)}); max is {MAX_SCOPED_FILES}")
    targets = [ensure_target_allowed(Path(p), allowed_root) for p in raw]
    # de-dupe resolved paths while preserving order
    seen: set[Path] = set()
    unique: list[Path] = []
    for t in targets:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    total = sum(t.stat().st_size for t in unique)
    if total > MAX_TOTAL_BYTES_WARN:
        print(f"WARNING: total target size {total} bytes exceeds {MAX_TOTAL_BYTES_WARN}", file=sys.stderr)
    return unique


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


def ensure_results_schema(path: Path) -> None:
    """Rewrite results.tsv if its header is missing columns from RESULTS_HEADER.

    Long-running runs that upgrade the helper mid-stream would otherwise append
    wide rows under a stale header and break DictReader consumers.
    """
    if not path.exists() or path.stat().st_size == 0:
        return
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        old_fields = list(reader.fieldnames or [])
        if old_fields == RESULTS_HEADER:
            return
        rows = list(reader)
    tmp = path.with_suffix(".tsv.migrate")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=RESULTS_HEADER, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: sanitize_tsv_field(row.get(key, "")) for key in RESULTS_HEADER})
    os.replace(tmp, path)
    print(
        f"Migrated results.tsv header ({len(old_fields)} -> {len(RESULTS_HEADER)} columns)",
        file=sys.stderr,
    )


def append_results(output_dir: Path, row: dict[str, Any]) -> None:
    path = results_path(output_dir)
    ensure_results_schema(path)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=RESULTS_HEADER, delimiter="\t", extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow({key: sanitize_tsv_field(row.get(key, "")) for key in RESULTS_HEADER})


def resolve_metric_spec(
    metric_regex: str | None = None,
    metric_name: str | None = None,
) -> tuple[str | None, str | None]:
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


def is_tie(
    score: float,
    best_score: float,
    *,
    rel_tol: float = TIE_REL_TOL,
    abs_tol: float = TIE_ABS_TOL,
) -> bool:
    """True when scores are effectively equal (float-safe)."""
    return math.isclose(float(score), float(best_score), rel_tol=rel_tol, abs_tol=abs_tol)


def is_improvement(
    score: float,
    best_score: float,
    direction: str,
    *,
    rel_tol: float = TIE_REL_TOL,
    abs_tol: float = TIE_ABS_TOL,
) -> bool:
    """True when score is strictly better than best after float-tie tolerance."""
    if is_tie(score, best_score, rel_tol=rel_tol, abs_tol=abs_tol):
        return False
    if direction == "higher":
        return float(score) > float(best_score)
    if direction == "lower":
        return float(score) < float(best_score)
    raise ValueError(f"unsupported direction: {direction}")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def content_hash_pairs(pairs: list[tuple[str, bytes]]) -> str:
    """Canonical content hash: sort by path string, then path\\0bytes\\0."""
    digest = hashlib.sha256()
    for path, data in sorted(pairs, key=lambda item: item[0]):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
    return digest.hexdigest()


def combined_targets_sha256(targets: list[Path]) -> str:
    pairs = [(str(t.resolve()), t.read_bytes()) for t in targets]
    return content_hash_pairs(pairs)


def resolve_artifact_under_snapshot(snap_path: Path, artifact_path: str) -> Path:
    """Resolve artifact path and require it stays under the snapshot directory."""
    if not artifact_path or artifact_path.startswith("/") or Path(artifact_path).is_absolute():
        raise SystemExit(
            f"ERROR: snapshot artifact_path must be relative (got {artifact_path!r})"
        )
    # Reject parent traversal before join
    parts = Path(artifact_path).parts
    if ".." in parts:
        raise SystemExit(f"ERROR: snapshot artifact_path must not contain '..' (got {artifact_path!r})")
    candidate = (snap_path / artifact_path).resolve()
    snap_resolved = snap_path.resolve()
    try:
        candidate.relative_to(snap_resolved)
    except ValueError:
        raise SystemExit(
            f"ERROR: snapshot artifact {candidate} escapes snapshot dir {snap_resolved}"
        )
    if not candidate.is_file():
        raise SystemExit(f"ERROR: snapshot artifact is not a file: {candidate}")
    return candidate


def snapshot_bundle_sha256(snap_path: Path, manifest: dict[str, Any]) -> str:
    pairs: list[tuple[str, bytes]] = []
    for entry in manifest.get("files", []):
        art = resolve_artifact_under_snapshot(snap_path, entry["artifact_path"])
        pairs.append((entry["path"], art.read_bytes()))
    return content_hash_pairs(pairs)


def total_size(targets: list[Path]) -> int:
    return sum(t.stat().st_size for t in targets)


def snapshot_targets(targets: list[Path], snapshots_dir: Path, experiment: int, status: str) -> Path:
    dest = snapshots_dir / f"experiment_{experiment:03d}_{status}"
    if dest.exists():
        shutil.rmtree(dest)
    files_dir = dest / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    manifest_files: list[dict[str, Any]] = []
    for target in targets:
        # Prefer basename when unique; else full sanitized absolute-ish path
        rel = Path(target.name)
        artifact = files_dir / sanitize_artifact_relpath(rel)
        # disambiguate collisions
        if artifact.exists():
            rel = sanitize_artifact_relpath(str(target).lstrip("/"))
            artifact = files_dir / rel
        artifact.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, artifact)
        manifest_files.append({
            "path": str(target.resolve()),
            "artifact_path": str(artifact.relative_to(dest)),
            "sha256": file_sha256(artifact),
            "bytes": artifact.stat().st_size,
        })
    manifest = {
        "type": "step_code_snapshot",
        "experiment": experiment,
        "status": status,
        "created_at": utc_now_iso(),
        "files": manifest_files,
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return dest


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
    return snapshot


def revert_targets_from_snapshot(
    targets: list[Path],
    snapshot: str,
    snapshots_dir: Path,
    *,
    expected_sha256: str | None = None,
    strict_snapshots: bool = False,
) -> None:
    snap_path = ensure_snapshot_allowed(Path(snapshot), snapshots_dir)

    # Legacy flat single-file snapshot support
    if snap_path.is_file():
        if len(targets) != 1:
            raise SystemExit("ERROR: legacy flat snapshot only supports a single target file")
        if expected_sha256:
            actual = file_sha256(snap_path)
            if actual != expected_sha256:
                msg = f"snapshot hash mismatch for {snap_path}: expected {expected_sha256}, got {actual}"
                if strict_snapshots:
                    raise SystemExit(f"ERROR: {msg}")
                print(f"WARNING: {msg}", file=sys.stderr)
        shutil.copy2(snap_path, targets[0])
        return

    manifest_path = snap_path / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"ERROR: snapshot directory missing manifest.json: {snap_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_path = {entry["path"]: entry for entry in manifest.get("files", [])}
    # Always validate artifact paths are sandboxed; verify content hashes.
    for entry in manifest.get("files", []):
        art = resolve_artifact_under_snapshot(snap_path, entry["artifact_path"])
        if entry.get("sha256") and file_sha256(art) != entry.get("sha256"):
            msg = f"snapshot artifact hash mismatch: {art}"
            if strict_snapshots:
                raise SystemExit(f"ERROR: {msg}")
            print(f"WARNING: {msg}", file=sys.stderr)

    if expected_sha256:
        actual = snapshot_bundle_sha256(snap_path, manifest)
        if actual != expected_sha256:
            msg = (
                f"snapshot bundle hash mismatch for {snap_path}: "
                f"expected {expected_sha256}, got {actual}"
            )
            if strict_snapshots:
                raise SystemExit(f"ERROR: {msg}")
            print(f"WARNING: {msg}", file=sys.stderr)

    for target in targets:
        entry = by_path.get(str(target.resolve())) or by_path.get(str(target))
        if entry is None:
            matches = [e for e in manifest.get("files", []) if Path(e["path"]).name == target.name]
            if len(matches) == 1:
                entry = matches[0]
            else:
                raise SystemExit(f"ERROR: snapshot does not contain target {target}")
        art = resolve_artifact_under_snapshot(snap_path, entry["artifact_path"])
        shutil.copy2(art, target)


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
    priv = getattr(args, "private_verify_command", None)
    if priv is not None and (priv or "") != (state.get("private_verify_command") or ""):
        changes.append("private_verify_command")
    if args.cwd is not None:
        state_cwd = (state.get("cwd") or "").strip()
        cli_cwd = str(Path(args.cwd).resolve())
        sealed_cwd = str(Path(state_cwd).resolve()) if state_cwd else ""
        if sealed_cwd and cli_cwd != sealed_cwd:
            changes.append("cwd")
        elif not sealed_cwd and cli_cwd != str(Path.cwd().resolve()):
            # Baseline stored empty only if cwd was default; still seal non-default CLI cwd
            changes.append("cwd")
    return changes


def _targets_override_requested(args: argparse.Namespace, state: dict[str, Any], allowed_root: Path) -> tuple[list[Path], bool]:
    """Return (targets, changed). When CLI omits target(s), use state. Seal changes."""
    state_raw = state.get("targets") or ([state["target"]] if state.get("target") else [])
    state_targets = [Path(p).resolve() for p in state_raw]
    cli_raw: list[str] | None = None
    if getattr(args, "targets", None):
        cli_raw = list(args.targets)
    elif getattr(args, "target", None):
        cli_raw = [args.target]
    if cli_raw is None:
        return [ensure_target_allowed(t, allowed_root) for t in state_targets], False
    cli_targets = [ensure_target_allowed(Path(p), allowed_root) for p in cli_raw]
    cli_set = sorted(t.resolve() for t in cli_targets)
    changed = cli_set != sorted(state_targets)
    return cli_targets, changed


def check_budget(state: dict[str, Any]) -> str | None:
    """Return error message if budget exhausted, else None.

    ``max_experiments`` counts candidate score runs *after* baseline.
    """
    max_exp = state.get("max_experiments")
    if max_exp not in (None, "", 0, "0"):
        max_exp_i = int(max_exp)
        candidates_done = max(0, int(state.get("last_experiment", 1)) - 1)
        if candidates_done >= max_exp_i:
            return (
                f"BUDGET_EXCEEDED: max_experiments={max_exp_i} candidate scores already completed "
                f"(last_experiment={state.get('last_experiment')})"
            )
    max_wall = state.get("max_wall_seconds")
    if max_wall not in (None, "", 0, "0"):
        created = state.get("created_at")
        if created:
            try:
                created_dt = parse_timestamp(str(created))
                elapsed = (utc_now() - created_dt).total_seconds()
                if elapsed > float(max_wall):
                    return (
                        f"BUDGET_EXCEEDED: max_wall_seconds={max_wall} elapsed={elapsed:.1f}s"
                    )
            except ValueError as exc:
                return (
                    f"BUDGET_EXCEEDED: unparseable created_at={created!r} ({exc}); "
                    f"refusing score while max_wall_seconds={max_wall} is set"
                )
    return None


def budget_progress(state: dict[str, Any]) -> dict[str, Any]:
    """Candidate + wall-clock budget progress for status (harness stop checks)."""
    last = int(state.get("last_experiment", 1) or 1)
    candidates_done = max(0, last - 1)
    max_exp = state.get("max_experiments")
    max_exp_i: int | None
    if max_exp in (None, "", 0, "0"):
        max_exp_i = None
        remaining: int | None = None
        candidates_exhausted = False
    else:
        max_exp_i = int(max_exp)
        remaining = max(0, max_exp_i - candidates_done)
        candidates_exhausted = candidates_done >= max_exp_i

    max_wall = state.get("max_wall_seconds")
    wall_elapsed: float | None = None
    wall_remaining: float | None = None
    wall_exhausted = False
    max_wall_f: float | None = None
    if max_wall not in (None, "", 0, "0"):
        max_wall_f = float(max_wall)
        created = state.get("created_at")
        if created:
            try:
                created_dt = parse_timestamp(str(created))
                wall_elapsed = max(0.0, (utc_now() - created_dt).total_seconds())
                wall_remaining = max(0.0, max_wall_f - wall_elapsed)
                wall_exhausted = wall_elapsed > max_wall_f
            except ValueError:
                wall_elapsed = None
                wall_remaining = None
                wall_exhausted = True  # fail-closed for status display

    return {
        "candidates_done": candidates_done,
        "candidates_remaining": remaining,
        "max_experiments": max_exp_i,
        "max_wall_seconds": max_wall_f,
        "wall_elapsed_seconds": wall_elapsed,
        "wall_remaining_seconds": wall_remaining,
        "wall_budget_exhausted": wall_exhausted,
        "budget_exhausted": candidates_exhausted or wall_exhausted,
    }


def state_public_dict(state: dict[str, Any]) -> dict[str, Any]:
    targets = state.get("targets") or ([state["target"]] if state.get("target") else [])
    progress = budget_progress(state)
    return {
        "target": state.get("target"),
        "targets": targets,
        "best_score": state.get("best_score"),
        "best_experiment": state.get("best_experiment"),
        "last_experiment": state.get("last_experiment"),
        "direction": state.get("direction"),
        "max_experiments": state.get("max_experiments"),
        "max_wall_seconds": state.get("max_wall_seconds"),
        "candidates_done": progress["candidates_done"],
        "candidates_remaining": progress["candidates_remaining"],
        "wall_elapsed_seconds": progress["wall_elapsed_seconds"],
        "wall_remaining_seconds": progress["wall_remaining_seconds"],
        "wall_budget_exhausted": progress["wall_budget_exhausted"],
        "budget_exhausted": progress["budget_exhausted"],
        "metric": state.get("metric"),
        "mode": state.get("mode", "mechanical-no-headless"),
        "best_snapshot": state.get("best_snapshot"),
        "lineage": state.get("lineage", ""),
        "next_parent_experiment": state.get("next_parent_experiment"),
        "private_verify_command": state.get("private_verify_command") or "",
        "instructions": state.get("instructions") or "",
    }


def cmd_baseline(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    paths = make_dirs(output_dir)
    allowed = Path(args.allowed_root).resolve() if args.allowed_root else Path.cwd().resolve()
    targets = resolve_targets(args, None, allowed)
    args.cwd = args.cwd or str(Path.cwd())
    args.timeout = resolve_timeout(args)

    if state_path(output_dir).exists() and not args.force:
        raise SystemExit(f"ERROR: {state_path(output_dir)} already exists. Pass --force to replace the baseline.")

    if args.force:
        # Replace research log so experiment ids restart cleanly (no duplicate 001 rows).
        results = results_path(output_dir)
        if results.exists():
            bak = output_dir / f"results.prev.{utc_now().strftime('%Y%m%dT%H%M%SZ')}.tsv"
            results.rename(bak)
            print(f"Rotated previous results to {bak}", file=sys.stderr)
        # Leave prior snapshots in place for audit; new baseline overwrites experiment_001_keep/

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

    private_score = None
    private_cmd = getattr(args, "private_verify_command", None) or ""
    if private_cmd:
        priv_result, private_score, priv_error = run_verify(args, private_cmd, metric_regex, metric_name)
        command_output_file(output_dir, 1, "private_verify", priv_result)
        if priv_error:
            print(f"ERROR: invalid baseline private verify: {priv_error}", file=sys.stderr)
            return 1
        decision_score = private_score
    else:
        decision_score = score

    guard_result, guard_error = run_guard(args, args.guard_command)
    command_output_file(output_dir, 1, "guard", guard_result)
    if guard_error:
        print(f"ERROR: baseline guard failed: {guard_error}", file=sys.stderr)
        if guard_result:
            print(guard_result.combined_output[-1000:], file=sys.stderr)
        return 1

    snapshot = snapshot_targets(targets, paths["snapshots"], 1, "keep")
    instructions = getattr(args, "instructions", None) or ""
    if instructions and Path(instructions).is_file():
        instructions = str(Path(instructions).resolve())

    max_experiments = getattr(args, "max_experiments", None)
    max_wall_seconds = getattr(args, "max_wall_seconds", None)
    max_score = getattr(args, "max_score", None)
    lineage = getattr(args, "lineage", None) or ""

    state = {
        "target": str(targets[0]),
        "targets": [str(t) for t in targets],
        "direction": args.direction,
        "verify_command": args.verify_command,
        "private_verify_command": private_cmd,
        "guard_command": args.guard_command or "",
        "metric": metric_name or "",
        "metric_regex": metric_regex or "",
        "max_score": max_score if max_score is not None else "",
        "cwd": args.cwd or "",
        "timeout": args.timeout,
        "best_score": decision_score,
        "best_public_score": score,
        "best_private_score": private_score if private_score is not None else "",
        "best_size": total_size(targets),
        "best_snapshot": str(snapshot),
        "best_snapshot_sha256": combined_targets_sha256(targets),
        "best_experiment": 1,
        "last_experiment": 1,
        "next_parent_experiment": 1,
        "lineage": lineage,
        "instructions": instructions,
        "max_experiments": max_experiments if max_experiments is not None else "",
        "max_wall_seconds": max_wall_seconds if max_wall_seconds is not None else "",
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "mode": "mechanical-no-headless",
    }
    save_state(output_dir, state)
    append_results(output_dir, {
        "experiment": "001",
        "score": format_score(score),
        "max_score": format_score(float(max_score)) if max_score is not None else "",
        "best_score": format_score(decision_score),
        "private_score": format_score(private_score),
        "decision_score": format_score(decision_score),
        "status": "keep",
        "description": args.description or "baseline",
        "timestamp": utc_now_iso(),
        "direction": args.direction,
        "verify_command": args.verify_command,
        "guard_command": args.guard_command or "",
        "snapshot": str(snapshot),
        "parent_experiment": "",
        "lineage": lineage,
    })
    print(f"Baseline recorded: {format_score(decision_score)} ({args.direction} is better)")
    print("STATUS=keep")
    if private_cmd:
        print(f"Public score: {format_score(score)} | Private score: {format_score(private_score)}")
    print(f"Snapshot: {snapshot}")
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    paths = make_dirs(output_dir)
    state = load_state(output_dir)

    budget_err = check_budget(state)
    if budget_err:
        print(f"ERROR: {budget_err}", file=sys.stderr)
        return BUDGET_EXIT_CODE

    allowed = Path(args.allowed_root).resolve() if args.allowed_root else Path.cwd().resolve()
    targets, targets_changed = _targets_override_requested(args, state, allowed)

    overrides = _cli_config_overrides(args, state)
    if targets_changed:
        overrides = list(overrides) + ["targets"]
    if overrides and not getattr(args, "allow_config_change", False):
        raise SystemExit(
            "ERROR: sealed config change refused for: "
            + ", ".join(overrides)
            + ". Re-run with --allow-config-change if intentional."
        )
    # Always revert the sealed full target set from state unless an allowed override changed it
    if not targets_changed:
        state_raw = state.get("targets") or ([state["target"]] if state.get("target") else [])
        targets = [ensure_target_allowed(Path(p), allowed) for p in state_raw]

    experiment = int(state.get("last_experiment", 1)) + 1
    parent = getattr(args, "parent_experiment", None)
    if parent is None or parent == "":
        parent_id = int(state.get("next_parent_experiment", state.get("best_experiment", 1)))
    else:
        parent_id = int(parent)

    direction = args.direction if args.direction is not None else state["direction"]
    verify_command = args.verify_command if args.verify_command is not None else state["verify_command"]
    guard_command = args.guard_command if args.guard_command is not None else state.get("guard_command", "")
    metric_regex = args.metric_regex if args.metric_regex is not None else state.get("metric_regex", "")
    metric_regex = metric_regex or None
    metric_name = args.metric if getattr(args, "metric", None) is not None else state.get("metric", "")
    metric_name = metric_name or None
    private_cmd = (
        args.private_verify_command
        if getattr(args, "private_verify_command", None) is not None
        else state.get("private_verify_command", "")
    ) or ""
    lineage = getattr(args, "lineage", None)
    if lineage is None:
        lineage = state.get("lineage", "") or ""
    args.cwd = args.cwd if args.cwd is not None else (state.get("cwd") or None)
    args.timeout = resolve_timeout(args, state)

    if getattr(args, "instructions", None) is not None:
        instructions = args.instructions
        if instructions and Path(instructions).is_file():
            instructions = str(Path(instructions).resolve())
        state["instructions"] = instructions

    verify_result, public_score, verify_error = run_verify(args, verify_command, metric_regex, metric_name)
    command_output_file(output_dir, experiment, "verify", verify_result)

    private_score = None
    status = "discard"
    reason = args.description or f"experiment {experiment:03d}"
    candidate_snapshot_status = "discard"
    decision_score: float | None = None

    if verify_error:
        status = "crash"
        reason = f"{reason} — verify failed: {verify_error}"
        candidate_snapshot_status = "crash"
    else:
        if private_cmd:
            priv_result, private_score, priv_error = run_verify(args, private_cmd, metric_regex, metric_name)
            command_output_file(output_dir, experiment, "private_verify", priv_result)
            if priv_error:
                status = "crash"
                reason = f"{reason} — private verify failed: {priv_error}"
                candidate_snapshot_status = "crash"
            else:
                decision_score = private_score
        else:
            decision_score = public_score

        if status != "crash":
            guard_result, guard_error = run_guard(args, guard_command)
            command_output_file(output_dir, experiment, "guard", guard_result)
            if guard_error:
                status = "crash"
                reason = f"{reason} — guard failed: {guard_error}"
                candidate_snapshot_status = "crash"
            else:
                best_score = float(state["best_score"])
                current_size = total_size(targets)
                best_size = int(state.get("best_size", current_size))
                assert decision_score is not None
                if is_improvement(float(decision_score), best_score, direction):
                    status = "keep"
                    candidate_snapshot_status = "keep"
                elif is_tie(float(decision_score), best_score) and current_size < best_size:
                    status = "keep"
                    candidate_snapshot_status = "keep"
                    reason = f"{reason} — tie on score, simpler target"
                else:
                    status = "discard"
                    candidate_snapshot_status = "discard"

    snapshot = snapshot_targets(targets, paths["snapshots"], experiment, candidate_snapshot_status)

    if status == "keep" and decision_score is not None:
        state.update({
            "best_score": decision_score,
            "best_public_score": public_score if public_score is not None else "",
            "best_private_score": private_score if private_score is not None else "",
            "best_size": total_size(targets),
            "best_snapshot": str(snapshot),
            "best_snapshot_sha256": combined_targets_sha256(targets),
            "best_experiment": experiment,
            "next_parent_experiment": experiment,
        })
    else:
        try:
            revert_targets_from_snapshot(
                targets,
                state["best_snapshot"],
                paths["snapshots"],
                expected_sha256=state.get("best_snapshot_sha256") or None,
                strict_snapshots=bool(getattr(args, "strict_snapshots", False)),
            )
        except SystemExit:
            raise
        except OSError as exc:
            raise SystemExit(f"ERROR: failed to revert targets to best snapshot: {exc}") from exc
        # After discard/crash, next parent is best keep (not this failed experiment)
        state["next_parent_experiment"] = int(state.get("best_experiment", 1))

    max_score_val = state.get("max_score", "")
    if getattr(args, "max_score", None) is not None and getattr(args, "allow_config_change", False):
        max_score_val = args.max_score
        state["max_score"] = max_score_val

    state.update({
        "last_experiment": experiment,
        "updated_at": utc_now_iso(),
        "target": str(targets[0]),
        "targets": [str(t) for t in targets],
        "direction": direction,
        "verify_command": verify_command,
        "private_verify_command": private_cmd,
        "guard_command": guard_command or "",
        "metric": metric_name or "",
        "metric_regex": metric_regex or "",
        "cwd": args.cwd or "",
        "timeout": args.timeout,
        "lineage": lineage,
    })
    save_state(output_dir, state)

    append_results(output_dir, {
        "experiment": f"{experiment:03d}",
        "score": format_score(public_score),
        "max_score": format_score(float(max_score_val)) if max_score_val not in ("", None) else "",
        "best_score": format_score(float(state["best_score"])),
        "private_score": format_score(private_score),
        "decision_score": format_score(decision_score),
        "status": status,
        "description": reason,
        "timestamp": utc_now_iso(),
        "direction": direction,
        "verify_command": verify_command,
        "guard_command": guard_command or "",
        "snapshot": str(snapshot),
        "parent_experiment": f"{parent_id:03d}",
        "lineage": lineage,
    })

    print(f"Experiment {experiment:03d}: {status.upper()}")
    # Machine-parseable single token for harness scripts (do not localize)
    print(f"STATUS={status}")
    print(
        f"Score: {format_score(public_score)} | Decision: {format_score(decision_score)} | "
        f"Best: {format_score(float(state['best_score']))} | Direction: {direction} | Parent: {parent_id:03d}"
    )
    if private_cmd:
        print(f"Private score: {format_score(private_score)}")
    print(f"Snapshot: {snapshot}")
    if status != "keep":
        print(f"Reverted targets to best snapshot: {state['best_snapshot']}")
    # Exit codes: 0 keep|discard, 1 crash, 2 budget (checked earlier)
    return 0 if status != "crash" else 1


def cmd_run_verify(args: argparse.Namespace) -> int:
    """Dry-run public verify, optional private verify, and optional guard."""
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

    decision_score = score
    private_cmd = getattr(args, "private_verify_command", None) or ""
    if private_cmd:
        priv_result, private_score, priv_error = run_verify(args, private_cmd, metric_regex, metric_name)
        print(f"Private verify exit: {priv_result.returncode}")
        if priv_error:
            print(f"Private metric: INVALID ({priv_error})")
            print(priv_result.combined_output[-1000:])
            return 1
        print(f"Private metric: {format_score(private_score)}")
        decision_score = private_score
        print(f"Decision metric: {format_score(decision_score)} (private)")
    else:
        print(f"Decision metric: {format_score(decision_score)} (public)")

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
    if getattr(args, "json", False):
        print(json.dumps(state_public_dict(state), indent=2, sort_keys=True))
        return 0
    progress = budget_progress(state)
    print(f"Target: {state['target']}")
    if state.get("targets") and len(state["targets"]) > 1:
        print(f"Targets: {', '.join(state['targets'])}")
    print(f"Mode: {state.get('mode', 'unknown')}")
    print(f"Best: {format_score(float(state['best_score']))} ({state['direction']} is better), experiment {int(state['best_experiment']):03d}")
    print(f"Best snapshot: {state['best_snapshot']}")
    if state.get("metric"):
        print(f"Metric name: {state['metric']}")
    if state.get("private_verify_command"):
        print(f"Private verify: {state['private_verify_command']}")
        print("Decision metric: private (public still logged)")
    if state.get("lineage"):
        print(f"Lineage: {state['lineage']}")
    if state.get("next_parent_experiment") is not None:
        print(f"Next parent: {int(state['next_parent_experiment']):03d}")
    # Budget progress (same numbers as status --json)
    if progress["max_experiments"] is not None:
        rem = progress["candidates_remaining"]
        cand_exh = (
            progress["candidates_done"] >= progress["max_experiments"]
            if progress["max_experiments"] is not None
            else False
        )
        print(
            f"Budget: {progress['candidates_done']}/{progress['max_experiments']} candidates used"
            f" ({rem} remaining)"
            + (" — EXHAUSTED" if cand_exh else "")
        )
    if progress["max_wall_seconds"] is not None:
        elapsed = progress["wall_elapsed_seconds"]
        remaining = progress["wall_remaining_seconds"]
        if elapsed is not None and remaining is not None:
            print(
                f"Wall budget: {elapsed:.1f}s elapsed / {progress['max_wall_seconds']:.0f}s"
                f" ({remaining:.1f}s remaining)"
                + (" — EXHAUSTED" if progress["wall_budget_exhausted"] else "")
            )
        else:
            print(f"Max wall seconds: {progress['max_wall_seconds']:.0f}")
    if state.get("instructions"):
        print(f"Instructions: {state['instructions']}")
    path = results_path(output_dir)
    if path.exists():
        rows = path.read_text(encoding="utf-8").splitlines()[-6:]
        print("\nRecent results:")
        print("\n".join(rows))
    return 0


def cmd_results(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    path = results_path(output_dir)
    if not path.exists():
        raise SystemExit(f"ERROR: no results.tsv at {path}")
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    last_n = getattr(args, "last", None)
    if last_n:
        rows = rows[-int(last_n) :]
    if getattr(args, "json", False):
        print(json.dumps(rows, indent=2))
    else:
        for row in rows:
            print("\t".join(str(row.get(h, "")) for h in RESULTS_HEADER))
    return 0


def cmd_best(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    state = load_state(output_dir)
    payload = {
        "best_score": state.get("best_score"),
        "best_experiment": state.get("best_experiment"),
        "best_snapshot": state.get("best_snapshot"),
        "direction": state.get("direction"),
        "target": state.get("target"),
        "targets": state.get("targets") or [state.get("target")],
    }
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Best score: {format_score(float(state['best_score']))}")
        print(f"Best experiment: {int(state['best_experiment']):03d}")
        print(f"Best snapshot: {state['best_snapshot']}")
    return 0


def cmd_fork(args: argparse.Namespace) -> int:
    """Record a fork from the current best without changing target files or sealed metric config."""
    output_dir = Path(args.output_dir).resolve()
    make_dirs(output_dir)
    state = load_state(output_dir)
    best_exp = int(state.get("best_experiment", 1))
    lineage = args.lineage or state.get("lineage", "") or "fork"
    desc = args.description or f"fork from best experiment {best_exp:03d}"
    state["next_parent_experiment"] = best_exp
    state["lineage"] = lineage
    state["updated_at"] = utc_now_iso()
    save_state(output_dir, state)
    # Audit trail only — does not consume a candidate score slot
    fork_id = f"fork-{utc_now().strftime('%Y%m%dT%H%M%S')}"
    append_results(output_dir, {
        "experiment": fork_id,
        "score": "",
        "max_score": "",
        "best_score": format_score(float(state["best_score"])),
        "private_score": "",
        "decision_score": "",
        "status": "fork",
        "description": desc,
        "timestamp": utc_now_iso(),
        "direction": state.get("direction", ""),
        "verify_command": state.get("verify_command", ""),
        "guard_command": state.get("guard_command", ""),
        "snapshot": state.get("best_snapshot", ""),
        "parent_experiment": f"{best_exp:03d}",
        "lineage": lineage,
    })
    print(f"Fork ready: next parent={best_exp:03d} lineage={lineage}")
    print(f"Logged: {fork_id} (status=fork; does not count toward max_experiments)")
    print("Sealed verify/metric/direction unchanged.")
    if args.description:
        print(f"Note: {args.description}")
    return 0


def add_common(
    parser: argparse.ArgumentParser,
    require_verify: bool = False,
    require_target: bool = False,
    require_direction: bool = False,
) -> None:
    parser.add_argument("--target", default=None, help="Single target file the active harness is optimizing")
    parser.add_argument("--targets", nargs="+", default=None, help="Multiple target files to snapshot/revert together")
    parser.add_argument("--output-dir", default="./autoresearch-results/", help="Directory for state, snapshots, runs, and results.tsv")
    parser.add_argument("--verify-command", required=require_verify, default=None, help="Command that prints/exposes the public numeric metric")
    parser.add_argument(
        "--private-verify-command",
        default=None,
        help="Optional private/held-out verify command; when set, keep/discard uses this score",
    )
    parser.add_argument(
        "--metric",
        default=None,
        help="Metric name to extract (e.g. Score, accuracy). Last name: value match wins.",
    )
    parser.add_argument(
        "--metric-regex",
        default=None,
        help="Regex for extracting the metric (overrides --metric). Last match wins.",
    )
    parser.add_argument("--max-score", type=float, default=None, help="Optional known max score for TSV logging")
    parser.add_argument("--direction", choices=("higher", "lower"), required=require_direction, default=None, help="Whether higher or lower metric values are better")
    parser.add_argument("--guard-command", default=None, help="Optional command that must exit 0 for a change to be kept")
    parser.add_argument("--cwd", default=None, help="Working directory for verify and guard commands")
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help=f"Timeout in seconds for verify and guard commands (default: inherit from state or {DEFAULT_TIMEOUT})",
    )
    parser.add_argument("--allowed-root", default=None, help="Restrict target paths to this root (default: cwd)")
    parser.add_argument("--description", default="", help="Short description of this baseline or candidate change")
    parser.add_argument("--lineage", default=None, help="Optional strategy/lineage tag for this experiment")
    parser.add_argument("--instructions", default=None, help="Steering instructions text or path to a file")
    parser.add_argument("--max-experiments", type=int, default=None, help="Max candidate score runs after baseline (0/omit = unlimited)")
    parser.add_argument("--max-wall-seconds", type=int, default=None, help="Wall-clock budget from baseline created_at")
    if require_target:
        # enforce at runtime that one of target/targets is present
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="No-headless autoresearch state manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    baseline = subparsers.add_parser("baseline", help="Run verify/guard once and establish the baseline")
    add_common(baseline, require_verify=True, require_target=True, require_direction=True)
    baseline.add_argument("--force", action="store_true", help="Replace an existing state.json baseline")
    baseline.set_defaults(func=cmd_baseline)

    score = subparsers.add_parser("score", help="Score the active harness's current candidate and keep/discard it")
    add_common(score, require_verify=False)
    score.add_argument("--parent-experiment", default=None, help="Explicit parent experiment id (default: next_parent from state)")
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
    status.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    status.set_defaults(func=cmd_status)

    results = subparsers.add_parser("results", help="Show results.tsv rows")
    results.add_argument("--output-dir", default="./autoresearch-results/")
    results.add_argument("--json", action="store_true", help="Emit JSON array of rows")
    results.add_argument("--last", type=int, default=None, help="Only last N rows")
    results.set_defaults(func=cmd_results)

    best = subparsers.add_parser("best", help="Show current best score/snapshot")
    best.add_argument("--output-dir", default="./autoresearch-results/")
    best.add_argument("--json", action="store_true", help="Emit JSON")
    best.set_defaults(func=cmd_best)

    fork = subparsers.add_parser("fork", help="Fork next experiment parent from best (no file changes)")
    fork.add_argument("--output-dir", default="./autoresearch-results/")
    fork.add_argument("--lineage", default=None, help="New lineage/strategy tag")
    fork.add_argument("--description", default="", help="Note for the operator/harness")
    fork.set_defaults(func=cmd_fork)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command in ("baseline",) and not args.target and not args.targets:
        parser.error("baseline requires --target or --targets")
    if args.command == "baseline" and args.target and args.targets:
        parser.error("use either --target or --targets, not both")
    if args.command == "score" and args.target and args.targets:
        parser.error("use either --target or --targets, not both")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
