# Product Requirements - Crypto Squid Hyperliquid MVP

## Objective
Build a clean, rules-based, Hyperliquid-only intraday reversal bot that captures bounce trades after sharp downside overreactions.

## Scope (MVP)
- Exchange: Hyperliquid only
- Symbols: BTC, ETH (SOL extensible but off by default)
- Direction: Long only
- Modes: Log-only, paper, live-ready
- Risk model: stop-aware sizing from account equity
- Logging: all signal decisions and all trades

## Entry rules (all required)
1. Sharp drop in last 3 minutes
   - BTC >= 0.75%
   - ETH >= 1.00%
2. Volume spike
   - 3-minute volume >= 2.0x rolling 20-period 3-minute baseline
3. Overextension
   - Price z-score <= -2.0 over short rolling lookback
4. Stabilization after flush
   - Wait at least 30 seconds
   - Require either panic-low hold for 30 seconds or downside deceleration candle pattern
5. Position/risk gate
   - No open/pending position
   - No risk block active

## Exit rules
- Hard stop: tighter of structure stop near panic low and fixed SL cap (symbol-specific)
- Take profit:
  - BTC +1.0%
  - ETH +1.2%
- Time stop: 90 minutes

## Risk constraints
- Risk per trade: 0.50% of account equity
- Max trades per day: 3
- Max consecutive losses: 2
- Daily realized loss stop: 2.0%
- No new entries when market data stale or live exchange unhealthy

## Out of scope
- Binance dependencies
- Polymarket logic
- ML/AI decisioning
- Sentiment/news ingestion
- Short-side live path

## Success criteria
- Deterministic signal pass/reject logging with reasons
- Deterministic trade lifecycle with explicit mode control
- No silent live trading defaults
- Clean review artifacts in SQLite + markdown reports
