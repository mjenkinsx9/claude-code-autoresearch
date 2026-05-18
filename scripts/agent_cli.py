#!/usr/bin/env python3
"""Small adapter for running an agent CLI from autoresearch scripts.

The original project was Claude Code-first. This adapter keeps that path while
also letting the same scripts run under Hermes or any command that can accept a
prompt file and print a final text response.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile


@dataclass
class AgentResult:
    backend: str
    returncode: int
    stdout: str
    stderr: str
    command: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _model_is_explicit(model: str | None) -> bool:
    """Return true when a model string looks portable enough to pass to Hermes."""
    if not model:
        return False
    aliases = {"opus", "sonnet", "haiku"}
    if model in aliases:
        return False
    return (
        "/" in model
        or model.startswith(("gpt-", "claude-", "gemini-", "qwen", "deepseek", "o1", "o3", "o4"))
    )


def _run_command(cmd: list[str], timeout: int, backend: str) -> AgentResult:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return AgentResult(
            backend=backend,
            returncode=result.returncode,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            command=" ".join(shlex.quote(part) for part in cmd),
        )
    except subprocess.TimeoutExpired as exc:
        return AgentResult(
            backend=backend,
            returncode=124,
            stdout=exc.stdout or "",
            stderr=f"agent command timed out after {timeout}s",
            command=" ".join(shlex.quote(part) for part in cmd),
        )
    except OSError as exc:
        return AgentResult(
            backend=backend,
            returncode=127,
            stdout="",
            stderr=str(exc),
            command=" ".join(shlex.quote(part) for part in cmd),
        )


def _run_custom_command(prompt: str, model: str, timeout: int, template: str) -> AgentResult:
    if not template:
        return AgentResult(
            backend="custom",
            returncode=127,
            stdout="",
            stderr="custom backend selected but no command template was provided",
            command="",
        )

    prompt_file = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".prompt.txt") as fh:
            fh.write(prompt)
            prompt_file = fh.name

        rendered = template.format(
            prompt=shlex.quote(prompt),
            prompt_file=shlex.quote(prompt_file),
            model=shlex.quote(model or ""),
        )
        result = subprocess.run(rendered, shell=True, capture_output=True, text=True, timeout=timeout)
        return AgentResult(
            backend="custom",
            returncode=result.returncode,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            command=rendered,
        )
    except subprocess.TimeoutExpired as exc:
        return AgentResult(
            backend="custom",
            returncode=124,
            stdout=exc.stdout or "",
            stderr=f"custom agent command timed out after {timeout}s",
            command=template,
        )
    finally:
        if prompt_file:
            try:
                Path(prompt_file).unlink(missing_ok=True)
            except OSError:
                pass


def run_agent_prompt(
    prompt: str,
    model: str = "",
    timeout: int = 120,
    backend: str | None = None,
    command_template: str | None = None,
) -> AgentResult:
    """Run a prompt through Claude Code, Hermes, or a custom command.

    backend values:
    - auto: try backends from AUTORESEARCH_AGENT_ORDER, default claude,hermes
    - claude: use `claude -p ... --output-format text`
    - hermes: use `hermes chat -Q -q ...`
    - custom: use AUTORESEARCH_AGENT_CMD or --agent-command

    Custom command templates can use:
    - {prompt_file}: path to a temporary UTF-8 prompt file
    - {prompt}: shell-quoted prompt text
    - {model}: shell-quoted model string
    """
    backend = (backend or os.getenv("AUTORESEARCH_AGENT_BACKEND") or "auto").strip().lower()
    command_template = command_template or os.getenv("AUTORESEARCH_AGENT_CMD", "")

    if backend == "custom" or command_template:
        return _run_custom_command(prompt, model, timeout, command_template)

    if backend == "auto":
        order = os.getenv("AUTORESEARCH_AGENT_ORDER", "claude,hermes")
        candidates = [item.strip().lower() for item in order.split(",") if item.strip()]
    else:
        candidates = [backend]

    errors: list[str] = []
    for candidate in candidates:
        if candidate == "claude":
            exe = shutil.which(os.getenv("AUTORESEARCH_CLAUDE_BIN", "claude"))
            if not exe:
                errors.append("claude CLI not found")
                continue
            cmd = [exe, "-p", prompt, "--output-format", "text"]
            if model:
                cmd.extend(["--model", model])
            result = _run_command(cmd, timeout, "claude")
            if result.ok:
                return result
            errors.append(f"claude failed exit {result.returncode}: {result.stderr[:200]}")
            continue

        if candidate == "hermes":
            exe = shutil.which(os.getenv("AUTORESEARCH_HERMES_BIN", "hermes"))
            if not exe:
                errors.append("hermes CLI not found")
                continue
            cmd = [exe, "chat", "-Q", "-q", prompt]
            hermes_model = os.getenv("AUTORESEARCH_HERMES_MODEL", "")
            if not hermes_model and _model_is_explicit(model):
                hermes_model = model
            if hermes_model:
                cmd.extend(["-m", hermes_model])
            result = _run_command(cmd, timeout, "hermes")
            if result.ok:
                return result
            errors.append(f"hermes failed exit {result.returncode}: {result.stderr[:200]}")
            continue

        errors.append(f"unsupported backend '{candidate}'")

    return AgentResult(
        backend=backend,
        returncode=127,
        stdout="",
        stderr="; ".join(errors) if errors else "no agent backend available",
        command="",
    )
