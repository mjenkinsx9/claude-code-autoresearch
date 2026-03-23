# Guide to Writing Effective Eval Criteria

The eval suite is the most important part of autoresearch. Bad evals lead to bad optimization — the model will find ways to game poorly written criteria without actually improving quality. This guide helps you write evals that drive real improvement.

## The Golden Rule: Binary Only

Every criterion must be answerable with **yes** or **no**. No scales, no ratings, no "rate 1-10."

Why? As one practitioner explains: "You're compounding probabilities. The more variability you give the model at every step along the chain, the more variable it gets in total. Imagine a cone — it starts narrow but the more variability, the more it compounds out." Binary questions give clean, reliable signal.

## Characteristics of Good Eval Criteria

### Specific and Observable

The evaluator (human or LLM) should be able to answer the question by looking at the output alone, without needing additional context or subjective judgment.

**Bad**: "Is the output good?" (what does "good" mean?)
**Good**: "Does the output contain at least one concrete example?"

**Bad**: "Does it resonate with the audience?" (subjective)
**Good**: "Does the first sentence describe a result or transformation, not just a feature?"

### Not Too Narrow

If criteria are too restrictive, the model will optimize for the letter of the law while missing the spirit.

**Bad**: "Is the output exactly 150 words?" (model will pad or trim to hit the number)
**Good**: "Is the output between 100-200 words?"

**Bad**: "Does the output start with the word 'Introducing'?" (too specific)
**Good**: "Does the opening line create curiosity or urgency?"

### Not Gameable

The model should not be able to trivially satisfy the criterion without actually improving quality.

**Bad**: "Does the output mention the product name?" (model just inserts it everywhere)
**Good**: "Does the output demonstrate understanding of the product's value proposition?"

**Bad**: "Does it include all five required sections?" (model creates empty sections)
**Good**: "Does each section contain substantive content (more than one sentence)?"

## Eval Criteria by Use Case

### For Skills (SKILL.md optimization)

1. Does the skill produce the expected output format?
2. Are all required sections/components present in the output?
3. Is the output free of placeholder or template text?
4. Does the output handle the given input without errors?
5. Would the output be useful without further editing?
6. Is the output consistent across multiple runs (same structure, similar quality)?
7. Does the skill follow its own stated instructions?
8. Is the output appropriately detailed (not too brief, not excessively verbose)?

### For Prompts

1. Does the response directly address the user's question?
2. Is the tone appropriate for the intended audience?
3. Does it avoid hallucinated or fabricated facts?
4. Is the response well-structured (clear beginning, middle, end)?
5. Does it include actionable next steps or recommendations?
6. Is it free of unnecessary caveats or hedging?
7. Would a domain expert find the content accurate?
8. Does it stay focused on the topic without tangents?
9. Does it cite specific quotes or sources when making factual claims?
10. When uncertain, does it explicitly say so rather than guessing?

### For Code

1. Does the script run without errors?
2. Does it produce the expected output for the test input?
3. Does it handle edge cases (empty input, large input, special characters)?
4. Is it under the performance threshold (time, memory)?
5. Is the code readable (clear variable names, comments where needed)?
6. Does it follow the project's coding conventions?
7. Are there no security vulnerabilities (injection, exposed secrets)?
8. Does it include error handling?

### For Email/Copy

1. Does the subject line create curiosity or urgency?
2. Is the opening sentence about the reader (not the sender)?
3. Does it include a clear call-to-action?
4. Is it under the word limit?
5. Does it avoid jargon or buzzwords?
6. Does it describe benefits (not just features)?
7. Is the tone conversational (not corporate/stiff)?
8. Does it include social proof or credibility?

### For Diagrams/Visual Output

1. Is all text in the output legible and grammatically correct?
2. Does it follow the specified color palette?
3. Is the layout linear (left-to-right or top-to-bottom)?
4. Is it free of numbering, ordinals, or sequential ordering?
5. Are all elements properly aligned?
6. Does it convey the intended concept clearly?

## How Many Criteria?

- **Minimum**: 3 criteria (fewer doesn't give enough signal)
- **Sweet spot**: 4-8 criteria
- **Maximum**: 10 criteria (more becomes unwieldy and increases noise)

The total eval score for one experiment = (number of yes answers) across all criteria, all test prompts, and all runs. For example: 4 criteria × 3 test prompts × 5 runs = max score of 60.

## Test Prompts

Alongside criteria, you need test prompts — the inputs that exercise the target. These should be:

- **Realistic**: things a real user would actually say or input
- **Diverse**: cover different use cases, edge cases, and difficulty levels
- **Consistent**: use the same prompts across all experiments so results are comparable

Aim for 3-5 test prompts. More gives better signal but costs more time per experiment.

## Common Pitfalls

1. **Vibes-based criteria**: "Does it feel professional?" — too subjective. Replace with observable traits.
2. **Overfitting criteria**: criteria so specific to one example that they don't generalize.
3. **Redundant criteria**: multiple criteria testing the same thing in different words.
4. **Missing the point**: criteria that technically pass but don't capture what actually matters to the user.
5. **Too many criteria**: drowns the signal in noise and makes each experiment take forever.

## Iterating on Evals

Your eval suite is not set in stone forever, but it should be stable within an experiment run. If you notice your evals aren't capturing what matters:

1. Finish the current run
2. Review which criteria are useful (always pass = non-discriminating, remove it)
3. Identify what's missing from the evals
4. Update the eval config
5. Re-baseline with the new evals
6. Start a new run
