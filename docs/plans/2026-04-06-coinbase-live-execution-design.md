# Coinbase Live Execution Design

Date: 2026-04-06
Scope: Coinbase Advanced Trade SPOT live execution for v2 strategy (limit-only, long-only).

## Goals
- Enable live execution using Coinbase Advanced Trade REST while preserving v2 strategy logic.
- Enforce Layer 1 risk rules (0.50% per trade, max 3/day, no shorts, limit-only).
- Add heartbeat + stale-feed protection to prevent stale trading.

## Non-Goals
- Futures/perps support.
- Market orders.
- Strategy logic changes or parameter tuning.

## Architecture
- New Coinbase live adapter for REST order placement, cancel, and status.
- Extend ExecutionRouter to route live orders when .env enables live mode.
- Keep v2 strategy unchanged except for the paper/live switch (mode propagated to router).
- Use existing WS feed for signals; REST polling for order status and fill confirmation.

## Data Flow
1. v2 strategy emits an ExecutionRequest (entry limit, TP, SL, size, reduce-only flags).
2. ExecutionRouter enforces guardrails and routes to paper or live adapter.
3. Live adapter places entry limit; monitors for fill or timeout.
4. On fill: places TP/SL (OCO if supported; otherwise separate reduce-only limits).
5. Runtime state and journal are updated with order IDs, fill prices, and status transitions.

## Safety + Guardrails
- Gate all new entries on:
  - TRADING_ENABLED=true
  - ENABLE_LIVE_TRADING=true
  - PAPER_MODE=false
- Enforce: limit-only, long-only, max trades/day, max consecutive losses, and risk-per-trade sizing.
- Stale feed detection: if no WS ticks for N seconds, disable new entries until recovered.
- Heartbeat: update runtime state on interval; optional Supabase heartbeat if configured.

## Configuration
- Use existing .env keys: COINBASE_API_KEY_NAME, COINBASE_PRIVATE_KEY.
- Add explicit live flags if not present: ENABLE_LIVE_TRADING, TRADING_ENABLED.

## Observability
- Log every order submit/cancel/fill with correlation IDs.
- Dashboard shows live mode flags, open orders, and last heartbeat timestamp.

## Testing
- Extend scripts/test_env.py to verify live REST auth (no order placement).
- Add a live connectivity check that hits product endpoints and account status only.
- Unit tests for router guardrails (no shorts, limit-only, daily max).

## Risks
- Coinbase OCO availability varies; fallback to two reduce-only limit orders if unavailable.
- Network or WS outages can create stale signals; mitigated by stale-feed gate and heartbeat.
