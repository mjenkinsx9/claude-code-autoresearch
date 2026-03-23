#!/usr/bin/env python3
"""
Autoresearch Loop Runner — Autonomous Self-Improvement System

Based on Karpathy's autoresearch: modify, test, score, keep/discard, repeat.
This script orchestrates the full experiment loop for any target file.

Usage:
    python autoresearch_loop.py \
        --target path/to/SKILL.md \
        --program path/to/program.md \
        --eval-config path/to/eval.json \
        --runs-per-experiment 5 \
        --output-dir ./autoresearch-results/

The loop runs indefinitely until manually stopped (Ctrl+C).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def load_config(eval_config_path: str) -> dict:
    """Load the eval configuration."""
    with open(eval_config_path) as f:
        return json.load(f)


def load_program(program_path: str) -> str:
    """Load the program.md instructions."""
    with open(program_path) as f:
        return f.read()


def read_target(target_path: str) -> str:
    """Read the current state of the target file."""
    with open(target_path) as f:
        return f.read()


def write_target(target_path: str, content: str):
    """Write updated content to the target file with validation."""
    if not content or not isinstance(content, str):
        raise ValueError(f"Invalid content to write: empty or non-string")
    # Validate UTF-8 encoding
    content.encode("utf-8")
    with open(target_path, "w") as f:
        f.write(content)


def backup_target(target_path: str, backup_dir: str, experiment_num: int) -> str:
    """Create a backup of the target file before modification."""
    backup_path = os.path.join(backup_dir, f"experiment_{experiment_num:03d}_before.bak")
    try:
        shutil.copy2(target_path, backup_path)
    except (IOError, OSError) as e:
        print(f"WARNING: Backup failed: {e}", file=sys.stderr)
        raise
    return backup_path


def revert_target(target_path: str, backup_path: str):
    """Revert target to backup."""
    try:
        shutil.copy2(backup_path, target_path)
    except (IOError, OSError) as e:
        print(f"WARNING: Revert failed: {e}", file=sys.stderr)
        raise


def save_snapshot(target_path: str, snapshot_dir: str, experiment_num: int, status: str):
    """Save a snapshot of the target file after experiment."""
    snapshot_path = os.path.join(snapshot_dir, f"experiment_{experiment_num:03d}_{status}.md")
    try:
        shutil.copy2(target_path, snapshot_path)
    except (IOError, OSError) as e:
        print(f"WARNING: Snapshot save failed: {e}", file=sys.stderr)
        raise
    return snapshot_path


def generate_experiment(
    target_content: str,
    program: str,
    results_history: list,
    eval_config: dict,
    model: str = "opus",
) -> dict:
    """
    Use an LLM to generate the next experiment — what change to make to the target.

    Returns:
        {"description": str, "new_content": str, "reasoning": str}
    """
    # Build context from history
    history_text = ""
    if results_history:
        history_text = "## Previous experiments:\n"
        for r in results_history[-20:]:  # Last 20 experiments
            history_text += f"- Exp {r['experiment']}: {r['score']}/{r['max_score']} ({r['status']}) — {r['description']}\n"
        history_text += "\n"

    criteria_text = "\n".join(
        f"- {c['question']}" for c in eval_config.get("criteria", [])
    )

    prompt = f"""You are an autonomous researcher running experiments to improve a target file.

## Program instructions:
{program}

## Current target file content:
```
{target_content}
```

## Eval criteria (binary yes/no):
{criteria_text}

{history_text}

## Your task:
Propose ONE focused experiment — a single change to the target file that you believe will improve the eval score.

Respond with ONLY a JSON object:
{{
  "description": "short description of what this experiment tries",
  "reasoning": "why you think this will help (1-2 sentences)",
  "new_content": "the COMPLETE new content of the target file with your change applied"
}}

