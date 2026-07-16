#!/usr/bin/env python3
"""Frozen evaluator: score = character count of target.txt (higher is better for demo)."""
from pathlib import Path
text = Path("target.txt").read_text(encoding="utf-8")
print(f"Score: {len(text)}", flush=True)
