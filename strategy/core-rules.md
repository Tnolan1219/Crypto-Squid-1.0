# Core Rules — CRYPTO SQUID v2 (Coinbase)

> Layer 1: immutable. Claude may NOT change these without explicit user approval.

## Exchange and instrument

- Coinbase Advanced Trade only
- Spot products: BTC-USD, ETH-USD
- Long-only
- No market orders — limit orders only (maker bias)

## Position limits

- Maximum one open position at a time
- Maximum 2 filled trades per day
- Maximum 4 signals evaluated per symbol per day

## Loss controls

- Stop trading for the day after 2 consecutive losses
- Stop trading for the day if realized daily PnL ≤ −1.0% of equity
- `TRADING_ENABLED=false` in `.env` halts all new entries immediately

## Risk per trade

- Stop-aware sizing: `size = (equity × 0.35%) / stop_distance`
- Maximum gross exposure: BTC 20% of equity, ETH 15% of equity

## Entry discipline

- Entry limit order only: signal price − 3 bps (maker-biased)
- Order lifetime: 15 seconds — cancel if unfilled. No chasing.
- No re-entry from the same setup within the same signal phase

## Exit discipline

- Two-target staged exit (50% at TP1, 50% at TP2)
- Stop moved to breakeven after TP1 hit
- Hard time stop: 15 minutes
- Fast-reduce: partial exit at 5 minutes if PnL is in the marginal zone

## Execution safety

- WebSocket disconnect > 5 seconds during an open position → flatten
- Spread rejection (> 3 consecutive) → halt entries for the day
- Market-data staleness → block all new entries

## Research discipline (anti-overfitting)

- Minimum 300 candidate events before any parameter change
- Minimum 80 paper trades before chronological validation
- One parameter change at a time
- All proposed changes written in `strategy/hypotheses.md` before testing
- Go-live checklist (see `docs/ANTI_OVERFITTING_PROTOCOL.md`) must pass before live trading
