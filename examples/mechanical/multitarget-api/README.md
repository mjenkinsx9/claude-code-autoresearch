# Multi-target API

Weco-style frozen `evaluate.py` with two mutable modules.

```bash
cd examples/mechanical/multitarget-api
python ../../../scripts/autoresearch_loop.py baseline \
  --targets features.py model.py \
  --verify-command 'python evaluate.py' \
  --metric Score \
  --direction higher \
  --max-experiments 15

# Edit features.py and/or model.py (not evaluate.py), then:
python ../../../scripts/autoresearch_loop.py score \
  --targets features.py model.py \
  --description 'improve featurize or score'
```

`evaluate.py` is the frozen orchestrator. Both mutable files are snapshotted and reverted together.
