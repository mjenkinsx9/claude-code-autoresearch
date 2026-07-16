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
    def test_max_wall_seconds_allows_score_within_budget(self):
        """Multi-hour wall budget must not false-expire due to timezone skew."""
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
                "--max-wall-seconds", "3600",
            ], work)
            state = json.loads((work / "autoresearch-results" / "state.json").read_text(encoding="utf-8"))
            # created_at must be timezone-aware UTC (offset present)
            self.assertTrue(
                "+" in state["created_at"] or state["created_at"].endswith("Z"),
                f"expected aware created_at, got {state['created_at']!r}",
            )
            target.write_text("aaaa", encoding="utf-8")
            keep = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "within wall budget",
            ], work)
            self.assertIn("KEEP", keep.stdout)
            self.assertNotIn("BUDGET_EXCEEDED", keep.stderr + keep.stdout)

    def test_max_wall_seconds_expired_refuses_score(self):
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
                "--max-wall-seconds", "3600",
            ], work)
            state_path = work / "autoresearch-results" / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            # Force baseline age beyond budget (UTC-aware)
            from datetime import datetime, timedelta, timezone
            state["created_at"] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
            state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
            before = target.read_text(encoding="utf-8")
            target.write_text("aaaa", encoding="utf-8")
            blocked = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "should hit wall budget",
            ], work, check=False)
            self.assertEqual(blocked.returncode, 2)
            self.assertIn("BUDGET_EXCEEDED", blocked.stderr + blocked.stdout)
            self.assertIn("max_wall_seconds", blocked.stderr + blocked.stdout)
            # Helper must not keep/revert — score refused before mutation of best
            state2 = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state2["best_score"], 3)
            self.assertEqual(state2["last_experiment"], 1)

    def test_check_budget_naive_created_at_not_false_expired(self):
        """Legacy naive local created_at must not be treated as UTC."""
        import importlib.util
        from datetime import datetime, timedelta

        mod_name = "autoresearch_loop_budget_naive"
        spec = importlib.util.spec_from_file_location(mod_name, LOOP)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)

        # Naive timestamp = local now (as old code wrote)
        naive_now = datetime.now().replace(microsecond=0).isoformat()
        err = mod.check_budget({
            "last_experiment": 1,
            "max_wall_seconds": 3600,
            "created_at": naive_now,
        })
        self.assertIsNone(err, f"fresh naive local created_at should be within budget, got {err}")

        old_naive = (datetime.now() - timedelta(hours=2)).replace(microsecond=0).isoformat()
        err2 = mod.check_budget({
            "last_experiment": 1,
            "max_wall_seconds": 3600,
            "created_at": old_naive,
        })
        self.assertIsNotNone(err2)
        self.assertIn("max_wall_seconds", err2)

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
            self.assertEqual(payload["candidates_done"], 0)
            self.assertIsNone(payload["candidates_remaining"])
            self.assertFalse(payload["budget_exhausted"])

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

    def test_status_json_budget_progress_after_scores(self):
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
                "--max-experiments", "2",
            ], work)
            target.write_text("aaaa", encoding="utf-8")
            run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "first candidate",
            ], work)
            status = run([
                PYTHON, str(LOOP), "status", "--json",
                "--output-dir", str(work / "autoresearch-results"),
            ], work)
            payload = json.loads(status.stdout)
            self.assertEqual(payload["candidates_done"], 1)
            self.assertEqual(payload["candidates_remaining"], 1)
            self.assertFalse(payload["budget_exhausted"])
            self.assertEqual(payload["max_experiments"], 2)

            target.write_text("aaaaa", encoding="utf-8")
            run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "second candidate",
            ], work)
            status2 = run([
                PYTHON, str(LOOP), "status", "--json",
                "--output-dir", str(work / "autoresearch-results"),
            ], work)
            payload2 = json.loads(status2.stdout)
            self.assertEqual(payload2["candidates_done"], 2)
            self.assertEqual(payload2["candidates_remaining"], 0)
            self.assertTrue(payload2["budget_exhausted"])


if __name__ == "__main__":
    unittest.main()
