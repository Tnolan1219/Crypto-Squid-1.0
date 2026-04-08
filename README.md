# Crypto Squid Runtime (VPS-Ready)

This repo is now structured so one command can run the orchestrator that manages strategies, control polling, logging, and failsafes without changing strategy logic.

## Architecture Overview

- `core/engine.py` - master loop, global state, failsafe checks, heartbeat updates
- `core/strategy_manager.py` - loads and runs strategies, supports per-strategy enable/mode/max position
- `core/execution_router.py` - centralized execution validation (size limits, maker-only, slippage checks)
- `core/supabase_control.py` - remote control polling from Supabase `strategy_control`
- `core/logger.py` - file + console logging under `logs/`
- `strategies/coinbase_v2_strategy.py` - adapter around existing v2 strategy modules in `src/`
- `integrations/noaa_client.py` - NOAA API integration utility
- `scripts/run_all.py` - single VPS entrypoint

## Supabase Control Table

Apply SQL in `ops/supabase/strategy_control.sql`.

Required columns are present:

- `id`
- `strategy_name`
- `enabled`
- `mode` (`paper`, `live`, `off`)
- `max_position`
- `last_updated`

The engine polls this table every 2-5 seconds and applies updates to each strategy dynamically.

## Environment Setup

1. Copy `.env.example` to `.env`.
2. Fill required keys:
   - `COINBASE_API_KEY_NAME`
   - `COINBASE_PRIVATE_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `CONTROL_API_TOKEN` (required for remote start/stop control)
3. Keep `TRADING_ENABLED=true` for active loop or set `false` for safe attach.

No keys are hardcoded in source.

## Install

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
```

## Run Locally

```bash
python scripts/run_all.py
```

What this does:

- Starts the master engine loop
- Starts configured strategies (`ENABLED_STRATEGIES`)
- Polls Supabase control table
- Writes logs to `logs/`
- Updates heartbeat through `last_updated`

## Enable / Disable Strategies

Update `strategy_control.enabled` in Supabase:

- `true` => strategy runs
- `false` => strategy is cancelled/paused

## Switch Paper / Live

Update `strategy_control.mode`:

- `paper` => paper behavior
- `live` => live mode path (router ready; keep strategy safeguards)
- `off` => same effect as disable for execution

## Stop System

- Ctrl+C in local terminal
- On VPS, stop the process manager service (systemd/pm2/supervisor)
- For immediate remote halt without restart, call `GET /control/stop` with `Authorization: Bearer <CONTROL_API_TOKEN>`

## Remote Control API (for Vercel proxy)

Dashboard server now exposes control-safe endpoints:

- `GET /health` - liveness + control-token configured flag
- `GET /snapshot` - runtime state + current control state
- `GET /control/status` - current manual trading toggle (auth required)
- `GET|POST /control/start` - enables trading loop (auth required)
- `GET|POST /control/stop` - disables trading loop (auth required)

Auth rules:

- Preferred: `Authorization: Bearer <CONTROL_API_TOKEN>`
- Optional fallback: `?token=<CONTROL_API_TOKEN>`

Control writes to `data/control/runtime_control.json`. Engine loop reads this file every tick.
Failsafe latch still overrides manual start if max daily loss guard has been breached.

## Local Pre-VPS Functional Checks

Run and verify:

```bash
python scripts/run_all.py
```

- strategies initialize
- no crash loop
- `logs/engine.log` receives heartbeat/control entries
- `logs/trades.log` and `logs/signals.log` created
- Supabase `strategy_control` toggles are reflected within poll interval
