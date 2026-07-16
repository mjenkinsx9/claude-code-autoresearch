from __future__ import annotations

import csv
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


def write_scorer(work: Path) -> None:
    (work / "score.py").write_text(
        "import pathlib, sys\n"
        "total = 0\n"
        "for p in sys.argv[1:]:\n"
        "    total += len(pathlib.Path(p).read_text(encoding='utf-8'))\n"
        "print('Score:', total)\n",
        encoding="utf-8",
    )


class LineageMultiTargetTests(unittest.TestCase):
    def test_parent_after_discard_is_best_not_failed(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = work / "target.txt"
            target.write_text("aaa", encoding="utf-8")
            write_scorer(work)
            run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} score.py target.txt",
                "--metric", "Score",
                "--direction", "higher",
            ], work)
            # improve -> keep 002
            target.write_text("aaaa", encoding="utf-8")
            run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "improve",
            ], work)
            # regress -> discard 003, parent should be 002
            target.write_text("a", encoding="utf-8")
            run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "regress",
            ], work)
            # next improve -> 004 parent should be best (002) not 003
            target.write_text("aaaaa", encoding="utf-8")
            run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "after discard",
            ], work)
            rows = list(csv.DictReader(
                (work / "autoresearch-results" / "results.tsv").open(encoding="utf-8"),
                delimiter="\t",
            ))
            by_exp = {r["experiment"]: r for r in rows}
            self.assertEqual(by_exp["002"]["parent_experiment"], "001")
            self.assertEqual(by_exp["003"]["parent_experiment"], "002")
            self.assertEqual(by_exp["003"]["status"], "discard")
            self.assertEqual(by_exp["004"]["parent_experiment"], "002")
            self.assertEqual(by_exp["004"]["status"], "keep")

    def test_multitarget_discard_restores_both(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            a = work / "a.txt"
            b = work / "b.txt"
            a.write_text("aa", encoding="utf-8")
            b.write_text("bb", encoding="utf-8")
            write_scorer(work)
            run([
                PYTHON, str(LOOP), "baseline",
                "--targets", str(a), str(b),
                "--verify-command", f"{PYTHON} score.py a.txt b.txt",
                "--metric", "Score",
                "--direction", "higher",
            ], work)
            a.write_text("aaa", encoding="utf-8")
            b.write_text("bbb", encoding="utf-8")
            keep = run([
                PYTHON, str(LOOP), "score",
                "--targets", str(a), str(b),
                "--description", "both longer",
            ], work)
            self.assertIn("KEEP", keep.stdout)
            a.write_text("x", encoding="utf-8")
            b.write_text("y", encoding="utf-8")
            discard = run([
                PYTHON, str(LOOP), "score",
                "--targets", str(a), str(b),
                "--description", "both worse",
            ], work)
            self.assertIn("DISCARD", discard.stdout)
            self.assertEqual(a.read_text(encoding="utf-8"), "aaa")
            self.assertEqual(b.read_text(encoding="utf-8"), "bbb")
            state = json.loads((work / "autoresearch-results" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(len(state["targets"]), 2)
            snap = Path(state["best_snapshot"])
            self.assertTrue(snap.is_dir())
            self.assertTrue((snap / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
