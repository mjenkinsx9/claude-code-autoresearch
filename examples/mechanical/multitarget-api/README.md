# Multi-target API

Weco-style frozen `evaluate.py` with two mutable modules.

```bash
cd examples/mechanical/multitarget-api
python ../../../scripts/autoresearch_loop.py baseline \
  --targets features.py model.py \
  --verify-command 'python evaluate.py' \
  --metric Score \
  --direction higher
```
