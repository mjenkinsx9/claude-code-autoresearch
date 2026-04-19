#!/usr/bin/env python3
"""
Autoresearch Eval Engine — Binary Yes/No Scoring System

Evaluates outputs against a set of binary criteria using an LLM as judge.
Each criterion is answered yes (1) or no (0). The total score is the sum
of all yes answers across all criteria and all runs.

Usage:
    python eval_engine.py --eval-config eval.json --output-dir ./outputs/ [--model sonnet]
    python eval_engine.py --eval-config eval.json --output "inline text to evaluate"
"""

import argparse
import json
import os
import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime


def load_eval_config(config_path: str) -> dict:
    """Load eval configuration from JSON file."""
    try:
        with open(config_path) as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Error: eval config file not found: '{config_path}'")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in eval config: {e}")
        sys.exit(1)

    required_keys = ["criteria", "test_prompts"]
    for key in required_keys:
        if key not in config:
            print(f"Error: eval config missing required key '{key}'")
            sys.exit(1)

    return config


def evaluate_single_output(output_text: str, criteria: list[dict], model: str = "sonnet") -> dict:
    """
    Evaluate a single output against all binary criteria.
    Uses claude CLI as the judge (or falls back to inline evaluation).

    Returns dict with:
        - scores: list of {criterion, passed: bool, evidence: str}
        - total_yes: int
        - total_criteria: int
    """
    # Build the evaluation prompt
    criteria_list = "\n".join(
        f"{i+1}. {c['question']}" for i, c in enumerate(criteria)
    )

    eval_prompt = f"""You are an objective evaluator. Evaluate the following output against each criterion.
For each criterion, answer ONLY "yes" or "no" and provide a brief evidence snippet (1 sentence max).

## Output to evaluate:
{output_text}

## Criteria:
{criteria_list}

## Response format (JSON array):
[
  {{"criterion": 1, "question": "...", "passed": true/false, "evidence": "brief reason"}},
  ...
]

Respond with ONLY the JSON array, no other text."""

    # Try using claude CLI first
    try:
        result = subprocess.run(
            ["claude", "-p", eval_prompt, "--model", model, "--output-format", "text"],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            response = result.stdout.strip()
        else:
            # CLI failed — warn and return zero-score evaluation
            print(f"WARNING: claude CLI failed with exit code {result.returncode}: {result.stderr[:200]}", file=sys.stderr)
            return _fallback_eval(criteria, f"claude CLI failed (exit {result.returncode})")
    except FileNotFoundError:
        # claude CLI not available
        print("WARNING: claude CLI not found — cannot perform evaluation", file=sys.stderr)
        return _fallback_eval(criteria, "claude CLI not found")
    except subprocess.TimeoutExpired:
        print("WARNING: evaluation timed out after 120s", file=sys.stderr)
        return _fallback_eval(criteria, "evaluation timed out")

    # Parse the JSON response
    try:
        # Extract JSON from response (handle markdown code blocks)
        json_str = response
        if "```" in json_str:
            # Find the first code block that starts with JSON content
            parts = json_str.split("```")
            json_str = ""
            for i, part in enumerate(parts[1:], start=1):
                # Skip language identifier if present
                stripped = part.strip()
                if stripped.startswith("json"):
                    stripped = stripped[4:].strip()
                # Check if this looks like JSON (starts with [ or {)
                if stripped.startswith("["):
                    json_str = stripped
                    break
                elif stripped.startswith("{"):
                    json_str = stripped
                    break

        scores = json.loads(json_str)

        # Validate passed field is actually a boolean
        total_yes = 0
        for s in scores:
            passed = s.get("passed", False)
            if isinstance(passed, bool):
                total_yes += 1 if passed else 0
            elif isinstance(passed, str):
                # LLM might return "yes"/"no" string
                total_yes += 1 if passed.lower() in ("yes", "true", "1") else 0
            elif isinstance(passed, (int, float)):
                total_yes += 1 if passed else 0
        return {
            "scores": scores,
            "total_yes": total_yes,
            "total_criteria": len(criteria),
        }
    except (json.JSONDecodeError, IndexError):
        return _fallback_eval(criteria, f"failed to parse eval response: {response[:200]}")


def _fallback_eval(criteria: list[dict], reason: str) -> dict:
    """Return a zero-score evaluation when the judge is unavailable."""
    return {
        "scores": [
            {"criterion": i+1, "question": c["question"], "passed": False,
             "evidence": f"Could not evaluate: {reason}"}
            for i, c in enumerate(criteria)
        ],
        "total_yes": 0,
        "total_criteria": len(criteria),
        "error": reason,
    }


def run_eval_suite(
    outputs: list[str],
    criteria: list[dict],
    model: str = "sonnet",
    verbose: bool = False,
) -> dict:
    """
    Run the full eval suite across multiple outputs.

    Returns:
        - per_output: list of individual eval results
        - total_yes: aggregate yes count
        - max_score: theoretical maximum
        - score_pct: percentage score
    """
    per_output = []
    total_yes = 0
    errors = []
    max_score = len(criteria) * len(outputs)

    for i, output in enumerate(outputs):
        if verbose:
            print(f"  Evaluating output {i+1}/{len(outputs)}...")
        result = evaluate_single_output(output, criteria, model)
        per_output.append(result)
        total_yes += result["total_yes"]
        if "error" in result:
            errors.append(f"output {i+1}: {result['error']}")

        if verbose:
            print(f"    Score: {result['total_yes']}/{result['total_criteria']}")

    score_pct = (total_yes / max_score * 100) if max_score > 0 else 0

    return {
        "per_output": per_output,
        "total_yes": total_yes,
        "max_score": max_score,
        "score_pct": round(score_pct, 1),
        "errors": errors,
        "timestamp": datetime.now().isoformat(),
    }


def load_outputs_from_dir(output_dir: str) -> list[str]:
    """Load all output files from a directory."""
    outputs = []
    output_path = Path(output_dir)
    if not output_path.exists():
        print(f"Error: output directory '{output_dir}' does not exist")
        sys.exit(1)

    for f in sorted(output_path.iterdir()):
        if f.is_file() and f.suffix in (".txt", ".md", ".html", ".json", ".py", ".jsx"):
            outputs.append(f.read_text())

    if not outputs:
        print(f"Warning: no output files found in '{output_dir}'")

    return outputs


def main():
    parser = argparse.ArgumentParser(description="Autoresearch Binary Eval Engine")
    parser.add_argument("--eval-config", required=True, help="Path to eval config JSON")
    parser.add_argument("--output-dir", help="Directory containing output files to evaluate")
    parser.add_argument("--output", help="Inline text to evaluate (alternative to --output-dir)")
    parser.add_argument("--model", default="sonnet", help="Model to use as judge (default: sonnet)")
    parser.add_argument("--verbose", action="store_true", help="Print detailed progress")
    parser.add_argument("--results-file", help="Path to save results JSON")
    args = parser.parse_args()

    config = load_eval_config(args.eval_config)
    criteria = config["criteria"]

    # Load outputs
    if args.output:
        outputs = [args.output]
    elif args.output_dir:
        outputs = load_outputs_from_dir(args.output_dir)
    else:
        print("Error: provide either --output or --output-dir")
        sys.exit(1)

    if not outputs:
        print("No outputs to evaluate")
        sys.exit(1)

    print(f"Evaluating {len(outputs)} output(s) against {len(criteria)} criteria...")
    print(f"Max possible score: {len(criteria) * len(outputs)}")
    print()

    results = run_eval_suite(outputs, criteria, args.model, args.verbose)

    print(f"\n{'='*50}")
    print(f"EVAL RESULTS")
    print(f"{'='*50}")
    print(f"Score: {results['total_yes']}/{results['max_score']} ({results['score_pct']}%)")
    print()

    # Show per-criterion breakdown
    criterion_pass_counts = {}
    for output_result in results["per_output"]:
        for score in output_result["scores"]:
            q = score.get("question", f"Criterion {score.get('criterion', '?')}")
            if q not in criterion_pass_counts:
                criterion_pass_counts[q] = {"passed": 0, "total": 0}
            criterion_pass_counts[q]["total"] += 1
            if score.get("passed", False):
                criterion_pass_counts[q]["passed"] += 1

    for q, counts in criterion_pass_counts.items():
        status = "PASS" if counts["passed"] == counts["total"] else "MIXED" if counts["passed"] > 0 else "FAIL"
        print(f"  [{status}] {q}: {counts['passed']}/{counts['total']}")

    # Save results
    if args.results_file:
        with open(args.results_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.results_file}")

    return results


if __name__ == "__main__":
    main()
