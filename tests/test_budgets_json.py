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


class BudgetsJsonTests(unittest.TestCase):
    def test_max_experiments_refuses_and_does_not_mutate(self):
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
                "--max-experiments", "1",
            ], work)
            target.write_text("aaaa", encoding="utf-8")
            run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "only allowed candidate",
            ], work)
            before = target.read_text(encoding="utf-8")
            target.write_text("aaaaa", encoding="utf-8")
            blocked = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "should budget fail",
            ], work, check=False)
            self.assertEqual(blocked.returncode, 2)
            self.assertIn("BUDGET_EXCEEDED", blocked.stderr + blocked.stdout)
            self.assertEqual(target.read_text(encoding="utf-8"), "aaaaa")  # score refused before mutate... wait
            # score should not revert or snapshot — target left as caller left it, but not reverted
            # Plan: "do not mutate the target" meaning helper doesn't change it. Content may still be user edit.
            # Best stays previous keep.
            state = json.loads((work / "autoresearch-results" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["best_score"], 4)
            self.assertEqual(state["last_experiment"], 2)

    def test_status_results_best_json(self):
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
            status = run([PYTHON, str(LOOP), "status", "--json", "--output-dir", str(work / "autoresearch-results")], work)
            payload = json.loads(status.stdout)
            self.assertEqual(payload["best_score"], 3)
            self.assertEqual(payload["best_experiment"], 1)
            self.assertIn("mode", payload)

            results = run([
                PYTHON, str(LOOP), "results", "--json", "--last", "5",
                "--output-dir", str(work / "autoresearch-results"),
            ], work)
            rows = json.loads(results.stdout)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "keep")

            best = run([
                PYTHON, str(LOOP), "best", "--json",
                "--output-dir", str(work / "autoresearch-results"),
            ], work)
            best_payload = json.loads(best.stdout)
            self.assertEqual(best_payload["best_score"], 3)
            self.assertEqual(best_payload["best_experiment"], 1)


if __name__ == "__main__":
    unittest.main()
