# Hello length (mechanical metric)

Frozen `evaluate.py` prints `Score: N` from `target.txt` length.

```bash
cd examples/mechanical/hello-length
python ../../../scripts/autoresearch_loop.py baseline \
  --target target.txt \
  --verify-command 'python evaluate.py' \
  --metric Score \
  --direction higher \
  --max-experiments 5

# make one change, then:
python ../../../scripts/autoresearch_loop.py score \
  --target target.txt \
  --description 'append text'
```