Remember:
- Make one focused change at a time
- Simpler is better — if you can improve by removing, do it
- Don't stack multiple changes
- If recent experiments failed, try a different approach
- Think about which eval criteria fail most and target those"""

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", model, "--output-format", "text"],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            return None

        response = result.stdout.strip()

        # Extract JSON
        json_str = response
        if "```" in json_str:
            parts = json_str.split("```")
            for part in parts[1:]:
                if part.startswith("json"):
                    json_str = part[4:].strip()
                    break
                elif part.strip().startswith("{"):
                    json_str = part.strip()
                    break

        return json.loads(json_str)

    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        print(f"  Error generating experiment: {e}")
        return None


def execute_target(
    target_path: str,
    test_prompt: str,
    eval_config: dict,
    run_index: int,
    output_dir: str,
    model: str = "sonnet",
) -> str:
    """
    Execute the target file against a test prompt and return the output.
    How this works depends on the target type.
    """
    target_content = read_target(target_path)
    target_ext = Path(target_path).suffix.lower()

    # For skills/prompts: feed the skill + test prompt to an LLM
    if target_ext in (".md", ".txt"):
        prompt = f"""Follow the instructions in the skill/prompt below to complete the task.

## Skill/Prompt instructions:
{target_content}

## Task:
{test_prompt}

