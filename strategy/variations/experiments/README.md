# Experiments Index

Store each variation test in its own folder.

## Naming

- `V001-<slug>`
- `V002-<slug>`

## Required files per experiment

- `plan.md` - hypothesis, single change, test window
- `change-spec.md` - exact value changed from baseline
- `results.md` - metrics and keep/discard decision

## Process

1. Copy `V000-template/` to the next ID.
2. Fill `change-spec.md` with one change only.
3. Run backtest(s) and record outputs in `results.md`.
4. Decide keep/discard before opening the next experiment.
