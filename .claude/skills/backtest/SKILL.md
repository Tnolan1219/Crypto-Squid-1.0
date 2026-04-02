---
name: backtest
description: >
  Run a Crypto Squid historical backtest using Coinbase public candle data.
  Use this skill whenever the user asks to run a backtest, test the strategy
  over historical data, check how the strategy performed over a past period,
  replay candles, or validate parameters against real price history. Trigger
  even if they just say "run a backtest" or "how did we do last week" or
  "test over 7 days". Always ask the user how many days to backtest before
  running — never silently assume a default.
---

# Crypto Squid Backtest Skill

## What this skill does

Runs `src/backtest_coinbase.py` against real Coinbase historical candles, then
reads the generated report and displays all key metrics to the user.

The script fetches public candle data (no API auth required), replays the
v1 strategy logic (MarketTracker → check_entry → PaperEngine), and writes
output to `backtests/runs/<YYYYMMDD-HHMMSS>/`.

---

## Step 1 — Collect parameters

Always ask the user these questions before running. Never silently apply defaults.

**Required (always ask):**
- How many days back do you want to test? (e.g. 1, 3, 7, 14, 30)

**Optional — offer defaults, let user accept or override:**
- Symbols: default `BTC-USD,ETH-USD`
- Granularity: default `ONE_MINUTE`
  - Choices: `ONE_MINUTE`, `FIVE_MINUTE`, `FIFTEEN_MINUTE`, `THIRTY_MINUTE`, `ONE_HOUR`, `TWO_HOUR`, `SIX_HOUR`, `ONE_DAY`
  - Note: longer granularities = fewer signals but faster fetch. 7+ days at ONE_MINUTE can take 30–60 seconds to fetch.
- Starting balance: default `$1000`
- Leverage factor: default `1.0` (reporting multiplier only — does not change sizing)
- Gate thresholds:
  - Minimum trades to pass: default `20`
  - Max drawdown % to pass: default `2.0`

If the user says "use defaults" or "just run it" for the optional params, accept all defaults and only ask for the number of days.

Present a one-line summary of what you're about to run before executing:
```
Running backtest: 7 days | BTC-USD,ETH-USD | ONE_MINUTE | $1000 balance
```

---

## Step 2 — Build and run the command

Working directory: `C:/Users/tnola/Downloads/cryptosquid-1.0-indep`
Python: `.venv/Scripts/python.exe`

```bash
cd C:/Users/tnola/Downloads/cryptosquid-1.0-indep && \
  .venv/Scripts/python.exe src/backtest_coinbase.py \
  --days <DAYS> \
  --symbols "<SYMBOLS>" \
  --granularity <GRANULARITY> \
  --start-balance <BALANCE> \
  --leverage-factor <LEVERAGE> \
  --min-trades <MIN_TRADES> \
  --max-drawdown-pct <MAX_DD>
```

The script prints the output folder path on completion (`Output folder: ...`).
Capture that path — you'll need it in the next step.

If the script errors, show the full stderr to the user and stop.

---

## Step 3 — Read and display results

Once the run completes, find the output folder (from the script's stdout or by
globbing `backtests/runs/` for the newest directory). Then:

1. Read `<output_dir>/summary.md` and display its full contents.
2. Read `<output_dir>/summary.json` to extract structured stats for the table below.

Display results in this format:

```
=== BACKTEST RESULTS ===
Window:   <start_utc>  →  <end_utc>
Duration: <days> days  |  Granularity: <granularity>
Symbols:  <symbols>
Balance:  $<start>  →  $<ending_balance>

PERFORMANCE
  Closed trades:    <trades_closed>
  Wins / Losses:    <wins> / <losses>
  Win rate:         <win_rate_pct>%
  Realized P/L:     $<realized_pnl_usd>  (<realized_pnl_pct>%)
  Leveraged P/L:    $<leveraged_realized_pnl_usd>  (<leveraged_realized_pnl_pct>%)
  Expectancy (EV):  $<expectancy_usd_per_trade> / trade
  Profit factor:    <profit_factor>
  Max drawdown:     <max_drawdown_pct>%

GATES
  minimum_trades            <PASS/FAIL>  (actual: <trades_closed>, required: <min_trades>)
  drawdown_guard            <PASS/FAIL>  (actual: <max_drawdown_pct>%, max: <max_drawdown_pct_limit>%)
  ready_for_live_execution  <PASS/FAIL>

OUTPUT FILES
  Folder:     backtests/runs/<stamp>/
  summary.md  summary.json  trades.csv  equity.csv  candles-*.csv
```

Gates use PASS (green intent) or FAIL (red intent) — make them visually clear.

---

## Step 4 — Offer follow-up actions

After displaying results, offer:
- "Re-run with different parameters"
- "Run `/propose-experiments` to explore parameter changes based on these results"
- "Run `/weekly-review` if you have live trade data to compare against"

---

## Notes

- Fetch time scales with days × granularity. 7 days at ONE_MINUTE ≈ 10,080 candles per symbol. Warn the user if they pick >14 days at ONE_MINUTE — it will be slow.
- The backtest uses v1 strategy components (not v2 signal engine). Results reflect the v1 signal logic.
- Do not modify any strategy files or params during the backtest run.
- Do not commit backtest output folders to git — they're large and ephemeral.
