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


class IntegrityLoopTests(unittest.TestCase):
    def _setup_work(self, work: Path) -> Path:
        target = work / "target.txt"
        target.write_text("aaa", encoding="utf-8")
        (work / "score.py").write_text(
            "import pathlib, sys\n"
            "print('Score:', len(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')))\n",
            encoding="utf-8",
        )
        return target

    def test_named_metric_baseline_and_score(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = self._setup_work(work)
            run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} score.py target.txt",
                "--metric", "Score",
                "--direction", "higher",
            ], work)
            state = json.loads((work / "autoresearch-results" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state.get("metric"), "Score")
            self.assertEqual(state["best_score"], 3)

            target.write_text("aaaa", encoding="utf-8")
            keep = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "longer",
            ], work)
            self.assertIn("KEEP", keep.stdout)

    def test_config_seal_blocks_verify_change(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = self._setup_work(work)
            run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} score.py target.txt",
                "--metric", "Score",
                "--direction", "higher",
            ], work)
            before = target.read_text(encoding="utf-8")
            blocked = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--verify-command", "echo Score: 999",
                "--description", "evil verify",
            ], work, check=False)
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("allow-config-change", (blocked.stderr + blocked.stdout).lower())
            self.assertEqual(target.read_text(encoding="utf-8"), before)

    def test_config_change_allowed_with_flag(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = self._setup_work(work)
            run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} score.py target.txt",
                "--metric", "Score",
                "--direction", "higher",
            ], work)
            (work / "score2.py").write_text(
                "import pathlib, sys\n"
                "print('Score:', len(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')) * 2)\n",
                encoding="utf-8",
            )
            target.write_text("aaaa", encoding="utf-8")
            allowed = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--verify-command", f"{PYTHON} score2.py target.txt",
                "--allow-config-change",
                "--description", "new verify",
            ], work)
            self.assertIn("KEEP", allowed.stdout)

    def test_snapshot_path_escape_refused(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = self._setup_work(work)
            evil = work / "evil.txt"
            evil.write_text("pwned", encoding="utf-8")
            run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} score.py target.txt",
                "--metric", "Score",
                "--direction", "higher",
            ], work)
            state_path = work / "autoresearch-results" / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["best_snapshot"] = str(evil.resolve())
            state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

            target.write_text("a", encoding="utf-8")
            result = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "should refuse escape",
            ], work, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("snapshot", (result.stderr + result.stdout).lower())
            # Target should not have been overwritten with evil content via failed revert path
            self.assertNotEqual(target.read_text(encoding="utf-8"), "pwned")

    def test_utf8_target_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = work / "target.txt"
            target.write_text("ααα", encoding="utf-8")
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
            target.write_text("αααα", encoding="utf-8")
            keep = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "more greek",
            ], work)
            self.assertIn("KEEP", keep.stdout)
            self.assertEqual(target.read_text(encoding="utf-8"), "αααα")

            target.write_text("α", encoding="utf-8")
            discard = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "regression",
            ], work)
            self.assertIn("DISCARD", discard.stdout)
            self.assertEqual(target.read_text(encoding="utf-8"), "αααα")

    def test_timeout_default_none_inherits_state(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = self._setup_work(work)
            run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} score.py target.txt",
                "--metric", "Score",
                "--direction", "higher",
                "--timeout", "90",
            ], work)
            state = json.loads((work / "autoresearch-results" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["timeout"], 90)
            target.write_text("aaaa", encoding="utf-8")
            run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "inherit timeout",
            ], work)
            state2 = json.loads((work / "autoresearch-results" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state2["timeout"], 90)

    def test_force_baseline_rotates_results_tsv(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = self._setup_work(work)
            run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} score.py target.txt",
                "--metric", "Score",
                "--direction", "higher",
            ], work)
            target.write_text("aaaa", encoding="utf-8")
            run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "pre-force keep",
            ], work)
            results = work / "autoresearch-results" / "results.tsv"
            before = results.read_text(encoding="utf-8")
            self.assertIn("002", before)

            target.write_text("aa", encoding="utf-8")
            forced = run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} score.py target.txt",
                "--metric", "Score",
                "--direction", "higher",
                "--force",
                "--description", "fresh baseline",
            ], work)
            self.assertIn("Baseline recorded", forced.stdout)
            new_text = results.read_text(encoding="utf-8")
            # Only one experiment row after header
            data_rows = [ln for ln in new_text.splitlines()[1:] if ln.strip()]
            self.assertEqual(len(data_rows), 1)
            self.assertIn("001", data_rows[0])
            self.assertNotIn("002", new_text)
            prev = list((work / "autoresearch-results").glob("results.prev.*.tsv"))
            self.assertEqual(len(prev), 1)
            self.assertIn("002", prev[0].read_text(encoding="utf-8"))

    def test_cwd_change_requires_allow_config_change(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            other = work / "other"
            other.mkdir()
            target = self._setup_work(work)
            run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} score.py target.txt",
                "--metric", "Score",
                "--direction", "higher",
                "--cwd", str(work),
            ], work)
            blocked = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--cwd", str(other),
                "--description", "cwd change",
            ], work, check=False)
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("cwd", (blocked.stderr + blocked.stdout).lower())
            self.assertIn("allow-config-change", (blocked.stderr + blocked.stdout).lower())


if __name__ == "__main__":
    unittest.main()
