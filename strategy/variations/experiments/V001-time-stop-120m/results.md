# Results - V001

## Runs

- Baseline (90m): `backtests/runs/20260402-194327`
- Variant (120m): `backtests/runs/20260402-194443`

## Metrics

- Baseline trades closed: 9
- Variant trades closed: 8
- Baseline win rate: 55.56%
- Variant win rate: 37.50%
- Baseline realized P/L %: -0.45%
- Variant realized P/L %: -0.79%

## Gate checks

- Baseline minimum_trades: FAIL
- Variant minimum_trades: FAIL
- Baseline drawdown_guard: FAIL
- Variant drawdown_guard: FAIL

## Decision

- Keep or discard: Discard
- Reason: Return worsened and win rate dropped on this window.
- Next action: Test one alternate time-stop rule change in a new experiment (single change only).
