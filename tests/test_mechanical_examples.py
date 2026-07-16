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
MULTI = ROOT / "examples" / "mechanical" / "multitarget-api"


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

    def test_multitarget_api_example_keep_and_discard(self):
        """examples/mechanical/multitarget-api: both files snapshotted/restored."""
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            for name in ("evaluate.py", "features.py", "model.py"):
                shutil.copy(MULTI / name, work / name)

            run([
                PYTHON, str(LOOP), "baseline",
                "--targets", str(work / "features.py"), str(work / "model.py"),
                "--verify-command", f"{PYTHON} evaluate.py",
                "--metric", "Score",
                "--direction", "higher",
                "--max-experiments", "5",
            ], work)
            base = float(json.loads(
                (work / "autoresearch-results" / "state.json").read_text(encoding="utf-8")
            )["best_score"])
            # baseline: featurize *2, sum([2,4,6]) = 12
            self.assertEqual(base, 12.0)

            # Improve model score multiplier
            (work / "model.py").write_text(
                "def score(features):\n    return sum(features) * 2\n",
                encoding="utf-8",
            )
            keep = run([
                PYTHON, str(LOOP), "score",
                "--targets", str(work / "features.py"), str(work / "model.py"),
                "--description", "double model sum",
            ], work)
            self.assertIn("KEEP", keep.stdout)
            best = float(json.loads(
                (work / "autoresearch-results" / "state.json").read_text(encoding="utf-8")
            )["best_score"])
            self.assertEqual(best, 24.0)

            # Regress features only
            (work / "features.py").write_text(
                "def featurize(xs):\n    return [0 for _ in xs]\n",
                encoding="utf-8",
            )
            discard = run([
                PYTHON, str(LOOP), "score",
                "--targets", str(work / "features.py"), str(work / "model.py"),
                "--description", "zero features",
            ], work)
            self.assertIn("DISCARD", discard.stdout)
            # Both files restored to best (features *2, model *2)
            features = (work / "features.py").read_text(encoding="utf-8")
            model = (work / "model.py").read_text(encoding="utf-8")
            self.assertIn("x * 2", features)
            self.assertIn("* 2", model)


if __name__ == "__main__":
    unittest.main()
