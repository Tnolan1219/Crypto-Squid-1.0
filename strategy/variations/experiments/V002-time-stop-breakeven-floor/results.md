# Results - V002

## Runs

Initial short-window check:
- Baseline: `backtests/runs/20260402-200948`
- Variant: `backtests/runs/20260402-200947`

Non-overlapping robustness windows (larger sample):
- Window A baseline: `backtests/runs/20260402-205141`
- Window A variant: `backtests/runs/20260402-210206`
- Window B baseline: `backtests/runs/20260402-211231`
- Window B variant: `backtests/runs/20260402-212249`
- Window C baseline: `backtests/runs/20260404-153132`
- Window C variant: `backtests/runs/20260404-153949`

## Metrics

Window A (2025-12-03 to 2026-04-02):
- Trades: 55 -> 55
- Realized P/L %: +0.39% -> -0.26%
- Expectancy ($/trade): +0.07 -> -0.05
- Profit factor: 1.022 -> 0.985
- Max drawdown %: 6.47% -> 6.34%

Window B (2025-08-05 to 2025-12-03):
- Trades: 86 -> 88
- Realized P/L %: +7.33% -> +11.32%
- Expectancy ($/trade): +0.85 -> +1.29
- Profit factor: 1.256 -> 1.407
- Max drawdown %: 9.18% -> 9.08%

Combined across both 120-day windows:
- Baseline realized P/L: +$77.26 (141 trades)
- Variant realized P/L: +$110.66 (143 trades)
- Net delta: +$33.40 in favor of variant

Window C (2025-04-07 to 2025-08-05):
- Trades: 15 -> 17
- Realized P/L %: +0.82% -> +2.88%
- Expectancy ($/trade): +0.54 -> +1.70
- Profit factor: 1.151 -> 1.471
- Max drawdown %: 3.53% -> 4.14%

Combined across all three windows:
- Baseline realized P/L: +$85.43 (156 trades)
- Variant realized P/L: +$139.50 (160 trades)
- Net delta: +$54.08 in favor of variant

## Gate checks

- minimum_trades: PASS in both larger windows
- drawdown_guard: FAIL in both larger windows for both baseline and variant

## Decision

- Keep or discard: Keep as preferred paper-test candidate
- Reason: Variant outperformed in 2 of 3 non-overlapping windows and improved aggregate returns.
- Next action: Validate in forward paper runtime before any production promotion.
