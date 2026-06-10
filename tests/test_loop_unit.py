import sys


def test_execute_target_runs_py_script(tmp_path):
    from autoresearch_loop import execute_target

    script = tmp_path / "target.py"
    script.write_text("print('hello-from-target')", encoding="utf-8")

    out = execute_target(
        str(script), "test input", {}, 0, str(tmp_path), allow_exec=True
    )
    assert "hello-from-target" in out
