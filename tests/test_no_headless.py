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
EVAL = ROOT / "scripts" / "eval_engine.py"
AGENT_CLI = ROOT / "scripts" / "agent_cli.py"


def run(args, cwd: Path, check: bool = True):
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if check and result.returncode != 0:
        raise AssertionError(
            f"command failed: {' '.join(map(str, args))}\n"
            f"exit={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


class NoHeadlessAutoresearchTests(unittest.TestCase):
    def test_help_exposes_no_headless_commands(self):
        loop_help = run([PYTHON, str(LOOP), "--help"], ROOT).stdout
        eval_help = run([PYTHON, str(EVAL), "--help"], ROOT).stdout
        self.assertIn("baseline", loop_help)
        self.assertIn("score", loop_help)
        self.assertIn("run-verify", loop_help)
        self.assertIn("--emit-prompt", eval_help)
        self.assertIn("--judgments-file", eval_help)
        self.assertNotIn("--agent-backend", eval_help)

    def test_mechanical_keep_and_discard_reverts_to_best_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = work / "target.txt"
            target.write_text("aaa")
            (work / "score.py").write_text(
                "import pathlib, sys\n"
                "print('Score:', len(pathlib.Path(sys.argv[1]).read_text()))\n"
            )

            base = run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} score.py target.txt",
                "--metric-regex", r"Score: (\d+)",
                "--direction", "higher",
            ], work)
            self.assertIn("STATUS=keep", base.stdout)
            self.assertIn("EXPERIMENT=001", base.stdout)
            self.assertIn("DIRECTION=higher", base.stdout)
            self.assertIn("PUBLIC=3", base.stdout)
            self.assertIn("MODE=mechanical-no-headless", base.stdout)
            self.assertIn("SCHEMA_VERSION=2", base.stdout)
            self.assertIn("OUTPUT_DIR=", base.stdout)

            target.write_text("aaaa")
            keep = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "longer candidate",
            ], work)
            self.assertIn("KEEP", keep.stdout)
            self.assertIn("STATUS=keep", keep.stdout)
            self.assertIn("EXPERIMENT=002", keep.stdout)
            self.assertIn("BEST=4", keep.stdout)
            self.assertIn("PUBLIC=4", keep.stdout)
            self.assertIn("DIRECTION=higher", keep.stdout)
            self.assertEqual(target.read_text(), "aaaa")

            target.write_text("a")
            discard = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "shorter regression",
            ], work)
            self.assertIn("DISCARD", discard.stdout)
            self.assertIn("STATUS=discard", discard.stdout)
            self.assertIn("REVERTED=true", discard.stdout)
            self.assertIn("SNAPSHOT=", discard.stdout)
            self.assertIn("BEST_SNAPSHOT=", discard.stdout)
            self.assertEqual(target.read_text(), "aaaa")

            rows = (work / "autoresearch-results" / "results.tsv").read_text()
            self.assertIn("longer candidate", rows)
            self.assertIn("shorter regression", rows)

    def test_guard_failure_is_crash_and_reverts(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = work / "target.txt"
            target.write_text("aaa")
            (work / "score.py").write_text(
                "import pathlib, sys\n"
                "print('Score:', len(pathlib.Path(sys.argv[1]).read_text()))\n"
            )
            (work / "guard.py").write_text(
                "import pathlib, sys\n"
                "sys.exit(1 if 'bad' in pathlib.Path('target.txt').read_text() else 0)\n"
            )

            run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} score.py target.txt",
                "--metric-regex", r"Score: (\d+)",
                "--direction", "higher",
                "--guard-command", f"{PYTHON} guard.py",
            ], work)

            target.write_text("aaaa bad")
            crash = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "guard failing improvement",
            ], work, check=False)
            self.assertEqual(crash.returncode, 1)
            self.assertIn("CRASH", crash.stdout)
            self.assertEqual(target.read_text(), "aaa")
            self.assertTrue((work / "autoresearch-results" / "runs" / "experiment_002" / "guard.txt").exists())

    def test_eval_engine_scores_supplied_judgments(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            config = work / "eval.json"
            config.write_text(json.dumps({
                "criteria": [{"id": 1, "question": "Does it work?"}],
                "test_prompts": ["demo"],
            }))
            judgments = json.dumps({
                "outputs": [{
                    "output_id": "sample",
                    "scores": [{"criterion": 1, "question": "Does it work?", "passed": True, "evidence": "yes"}],
                }]
            })
            prompt = run([
                PYTHON, str(EVAL),
                "--eval-config", str(config),
                "--output", "sample output",
                "--emit-prompt",
            ], work).stdout
            self.assertIn("Do not call any headless model command", prompt)

            scored = run([
                PYTHON, str(EVAL),
                "--eval-config", str(config),
                "--output", "sample output",
                "--judgments", judgments,
            ], work).stdout
            self.assertIn("Score: 1/1", scored)

    def test_legacy_agent_cli_is_disabled(self):
        result = run([PYTHON, str(AGENT_CLI)], ROOT, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Headless agent invocation has been removed", result.stdout)


if __name__ == "__main__":
    unittest.main()
