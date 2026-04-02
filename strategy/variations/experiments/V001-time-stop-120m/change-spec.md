# Change Spec - V001

## Baseline reference

- Strategy version: v1 replay logic in `src/backtest_coinbase.py`
- Baseline config: `MAX_HOLD_MINUTES=90`

## Exact change (one only)

- Field: `MAX_HOLD_MINUTES`
- From: `90`
- To: `120`

## Unchanged controls

- Risk per trade: 0.50%
- Max trades/day: 3
- Max consecutive losses: 2
- Daily loss limit: 2.0%
- Entry thresholds and TP/SL logic unchanged
