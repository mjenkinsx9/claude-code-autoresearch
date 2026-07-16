from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOOP_PATH = ROOT / "scripts" / "autoresearch_loop.py"

import sys

_spec = importlib.util.spec_from_file_location("autoresearch_loop", LOOP_PATH)
assert _spec and _spec.loader
_loop = importlib.util.module_from_spec(_spec)
sys.modules["autoresearch_loop"] = _loop
_spec.loader.exec_module(_loop)

metric_from_output = _loop.metric_from_output
resolve_metric_spec = _loop.resolve_metric_spec


class MetricExtractionTests(unittest.TestCase):
    def test_metric_name_uses_last_named_value(self):
        out = "accuracy: 0.1\nprogress 2\naccuracy: 0.9\n"
        self.assertEqual(metric_from_output(out, metric_name="accuracy"), 0.9)

    def test_metric_name_case_insensitive(self):
        out = "Score: 3\nother 9\nscore: 7\n"
        self.assertEqual(metric_from_output(out, metric_name="Score"), 7.0)

    def test_metric_regex_overrides_name(self):
        out = "accuracy: 0.1\ncustom 42\naccuracy: 0.9\n"
        self.assertEqual(
            metric_from_output(out, metric_regex=r"custom\s+(\d+)", metric_name="accuracy"),
            42.0,
        )

    def test_last_number_fallback(self):
        out = "hello 1 world 2.5 done"
        self.assertEqual(metric_from_output(out), 2.5)

    def test_missing_metric_name_raises(self):
        with self.assertRaises(ValueError):
            metric_from_output("nope", metric_name="accuracy")

    def test_resolve_prefers_regex_over_name(self):
        regex, name = resolve_metric_spec(metric_regex=r"Score: (\d+)", metric_name="accuracy")
        self.assertEqual(regex, r"Score: (\d+)")
        self.assertIsNone(name)


if __name__ == "__main__":
    unittest.main()
