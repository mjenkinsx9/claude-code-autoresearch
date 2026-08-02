# Constrained compress

Minimize `metric` (prompt chars) while holding classification accuracy.

```bash
cd examples/mechanical/constrained-compress
python ../../../scripts/autoresearch_loop.py baseline \
  --target optimize.py \
  --verify-command 'python evaluate.py' \
  --metric metric \
  --direction lower \
  --max-experiments 20

# Edit only PROMPT in optimize.py (keep classify() correct), then:
python ../../../scripts/autoresearch_loop.py score \
  --target optimize.py \
  --description 'shorten PROMPT holding accuracy'
```

`evaluate.py` is frozen — do not let the agent rewrite the scorer.
