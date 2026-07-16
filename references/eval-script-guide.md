# Writing Evaluation Scripts for Autoresearch

How to write a mechanical evaluation that drives the no-headless loop well.

## Metric contract

Print a **named metric last** on stdout (or stderr + stdout combined). Progress logs should go to **stderr** so they do not steal the last-number fallback.

```python
print(f"Score: {value}")  # last line preferred
```

Baseline with a named metric:

```bash
python scripts/autoresearch_loop.py baseline \
  --target optimize.py \
  --verify-command 'python evaluate.py' \
  --metric Score \
  --direction higher
```

Use `--metric-regex` only when the format is nonstandard. Avoid relying on the last-number fallback for autonomous runs.

## Frozen evaluator, mutable target

| Role | Editable by loop? |
|---|---|
| Target skill / code / prompt region | Yes (`--target` / `--targets`) |
| `evaluate.py` / guard / data splits | **No** (unless a human changes them) |

The evaluator should **import** the candidate, not re-implement it. If the agent overwrites the only copy of baseline logic, keep a frozen baseline copy for comparison.

## Constrained multi-objective (penalty composite)

When you must optimize cost under a quality floor, encode constraints in one scalar:

```python
# minimize metric
if accuracy >= THRESHOLD:
    metric = chars
else:
    metric = chars + 10_000_000  # huge penalty
print(f"accuracy: {accuracy}")
print(f"chars: {chars}")
print(f"metric: {metric}")
```

Then baseline with `--metric metric --direction lower`.

## Public vs private scores

Optional held-out selection:

```bash
python scripts/autoresearch_loop.py baseline \
  --target target.txt \
  --verify-command 'python eval_public.py' \
  --private-verify-command 'python eval_private.py' \
  --metric Score \
  --direction higher
```

Keep/discard uses the **private** score when configured; both are logged.

## Speed and reliability

- Subsample and fix a seed for fast iteration.
- Import the candidate in a try/except; print traceback and exit non-zero on crash.
- Validate constraints (shapes, ranges) before printing the metric.
- Print the decision metric near the **end** of output.

## Anti-patterns

- Subjective “looks better” without a number.
- Self-judged binary criteria without a second criteria set or private holdout.
- Letting the agent edit `evaluate.py`.
- Using last-number extraction with noisy progress percentages on stdout.
- Changing verify/metric mid-run without `--allow-config-change`.

## See also

- `examples/mechanical/hello-length/` — minimal length metric + score loop
- `examples/mechanical/constrained-compress/` — quality-floor penalty (minimize)
- `examples/mechanical/multitarget-api/` — frozen evaluate.py + `--targets features.py model.py`
- `references/eval-criteria-guide.md` — binary (harness-judged) criteria
