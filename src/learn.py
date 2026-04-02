"""Pull structured learning insights from trade history data."""

from __future__ import annotations

import argparse
import sqlite3
from datetime import date, timedelta
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull learning insights from trades DB")
    parser.add_argument("--week", help="ISO week label (YYYY-WNN)")
    args = parser.parse_args()

    db = Path(__file__).parent.parent / "data" / "trades" / "trades.db"
    if not db.exists():
        print("No database found yet at data/trades/trades.db")
        return

    with sqlite3.connect(str(db)) as conn:
        if args.week:
            year = int(args.week[:4])
            week = int(args.week[-2:])
            start = date.fromisocalendar(year, week, 1)
            end = start + timedelta(days=6)
            rows = conn.execute(
                """
                SELECT ts_exit, symbol, pnl_usd, exit_reason, notes
                FROM trades
                WHERE date(ts_exit) >= ? AND date(ts_exit) <= ?
                ORDER BY ts_exit DESC
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT ts_exit, symbol, pnl_usd, exit_reason, notes
                FROM trades
                ORDER BY ts_exit DESC
                LIMIT 100
                """
            ).fetchall()

    total = len(rows)
    wins = sum(1 for _, _, pnl, _, _ in rows if (pnl or 0.0) > 0)
    losses = sum(1 for _, _, pnl, _, _ in rows if (pnl or 0.0) < 0)
    pnl_total = sum((pnl or 0.0) for _, _, pnl, _, _ in rows)
    by_reason = {}
    for _, _, _, reason, _ in rows:
        key = reason or "UNKNOWN"
        by_reason[key] = by_reason.get(key, 0) + 1

    print(f"Trades: {total}")
    print(f"Wins: {wins}  Losses: {losses}")
    print(f"Win rate: {(wins / total * 100.0):.1f}%" if total else "Win rate: 0.0%")
    print(f"Net PnL: {pnl_total:+.2f} USD")
    print("Exit reasons:")
    for reason, count in sorted(by_reason.items(), key=lambda item: item[1], reverse=True):
        print(f"- {reason}: {count}")


if __name__ == "__main__":
    main()
