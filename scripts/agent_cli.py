#!/usr/bin/env python3
"""Compatibility notice for the old headless agent adapter.

Autoresearch Agent no longer shells out to model CLIs. The active harness
(Claude Code, Codex, Gemini CLI, Pi, Hermes, or another agent runtime) should
run the autoresearch loop in-session and use the deterministic helper scripts
for scoring, guard checks, snapshots, and logs.

This module is kept only so older imports fail with a clear migration message
instead of silently launching a paid/limited headless command.
"""

from __future__ import annotations

from dataclasses import dataclass


class HeadlessAgentDisabledError(RuntimeError):
    """Raised when legacy code tries to invoke a headless agent subprocess."""


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


MIGRATION_MESSAGE = (
    "Headless agent invocation has been removed. Run autoresearch inside the "
    "active harness session and use scripts/autoresearch_loop.py for mechanical "
    "verify/guard/snapshot/keep-discard operations. Use scripts/eval_engine.py "
    "to emit judge prompts and score judgments supplied by the active harness."
)


def run_agent_prompt(*_args, **_kwargs) -> AgentResult:
    """Legacy entry point retained for explicit migration failure."""
    raise HeadlessAgentDisabledError(MIGRATION_MESSAGE)


def main() -> int:
    print(MIGRATION_MESSAGE)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
