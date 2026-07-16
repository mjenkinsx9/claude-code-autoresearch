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

    def test_results_header_migrates_when_columns_added(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = self._setup_work(work)
            out = work / "autoresearch-results"
            out.mkdir()
            # Stale header without decision_score / lineage extras
            stale = out / "results.tsv"
            stale.write_text(
                "experiment\tscore\tmax_score\tbest_score\tstatus\tdescription\t"
                "timestamp\tdirection\tverify_command\tguard_command\tsnapshot\n"
                "001\t3\t\t3\tkeep\tbaseline\t2026-07-16T00:00:00\thigher\t\t\tsnap\n",
                encoding="utf-8",
            )
            # Seed minimal state via real baseline in a sibling dir then copy?
            # Easier: run score path after baseline in work with pre-seeded stale TSV
            # Baseline refuses if state exists; score needs state. Create baseline first without TSV race:
            # Write state by running baseline in empty dir then replace TSV with stale and score.
            run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} score.py target.txt",
                "--metric", "Score",
                "--direction", "higher",
                "--output-dir", str(out),
            ], work)
            # Overwrite with stale-schema TSV that still has baseline row semantics
            stale.write_text(
                "experiment\tscore\tmax_score\tbest_score\tstatus\tdescription\t"
                "timestamp\tdirection\tverify_command\tguard_command\tsnapshot\n"
                "001\t3\t\t3\tkeep\tbaseline\t2026-07-16T00:00:00\thigher\t\t\tsnap\n",
                encoding="utf-8",
            )
            target.write_text("aaaa", encoding="utf-8")
            scored = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--description", "after migrate",
                "--output-dir", str(out),
            ], work)
            self.assertIn("STATUS=keep", scored.stdout)
            header = stale.read_text(encoding="utf-8").splitlines()[0].split("\t")
            self.assertIn("decision_score", header)
            self.assertIn("parent_experiment", header)
            self.assertIn("lineage", header)
            import csv
            rows = list(csv.DictReader(stale.open(encoding="utf-8"), delimiter="\t"))
            self.assertEqual(rows[0]["experiment"], "001")
            self.assertEqual(rows[0].get("decision_score", ""), "")  # migrated blank
            self.assertEqual(rows[-1]["status"], "keep")
            self.assertEqual(rows[-1]["decision_score"], "4")

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

    def test_baseline_rotates_orphan_results_tsv_without_state(self):
        """Fresh baseline must not append onto a leftover results.tsv when state.json is missing."""
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = self._setup_work(work)
            out = work / "autoresearch-results"
            out.mkdir(parents=True)
            orphan = out / "results.tsv"
            orphan.write_text(
                "experiment\tscore\tmax_score\tbest_score\tprivate_score\tdecision_score\tstatus\t"
                "description\ttimestamp\tdirection\tverify_command\tguard_command\t"
                "snapshot\tparent_experiment\tlineage\n"
                "001\t99\t\t99\t\t99\tkeep\torphan\t2026-07-16T00:00:00+00:00\thigher\t\t\t\t\t\n"
                "002\t1\t\t99\t\t1\tdiscard\told\t2026-07-16T00:01:00+00:00\thigher\t\t\t\t001\t\n",
                encoding="utf-8",
            )
            run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} score.py target.txt",
                "--metric", "Score",
                "--direction", "higher",
            ], work)
            text = (out / "results.tsv").read_text(encoding="utf-8")
            data_rows = [ln for ln in text.splitlines()[1:] if ln.strip()]
            self.assertEqual(len(data_rows), 1)
            self.assertIn("001", data_rows[0])
            self.assertNotIn("002", text)
            self.assertNotIn("orphan", text)
            prev = list(out.glob("results.prev.*.tsv"))
            self.assertEqual(len(prev), 1)
            self.assertIn("orphan", prev[0].read_text(encoding="utf-8"))

    def test_force_baseline_never_clobbers_prior_rotated_tsv(self):
        """Second --force must not overwrite an existing results.prev archive."""
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = self._setup_work(work)
            out = work / "autoresearch-results"
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
                "--description", "keep for first archive",
            ], work)
            # Force twice in a row; archives must both survive even if timestamps collide.
            for desc in ("force-a", "force-b"):
                target.write_text("aa", encoding="utf-8")
                run([
                    PYTHON, str(LOOP), "baseline",
                    "--target", str(target),
                    "--verify-command", f"{PYTHON} score.py target.txt",
                    "--metric", "Score",
                    "--direction", "higher",
                    "--force",
                    "--description", desc,
                ], work)
            prev = sorted(out.glob("results.prev.*.tsv"))
            self.assertGreaterEqual(len(prev), 2, f"expected >=2 archives, got {prev}")
            bodies = [p.read_text(encoding="utf-8") for p in prev]
            # At least one archive must retain the pre-first-force experiment 002 row
            self.assertTrue(
                any("002" in body for body in bodies),
                "prior research log with experiment 002 was lost to rename clobber",
            )
            # Current results is a fresh single-row baseline
            current = (out / "results.tsv").read_text(encoding="utf-8")
            data_rows = [ln for ln in current.splitlines()[1:] if ln.strip()]
            self.assertEqual(len(data_rows), 1)

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

    def test_max_score_change_requires_allow_config_change(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            target = self._setup_work(work)
            run([
                PYTHON, str(LOOP), "baseline",
                "--target", str(target),
                "--verify-command", f"{PYTHON} score.py target.txt",
                "--metric", "Score",
                "--direction", "higher",
                "--max-score", "10",
            ], work)
            target.write_text("aaaa", encoding="utf-8")
            blocked = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--max-score", "99",
                "--description", "change max",
            ], work, check=False)
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("max_score", (blocked.stderr + blocked.stdout).lower())
            # Same max is a no-op (not a seal break)
            allowed_same = run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--max-score", "10",
                "--description", "same max",
            ], work)
            self.assertIn("STATUS=keep", allowed_same.stdout)
            # Explicit change with allow updates state
            target.write_text("aaaaa", encoding="utf-8")
            run([
                PYTHON, str(LOOP), "score",
                "--target", str(target),
                "--max-score", "99",
                "--allow-config-change",
                "--description", "raise max",
            ], work)
            state = json.loads((work / "autoresearch-results" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(float(state["max_score"]), 99.0)


if __name__ == "__main__":
    unittest.main()
