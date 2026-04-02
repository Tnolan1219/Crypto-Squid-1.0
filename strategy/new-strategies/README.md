# Candidate New Strategies

This folder is for strategy concepts not yet accepted into production logic.

Use a dedicated folder per concept:

```
strategy/new-strategies/concepts/
  S###-<slug>/
    thesis.md
    rules.md
    validation.md
```

Use one document per concept and include:
- setup rules
- entry/exit rules
- risk model
- expected market regime
- validation plan

Keep production strategy in `src/strategy.py` unchanged until a concept passes testing.
