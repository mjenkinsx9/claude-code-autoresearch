import os
import subprocess
import sys

import pytest

import agent_cli


def test_quote_arg_windows_style(monkeypatch):
    monkeypatch.setattr(os, "name", "nt")
    quoted = agent_cli._quote_arg(r"C:\tmp\a b.txt")
    # cmd.exe-compatible double quotes, no POSIX single quotes
    assert "'" not in quoted
    assert quoted == '"C:\\tmp\\a b.txt"'


def test_quote_arg_posix_style(monkeypatch):
    monkeypatch.setattr(os, "name", "posix")
    assert agent_cli._quote_arg("a b.txt") == "'a b.txt'"


def test_custom_backend_receives_clean_path(tmp_path):
    """End-to-end: the {prompt_file} path must reach the child unquoted."""
    echo_script = tmp_path / "echo_path.py"
    echo_script.write_text(
        "import sys\nprint(open(sys.argv[1], encoding='utf-8').read())\n",
        encoding="utf-8",
    )
    result = agent_cli.run_agent_prompt(
        "PROMPT_MARKER_42",
        backend="custom",
        command_template=f'"{sys.executable}" "{echo_script}" {{prompt_file}}',
        timeout=60,
    )
    assert result.ok, result.stderr
    assert "PROMPT_MARKER_42" in result.stdout
