# Changelog

## 2026-04-11 - Crypto-Squid 3.1 (Official Source of Truth)
- Promoted strategy naming and runtime versioning to `Crypto-Squid 3.1`
- Upgraded `src/params_v3.py` with 3.1 per-asset table (BTC/ETH/SOL/DOGE/ADA/AVAX/POL/MATIC)
- Added non-fragile timing profile (5m panic window, longer stabilization windows)
- Added capital-per-trade controls, portfolio total exposure cap, and BTC stress gate for alt entries
- Added live safety requirements: `TRADING_ENABLED=true` and `LIVE_TRADING_CONFIRM=YES`
- Added 3.1 source-of-truth docs under `docs/crypto-squid-3.1/`
- Added VPS access/deploy contract doc at `ops/vultr/ACCESS_AND_DEPLOY_CONTRACT.md`

## 2026-04-11 - Crypto Squid 3.0 Upgrade (Multi-Asset + Adaptive Filters)
- Added `src/params_v3.py` with Crypto Squid 3.0 risk, signal, and per-symbol configuration
- Preserved prior baseline as `src/params_v1_0.py` (legacy snapshot aliasing prior v2 config)
- Added `src/signal_v3.py` with new regime filter (15m VWAP or non-negative EMA slope), tightened disorder filter, and upgraded stabilization checks
- Added `src/paper_engine_v3.py` with trailing stop management after TP1
- Added `strategies/coinbase_v3_strategy.py` with active Coinbase product filtering and simultaneous multi-symbol scanning
- Updated engine registration/defaults to support and prefer `coinbase_v3`
- Updated dashboard symbol table and chart labels to reflect dynamic multi-asset scanning
- Updated project state in `STATE.md` for v3 runtime and next actions

## 2026-04-08 - Live Reporting + Repeatable Ops Playbooks
- Added Coinbase reporting pipeline at `src/coinbase_reporting.py` (prices, balances, open orders, recent fills)
- Expanded `src/dashboard.py` snapshot/health payloads with reporting + engine heartbeat fields
- Expanded Vercel dashboard (`index.html`) with running indicator icon, live BTC/ETH, open orders/fills tables, and reporting KPIs
- Added complete local->VPS->Vercel retro + repeatable workflow doc: `ops/vultr/LOCAL_TO_VPS_FULL_WORKFLOW.md`
- Added reusable Kalshi-on-same-VPS attach template: `ops/vultr/KALSHI_VPS_ATTACH_TEMPLATE.md`

## 2026-04-08 - Vultr + Vercel Remote Ops Hardening
- Added runtime manual control file gate (`data/control/runtime_control.json`) read by `core/engine.py` each loop
- Added failsafe latch behavior in engine to prevent remote re-enable after max-daily-loss breach
- Expanded `src/dashboard.py` with secure control endpoints: `/health`, `/snapshot`, `/control/status|start|stop`
- Added `CONTROL_API_TOKEN`, `DASHBOARD_HOST`, and `DASHBOARD_PORT` support in runtime config handling
- Aligned `.env.example` risk defaults with immutable strategy constraints (`0.50%`, `3/day`, `1.0%` daily loss)
- Added Vultr deployment bundle under `ops/vultr/` (bootstrap script, systemd units, nginx template, checklist, runbook)
- Added minimal Vercel proxy dashboard project under `ops/vercel-dashboard/` for remote monitoring and control

## 2026-04-08 - Live Deployment Execution
- Deployed current runtime to Vultr VPS `45.76.2.84` via automated SFTP + remote bootstrap flow
- Verified services active: `cryptosquid-engine` and `cryptosquid-dashboard`
- Verified health, snapshot, and authenticated control endpoints locally and externally
- Enabled and verified host security controls: UFW + fail2ban + unattended-upgrades
- Deployed Vercel proxy dashboard and verified remote start/stop actions through Vercel API routes
- Fixed VPS dependency compatibility by pinning `numpy==2.2.6` for Ubuntu 22.04 Python 3.10 runtime

