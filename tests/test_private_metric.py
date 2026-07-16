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


class PrivateMetricTests(unittest.TestCase):
    def test_run_verify_dry_runs_private_and_reports_decision(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = work / "target.txt"
            target.write_text("public=1 private=7", encoding="utf-8")
            (work / "public.py").write_text(
                "import pathlib\n"
                "t=pathlib.Path('target.txt').read_text()\n"
                "print('Score:', t.count('x'))\n",
                encoding="utf-8",
            )
            (work / "private.py").write_text(
                "import pathlib,re\n"
                "t=pathlib.Path('target.txt').read_text()\n"
                "m=re.search(r'private=(\\d+)', t)\n"
                "print('Score:', m.group(1) if m else 0)\n",
                encoding="utf-8",
            )
            out = run([
                PYTHON, str(LOOP), "run-verify",
                "--verify-command", f"{PYTHON} public.py",
                "--private-verify-command", f"{PYTHON} private.py",
                "--metric", "Score",
            ], work)
            self.assertIn("Metric: 0", out.stdout)  # public: no x
            self.assertIn("Private metric: 7", out.stdout)
            self.assertIn("Decision metric: 7", out.stdout)
            self.assertIn("(private)", out.stdout)

    def test_results_log_decision_score_column(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = work / "target.txt"
            target.write_text("public=1 private=5", encoding="utf-8")
            (work / "public.py").write_text(
                "import pathlib\n"
                "t=pathlib.Path('target.txt').read_text()\n"
                "print('Score:', t.count('x'))\n",
                encoding="utf-8",
            )
            (work / "private.py").write_text(
                "import pathlib,re\n"
                "t=pathlib.Path('target.txt').read_text()\n"
                "m=re.search(r'private=(\\d+)', t)\n"
                "print('Score:', m.group(1) if m else 0)\n",
                encoding="utf-8",
            )
            run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} public.py",
                "--private-verify-command", f"{PYTHON} private.py",
                "--metric", "Score",
                "--direction", "higher",
            ], work)
            target.write_text("public=1 private=1 xxxx", encoding="utf-8")
            run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "public up private down",
            ], work)
            import csv
            rows = list(csv.DictReader(
                (work / "autoresearch-results" / "results.tsv").open(encoding="utf-8"),
                delimiter="\t",
            ))
            self.assertIn("decision_score", rows[0])
            self.assertEqual(rows[0]["decision_score"], "5")
            # Discarded row: public spiked to 4 x's, private decision 1
            last = rows[-1]
            self.assertEqual(last["status"], "discard")
            self.assertEqual(last["score"], "4")
            self.assertEqual(last["private_score"], "1")
            self.assertEqual(last["decision_score"], "1")

    def test_public_up_private_down_discards(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = work / "target.txt"
            target.write_text("public=1 private=5", encoding="utf-8")
            # public metric: count of 'x'; private: fixed parse from file token
            (work / "public.py").write_text(
                "import pathlib\n"
                "t=pathlib.Path('target.txt').read_text()\n"
                "print('Score:', t.count('x'))\n",
                encoding="utf-8",
            )
            (work / "private.py").write_text(
                "import pathlib,re\n"
                "t=pathlib.Path('target.txt').read_text()\n"
                "m=re.search(r'private=(\\d+)', t)\n"
                "print('Score:', m.group(1) if m else 0)\n",
                encoding="utf-8",
            )
            run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} public.py",
                "--private-verify-command", f"{PYTHON} private.py",
                "--metric", "Score",
                "--direction", "higher",
            ], work)
            # Public improves (more x) but private drops
            target.write_text("public=1 private=1 xxxx", encoding="utf-8")
            out = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "public up private down",
            ], work)
            self.assertIn("DISCARD", out.stdout)
            self.assertEqual(target.read_text(encoding="utf-8"), "public=1 private=5")

    def test_private_up_keeps(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = work / "target.txt"
            target.write_text("public=1 private=5", encoding="utf-8")
            (work / "public.py").write_text(
                "import pathlib\n"
                "t=pathlib.Path('target.txt').read_text()\n"
                "print('Score:', t.count('x'))\n",
                encoding="utf-8",
            )
            (work / "private.py").write_text(
                "import pathlib,re\n"
                "t=pathlib.Path('target.txt').read_text()\n"
                "m=re.search(r'private=(\\d+)', t)\n"
                "print('Score:', m.group(1) if m else 0)\n",
                encoding="utf-8",
            )
            run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} public.py",
                "--private-verify-command", f"{PYTHON} private.py",
                "--metric", "Score",
                "--direction", "higher",
            ], work)
            target.write_text("public=1 private=9", encoding="utf-8")
            out = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "private improved",
            ], work)
            self.assertIn("KEEP", out.stdout)
            self.assertEqual(target.read_text(encoding="utf-8"), "public=1 private=9")
            state = json.loads((work / "autoresearch-results" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["best_score"], 9)

    def test_fork_sets_parent_to_best(self):
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
            target.write_text("aaaa", encoding="utf-8")
            run([PYTHON, str(LOOP), "score", "--target", str(target), "--description", "keep"], work)
            target.write_text("a", encoding="utf-8")
            run([PYTHON, str(LOOP), "score", "--target", str(target), "--description", "discard"], work)
            fork = run([
                PYTHON, str(LOOP), "fork",
                "--output-dir", str(work / "autoresearch-results"),
                "--lineage", "explore-alt",
                "--description", "try other approach",
            ], work)
            self.assertIn("next parent=002", fork.stdout)
            self.assertIn("status=fork", fork.stdout)
            state = json.loads((work / "autoresearch-results" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["next_parent_experiment"], 2)
            self.assertEqual(state["lineage"], "explore-alt")
            # Fork does not consume a score experiment id
            self.assertEqual(int(state["last_experiment"]), 3)
            import csv
            rows = list(csv.DictReader(
                (work / "autoresearch-results" / "results.tsv").open(encoding="utf-8"),
                delimiter="\t",
            ))
            fork_rows = [r for r in rows if r["status"] == "fork"]
            self.assertEqual(len(fork_rows), 1)
            self.assertTrue(fork_rows[0]["experiment"].startswith("fork-"))
            self.assertEqual(fork_rows[0]["parent_experiment"], "002")
            self.assertEqual(fork_rows[0]["lineage"], "explore-alt")
            target.write_text("aaaaaa", encoding="utf-8")
            run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "after fork",
            ], work)
            rows = list(csv.DictReader(
                (work / "autoresearch-results" / "results.tsv").open(encoding="utf-8"),
                delimiter="\t",
            ))
            last = rows[-1]
            self.assertEqual(last["parent_experiment"], "002")
            self.assertEqual(last["lineage"], "explore-alt")
            self.assertEqual(last["status"], "keep")


if __name__ == "__main__":
    unittest.main()