Complete the task according to the instructions above."""

        try:
            result = subprocess.run(
                ["claude", "-p", prompt, "--model", model, "--output-format", "text"],
                capture_output=True, text=True, timeout=180
            )
            if result.returncode == 0:
                output = result.stdout.strip()
                # Save output
                output_file = os.path.join(output_dir, f"run_{run_index:02d}.txt")
                with open(output_file, "w") as f:
                    f.write(output)
                return output
            else:
                # Include partial stdout for debugging
                partial = result.stdout[:500] if result.stdout else ""
                return f"ERROR: claude returned exit code {result.returncode}\n{result.stderr}\n--- STDOUT (partial) ---\n{partial}"
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            return f"ERROR: {e}"

    # For Python scripts: execute them
    elif target_ext == ".py":
        try:
            result = subprocess.run(
                [sys.executable, target_path],
                input=test_prompt,
                capture_output=True, text=True, timeout=120
            )
            output = result.stdout + result.stderr
            output_file = os.path.join(output_dir, f"run_{run_index:02d}.txt")
            with open(output_file, "w") as f:
                f.write(output)
            return output
        except subprocess.TimeoutExpired:
            return "ERROR: script timed out (>120s)"

    else:
        return f"ERROR: unsupported target type '{target_ext}'"


def run_eval(
    outputs: list[str],
    eval_config: dict,
    model: str = "sonnet",
) -> dict:
    """Run the binary eval suite on a list of outputs."""
    from eval_engine import run_eval_suite
    return run_eval_suite(outputs, eval_config["criteria"], model, verbose=False)


def append_results_tsv(results_file: str, entry: dict):
    """Append an entry to results.tsv."""
    if not os.path.exists(results_file):
        with open(results_file, "w") as f:
            f.write("experiment\tscore\tmax_score\tstatus\tdescription\ttimestamp\n")

    with open(results_file, "a") as f:
        f.write(f"{entry['experiment']}\t{entry['score']}\t{entry['max_score']}\t"
                f"{entry['status']}\t{entry['description']}\t{entry['timestamp']}\n")


def print_banner(experiment_num: int, description: str):
    """Print experiment start banner."""
    print(f"\n{'='*60}")
    print(f"  EXPERIMENT {experiment_num:03d}")
    print(f"  {description}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")


def print_result(entry: dict, best_score: int):
    """Print experiment result."""
    emoji = "✅" if entry["status"] == "keep" else "❌" if entry["status"] == "discard" else "💥"
    print(f"\n{emoji} Experiment {entry['experiment']:03d}: "
          f"{entry['score']}/{entry['max_score']} — {entry['status'].upper()}")
    print(f"   {entry['description']}")
    print(f"   Best so far: {best_score}/{entry['max_score']}")


def main():
    parser = argparse.ArgumentParser(description="Autoresearch Loop Runner")
    parser.add_argument("--target", required=True, help="Path to target file to optimize")
    parser.add_argument("--program", required=True, help="Path to program.md instructions")
    parser.add_argument("--eval-config", required=True, help="Path to eval config JSON")
    parser.add_argument("--runs-per-experiment", type=int, default=5,
                        help="Number of test runs per experiment (default: 5)")
    parser.add_argument("--output-dir", default="./autoresearch-results/",
                        help="Directory for results and snapshots")
    parser.add_argument("--experiment-model", default="opus",
                        help="Model for generating experiments (default: opus)")
    parser.add_argument("--execution-model", default="sonnet",
                        help="Model for executing target (default: sonnet)")
    parser.add_argument("--eval-model", default="sonnet",
                        help="Model for evaluation judging (default: sonnet)")
    parser.add_argument("--max-experiments", type=int, default=0,
                        help="Max experiments to run (0 = infinite, default: 0)")
    args = parser.parse_args()

    # Setup directories
    output_dir = Path(args.output_dir)
    snapshots_dir = output_dir / "snapshots"
    backups_dir = output_dir / "backups"
    runs_dir = output_dir / "runs"

    for d in [output_dir, snapshots_dir, backups_dir, runs_dir]:
        d.mkdir(parents=True, exist_ok=True)

    results_file = str(output_dir / "results.tsv")

    # Load configuration
    eval_config = load_config(args.eval_config)
    program = load_program(args.program)
    test_prompts = eval_config.get("test_prompts", ["Default test"])

    # Add eval_engine to path
    script_dir = Path(__file__).parent
    sys.path.insert(0, str(script_dir))

    print(f"\n{'#'*60}")
    print(f"  AUTORESEARCH LOOP")
    print(f"  Target: {args.target}")
    print(f"  Criteria: {len(eval_config.get('criteria', []))}")
    print(f"  Test prompts: {len(test_prompts)}")
    print(f"  Runs per experiment: {args.runs_per_experiment}")
    print(f"  Max score per experiment: "
          f"{len(eval_config.get('criteria', [])) * len(test_prompts) * args.runs_per_experiment}")
    print(f"{'#'*60}\n")

    # State
    results_history = []
    best_score = -1
    experiment_num = 0
    consecutive_failures = 0
    MAX_CONSECUTIVE_FAILURES = 5

    # Establish baseline
    print("Establishing baseline...")
    experiment_num += 1
    backup_path = backup_target(args.target, str(backups_dir), experiment_num)

    exp_runs_dir = runs_dir / f"experiment_{experiment_num:03d}"
    exp_runs_dir.mkdir(exist_ok=True)

    all_outputs = []
    for prompt_idx, test_prompt in enumerate(test_prompts):
        for run_idx in range(args.runs_per_experiment):
            print(f"  Baseline run: prompt {prompt_idx+1}/{len(test_prompts)}, "
                  f"run {run_idx+1}/{args.runs_per_experiment}")
            output = execute_target(
                args.target, test_prompt, eval_config,
                prompt_idx * args.runs_per_experiment + run_idx,
                str(exp_runs_dir), args.execution_model,
            )
            all_outputs.append(output)

    # Score baseline
    eval_results = run_eval(all_outputs, eval_config, args.eval_model)
    best_score = eval_results["total_yes"]
    max_score = eval_results["max_score"]

    entry = {
        "experiment": f"{experiment_num:03d}",
        "score": best_score,
        "max_score": max_score,
        "status": "keep",
        "description": "baseline — original target file",
        "timestamp": datetime.now().isoformat(),
    }
    results_history.append(entry)
    append_results_tsv(results_file, entry)
    save_snapshot(args.target, str(snapshots_dir), experiment_num, "keep")

    print(f"\n🎯 Baseline score: {best_score}/{max_score} ({eval_results['score_pct']}%)")
    print(f"\nStarting autonomous experimentation loop...\n")

    # Main loop
    try:
        while True:
            experiment_num += 1

            if args.max_experiments > 0 and experiment_num > args.max_experiments:
                print(f"\nReached max experiments ({args.max_experiments}). Stopping.")
                break

            # Generate experiment
            print(f"Generating experiment {experiment_num:03d}...")
            current_content = read_target(args.target)
            experiment = generate_experiment(
                current_content, program, results_history,
                eval_config, args.experiment_model,
            )

            if experiment is None:
                print("  Failed to generate experiment, retrying...")
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    print(f"\nFATAL: {MAX_CONSECUTIVE_FAILURES} consecutive failures to generate experiment. Stopping.")
                    break
                time.sleep(5)
                continue
            consecutive_failures = 0

            description = experiment.get("description", "unknown change")
            new_content = experiment.get("new_content", "")

            # Validate new_content before writing
            if not new_content or not isinstance(new_content, str):
                print(f"  ERROR: LLM returned invalid content (empty or non-string), skipping experiment")
                revert_target(args.target, backup_path)
                continue

            print_banner(experiment_num, description)
            print(f"  Reasoning: {experiment.get('reasoning', 'none')}")

            # Backup and apply change
            backup_path = backup_target(args.target, str(backups_dir), experiment_num)
            write_target(args.target, new_content)

            # Run test executions
            exp_runs_dir = runs_dir / f"experiment_{experiment_num:03d}"
            exp_runs_dir.mkdir(exist_ok=True)

            all_outputs = []
            crash = False
            for prompt_idx, test_prompt in enumerate(test_prompts):
                for run_idx in range(args.runs_per_experiment):
                    print(f"  Run: prompt {prompt_idx+1}/{len(test_prompts)}, "
                          f"run {run_idx+1}/{args.runs_per_experiment}")
                    output = execute_target(
                        args.target, test_prompt, eval_config,
                        prompt_idx * args.runs_per_experiment + run_idx,
                        str(exp_runs_dir), args.execution_model,
                    )
                    if output.startswith("ERROR:"):
                        print(f"    ⚠️  {output}")
                        crash = True
                    all_outputs.append(output)

            if crash:
                # At least one run crashed — warn but continue scoring with partial outputs
                crashed_count = sum(1 for o in all_outputs if o.startswith("ERROR:"))
                print(f"  WARNING: {crashed_count}/{len(all_outputs)} runs crashed")
                entry = {
                    "experiment": f"{experiment_num:03d}",
                    "score": 0,
                    "max_score": max_score,
                    "status": "crash",
                    "description": description,
                    "timestamp": datetime.now().isoformat(),
                }
                results_history.append(entry)
                append_results_tsv(results_file, entry)
                revert_target(args.target, backup_path)
                save_snapshot(args.target, str(snapshots_dir), experiment_num, "crash")
                print_result(entry, best_score)
                continue

            # Score
            eval_results = run_eval(all_outputs, eval_config, args.eval_model)
            score = eval_results["total_yes"]

            if score > best_score:
                status = "keep"
                best_score = score
                save_snapshot(args.target, str(snapshots_dir), experiment_num, "keep")
            else:
                status = "discard"
                revert_target(args.target, backup_path)
                save_snapshot(args.target, str(snapshots_dir), experiment_num, "discard")

            entry = {
                "experiment": f"{experiment_num:03d}",
                "score": score,
                "max_score": max_score,
                "status": status,
                "description": description,
                "timestamp": datetime.now().isoformat(),
            }
            results_history.append(entry)
            append_results_tsv(results_file, entry)
            print_result(entry, best_score)

            # Save detailed eval results
            eval_output_path = exp_runs_dir / "eval_results.json"
            with open(eval_output_path, "w") as f:
                json.dump(eval_results, f, indent=2)

    except KeyboardInterrupt:
        print(f"\n\n{'='*60}")
        print(f"  AUTORESEARCH STOPPED BY USER")
        print(f"  Total experiments: {experiment_num}")
        print(f"  Best score: {best_score}/{max_score}")
        print(f"  Results: {results_file}")
        print(f"{'='*60}\n")

    # Final summary
    print(f"\n📊 Final Summary:")
    print(f"   Experiments run: {len(results_history)}")
    print(f"   Best score: {best_score}/{max_score}")
    keeps = sum(1 for r in results_history if r["status"] == "keep")
    discards = sum(1 for r in results_history if r["status"] == "discard")
    crashes = sum(1 for r in results_history if r["status"] == "crash")
    print(f"   Kept: {keeps} | Discarded: {discards} | Crashed: {crashes}")
    print(f"   Results log: {results_file}")
    print(f"   Snapshots: {snapshots_dir}")


if __name__ == "__main__":
    main()
