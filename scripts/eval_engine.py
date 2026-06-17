#!/usr/bin/env python3
"""
Autoresearch Agent eval helper — no-headless binary scoring.

This helper never calls an LLM CLI. It prepares a judge prompt for the active
agent/harness and scores JSON judgments that the active agent supplies. This
keeps evaluation portable across Claude Code, Codex, Gemini CLI, Pi, Hermes,
and other harnesses without spawning paid/limited headless print commands.

Typical flow:

    python scripts/eval_engine.py --eval-config eval.json --output-dir outputs --emit-prompt

The active agent reads the prompt, judges the outputs in-session, writes the
JSON judgments to a file, then runs:

    python scripts/eval_engine.py --eval-config eval.json --output-dir outputs --judgments-file judgments.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SUPPORTED_OUTPUT_SUFFIXES = (".txt", ".md", ".html", ".json", ".py", ".jsx", ".ts", ".tsx")


def load_eval_config(config_path: str) -> dict[str, Any]:
    try:
        config = json.loads(Path(config_path).read_text())
    except FileNotFoundError:
        raise SystemExit(f"Error: eval config file not found: {config_path!r}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Error: invalid JSON in eval config: {exc}")

    for key in ("criteria", "test_prompts"):
        if key not in config:
            raise SystemExit(f"Error: eval config missing required key {key!r}")
    return config


def load_outputs_from_dir(output_dir: str) -> list[dict[str, str]]:
    path = Path(output_dir)
    if not path.exists():
        raise SystemExit(f"Error: output directory {output_dir!r} does not exist")
    outputs: list[dict[str, str]] = []
    for file_path in sorted(path.iterdir()):
        if file_path.is_file() and file_path.suffix in SUPPORTED_OUTPUT_SUFFIXES:
            outputs.append({"id": file_path.name, "text": file_path.read_text(errors="replace")})
    if not outputs:
        print(f"Warning: no output files found in {output_dir!r}", file=sys.stderr)
    return outputs


def load_outputs(args: argparse.Namespace) -> list[dict[str, str]]:
    if args.output:
        return [{"id": "inline-output-1", "text": args.output}]
    if args.output_dir:
        return load_outputs_from_dir(args.output_dir)
    raise SystemExit("Error: provide either --output or --output-dir")


def build_eval_prompt(outputs: list[dict[str, str]], criteria: list[dict[str, Any]]) -> str:
    criteria_list = "\n".join(f"{i + 1}. {c['question']}" for i, c in enumerate(criteria))
    output_blocks = []
    for index, output in enumerate(outputs, start=1):
        output_blocks.append(
            f"### Output {index}: {output['id']}\n"
            "```\n"
            f"{output['text']}\n"
            "```"
        )

    return f"""You are the active autoresearch judge running inside the current agent harness.
Do not call any headless model command. Evaluate each output against each binary criterion.

For every criterion, answer with a boolean `passed` value and one concise evidence sentence.
Return ONLY valid JSON in this shape:

{{
  "outputs": [
    {{
      "output_id": "{outputs[0]['id'] if outputs else 'example.txt'}",
      "scores": [
        {{"criterion": 1, "question": "...", "passed": true, "evidence": "..."}}
      ]
    }}
  ]
}}

## Criteria
{criteria_list}

