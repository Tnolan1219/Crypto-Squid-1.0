# Implementation Plan — Coinbase Live Execution

## Phase 1 — Plumbing and config
1. Extend `core/settings.py` to load live flags and risk settings from `.env`.
2. Update `core/engine.py` to set strategy mode based on `ENABLE_LIVE_TRADING` and `PAPER_MODE`.
3. Add `LIVE_STALE_FEED_SECONDS` and `STOP_LIMIT_OFFSET_BPS` defaults to `.env.example`.

## Phase 2 — Coinbase live adapter
1. Add `src/coinbase_live.py` with a `CoinbaseLiveClient` wrapper for:
   - limit GTC buy/sell
   - stop-limit GTC sell
   - limit IOC sell (time-stop/fast-reduce)
   - get_order, get_fills, cancel_orders
2. Cache product increments and format size/price safely.

## Phase 3 — Live execution engine
1. Add `src/live_engine_v2.py`:
   - Track pending entry orders and open positions.
   - Place TP1/TP2/SL orders after entry fill.
   - Handle TP1 hit (move stop to breakeven) and TP2/SL exits.
   - Handle time stop and fast-reduce with limit IOC sells.
   - Enforce daily trade limits and consecutive losses.

## Phase 4 — Strategy integration
1. Update `strategies/coinbase_v2_strategy.py` to:
   - Use live engine when mode == "live".
   - Keep paper engine when mode == "paper".
   - Block new entries if stale feed or risk guardrails fail.
   - Include heartbeat + market-data freshness in runtime state.

## Phase 5 — Logging + journal
1. Update `src/trade_history.py` to record `mode` from trade record.
2. Ensure live trades write to journal and reports just like paper.

## Phase 6 — Verification
1. Update `scripts/test_env.py` to validate live REST permissions.
2. Run `scripts/test_env.py` and a short live connectivity check (no orders) before enabling live.
