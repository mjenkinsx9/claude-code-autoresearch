import subprocess
import sys
from pathlib import Path

from conftest import FIXTURES_DIR, SCRIPTS_DIR

LOOP = SCRIPTS_DIR / "autoresearch_loop.py"
STUB = FIXTURES_DIR / "agent_stub.py"


def _write_fixtures(tmp_path):
    (tmp_path / "target.md").write_text("# Target\noriginal\n", encoding="utf-8")
    (tmp_path / "program.md").write_text("Improve the target.\n", encoding="utf-8")
    (tmp_path / "eval.json").write_text(
        '{"criteria": [{"id": 1, "question": "Is it good?"},'
        ' {"id": 2, "question": "Is it complete?"}],'
        ' "test_prompts": ["do the thing"]}',
        encoding="utf-8",
    )


def test_bounded_run_completes_and_logs(tmp_path):
    _write_fixtures(tmp_path)
    cmd = [
        sys.executable, str(LOOP),
        "--target", "target.md",
        "--program", "program.md",
        "--eval-config", "eval.json",
        "--runs-per-experiment", "1",
        "--max-experiments", "2",
        "--agent-backend", "custom",
        "--agent-command", f'"{sys.executable}" "{STUB}" {{prompt_file}}',
    ]
    result = subprocess.run(
        cmd, cwd=tmp_path, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    results_tsv = tmp_path / "autoresearch-results" / "results.tsv"
    assert results_tsv.exists()
    lines = results_tsv.read_text(encoding="utf-8").strip().splitlines()
    # header + baseline + 1 experiment (experiment_num 2 hits the bound)
    assert lines[0].startswith("experiment\tscore")
    assert len(lines) >= 2
    assert "baseline" in lines[1]


def test_broken_backend_aborts_at_baseline(tmp_path):
    _write_fixtures(tmp_path)
    cmd = [
        sys.executable, str(LOOP),
        "--target", "target.md",
        "--program", "program.md",
        "--eval-config", "eval.json",
        "--runs-per-experiment", "1",
        "--max-experiments", "2",
        "--agent-backend", "custom",
        "--agent-command", f'"{sys.executable}" -c "import sys; sys.exit(1)"',
    ]
    result = subprocess.run(
        cmd, cwd=tmp_path, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )
    assert result.returncode == 2
    combined = result.stdout + result.stderr
    assert "baseline" in combined.lower()
    # No baseline row should have been logged as a keep
    results_tsv = tmp_path / "autoresearch-results" / "results.tsv"
    if results_tsv.exists():
        assert "keep" not in results_tsv.read_text(encoding="utf-8")
