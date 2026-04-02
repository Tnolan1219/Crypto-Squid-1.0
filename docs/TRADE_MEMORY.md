# Trade Memory + Obsidian Sync

## Goal
Keep one accurate source of truth for every closed paper trade, then mirror it into Obsidian in a stable folder structure.

## Source of Truth
- SQLite: `data/trades/trades.db` (`trades` table)
- Every closed trade is written immediately after exit (TP, SL, TIME_STOP)

## Local Organized Outputs
- Per-trade notes: `journal/raw-trades/<YYYY-MM-DD>-<trade_id>.md`
- Daily report: `reports/daily/<YYYY-MM-DD>.md`
- Weekly report: `reports/weekly/<YYYY-WNN>.md`
- Lessons log: `memory/lessons.md`
- Learning snapshot JSON: `memory/learning_snapshot.json`
- Runtime snapshot: `data/trades/runtime_state.json`

## Obsidian Mirror (Optional)
Set `OBSIDIAN_VAULT_PATH` in `.env` to your Obsidian vault root directory.
If unset, the bot auto-tries `C:/Users/tnola/OneDrive/Documents/Obsidian Vault`.

Mirror target inside vault:
- `08_Trading/CryptoSquid/index.md`
- `08_Trading/CryptoSquid/trades/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>-<trade_id>.md`
- `08_Trading/CryptoSquid/reports/daily/<YYYY-MM-DD>.md`
- `08_Trading/CryptoSquid/reports/weekly/<YYYY-WNN>.md`
- `08_Trading/CryptoSquid/self-improvement/lessons.md`
- `08_Trading/CryptoSquid/self-improvement/learning_snapshot.json`

If the vault path is missing or invalid, bot continues normally with local files only.

## Pulling Insights for Self-Improvement
- Run `python src/learn.py` for latest 100-trade summary.
- Run `python src/learn.py --week YYYY-WNN` for week-specific analysis.
- Use weekly report + lessons file before proposing any parameter experiment.

## Accuracy Fields Captured Per Trade
- `trade_id`, `symbol`, `ts_entry`, `ts_exit`
- `entry_price`, `exit_price`, `stop_price`, `target_price`
- `size`, `risk_usd`, `pnl_usd`, `hold_seconds`
- `exit_reason`, `status`, `strategy_version`
- Entry snapshot metrics: `drop_pct`, `zscore` (stored in notes)
