# Plan - V001

## Objective

Test whether extending hold duration improves realized returns under backtest risk guardrails.

## Single change under test

- Parameter/rule: `MAX_HOLD_MINUTES`
- Baseline value: `90`
- Variant value: `120`

## Hypothesis

Allowing more time may let mean-reversion complete and improve expectancy.

## Backtest plan

- Window A: trailing 30 days
- Granularity: `FIVE_MINUTE`
- Symbols: `BTC-USD,ETH-USD`

## Promotion criteria

- Improve realized P/L % and expectancy vs baseline.
- No material drawdown deterioration.
