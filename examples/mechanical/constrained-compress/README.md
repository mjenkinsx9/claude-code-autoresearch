# Constrained compress

Minimize `metric` (prompt chars) while holding classification accuracy.

```bash
cd examples/mechanical/constrained-compress
python ../../../scripts/autoresearch_loop.py baseline \
  --target optimize.py \
  --verify-command 'python evaluate.py' \
  --metric metric \
  --direction lower
```
