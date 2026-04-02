# Backtests

Organized storage for historical backtest runs.

## Structure
- `runs/<timestamp>/summary.json`
- `runs/<timestamp>/summary.md`
- `runs/<timestamp>/trades.csv`
- `runs/<timestamp>/equity.csv`
- `runs/<timestamp>/candles-<symbol>.csv`

## Notes
- Results are deterministic for a fixed candle set.
- `leverage_factor` is reporting-only unless execution logic is explicitly changed.
