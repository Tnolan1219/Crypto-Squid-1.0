# Crypto Squid - Hyperliquid MVP Quick Start

## 1) Setup

```bash
cp .env.example .env  # Windows PowerShell: copy .env.example .env
pip install -r requirements.txt
```

Edit `.env` and set at minimum:
- `ACCOUNT_CAPITAL_USD`
- `COINBASE_API_KEY_NAME`
- `COINBASE_PRIVATE_KEY`
- `LOG_ONLY=true` for first run
- `SYMBOLS=BTC,ETH`

## 2) Run modes

### Log-only (recommended first)
```bash
python src/bot_v2.py
```

### Local dashboard (run in a second terminal)
```bash
python src/dashboard.py
```

Open `http://127.0.0.1:8787`.
The dashboard reads `data/trades/runtime_state.json` written by `src/bot.py`.

### Strict paper test harness (timed + pass/fail gates)
```bash
python src/paper_test_harness.py --minutes 30 --interval 2 --min-trades 1 --max-errors 0 --max-drawdown-pct 2.0
```

Optional leverage tracking in reports (reporting only):
```bash
python src/paper_test_harness.py --minutes 30 --leverage-factor 2.0
```

Harness outputs:
- JSON report: `reports/daily/paper-test-<timestamp>.json`
- Markdown report: `reports/daily/paper-test-<timestamp>.md`

Readiness gate in report:
- `ready_for_live_execution_code: PASS/FAIL`

### Historical backtest on Coinbase candles
```bash
python src/backtest_coinbase.py --days 7 --granularity ONE_MINUTE --start-balance 1000 --min-trades 20 --max-drawdown-pct 2.0
```

Optional leverage tracking in reports (reporting only):
```bash
python src/backtest_coinbase.py --days 7 --granularity ONE_MINUTE --leverage-factor 2.0
```

Backtest output is organized in:
- `backtests/runs/<timestamp>/summary.json`
- `backtests/runs/<timestamp>/summary.md`
- `backtests/runs/<timestamp>/trades.csv`
- `backtests/runs/<timestamp>/equity.csv`
- `backtests/runs/<timestamp>/candles-<symbol>.csv`

### Paper mode
```bash
# .env
LOG_ONLY=false
PAPER_MODE=true
ENABLE_LIVE_TRADING=false
python src/bot.py
```

Dashboard checks for paper mode:
- `Mode: Paper Mode` tag shown
- `enable_live_trading=false` in API payload (`/api/state`)
- Trades appear in the table with simulated P/L

### Live-ready mode (explicit opt-in)
```bash
# .env
LOG_ONLY=false
PAPER_MODE=false
ENABLE_LIVE_TRADING=true
HYPERLIQUID_SECRET_KEY=<private_key>
HYPERLIQUID_ACCOUNT_ADDRESS=<wallet_or_vault_address>
python src/bot.py
```

Dashboard checks for live-enabled mode:
- `Mode: Live Enabled` tag shown
- `enable_live_trading=true` in `/api/state`
- Verify `TRADING_ENABLED=true` only while supervised

Note: the current Coinbase loop executes paper trades only. The dashboard reports mode flags from `.env` so you can confirm whether you are in paper/log-only/live-enabled configuration.

## 3) Expected outputs
- Structured logs in terminal and `logs/bot.log`
- Trade history in `data/trades/trades.db`
- Trade journal files in `journal/raw-trades/`
- Daily markdown report in `reports/daily/`
- Runtime dashboard state in `data/trades/runtime_state.json`

### Optional: Obsidian memory mirror
Set `OBSIDIAN_VAULT_PATH` in `.env` to your vault root.
If you leave it empty, the bot auto-tries `C:/Users/tnola/OneDrive/Documents/Obsidian Vault`.

When enabled, each closed trade is mirrored to:
- `08_Trading/CryptoSquid/trades/YYYY/YYYY-MM/`
- `08_Trading/CryptoSquid/reports/daily/`
- `08_Trading/CryptoSquid/reports/weekly/`
- `08_Trading/CryptoSquid/self-improvement/lessons.md`
- `08_Trading/CryptoSquid/self-improvement/learning_snapshot.json`
- `08_Trading/CryptoSquid/index.md`

Pull learning insights anytime:
```bash
python src/learn.py
python src/learn.py --week 2026-W14
```

## 4) Safety checks before live
- Confirm at least 20 paper trades reviewed
- Confirm no rule violations in logged signals/trades
- Keep `TRADING_ENABLED=true` only while supervised
- Use account with strictly limited capital during MVP
