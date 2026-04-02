"""Persistent trade history + optional Obsidian vault mirror."""

from __future__ import annotations

import os
import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


class TradeHistoryStore:
    def __init__(self, root: Path):
        self._db_path = root / "data" / "trades" / "trades.db"
        self._journal_path = root / "journal" / "raw-trades"
        self._reports_path = root / "reports" / "daily"
        self._weekly_reports_path = root / "reports" / "weekly"
        self._memory_path = root / "memory"
        self._vault_path = _resolve_vault_path()
        self._vault_root = None
        if self._vault_path:
            self._vault_root = self._vault_path / "08_Trading" / "CryptoSquid"

        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._journal_path.mkdir(parents=True, exist_ok=True)
        self._reports_path.mkdir(parents=True, exist_ok=True)
        self._weekly_reports_path.mkdir(parents=True, exist_ok=True)
        self._memory_path.mkdir(parents=True, exist_ok=True)
        if self._vault_root:
            self._vault_root.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def sync_existing(self) -> None:
        with self._conn() as conn:
            days = conn.execute(
                "SELECT DISTINCT date(ts_exit) FROM trades WHERE ts_exit IS NOT NULL ORDER BY 1"
            ).fetchall()
        today_week = _iso_week_label(datetime.now(timezone.utc).date().isoformat())
        weeks = {today_week}
        for (day,) in days:
            if not day:
                continue
            weeks.add(_iso_week_label(day))
            (self._reports_path / f"{day}.md").write_text(self._daily_report_md(day), encoding="utf-8")
            if self._vault_root:
                reports_dir = self._vault_root / "reports" / "daily"
                reports_dir.mkdir(parents=True, exist_ok=True)
                (reports_dir / f"{day}.md").write_text(self._daily_report_md(day), encoding="utf-8")
        for week in sorted(weeks):
            self._write_weekly_report(week)
        self._write_lessons()
        self._write_learning_snapshot()
        if self._vault_root:
            (self._vault_root / "index.md").write_text(self._index_md(), encoding="utf-8")

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path))

    def _init_db(self) -> None:
        with self._conn() as conn:
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

    def write_trade(self, trade: dict, strategy_version: str = "coinbase-paper-v1") -> None:
        hold_seconds = int(round(trade.get("duration_seconds", 0.0)))
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
                    trade.get("trade_id"),
                    trade.get("ts_entry"),
                    trade.get("ts_exit"),
                    trade.get("symbol"),
                    trade.get("entry"),
                    trade.get("stop"),
                    trade.get("tp"),
                    trade.get("size"),
                    trade.get("risk_usd"),
                    trade.get("exit"),
                    trade.get("pnl"),
                    hold_seconds,
                    trade.get("reason"),
                    "paper",
                    strategy_version,
                    trade.get("status", "CLOSED"),
                    self._build_note(trade),
                ),
            )

        self._write_local_trade_note(trade, hold_seconds)
        self._write_local_daily_report(trade)
        self._write_weekly_report(_iso_week_label(_day_from_iso(trade.get("ts_exit"))))
        self._write_lessons()
        self._write_learning_snapshot()
        self._write_vault_files(trade, hold_seconds)

    def _build_note(self, trade: dict) -> str:
        drop = trade.get("drop_pct")
        zscore = trade.get("zscore")
        return f"drop={drop:+.3f}%, z={zscore:+.2f}" if drop is not None and zscore is not None else ""

    def _write_local_trade_note(self, trade: dict, hold_seconds: int) -> None:
        day = _day_from_iso(trade.get("ts_exit"))
        path = self._journal_path / f"{day}-{trade.get('trade_id')}.md"
        content = _trade_markdown(trade, hold_seconds, title_prefix="# Trade Review")
        path.write_text(content, encoding="utf-8")

    def _write_local_daily_report(self, trade: dict) -> None:
        day = _day_from_iso(trade.get("ts_exit"))
        report_path = self._reports_path / f"{day}.md"
        report_path.write_text(self._daily_report_md(day), encoding="utf-8")

    def _write_vault_files(self, trade: dict, hold_seconds: int) -> None:
        if not self._vault_root:
            return

        day = _day_from_iso(trade.get("ts_exit"))
        year = day[:4]
        month = day[:7]
        trade_dir = self._vault_root / "trades" / year / month
        reports_dir = self._vault_root / "reports" / "daily"
        trade_dir.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)

        trade_path = trade_dir / f"{day}-{trade.get('trade_id')}.md"
        trade_path.write_text(_trade_markdown(trade, hold_seconds, title_prefix="# Crypto Squid Trade"), encoding="utf-8")

        daily_report = reports_dir / f"{day}.md"
        daily_report.write_text(self._daily_report_md(day), encoding="utf-8")

        index_path = self._vault_root / "index.md"
        index_path.write_text(self._index_md(), encoding="utf-8")

    def _write_weekly_report(self, week_label: str) -> None:
        content = self._weekly_report_md(week_label)
        (self._weekly_reports_path / f"{week_label}.md").write_text(content, encoding="utf-8")
        if self._vault_root:
            weekly_dir = self._vault_root / "reports" / "weekly"
            weekly_dir.mkdir(parents=True, exist_ok=True)
            (weekly_dir / f"{week_label}.md").write_text(content, encoding="utf-8")

    def _write_lessons(self) -> None:
        content = self._lessons_md()
        (self._memory_path / "lessons.md").write_text(content, encoding="utf-8")
        if self._vault_root:
            imp_dir = self._vault_root / "self-improvement"
            imp_dir.mkdir(parents=True, exist_ok=True)
            (imp_dir / "lessons.md").write_text(content, encoding="utf-8")

    def _write_learning_snapshot(self) -> None:
        payload = self._learning_snapshot()
        path = self._memory_path / "learning_snapshot.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if self._vault_root:
            imp_dir = self._vault_root / "self-improvement"
            imp_dir.mkdir(parents=True, exist_ok=True)
            (imp_dir / "learning_snapshot.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _daily_report_md(self, day: str) -> str:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT trade_id, ts_exit, symbol, pnl_usd, exit_reason, hold_seconds
                FROM trades
                WHERE date(ts_exit) = ?
                ORDER BY ts_exit ASC
                """,
                (day,),
            ).fetchall()

        wins = sum(1 for _, _, _, pnl, _, _ in rows if (pnl or 0.0) > 0)
        pnl_total = sum((pnl or 0.0) for _, _, _, pnl, _, _ in rows)
        lines = [
            f"# Daily Trade Report - {day}",
            "",
            f"- Trades: {len(rows)}",
            f"- Wins: {wins}",
            f"- Losses: {len(rows) - wins}",
            f"- Net PnL: {pnl_total:+.2f} USD",
            "",
            "| Time (UTC) | Trade ID | Symbol | Exit | Hold (s) | PnL USD |",
            "|------------|----------|--------|------|----------|---------|",
        ]
        for trade_id, ts_exit, symbol, pnl, reason, hold_seconds in rows:
            time_text = _time_from_iso(ts_exit)
            pnl_text = f"{(pnl or 0.0):+.2f}"
            lines.append(
                f"| {time_text} | {trade_id} | {symbol} | {reason or '-'} | {hold_seconds or 0} | {pnl_text} |"
            )
        return "\n".join(lines) + "\n"

    def _index_md(self) -> str:
        with self._conn() as conn:
            total, pnl_sum = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(pnl_usd), 0.0) FROM trades"
            ).fetchone()
            recent = conn.execute(
                """
                SELECT ts_exit, trade_id, symbol, pnl_usd, exit_reason
                FROM trades
                ORDER BY ts_exit DESC
                LIMIT 15
                """
            ).fetchall()

        wins = sum(1 for _, _, _, pnl, _ in recent if (pnl or 0.0) > 0)
        lines = [
            "# Crypto Squid Trade Memory",
            "",
            f"- Last sync: {datetime.now(timezone.utc).isoformat()}",
            f"- Total closed trades: {total}",
            f"- Net PnL: {pnl_sum:+.2f} USD",
            f"- Recent win rate (last {len(recent)}): {(wins / len(recent) * 100.0):.1f}%" if recent else "- Recent win rate: 0.0%",
            "",
            "## Recent Trades",
            "| Exit (UTC) | Trade ID | Symbol | Reason | PnL USD |",
            "|------------|----------|--------|--------|---------|",
        ]
        for ts_exit, trade_id, symbol, pnl, reason in recent:
            lines.append(
                f"| {ts_exit or '-'} | {trade_id} | {symbol} | {reason or '-'} | {(pnl or 0.0):+.2f} |"
            )
        return "\n".join(lines) + "\n"

    def _weekly_report_md(self, week_label: str) -> str:
        start_day, end_day = _week_bounds(week_label)
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT ts_exit, symbol, pnl_usd, exit_reason, hold_seconds, notes
                FROM trades
                WHERE date(ts_exit) >= ? AND date(ts_exit) <= ?
                ORDER BY ts_exit ASC
                """,
                (start_day, end_day),
            ).fetchall()

        total = len(rows)
        wins = sum(1 for _, _, pnl, _, _, _ in rows if (pnl or 0.0) > 0)
        losses = sum(1 for _, _, pnl, _, _, _ in rows if (pnl or 0.0) < 0)
        pnl_total = sum((pnl or 0.0) for _, _, pnl, _, _, _ in rows)
        avg_hold = (sum((hold or 0) for _, _, _, _, hold, _ in rows) / total) if total else 0.0

        by_reason = {}
        by_symbol = {}
        for _, symbol, pnl, reason, _, _ in rows:
            key = reason or "UNKNOWN"
            by_reason[key] = by_reason.get(key, 0) + 1
            bucket = by_symbol.setdefault(symbol, {"count": 0, "pnl": 0.0})
            bucket["count"] += 1
            bucket["pnl"] += pnl or 0.0

        verdict = "STABLE"
        if total >= 15 and (wins / total) < 0.5:
            verdict = "INVESTIGATE"
        if total >= 15 and pnl_total < 0:
            verdict = "PAUSE"

        top_reason = sorted(by_reason.items(), key=lambda item: item[1], reverse=True)[0][0] if by_reason else "N/A"
        top_symbol = (
            sorted(by_symbol.items(), key=lambda item: item[1]["count"], reverse=True)[0][0] if by_symbol else "N/A"
        )
        lines = [
            f"# Weekly Report - {week_label}",
            "",
            f"- Window: {start_day} to {end_day}",
            f"- Trades: {total}",
            f"- Wins: {wins}",
            f"- Losses: {losses}",
            f"- Win rate: {(wins / total * 100.0):.1f}%" if total else "- Win rate: 0.0%",
            f"- Net PnL: {pnl_total:+.2f} USD",
            f"- Avg hold: {avg_hold:.1f} sec",
            f"- Verdict: {verdict}",
            "",
            "## Pattern Findings",
            f"- Most common exit reason: {top_reason}",
            f"- Most active symbol: {top_symbol}",
            "",
            "## Symbol Breakdown",
            "| Symbol | Trades | Net PnL USD |",
            "|--------|--------|-------------|",
        ]
        for symbol, data in sorted(by_symbol.items()):
            lines.append(f"| {symbol} | {data['count']} | {data['pnl']:+.2f} |")
        return "\n".join(lines) + "\n"

    def _lessons_md(self) -> str:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT ts_exit, symbol, pnl_usd, exit_reason, notes
                FROM trades
                ORDER BY ts_exit DESC
                LIMIT 60
                """
            ).fetchall()

        total = len(rows)
        wins = sum(1 for _, _, pnl, _, _ in rows if (pnl or 0.0) > 0)
        losses = sum(1 for _, _, pnl, _, _ in rows if (pnl or 0.0) < 0)
        loss_by_reason = {}
        for _, _, pnl, reason, _ in rows:
            if (pnl or 0.0) < 0:
                key = reason or "UNKNOWN"
                loss_by_reason[key] = loss_by_reason.get(key, 0) + 1

        primary_loss_reason = (
            sorted(loss_by_reason.items(), key=lambda item: item[1], reverse=True)[0][0]
            if loss_by_reason
            else "N/A"
        )
        lines = [
            "# Crypto Squid Lessons",
            "",
            f"- Last update: {datetime.now(timezone.utc).isoformat()}",
            f"- Sample size (most recent trades): {total}",
            f"- Wins: {wins}",
            f"- Losses: {losses}",
            f"- Main loss reason: {primary_loss_reason}",
            "",
            "## Lessons",
            f"- Protect downside first: frequent loss mode is `{primary_loss_reason}`.",
            "- Keep one-parameter experiments only; avoid stacked changes.",
            "- Review weekly report before tuning any threshold.",
            "",
            "## Latest Trade Outcomes",
            "| Exit (UTC) | Symbol | Reason | PnL USD | Notes |",
            "|------------|--------|--------|---------|-------|",
        ]
        for ts_exit, symbol, pnl, reason, notes in rows[:20]:
            note_text = (notes or "").replace("|", "/")[:48]
            lines.append(f"| {ts_exit or '-'} | {symbol} | {reason or '-'} | {(pnl or 0.0):+.2f} | {note_text} |")
        return "\n".join(lines) + "\n"

    def _learning_snapshot(self) -> dict:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT ts_exit, symbol, pnl_usd, exit_reason, hold_seconds, notes
                FROM trades
                ORDER BY ts_exit DESC
                LIMIT 300
                """
            ).fetchall()

        wins = [row for row in rows if (row[2] or 0.0) > 0]
        losses = [row for row in rows if (row[2] or 0.0) < 0]
        by_reason = {}
        for _, _, _, reason, _, _ in rows:
            key = reason or "UNKNOWN"
            by_reason[key] = by_reason.get(key, 0) + 1

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sample_size": len(rows),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate_pct": (len(wins) / len(rows) * 100.0) if rows else 0.0,
            "avg_win_usd": (sum((r[2] or 0.0) for r in wins) / len(wins)) if wins else 0.0,
            "avg_loss_usd": (sum((r[2] or 0.0) for r in losses) / len(losses)) if losses else 0.0,
            "exit_reason_counts": by_reason,
            "recent_trades": [
                {
                    "ts_exit": ts_exit,
                    "symbol": symbol,
                    "pnl_usd": pnl,
                    "exit_reason": reason,
                    "hold_seconds": hold_seconds,
                    "notes": notes,
                }
                for ts_exit, symbol, pnl, reason, hold_seconds, notes in rows[:50]
            ],
        }


