from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
LOOP = ROOT / "scripts" / "autoresearch_loop.py"


def run(args, cwd: Path, check: bool = True):
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if check and result.returncode != 0:
        raise AssertionError(
            f"command failed: {' '.join(map(str, args))}\n"
            f"exit={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


class SnapshotSandboxTests(unittest.TestCase):
    def test_artifact_path_escape_refused(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = work / "target.txt"
            target.write_text("aaa", encoding="utf-8")
            (work / "score.py").write_text(
                "import pathlib, sys\n"
                "print('Score:', len(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')))\n",
                encoding="utf-8",
            )
            run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} score.py target.txt",
                "--metric", "Score",
                "--direction", "higher",
            ], work)
            state = json.loads((work / "autoresearch-results" / "state.json").read_text(encoding="utf-8"))
            snap = Path(state["best_snapshot"])
            manifest_path = snap / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            # Plant path escape
            manifest["files"][0]["artifact_path"] = "../evil.txt"
            (snap.parent / "evil.txt").write_text("pwned", encoding="utf-8")
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            target.write_text("a", encoding="utf-8")
            result = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "should refuse escape",
                "--strict-snapshots",
            ], work, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("artifact", (result.stderr + result.stdout).lower())
            self.assertNotEqual(target.read_text(encoding="utf-8"), "pwned")

    def test_strict_snapshots_detects_bundle_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = work / "target.txt"
            target.write_text("aaa", encoding="utf-8")
            (work / "score.py").write_text(
                "import pathlib, sys\n"
                "print('Score:', len(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')))\n",
                encoding="utf-8",
            )
            run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} score.py target.txt",
                "--metric", "Score",
                "--direction", "higher",
            ], work)
            state = json.loads((work / "autoresearch-results" / "state.json").read_text(encoding="utf-8"))
            snap = Path(state["best_snapshot"])
            manifest = json.loads((snap / "manifest.json").read_text(encoding="utf-8"))
            art = snap / manifest["files"][0]["artifact_path"]
            art.write_text("TAMPERED", encoding="utf-8")
            # Keep manifest sha stale so per-file check also fires; bundle hash will differ too
            target.write_text("a", encoding="utf-8")
            result = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "tamper",
                "--strict-snapshots",
            ], work, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(
                "hash mismatch" in (result.stderr + result.stdout).lower()
                or "artifact" in (result.stderr + result.stdout).lower()
            )

    def test_subset_targets_require_allow_config_change(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            a = work / "a.txt"
            b = work / "b.txt"
            a.write_text("aa", encoding="utf-8")
            b.write_text("bb", encoding="utf-8")
            (work / "score.py").write_text(
                "import pathlib, sys\n"
                "print('Score:', sum(len(pathlib.Path(p).read_text()) for p in sys.argv[1:]))\n",
                encoding="utf-8",
            )
            run([
                PYTHON, str(LOOP), "baseline",
                "--targets", str(a), str(b),
                "--verify-command", f"{PYTHON} score.py a.txt b.txt",
                "--metric", "Score",
                "--direction", "higher",
            ], work)
            a.write_text("aaa", encoding="utf-8")
            blocked = run([
                PYTHON, str(LOOP), "score",
                "--target", str(a),
                "--description", "subset without unlock",
            ], work, check=False)
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("targets", (blocked.stderr + blocked.stdout).lower())
            state = json.loads((work / "autoresearch-results" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(len(state["targets"]), 2)


if __name__ == "__main__":
    unittest.main()
