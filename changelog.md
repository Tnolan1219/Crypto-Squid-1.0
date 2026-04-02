# Changelog

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
