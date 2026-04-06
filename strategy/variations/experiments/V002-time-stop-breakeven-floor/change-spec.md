# Change Spec - V002

## Baseline reference

- Backtest script: `src/backtest_coinbase.py`
- Baseline run mode: default TIME_STOP behavior

## Exact change (one only)

- Field/rule: TIME_STOP execution behavior
- From: `exit_price = price`
- To: `exit_price = max(price, entry)`

## Unchanged controls

- `MAX_HOLD_MINUTES=90`
- Risk per trade: 0.50%
- Max trades/day: 3
- Max consecutive losses: 2
- Daily loss limit: 2.0%
- Entry thresholds and TP/SL unchanged
