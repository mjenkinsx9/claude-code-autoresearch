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

            run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} score.py target.txt",
                "--metric-regex", r"Score: (\d+)",
                "--direction", "higher",
            ], work)

            target.write_text("aaaa")
            keep = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "longer candidate",
            ], work)
            self.assertIn("KEEP", keep.stdout)
            self.assertEqual(target.read_text(), "aaaa")

            target.write_text("a")
            discard = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "shorter regression",
            ], work)
            self.assertIn("DISCARD", discard.stdout)
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

    def test_generate_dashboard_renders_results_tsv(self):
        DASHBOARD = ROOT / "scripts" / "generate_dashboard.py"
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            results = work / "results.tsv"
            results.write_text(
                "experiment\tscore\tmax_score\tbest_score\tstatus\tdescription\ttimestamp\tdirection\tverify_command\tguard_command\tsnapshot\n"
                "001\t5\t\t5\tkeep\tbaseline\t2026-01-01T00:00:00\thigher\tcmd\t\tsnap1\n"
                "002\t7\t\t7\tkeep\timprovement\t2026-01-01T00:01:00\thigher\tcmd\t\tsnap2\n"
            )
            output = work / "dashboard.html"
            result = run([
                PYTHON, str(DASHBOARD),
                "--results", str(results),
                "--output", str(output),
            ], work)
            self.assertIn("Dashboard written to", result.stdout)
            html = output.read_text()
            self.assertIn("Best score", html)
            self.assertIn("improvement", html)

    def test_eval_engine_rejects_config_missing_required_keys(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            config = work / "eval.json"
            config.write_text(json.dumps({"criteria": [{"id": 1, "question": "Does it work?"}]}))
            result = run([
                PYTHON, str(EVAL),
                "--eval-config", str(config),
                "--output", "sample output",
                "--emit-prompt",
            ], work, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("test_prompts", result.stdout + result.stderr)

    def test_run_verify_dry_run_reports_metric_without_state(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            (work / "score.py").write_text(
                "print('Score: 42')\n"
            )
            result = run([
                PYTHON, str(LOOP), "run-verify",
                "--verify-command", f"{PYTHON} score.py",
                "--metric-regex", r"Score: (\d+)",
            ], work)
            self.assertIn("42", result.stdout)
            self.assertFalse((work / "autoresearch-results").exists())

    def test_generate_dashboard_missing_results_file_errors(self):
        DASHBOARD = ROOT / "scripts" / "generate_dashboard.py"
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            result = run([
                PYTHON, str(DASHBOARD),
                "--results", str(work / "missing.tsv"),
                "--output", str(work / "dashboard.html"),
            ], work, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("results file not found", result.stdout + result.stderr)

    def test_tie_score_kept_when_target_shrinks(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = work / "target.txt"
            target.write_text("aaaaaaaaaa")
            (work / "score.py").write_text(
                "print('Score: 10')\n"
            )
            run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} score.py",
                "--metric-regex", r"Score: (\d+)",
                "--direction", "higher",
            ], work)

            target.write_text("aaa")
            result = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "same score, smaller file",
            ], work)
            self.assertIn("KEEP", result.stdout)
            self.assertIn("tie on score", (work / "autoresearch-results" / "results.tsv").read_text())

    def test_target_outside_allowed_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            outside = Path(tempfile.mkdtemp())
            try:
                target = outside / "target.txt"
                target.write_text("aaa")
                result = run([
                    PYTHON, str(LOOP), "baseline",
                    "--target", str(target),
                    "--verify-command", "echo Score: 1",
                    "--metric-regex", r"Score: (\d+)",
                    "--direction", "higher",
                    "--allowed-root", str(work),
                ], work, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("is not under --allowed-root", result.stdout + result.stderr)
            finally:
                shutil.rmtree(outside, ignore_errors=True)

    def test_metric_regex_no_match_is_crash(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = work / "target.txt"
            target.write_text("aaa")
            (work / "score.py").write_text("print('nothing useful here')\n")
            result = run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} score.py",
                "--metric-regex", r"Score: (\d+)",
                "--direction", "higher",
            ], work, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertIn("invalid baseline verify result", result.stderr)
            self.assertFalse((work / "autoresearch-results" / "state.json").exists())

    def test_eval_engine_accepts_bare_list_of_score_records(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            config = work / "eval.json"
            config.write_text(json.dumps({
                "criteria": [{"id": 1, "question": "Is it correct?"}],
                "test_prompts": ["demo"],
            }))
            judgments = json.dumps([
                {"criterion": 1, "question": "Is it correct?", "passed": "no", "evidence": "nope"},
            ])
            scored = run([
                PYTHON, str(EVAL),
                "--eval-config", str(config),
                "--output", "sample output",
                "--judgments", judgments,
            ], work).stdout
            self.assertIn("Score: 0/1", scored)

    def test_status_command_reports_best_and_recent_rows(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = work / "target.txt"
            target.write_text("aaa")
            (work / "score.py").write_text("print('Score: 3')\n")
            run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} score.py",
                "--metric-regex", r"Score: (\d+)",
                "--direction", "higher",
            ], work)
            result = run([PYTHON, str(LOOP), "status"], work)
            self.assertIn("Best: 3", result.stdout)
            self.assertIn("Recent results", result.stdout)

    def test_run_verify_reports_guard_failure(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            (work / "score.py").write_text("print('Score: 5')\n")
            (work / "guard.py").write_text("import sys; sys.exit(1)\n")
            result = run([
                PYTHON, str(LOOP), "run-verify",
                "--verify-command", f"{PYTHON} score.py",
                "--metric-regex", r"Score: (\d+)",
                "--guard-command", f"{PYTHON} guard.py",
            ], work, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Guard exit: 1", result.stdout)

    def test_generate_dashboard_lower_is_better_and_blank_scores(self):
        DASHBOARD = ROOT / "scripts" / "generate_dashboard.py"
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            results = work / "results.tsv"
            results.write_text(
                "experiment\tscore\tmax_score\tbest_score\tstatus\tdescription\ttimestamp\tdirection\tverify_command\tguard_command\tsnapshot\n"
                "001\t100\t\t100\tkeep\tbaseline\t2026-01-01T00:00:00\tlower\tcmd\t\tsnap1\n"
                "002\t\t\t100\tcrash\tbroken run\t2026-01-01T00:01:00\tlower\tcmd\t\tsnap2\n"
                "003\t40\t\t40\tkeep\tmuch smaller\t2026-01-01T00:02:00\tlower\tcmd\t\tsnap3\n"
            )
            output = work / "dashboard.html"
            run([
                PYTHON, str(DASHBOARD),
                "--results", str(results),
                "--output", str(output),
                "--title", "Lower Is Better Run",
            ], work)
            html = output.read_text()
            self.assertIn("<div class=\"stat\">40</div>", html)
            self.assertIn("lower is better", html)
            self.assertIn("Lower Is Better Run", html)

    def test_run_agent_prompt_raises_when_imported_directly(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import agent_cli
            with self.assertRaises(agent_cli.HeadlessAgentDisabledError):
                agent_cli.run_agent_prompt("some prompt")
        finally:
            sys.path.remove(str(ROOT / "scripts"))

    def test_baseline_rerun_without_force_errors_then_force_overwrites(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = work / "target.txt"
            target.write_text("aaa")
            (work / "score.py").write_text("print('Score: 3')\n")
            base_args = [
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} score.py",
                "--metric-regex", r"Score: (\d+)",
                "--direction", "higher",
            ]
            run(base_args, work)

            blocked = run(base_args, work, check=False)
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("already exists", blocked.stdout + blocked.stderr)

            (work / "score.py").write_text("print('Score: 9')\n")
            forced = run(base_args + ["--force"], work)
            self.assertIn("Baseline recorded: 9", forced.stdout)

    def test_dashboard_computes_score_percentage_when_max_score_present(self):
        DASHBOARD = ROOT / "scripts" / "generate_dashboard.py"
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            results = work / "results.tsv"
            results.write_text(
                "experiment\tscore\tmax_score\tbest_score\tstatus\tdescription\ttimestamp\tdirection\tverify_command\tguard_command\tsnapshot\n"
                "001\t7\t10\t7\tkeep\tbinary eval baseline\t2026-01-01T00:00:00\thigher\tcmd\t\tsnap1\n"
            )
            output = work / "dashboard.html"
            run([
                PYTHON, str(DASHBOARD),
                "--results", str(results),
                "--output", str(output),
            ], work)
            sys.path.insert(0, str(ROOT / "scripts"))
            try:
                import generate_dashboard
                rows = generate_dashboard.load_results(str(results))
                self.assertEqual(rows[0]["score_pct"], 70.0)
            finally:
                sys.path.remove(str(ROOT / "scripts"))


if __name__ == "__main__":
    unittest.main()
