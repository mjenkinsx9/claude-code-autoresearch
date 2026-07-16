#!/usr/bin/env python3
"""Frozen orchestrator — never edit. Imports features + model."""
from features import featurize
from model import score
data = [1, 2, 3]
print(f"Score: {score(featurize(data))}", flush=True)
