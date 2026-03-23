# autoresearch program.md — Template

This is the template for your program.md file. Copy this, fill in the blanks, and point your agent at it. This file is edited by the human, not the agent — it's your "research org code."

## Setup

To set up a new autoresearch experiment:

1. **Agree on a run tag**: Use today's date (e.g. `mar21`). This identifies the experiment run.
2. **Read the target file**: Read the file being optimized for full context.
3. **Read the eval config**: Understand what "better" means for this experiment.
4. **Initialize results.tsv**: Create the results file with just the header row.
5. **Establish baseline**: Run the target as-is to get the baseline score.
6. **Confirm and go**: Confirm setup looks good, then kick off experimentation.

## Target

- **File to optimize**: `[PATH TO YOUR TARGET FILE]`
- **What it does**: `[DESCRIPTION OF WHAT THE TARGET FILE DOES]`
- **What success looks like**: `[DESCRIPTION OF IDEAL OUTPUT]`

## Eval Configuration

The eval suite consists of binary yes/no questions. Each test run generates an output, and each output is scored against all criteria.

**Eval criteria** (edit these to match your needs):

1. `[YOUR CRITERION 1 — e.g., "Does the output follow the specified format?"]`
2. `[YOUR CRITERION 2 — e.g., "Is all text grammatically correct?"]`
3. `[YOUR CRITERION 3 — e.g., "Does it address the user's core question?"]`
4. `[YOUR CRITERION 4 — e.g., "Is the tone consistent throughout?"]`

**Test prompts** (the inputs used to exercise the target):

1. `[TEST PROMPT 1 — a realistic input the target would receive]`
2. `[TEST PROMPT 2 — a different realistic input]`
3. `[TEST PROMPT 3 — an edge case or challenging input]`

**Runs per experiment**: `[5-10 recommended]`

**Max score per experiment**: criteria_count × runs_per_experiment × test_prompts_count

## Constraints

**What you CAN do:**
- Modify the target file — everything is fair game: wording, structure, format, examples, tone, logic, etc.

**What you CANNOT do:**
- Modify the eval criteria (those are fixed by the human)
- Change the test prompts
- Install new dependencies (work with what's available)
- Modify the eval engine

## Experimentation Strategy

The goal is simple: **get the highest eval score.**

Suggested experiment progression:
1. **Baseline**: Run as-is to establish the starting score
2. **Quick wins**: Fix obvious issues (typos, unclear instructions, missing sections)
3. **Structural changes**: Reorganize content, add/remove sections
4. **Tone and style**: Adjust language, formality, specificity
5. **Edge cases**: Handle unusual inputs or scenarios
6. **Simplification**: Remove anything that doesn't improve the score
7. **Radical experiments**: Try completely different approaches

When you're stuck, try:
- Re-read the eval criteria and think about what would make each one pass more reliably
- Look at which criteria fail most often and focus there
- Try the opposite of what you've been doing
- Simplify — remove complexity and see if the score holds

## The Experiment Loop

LOOP FOREVER:

1. Review the results log and current target file
2. Plan an experiment — one focused change at a time
3. Edit the target file
4. Run the experiment (execute target × runs_per_experiment for each test prompt)
5. Score all outputs against the eval criteria
6. Record results in results.tsv
7. If score improved → KEEP the change (this is now the new baseline)
8. If score is equal or worse → REVERT to previous version
9. Go to step 1

**Timeout**: If a single test run takes more than 2 minutes, kill it and treat as a failure.

**Crashes**: If a run crashes due to a fixable bug (typo, missing import), fix it and re-run. If the approach is fundamentally broken, log it as "crash" and move on.

**NEVER STOP**: Once experimentation begins, do NOT pause to ask the human. The human might be asleep or away. You are autonomous. Work indefinitely until manually interrupted.

## Output Format

After each experiment, log to results.tsv:

```
experiment	score	max_score	status	description	timestamp
```

- experiment: sequential number (001, 002, etc.)
- score: total yes answers across all runs and criteria
- max_score: theoretical maximum (criteria × runs × prompts)
- status: keep, discard, or crash
- description: short text describing what this experiment tried
- timestamp: ISO 8601 timestamp

## Notes

- The research log is the most valuable output. Keep detailed descriptions.
- Each experiment should try ONE thing. Don't stack multiple changes.
- If you find a big win, consolidate it before moving on to the next idea.
- Periodically re-read the target file fresh to spot issues you've grown blind to.