## 2026-04-04 - VPS Runtime Attach Layer
- Added modular runtime orchestration under `core/` with `Engine`, `StrategyManager`, `ExecutionRouter`, and Supabase control polling
- Added strategy adapter `strategies/coinbase_v2_strategy.py` that runs existing v2 logic without strategy rule changes
- Added one-command entrypoint `scripts/run_all.py` for VPS process management
- Added Supabase SQL bootstrap `ops/supabase/strategy_control.sql` for remote enable/mode/max-position control
- Added NOAA integration client scaffold at `integrations/noaa_client.py`
- Added repository `README.md` for local run, paper/live switching, stop procedure, and architecture overview
- Updated `.env.example` and `requirements.txt` for Supabase and VPS control dependencies

## 2026-04-01 - Local Monitoring Dashboard
- Added localhost dashboard server at `src/dashboard.py` with `GET /api/state`
- Added real-time frontend at `src/dashboard.html` for P/L, position, symbol metrics, and charts
- Added runtime state writer at `src/runtime_store.py` and wired bot loop to publish live telemetry
- Expanded `PaperEngine` trade records with symbol, entry/exit, size, pnl%, and duration
- Updated `QUICKSTART.md` with dashboard run steps and paper vs live-enabled verification checks

## 2026-04-01 - Paper Test Harness
- Added timed validation harness at `src/paper_test_harness.py`
- Added strict pass/fail gates for minimum trades, data health errors, and drawdown guard
- Added report export to `reports/daily/` as both JSON and Markdown with `ready_for_live_execution_code`

## 2026-04-01 - Coinbase Candle Backtester
- Added historical backtester at `src/backtest_coinbase.py` using Coinbase public candles API
- Added organized run outputs under `backtests/runs/<timestamp>/` (summary, trades, equity, candles)
- Added readiness gates for minimum trades and drawdown in backtest reports

## 2026-04-01 - Metrics and Research Organization
- Updated drawdown gates to use true equity max drawdown in backtests and paper harness
- Added expectancy and profit factor tracking in runtime state and dashboard KPIs
- Added optional leverage-factor reporting in harness and backtest outputs (tracking only)
- Added organized research folders and templates in `strategy/variations/` and `strategy/new-strategies/`

## 2026-04-01 - Trade Memory + Obsidian Sync
- Added persistent paper-trade writes on every close event (TP/SL/TIME_STOP)
- Added organized local history outputs: SQLite records, per-trade journal files, and daily reports
- Added optional Obsidian mirror (`OBSIDIAN_VAULT_PATH`) for centralized memory
- Added auto-generated vault index at `08_Trading/CryptoSquid/index.md`
- Added weekly reports + lessons + learning snapshot sync to local `memory/` and Obsidian
- Added `src/learn.py` CLI to pull insights from trade data for self-improvement

## 2026-03-30 - Hyperliquid MVP Conversion
- Replaced Binance-only architecture with Hyperliquid-only architecture
- Implemented new signal engine: sharp drop + volume spike + z-score + stabilization
- Implemented explicit modes: log-only, paper, live-ready
- Added stop-aware risk engine with daily guards and loss limits
- Rebuilt execution lifecycle with limit-entry timeout, TP/SL, and time-stop
- Expanded SQLite logging to include both signal decisions and trade records
- Updated docs and strategy files for new Hyperliquid MVP specification

## 2026-03-28 — Phase 0 + Phase 1 Complete
- Built full framework: CLAUDE.md, PRD, EDD, IMPLEMENTATION_PLAN, STATE
- Built strategy docs: core-rules, tunable-params, hypotheses, regime-definitions
- Built MVP bot: config, detector, executor, logger, bot (main)
- Built slash commands: /review-trade, /weekly-review, /propose-experiments
- Built journal template and memory system
- Fixed: end-of-month bug in daily report scheduler
- Fixed: asyncio.get_running_loop() instead of deprecated get_event_loop()
- Removed: unused python-binance dependency
