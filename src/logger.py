"""Signal and trade persistence for review and iteration."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import structlog

from config import Config
from models import SignalDecision, TradeRecord

log = structlog.get_logger()


class TradeLogger:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.cfg.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.cfg.journal_path.mkdir(parents=True, exist_ok=True)
        self.cfg.reports_path.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.cfg.db_path))

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    price REAL NOT NULL,
                    drop_pct REAL NOT NULL,
                    volume_ratio REAL NOT NULL,
                    zscore REAL NOT NULL,
                    stabilization TEXT NOT NULL,
                    passed INTEGER NOT NULL,
                    reject_reason TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT UNIQUE NOT NULL,
                    ts_entry TEXT,
                    ts_exit TEXT,
                    symbol TEXT NOT NULL,
                    entry_price REAL,
                    stop_price REAL,
                    target_price REAL,
                    size REAL,
                    risk_usd REAL,
                    exit_price REAL,
                    pnl_usd REAL,
                    hold_seconds INTEGER,
                    exit_reason TEXT,
                    mode TEXT,
                    strategy_version TEXT,
                    status TEXT,
                    notes TEXT
                )
                """
            )

    def write_signal(self, signal: SignalDecision) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO signals (
                    ts, symbol, price, drop_pct, volume_ratio, zscore,
                    stabilization, passed, reject_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signal.ts.isoformat(),
                    signal.symbol,
                    signal.price,
                    signal.drop_pct,
                    signal.volume_ratio,
                    signal.zscore,
                    signal.stabilization,
                    1 if signal.passed else 0,
                    signal.reject_reason,
                ),
            )

    def write_trade(self, rec: TradeRecord) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO trades (
                    trade_id, ts_entry, ts_exit, symbol,
                    entry_price, stop_price, target_price, size, risk_usd,
                    exit_price, pnl_usd, hold_seconds, exit_reason,
                    mode, strategy_version, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec.trade_id,
                    _fmt_ts(rec.entry_time),
                    _fmt_ts(rec.exit_time),
                    rec.signal.symbol,
                    rec.entry_price,
                    rec.stop_price,
                    rec.target_price,
                    rec.size,
                    rec.risk_usd,
                    rec.exit_price,
                    rec.pnl_usd,
                    rec.hold_seconds,
                    rec.exit_reason,
                    rec.mode,
                    rec.strategy_version,
                    rec.status,
                    rec.notes,
                ),
            )
        self._write_journal_entry(rec)

    def write_daily_report(self, day: Optional[date] = None) -> None:
        day = day or date.today()
        day_str = day.isoformat()
        with self._conn() as conn:
            signal_rows = conn.execute(
                "SELECT passed FROM signals WHERE date(ts) = ?",
                (day_str,),
            ).fetchall()
            trade_rows = conn.execute(
                """
                SELECT status, pnl_usd, hold_seconds, symbol
                FROM trades
                WHERE date(ts_entry) = ?
                """,
                (day_str,),
            ).fetchall()

        if not signal_rows and not trade_rows:
            return

        signal_total = len(signal_rows)
        signal_pass = sum(1 for r in signal_rows if r[0] == 1)
        trade_total = len(trade_rows)
        wins = sum(1 for r in trade_rows if r[0] == "TP")
        losses = sum(1 for r in trade_rows if r[0] == "SL")
        pnl = sum((r[1] or 0.0) for r in trade_rows)

        lines = [
            f"# Daily Report - {day_str}",
            "",
            "## Signals",
            f"- Total: {signal_total}",
            f"- Passed: {signal_pass}",
            f"- Rejected: {signal_total - signal_pass}",
            "",
            "## Trades",
            f"- Total: {trade_total}",
            f"- Wins (TP): {wins}",
            f"- Losses (SL): {losses}",
            f"- PnL: {pnl:+.2f} USD",
            "",
            "## Trade List",
            "| # | Symbol | Status | PnL USD | Hold Sec |",
            "|---|--------|--------|---------|----------|",
        ]

        for i, (status, pnl_usd, hold_seconds, symbol) in enumerate(trade_rows, 1):
            pnl_text = f"{pnl_usd:+.2f}" if pnl_usd is not None else "-"
            hold_text = str(hold_seconds) if hold_seconds is not None else "-"
            lines.append(f"| {i} | {symbol} | {status} | {pnl_text} | {hold_text} |")

        report_path = self.cfg.reports_path / f"{day_str}.md"
        report_path.write_text("\n".join(lines), encoding="utf-8")

    def _write_journal_entry(self, rec: TradeRecord) -> None:
        sig = rec.signal
        day = sig.ts.strftime("%Y-%m-%d")
        suffix = rec.trade_id.split("-")[-1]
        path = self.cfg.journal_path / f"{day}-{sig.symbol}-{suffix}.md"
        content = f"""# Trade Review - {sig.symbol} - {sig.ts.strftime("%Y-%m-%d %H:%M UTC")}

## Signal
- Drop %: {sig.drop_pct:.3f}
- Volume ratio: {sig.volume_ratio:.3f}
- Z-score: {sig.zscore:.3f}
- Stabilization: {sig.stabilization}

## Execution
- Mode: {rec.mode}
- Entry time: {_fmt_ts(rec.entry_time) or "-"}
- Entry: {rec.entry_price or "-"}
- Stop: {rec.stop_price or "-"}
- Target: {rec.target_price or "-"}
- Size: {rec.size or "-"}

## Exit
- Exit time: {_fmt_ts(rec.exit_time) or "-"}
- Exit price: {rec.exit_price or "-"}
- Status: {rec.status}
- Reason: {rec.exit_reason or rec.notes or "-"}
- PnL: {f"{rec.pnl_usd:+.2f} USD" if rec.pnl_usd is not None else "-"}
- Hold seconds: {rec.hold_seconds if rec.hold_seconds is not None else "-"}
- Strategy version: {rec.strategy_version}
"""
        path.write_text(content, encoding="utf-8")


def _fmt_ts(ts: Optional[datetime]) -> Optional[str]:
    if ts is None:
        return None
    return ts.isoformat()
