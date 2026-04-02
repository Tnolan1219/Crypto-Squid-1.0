# Local Paper Session Runtime Skill

## Purpose
Run Crypto Squid paper sessions locally with repeatable startup, safety checks, a live local dashboard, and end-of-session reporting written to disk.

## Use When
- User asks to start a paper test or paper trading session
- User asks for live local dashboard visibility during runtime
- User asks for key run metrics when session ends

## Do Not
- Do not enable live trading automatically
- Do not change strategy logic while starting runtime
- Do not skip safety checks before startup

## Required Safety Checks (before every run)
1. Confirm `.env` keeps paper-safe mode:
   - `ENABLE_LIVE_TRADING=false`
   - `PAPER_MODE=true`
   - `TRADING_ENABLED=true` only if user wants entries active
2. Confirm no duplicate bot/dashboard processes are left running (`tasklist` / `ps aux`).
3. Confirm output dirs are writable: `data/trades/`, `data/events/`, `reports/daily/`, `logs/`.

## Startup Workflow
1. Kill any stale processes running `src/bot_v2.py` or `src/dashboard.py`.
2. Ensure directories exist: `data/trades`, `data/events`, `reports/daily`, `logs`.
3. Start bot in background, logging to `logs/bot_v2.out.log` and `logs/bot_v2.err.log`.
4. Start dashboard in background, logging to `logs/dashboard.out.log` and `logs/dashboard.err.log`.
5. Wait ~4 seconds, then verify dashboard responds at `http://127.0.0.1:8787/api/state`.
6. Fetch initial state and display to user.

## Commands
```bash
# Start bot
nohup .venv/Scripts/python.exe src/bot_v2.py > logs/bot_v2.out.log 2> logs/bot_v2.err.log &

# Start dashboard
nohup .venv/Scripts/python.exe src/dashboard.py > logs/dashboard.out.log 2> logs/dashboard.err.log &

# Verify dashboard
curl -s http://127.0.0.1:8787/api/state
```

## Live Update Requirements
Always provide after startup:
- Dashboard link: `http://127.0.0.1:8787/`
- API state link: `http://127.0.0.1:8787/api/state`
- Bot PID and dashboard PID
- Current symbol/price/signal state from `/api/state`
- Event count and trade count

Poll `/api/state` to show live updates when user asks to inspect the session.

## End-of-Session Reporting
When bot is stopped (Ctrl+C / KeyboardInterrupt), `bot_v2.py` automatically writes:
- `reports/daily/session-<YYYYMMDD-HHMMSS>.json` — full summary with all stats + trade list
- `reports/daily/session-<YYYYMMDD-HHMMSS>.md` — human-readable report

Report always contains:
- `started_at`, `ended_at`, `elapsed_minutes`
- `mode` (paper/live flags)
- `event_count`
- **stats**: `trades_closed`, `wins`, `losses`, `win_rate_pct`, `realized_pnl_usd`, `realized_pnl_pct`, `expectancy_usd_per_trade` (EV), `profit_factor`, `max_drawdown_pct`, `starting_balance`, `ending_balance`
- Full `trades` array

After session ends, Claude should:
1. Read the generated `.md` report and display the stats table to the user.
2. Note location of JSON file for programmatic use.

## Success Criteria
- Bot and dashboard processes healthy, PIDs confirmed
- `http://127.0.0.1:8787/` reachable and returning live data
- `data/trades/runtime_state.json` updating every ~250ms
- Session report written to `reports/daily/` on exit with all required metrics
