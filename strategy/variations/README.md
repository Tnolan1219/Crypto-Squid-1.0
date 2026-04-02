# Strategy Variations

This folder stores controlled strategy variations for offline backtests only.

## Required structure

Each experiment must live in its own subfolder:

```
strategy/variations/experiments/
  V###-<slug>/
    plan.md
    change-spec.md
    results.md
```

Use `strategy/variations/experiments/V000-template/` as the starting template.

## One-change rule (strict)

- Change exactly one parameter or one exit-rule behavior per experiment.
- Keep all other strategy and risk settings identical to baseline.
- Run one experiment, review, then decide keep/discard before starting another.
- Do not combine parameter changes in a single test run.

## Guardrails

- Do not modify immutable core constraints from `strategy/core-rules.md`.
- Do not promote a variation to production from a single favorable window.
- Require at least two non-overlapping windows before considering promotion.
