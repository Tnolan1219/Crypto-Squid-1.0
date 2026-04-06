# Plan - V002

## Objective

Reduce losses from time-stop exits without changing entry logic or stop-loss logic.

## Single change under test

- Parameter/rule: TIME_STOP exit rule
- Baseline value: exit at market price when hold window expires
- Variant value: at TIME_STOP, floor exit to entry price (never negative TIME_STOP PnL)

## Hypothesis

If time-stop losers are clipped to break-even, expectancy and drawdown should improve.

## Backtest plan

- Window A: trailing 30 days
- Granularity: `FIVE_MINUTE`
- Symbols: `BTC-USD,ETH-USD`

## Promotion criteria

- Realized P/L % improves vs baseline.
- Expectancy improves vs baseline.
- Max drawdown does not worsen.
