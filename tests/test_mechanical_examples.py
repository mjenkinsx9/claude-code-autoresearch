"""Smoke the shipped mechanical examples with the real loop helper."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
LOOP = ROOT / "scripts" / "autoresearch_loop.py"
HELLO = ROOT / "examples" / "mechanical" / "hello-length"
COMPRESS = ROOT / "examples" / "mechanical" / "constrained-compress"


def run(args, cwd: Path, check: bool = True):
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if check and result.returncode != 0:
        raise AssertionError(
            f"command failed: {' '.join(map(str, args))}\n"
            f"exit={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


class MechanicalExampleSmokeTests(unittest.TestCase):
    def test_hello_length_baseline_keep_discard(self):
        """examples/mechanical/hello-length works with real baseline/score."""
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            shutil.copy(HELLO / "evaluate.py", work / "evaluate.py")
            target = work / "target.txt"
            target.write_text((HELLO / "target.txt").read_text(encoding="utf-8"), encoding="utf-8")

            baseline = run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} evaluate.py",
                "--metric", "Score",
                "--direction", "higher",
                "--max-experiments", "5",
            ], work)
            self.assertIn("Baseline recorded", baseline.stdout)
            state = json.loads((work / "autoresearch-results" / "state.json").read_text(encoding="utf-8"))
            base = float(state["best_score"])
            self.assertGreater(base, 0)

            # Improve length
            target.write_text(target.read_text(encoding="utf-8") + "!!!!", encoding="utf-8")
            keep = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "append bangs",
            ], work)
            self.assertIn("KEEP", keep.stdout)
            state2 = json.loads((work / "autoresearch-results" / "state.json").read_text(encoding="utf-8"))
            self.assertGreater(float(state2["best_score"]), base)

            # Regression
            target.write_text("x", encoding="utf-8")
            discard = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "too short",
            ], work)
            self.assertIn("DISCARD", discard.stdout)
            self.assertNotEqual(target.read_text(encoding="utf-8"), "x")

    def test_constrained_compress_minimize_and_penalty_discard(self):
        """constrained-compress: shorter valid prompt KEEP; accuracy break DISCARD."""
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            shutil.copy(COMPRESS / "evaluate.py", work / "evaluate.py")
            shutil.copy(COMPRESS / "optimize.py", work / "optimize.py")

            run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(work / "optimize.py"),
                "--verify-command", f"{PYTHON} evaluate.py",
                "--metric", "metric",
                "--direction", "lower",
                "--max-experiments", "5",
            ], work)
            base = float(json.loads(
                (work / "autoresearch-results" / "state.json").read_text(encoding="utf-8")
            )["best_score"])

            (work / "optimize.py").write_text(
                'PROMPT = "good=>POS else NEG"\n'
                "def classify(text: str) -> str:\n"
                '    return "POSITIVE" if "good" in text.lower() else "NEGATIVE"\n',
                encoding="utf-8",
            )
            keep = run([
                PYTHON, str(LOOP), "score",
                "--target", str(work / "optimize.py"),
                "--description", "compress prompt",
            ], work)
            self.assertIn("KEEP", keep.stdout)
            best = float(json.loads(
                (work / "autoresearch-results" / "state.json").read_text(encoding="utf-8")
            )["best_score"])
            self.assertLess(best, base)

            (work / "optimize.py").write_text(
                'PROMPT = "x"\n'
                "def classify(text: str) -> str:\n"
                '    return "POSITIVE"\n',
                encoding="utf-8",
            )
            discard = run([
                PYTHON, str(LOOP), "score",
                "--target", str(work / "optimize.py"),
                "--description", "break accuracy",
            ], work)
            self.assertIn("DISCARD", discard.stdout)
            # Reverted to compressed valid prompt
            text = (work / "optimize.py").read_text(encoding="utf-8")
            self.assertIn("good", text.lower())
            self.assertNotIn('return "POSITIVE"\n', text.replace("if", ""))


if __name__ == "__main__":
    unittest.main()
