# Engineering Design - Crypto Squid Hyperliquid MVP

## Architecture

```
bot.py
  -> hyperliquid_client.py (websocket market data, optional live sdk execution)
  -> detector.py (rule engine and stabilization state machine)
  -> risk.py (daily guards and stop-aware sizing)
  -> executor.py (log-only/paper/live trade lifecycle)
  -> logger.py (SQLite signals/trades + journal + daily reports)
  -> config.py (single config surface from .env)
```

## Design principles
- Hyperliquid-only integration
- One process, deterministic flow, no hidden threads for strategy logic
- No market orders in strategy path
- Explicit mode gating with live disabled by default
- Single open or pending position at a time

## Signal data flow
1. Market trade ticks arrive from Hyperliquid websocket.
2. Signal engine computes:
   - 3-minute drop %
   - 3-minute volume ratio vs rolling 20x 3-minute baseline
   - rolling price z-score
3. If sharp-drop condition appears, signal either:
   - rejected with reason (volume/zscore fail), or
   - enters stabilization state.
4. After wait window, stabilization either passes or times out with reason.
5. Every decision is persisted to `signals` table.

## Trade data flow
1. Passed signal is risk-gated (trade count, consecutive losses, daily loss %, data/exchange health).
2. Entry is stop-aware sized from `RISK_PER_TRADE_PCT`.
3. Execution mode:
   - `log-only`: records skipped trade
   - `paper`: simulates limit entry/exit by price stream
   - `live`: routes through Hyperliquid SDK wrapper
4. Trade closes via TP, SL, or time-stop and is persisted.

## Data model
- SQLite db: `data/trades/trades.db`
  - `signals`: timestamp, symbol, drop %, volume ratio, z-score, stabilization, pass/reject reason
  - `trades`: lifecycle fields, prices, size, PnL, reason, mode, strategy version

## Safety model
- `ENABLE_LIVE_TRADING=false` by default
- Live path requires key material and client health
- `TRADING_ENABLED=false` halts new entries
- stale data or unhealthy exchange blocks new entries
