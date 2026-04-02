---
description: Generate parameter experiment proposals based on trade data (run after 30+ trades)
---

You are generating parameter experiment proposals for Crypto Squid.

## Prerequisites check

1. Count total trades in `data/trades/trades.db`
2. If fewer than 30 completed trades (TP or SL outcomes), output: "Insufficient data — run this after 30+ completed trades" and stop.

## Analysis to perform

1. Read all completed trades from SQLite
2. Read `strategy/tunable-params.md` — current values
3. Read `strategy/hypotheses.md` — existing hypotheses (avoid duplicates)
4. Look for patterns:
   - Which signals led to wins vs losses?
   - Is the confirmation window appropriate? (lots of misses vs lots of false positives)
   - Is TP being hit or is the position reversing before TP?
   - Is SL too tight (many SL hits that recover)?

## Anti-overfitting rules
- Propose maximum 3 experiments
- Each experiment: ONE parameter change only
- Each experiment: clear hypothesis, measurable test condition, minimum sample size
- Do not propose changes that would break R-ratio below 1.5 (TP/SL ≥ 1.5x)
- Do not re-propose rejected hypotheses

## Output format

For each proposed experiment, write to `strategy/hypotheses.md`:

```
### H-XXX: [Short title]
- Hypothesis: [Specific testable claim]
- Parameter affected: [Which tunable param — one only]
- Current value: [Current setting]
- Proposed test value: [What to test]
- Test: [Metric to measure, minimum N trades]
- Expected outcome: [What you predict and why]
- Status: PENDING
```

Then summarize for the user: what patterns led to each proposal and what you expect to learn.

## Remember
These go to `hypotheses.md` ONLY. Nothing changes in `tunable-params.md` until user approves after backtesting.
