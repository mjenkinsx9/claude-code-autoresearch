"""End-to-end proof: real loop helpers improve a mutable target under a frozen eval."""

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


EVALUATE = '''#!/usr/bin/env python3
from pathlib import Path
REQUIRED = ["Goal:", "Target:", "Metric:", "Direction:", "Verify:", "Guard:", "Stop rules:", "One change:"]
text = Path("program.md").read_text(encoding="utf-8")
score = sum(1 for req in REQUIRED if req.lower() in text.lower())
print(f"Score: {score}")
'''


class MetaSelfImproveTests(unittest.TestCase):
    def test_real_loop_improves_program_checklist(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            (work / "evaluate.py").write_text(EVALUATE, encoding="utf-8")
            program = work / "program.md"
            program.write_text(
                "# Autoresearch program\n\nGoal: demo.\nTarget: this file.\n",
                encoding="utf-8",
            )
            run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(program),
                "--verify-command", f"{PYTHON} evaluate.py",
                "--metric", "Score",
                "--direction", "higher",
                "--max-experiments", "6",
            ], work)
            baseline_state = json.loads((work / "autoresearch-results" / "state.json").read_text(encoding="utf-8"))
            baseline_score = float(baseline_state["best_score"])
            self.assertEqual(baseline_score, 2.0)

            # One focused improvement
            program.write_text(
                program.read_text(encoding="utf-8")
                + "\nMetric: Score from evaluate.py.\nDirection: higher is better.\n",
                encoding="utf-8",
            )
            keep = run([
                PYTHON, str(LOOP), "score",
                "--target", str(program),
                "--description", "add metric and direction",
            ], work)
            self.assertIn("KEEP", keep.stdout)

            # Non-improving noise discarded
            program.write_text(
                program.read_text(encoding="utf-8") + "\nnoise only\n",
                encoding="utf-8",
            )
            discard = run([
                PYTHON, str(LOOP), "score",
                "--target", str(program),
                "--description", "noise",
            ], work)
            self.assertIn("DISCARD", discard.stdout)
            self.assertNotIn("noise only", program.read_text(encoding="utf-8"))

            # Further improvement
            program.write_text(
                program.read_text(encoding="utf-8")
                + "Verify: python evaluate.py\nGuard: omitted.\n"
                + "Stop rules: budget.\nOne change: per experiment.\n",
                encoding="utf-8",
            )
            keep2 = run([
                PYTHON, str(LOOP), "score",
                "--target", str(program),
                "--description", "complete remaining sections",
            ], work)
            self.assertIn("KEEP", keep2.stdout)

            state = json.loads((work / "autoresearch-results" / "state.json").read_text(encoding="utf-8"))
            self.assertGreater(float(state["best_score"]), baseline_score)
            self.assertEqual(float(state["best_score"]), 8.0)

            rows = list(csv.DictReader(
                (work / "autoresearch-results" / "results.tsv").open(encoding="utf-8"),
                delimiter="\t",
            ))
            keeps = [r for r in rows if r["status"] == "keep"]
            self.assertGreaterEqual(len(keeps), 3)
            self.assertTrue(any(r["status"] == "discard" for r in rows))


if __name__ == "__main__":
    unittest.main()
