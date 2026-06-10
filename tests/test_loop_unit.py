import sys


def test_execute_target_runs_py_script(tmp_path):
    from autoresearch_loop import execute_target

    script = tmp_path / "target.py"
    script.write_text("print('hello-from-target')", encoding="utf-8")

    out = execute_target(
        str(script), "test input", {}, 0, str(tmp_path), allow_exec=True
    )
    assert "hello-from-target" in out


def test_target_roundtrip_preserves_unicode(tmp_path):
    from autoresearch_loop import read_target, write_target

    target = tmp_path / "t.md"
    content = "# Target\nunicode: café \U0001f680 ✓\n"
    write_target(str(target), content)
    assert read_target(str(target)) == content


def test_force_utf8_output_reconfigures_streams():
    import sys
    from autoresearch_loop import _force_utf8_output

    saved_stdout, saved_stderr = sys.stdout, sys.stderr
    try:
        _force_utf8_output()
        enc = (sys.stdout.encoding or "").lower().replace("-", "")
        assert enc == "utf8"
        assert sys.stdout.errors == "replace"
    finally:
        sys.stdout = saved_stdout
        sys.stderr = saved_stderr


def test_run_guard_passes_and_fails():
    import sys
    from autoresearch_loop import run_guard

    assert run_guard("") is True  # no guard configured
    assert run_guard(f'"{sys.executable}" -c "import sys; sys.exit(0)"') is True
    assert run_guard(f'"{sys.executable}" -c "import sys; sys.exit(1)"') is False
    assert run_guard(f'"{sys.executable}" -c "import time; time.sleep(5)"', timeout=1) is False
