# Implementation Plan - Hyperliquid Conversion

## Phase A - Audit and map legacy components
- Identify Binance-only code paths and liquidation-feed assumptions
- Keep reusable modules: config pattern, logging shape, daily report workflow
- Replace incompatible modules: detector, execution, exchange integration

## Phase B - Core refactor
- `src/config.py`: new Hyperliquid strategy and mode config
- `src/hyperliquid_client.py`: market websocket + live sdk wrapper
- `src/detector.py`: new overreaction signal engine
- `src/risk.py`: risk constraints and stop-aware sizing
- `src/executor.py`: mode-specific execution state machine
- `src/logger.py`: signal + trade persistence
- `src/bot.py`: simplified orchestrator

## Phase C - Documentation migration
- Rewrite PRD and engineering design for Hyperliquid MVP
- Replace Quickstart with mode-safe runbook
- Update strategy parameter docs to new thresholds
- Update state/changelog to new phase and next validation tests

## Phase D - Validation checklist
- Compile source tree
- Run log-only for 30+ minutes and verify signal rejects/passes
- Run paper mode for several sessions to verify PnL and daily guards
- Run controlled live-ready smoke test with minimal size and strict monitoring
