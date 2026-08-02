from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "scripts" / "generate_dashboard.py"

_mod_name = "generate_dashboard_under_test"
_spec = importlib.util.spec_from_file_location(_mod_name, DASH)
assert _spec and _spec.loader
_dash = importlib.util.module_from_spec(_spec)
sys.modules[_mod_name] = _dash
_spec.loader.exec_module(_dash)


class DashboardBestScoreTests(unittest.TestCase):
    def test_best_uses_tsv_best_score_not_public_peak(self):
        """Public can spike on a discarded row; decision best stays private/best_score."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "results.tsv"
            path.write_text(
                "experiment\tscore\tmax_score\tbest_score\tprivate_score\tstatus\t"
                "description\ttimestamp\tdirection\tverify_command\tguard_command\t"
                "snapshot\tparent_experiment\tlineage\n"
                "001\t0\t\t5\t5\tkeep\tbaseline\t2026-07-16T00:00:00+00:00\thigher\t\t\t\t\t\n"
                "002\t99\t\t5\t1\tdiscard\tpublic spike private down\t2026-07-16T00:01:00+00:00\thigher\t\t\t\t001\t\n"
                "003\t0\t\t9\t9\tkeep\tprivate improved\t2026-07-16T00:02:00+00:00\thigher\t\t\t\t001\t\n",
                encoding="utf-8",
            )
            rows = _dash.load_results(str(path))
            best, direction = _dash.decision_best_score(rows)
            self.assertEqual(direction, "higher")
            self.assertEqual(best, 9.0)
            html = _dash.generate_html(rows, "test")
            # Headline stat card uses decision best (9), not discarded public 99
            self.assertIn('<div class="stat">9</div>', html)
            self.assertNotIn('<div class="stat">99</div>', html)
            self.assertIn("<th>Decision</th>", html)
            # Discarded row decision is private 1, not public 99
            self.assertIn("<td>99</td><td>1</td><td>1</td>", html.replace(" ", ""))

    def test_best_respects_lower_direction(self):
        rows = [
            {
                "direction": "lower",
                "status": "keep",
                "score_num": 10.0,
                "private_score_num": None,
                "best_score_num": 10.0,
                "decision_score_num": 10.0,
            },
            {
                "direction": "lower",
                "status": "keep",
                "score_num": 4.0,
                "private_score_num": None,
                "best_score_num": 4.0,
                "decision_score_num": 4.0,
            },
            {
                "direction": "lower",
                "status": "discard",
                "score_num": 1.0,
                "private_score_num": None,
                "best_score_num": 4.0,
                "decision_score_num": 1.0,
            },
        ]
        best, direction = _dash.decision_best_score(rows)
        self.assertEqual(direction, "lower")
        self.assertEqual(best, 4.0)

    def test_chart_path_starts_after_null_score_rows(self):
        """Fork rows lack decision scores; chart must moveTo first numeric point, not i===0."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "results.tsv"
            path.write_text(
                "experiment\tscore\tmax_score\tbest_score\tprivate_score\tdecision_score\tstatus\t"
                "description\ttimestamp\tdirection\tverify_command\tguard_command\t"
                "snapshot\tparent_experiment\tlineage\n"
                "001\t3\t\t3\t\t3\tkeep\tbaseline\t2026-07-16T00:00:00+00:00\thigher\t\t\t\t\t\n"
                "fork-1\t\t\t3\t\t\tfork\tfork marker\t2026-07-16T00:01:00+00:00\thigher\t\t\t\t001\texplore\n"
                "002\t5\t\t5\t\t5\tkeep\timprove\t2026-07-16T00:02:00+00:00\thigher\t\t\t\t001\texplore\n",
                encoding="utf-8",
            )
            rows = _dash.load_results(str(path))
            html = _dash.generate_html(rows, "fork-chart")
            self.assertIn("pathStarted", html)
            self.assertNotIn("if (i === 0) ctx.moveTo", html)
            self.assertIn('"status": "fork"', html)
            self.assertIn('"score": null', html)

    def test_main_creates_missing_output_parent_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            results = work / "results.tsv"
            results.write_text(
                "experiment\tscore\tmax_score\tbest_score\tprivate_score\tdecision_score\tstatus\t"
                "description\ttimestamp\tdirection\tverify_command\tguard_command\t"
                "snapshot\tparent_experiment\tlineage\n"
                "001\t3\t\t3\t\t3\tkeep\tbaseline\t2026-07-16T00:00:00+00:00\thigher\t\t\t\t\t\n",
                encoding="utf-8",
            )
            out = work / "reports" / "nested" / "dashboard.html"
            self.assertFalse(out.parent.exists())
            rc = _dash.main([
                "--results", str(results),
                "--output", str(out),
                "--title", "nested-out",
            ])
            self.assertEqual(rc, 0)
            self.assertTrue(out.is_file())
            self.assertIn("nested-out", out.read_text(encoding="utf-8"))

    def test_results_path_must_be_a_file(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            not_a_file = work / "not-a-file"
            not_a_file.mkdir()
            with self.assertRaises(SystemExit) as ctx:
                _dash.load_results(str(not_a_file))
            self.assertIn("not a file", str(ctx.exception).lower())
            missing = work / "missing.tsv"
            with self.assertRaises(SystemExit) as ctx2:
                _dash.load_results(str(missing))
            self.assertIn("not found", str(ctx2.exception).lower())


if __name__ == "__main__":
    unittest.main()