def _resolve_vault_path() -> Path | None:
    raw = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    candidates = [raw] if raw else []
    candidates.append("C:/Users/tnola/OneDrive/Documents/Obsidian Vault")
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return path
    return None


def _day_from_iso(ts: str | None) -> str:
    if not ts:
        return datetime.now(timezone.utc).date().isoformat()
    return ts[:10]


def _time_from_iso(ts: str | None) -> str:
    if not ts:
        return "-"
    return ts[11:19] if len(ts) >= 19 else ts


def _trade_markdown(trade: dict, hold_seconds: int, title_prefix: str) -> str:
    pnl = trade.get("pnl", 0.0)
    drop = trade.get("drop_pct")
    zscore = trade.get("zscore")
    return "\n".join(
        [
            f"{title_prefix} - {trade.get('trade_id')}",
            "",
            "## Trade",
            f"- Symbol: {trade.get('symbol')}",
            f"- Entry time (UTC): {trade.get('ts_entry')}",
            f"- Exit time (UTC): {trade.get('ts_exit')}",
            f"- Entry: {trade.get('entry')}",
            f"- Exit: {trade.get('exit')}",
            f"- Stop: {trade.get('stop')}",
            f"- Target: {trade.get('tp')}",
            f"- Size: {trade.get('size')}",
            f"- Risk USD: {trade.get('risk_usd')}",
            f"- Hold seconds: {hold_seconds}",
            f"- Exit reason: {trade.get('reason')}",
            f"- PnL USD: {pnl:+.2f}",
            "",
            "## Signal Snapshot",
            f"- Drop %: {drop if drop is not None else '-'}",
            f"- Z-score: {zscore if zscore is not None else '-'}",
            "",
        ]
    )


def _iso_week_label(day_str: str) -> str:
    day = date.fromisoformat(day_str)
    iso_year, iso_week, _ = day.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _week_bounds(week_label: str) -> tuple[str, str]:
    year = int(week_label[:4])
    week = int(week_label[-2:])
    start = date.fromisocalendar(year, week, 1)
    end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()