## Outputs
{chr(10).join(output_blocks)}
"""


def normalize_judgments(raw: Any) -> list[dict[str, Any]]:
    """Accept several practical JSON shapes and normalize to per-output records."""
    if isinstance(raw, dict) and isinstance(raw.get("outputs"), list):
        return raw["outputs"]
    if isinstance(raw, dict) and isinstance(raw.get("scores"), list):
        return [raw]
    if isinstance(raw, list):
        if all(isinstance(item, dict) and "scores" in item for item in raw):
            return raw
        if all(isinstance(item, dict) and "criterion" in item for item in raw):
            return [{"output_id": "output-1", "scores": raw}]
    raise ValueError("judgments JSON must contain an 'outputs' array or a list of score records")


def passed_to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"yes", "true", "1", "pass", "passed"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def score_judgments(judgments: list[dict[str, Any]], criteria: list[dict[str, Any]]) -> dict[str, Any]:
    per_output = []
    total_yes = 0
    expected_per_output = len(criteria)
    errors: list[str] = []

    for output_index, output_result in enumerate(judgments, start=1):
        scores = output_result.get("scores", [])
        if not isinstance(scores, list):
            errors.append(f"output {output_index}: scores is not a list")
            scores = []
        output_yes = 0
        normalized_scores = []
        for score in scores:
            if not isinstance(score, dict):
                errors.append(f"output {output_index}: non-object score entry")
                continue
            passed = passed_to_bool(score.get("passed", False))
            if passed:
                output_yes += 1
            normalized_scores.append({**score, "passed": passed})
        if len(normalized_scores) != expected_per_output:
            errors.append(
                f"output {output_index}: expected {expected_per_output} score entries, got {len(normalized_scores)}"
            )
        total_yes += output_yes
        per_output.append({
            "output_id": output_result.get("output_id", f"output-{output_index}"),
            "scores": normalized_scores,
            "total_yes": output_yes,
            "total_criteria": expected_per_output,
        })

    max_score = expected_per_output * len(judgments)
    score_pct = (total_yes / max_score * 100) if max_score else 0
    return {
        "per_output": per_output,
        "total_yes": total_yes,
        "max_score": max_score,
        "score_pct": round(score_pct, 1),
        "errors": errors,
        "timestamp": datetime.now().isoformat(),
        "mode": "harness-judged-no-headless",
    }


def load_judgments(args: argparse.Namespace) -> Any:
    if args.judgments:
        return json.loads(args.judgments)
    if args.judgments_file:
        return json.loads(Path(args.judgments_file).read_text())
    return None


def print_summary(results: dict[str, Any]) -> None:
    print("\n" + "=" * 50)
    print("EVAL RESULTS")
    print("=" * 50)
    print(f"Score: {results['total_yes']}/{results['max_score']} ({results['score_pct']}%)")
    if results.get("errors"):
        print("Warnings:")
        for error in results["errors"]:
            print(f"  - {error}")

    criterion_pass_counts: dict[str, dict[str, int]] = {}
    for output_result in results["per_output"]:
        for score in output_result["scores"]:
            question = score.get("question", f"Criterion {score.get('criterion', '?')}")
            criterion_pass_counts.setdefault(question, {"passed": 0, "total": 0})
            criterion_pass_counts[question]["total"] += 1
            if score.get("passed", False):
                criterion_pass_counts[question]["passed"] += 1

    for question, counts in criterion_pass_counts.items():
        status = "PASS" if counts["passed"] == counts["total"] else "MIXED" if counts["passed"] else "FAIL"
        print(f"  [{status}] {question}: {counts['passed']}/{counts['total']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="No-headless binary eval helper")
    parser.add_argument("--eval-config", required=True, help="Path to eval config JSON")
    parser.add_argument("--output-dir", help="Directory containing output files to evaluate")
    parser.add_argument("--output", help="Inline text to evaluate")
    parser.add_argument("--emit-prompt", action="store_true", help="Print the judge prompt for the active harness")
    parser.add_argument("--prompt-file", help="Write the judge prompt to this file")
    parser.add_argument("--judgments", help="Inline judgments JSON from the active harness")
    parser.add_argument("--judgments-file", help="File containing judgments JSON from the active harness")
    parser.add_argument("--results-file", help="Path to save scored results JSON")
    return parser


def main(argv: list[str] | None = None) -> dict[str, Any] | int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_eval_config(args.eval_config)
    outputs = load_outputs(args)
    if not outputs:
        raise SystemExit("No outputs to evaluate")

    prompt = build_eval_prompt(outputs, config["criteria"])
    if args.prompt_file:
        Path(args.prompt_file).write_text(prompt)
        print(f"Judge prompt written to {args.prompt_file}")

    raw_judgments = load_judgments(args)
    if raw_judgments is None:
        if args.emit_prompt or not args.prompt_file:
            print(prompt)
        if not args.emit_prompt and args.prompt_file:
            print("No judgments supplied. Active harness should fill judgments JSON, then rerun with --judgments-file.")
        return 0

    try:
        judgments = normalize_judgments(raw_judgments)
    except ValueError as exc:
        raise SystemExit(f"Error: {exc}") from exc

    results = score_judgments(judgments, config["criteria"])
    print_summary(results)
    if args.results_file:
        Path(args.results_file).write_text(json.dumps(results, indent=2) + "\n")
        print(f"\nResults saved to {args.results_file}")
    return results


if __name__ == "__main__":
    main()
