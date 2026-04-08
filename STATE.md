# Crypto Squid — State

## Engine
Coinbase Advanced Trade (WebSocket + REST)

## Phase
v2 Strategy Build — Event Study + Paper Validation

## Last Completed Step
Built full CRYPTO SQUID v2 system:
- Coinbase WebSocket feed (trades + L2 spread)
- 1-second bar builder with rolling 30-min windows
- 5-stage signal engine (regime → panic → disorder → stabilization → entry)
- Staged-exit paper engine (TP1/TP2/breakeven stop/time stop)
- Event study collector (all candidate events → data/events/events.csv)
- Anti-overfitting research protocol documented
- v2 parameters as Python dataclasses (src/params_v2.py)
- All strategy docs updated: core-rules.md, tunable-params.md, v2-params.md

## In Progress
Phase 1 — Event collection. Run bot_v2.py to accumulate candidate events.

## Runtime Status
- VPS attach layer ready:
  - `core/engine.py` master loop
  - `core/strategy_manager.py` dynamic strategy controls
  - `core/execution_router.py` centralized execution guardrails
  - `core/supabase_control.py` remote polling + heartbeat
  - `scripts/run_all.py` one-command runtime entrypoint
- Remote operations layer ready:
  - `src/dashboard.py` now exposes `/health`, `/snapshot`, `/control/status|start|stop`
  - Manual runtime gate at `data/control/runtime_control.json`
  - Vultr deploy assets in `ops/vultr/`
  - Vercel proxy dashboard scaffold in `ops/vercel-dashboard/`
- Strategy logic remains unchanged (adapter wraps existing v2 behavior)
- Production deployment status:
  - Vultr VPS live at `45.76.2.84` (engine + dashboard services active)
  - UFW enabled (`22`, `80`, `443`), fail2ban active, unattended-upgrades active
  - Vercel proxy dashboard live and control path verified end-to-end

## Go-Live Gate (from docs/ANTI_OVERFITTING_PROTOCOL.md)
- [ ] 300+ candidate events in data/events/events.csv
- [ ] 80+ paper trades closed
- [ ] Positive net expectancy (after fees) in chronological validation + test
- [ ] No single month > 35% of total PnL
- [ ] DSR > 0 on out-of-sample
- [ ] WebSocket stable 5 consecutive days
- [ ] User explicit sign-off: "approved for live"

## Next Actions
- [ ] Run: `.venv/Scripts/python.exe src/bot_v2.py`
- [ ] Monitor output every 10 seconds — confirm prices, drop%, z-score, spread
- [ ] Let run for hours/days to accumulate events
- [ ] Add DNS domain for VPS API and enable TLS via certbot (currently HTTP)
- [ ] Rotate exposed Coinbase API key + VPS root password, then update `/opt/cryptosquid/.env`
- [ ] Run `/weekly-review` after 1 week of data
- [ ] Run `/propose-experiments` after 300 events collected
- [ ] After 80 paper trades: run chronological validation (Phase 3)

## Bot Commands

| Command | Purpose |
|---|---|
| `.venv/Scripts/python.exe src/bot_v2.py` | v2 WebSocket bot — primary |
| `.venv/Scripts/python.exe src/bot.py` | v1 REST polling bot — sanity check only |

## Architecture (current)

```
src/
  bot_v2.py          — main v2 loop (WebSocket-driven, event study)
  coinbase_ws.py     — Coinbase WebSocket client (trades + L2)
  bar_builder.py     — 1-second bars + rolling stats (thread-safe)
  signal_v2.py       — 5-stage signal state machine
  paper_engine_v2.py — staged exits (TP1 → breakeven stop → TP2 → time stop)
  event_collector.py — CSV event logger (data/events/events.csv)
  params_v2.py       — all v2 parameters as frozen dataclasses
  risk.py            — position_size() + full RiskEngine
  runtime_store.py   — atomic JSON state writer
  --- v1 (preserved, still functional) ---
  bot.py, market_data.py, tracker.py, strategy.py, paper_engine.py
  --- Hyperliquid-era (preserved) ---
  config.py, detector.py, executor.py, hyperliquid_client.py, models.py, logger.py
```

## Data

```
data/events/events.csv   — event study (all candidates)
data/trades/             — runtime state JSON
journal/raw-trades/      — trade journals
reports/daily/           — daily reports
```

## Known Gaps (Phase 2+)
- L2 spread tracking may be coarse until order book depth is calibrated
- Volume imbalance uses WebSocket side labels (accurate enough for screening)
- No live order placement yet (paper only)
