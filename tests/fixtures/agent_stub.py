"""Deterministic stand-in for an agent CLI. Usage: python agent_stub.py <prompt_file> [mode]

Modes (optional 2nd arg):
  ok          (default) well-formed responses for every role
  bad-judge   judge returns garbage (list of strings)
  exec-error  executor fails — but only for experiment content ("improved" in
              the prompt), so the baseline still succeeds and the loop starts
"""
import json
import sys

prompt = open(sys.argv[1], encoding="utf-8").read()
mode = sys.argv[2] if len(sys.argv) > 2 else "ok"

if "objective evaluator" in prompt:
    if mode == "bad-judge":
        print(json.dumps(["yes", "no"]))
    else:
        # Pass criterion 1, fail the rest — stable, non-trivial score
        print(json.dumps([
            {"criterion": 1, "question": "q1", "passed": True, "evidence": "ok"},
            {"criterion": 2, "question": "q2", "passed": False, "evidence": "no"},
        ]))
elif "autonomous researcher" in prompt:
    print(json.dumps({
        "description": "stub experiment",
        "reasoning": "deterministic test change",
        "new_content": "# Target\nimproved content with unicode: café ✓\n",
    }))
else:
    # Executor role. In exec-error mode, fail only once an experiment has been
    # applied (the generator's new_content contains "improved") — the baseline
    # against the original target must still pass so the loop actually starts.
    if mode == "exec-error" and "improved" in prompt:
        sys.exit(1)
    print("stub task output with unicode: café")
