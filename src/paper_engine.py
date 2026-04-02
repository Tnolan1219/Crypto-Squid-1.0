"""Paper trading engine — simulates trade lifecycle with PnL tracking."""

import time
from datetime import datetime, timezone
from uuid import uuid4


class PaperEngine:
    def __init__(self, balance: float = 1000.0):
        self.balance = balance
        self.start_balance = balance
        self.position = None
        self.trades = []

    def enter(
        self,
        symbol: str,
        entry: float,
        size: float,
        stop: float,
        tp: float,
        drop_pct: float,
        zscore: float,
        opened_at_ts: float | None = None,
        opened_at_iso: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        opened_at = time.time() if opened_at_ts is None else float(opened_at_ts)
        opened_iso = opened_at_iso or now.isoformat()
        self.position = {
            "trade_id": f"paper-{now.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}",
            "symbol": symbol,
            "entry": entry,
            "size": size,
            "stop": stop,
            "tp": tp,
            "drop_pct": drop_pct,
            "zscore": zscore,
            "opened_at": opened_at,
            "opened_at_iso": opened_iso,
        }
        print(
            f"[ENTER] symbol={symbol} price={entry:.4f} size={size:.6f} stop={stop:.4f} tp={tp:.4f}"
        )

    def exit(self, price: float, reason: str, exit_ts: float | None = None, exit_iso: str | None = None) -> dict:
        if self.position is None:
            return {}

        entry = self.position["entry"]
        size = self.position["size"]
        pnl = (price - self.position["entry"]) * self.position["size"]
        self.balance += pnl
        print(f"[EXIT]  price={price:.4f}  reason={reason}  pnl={pnl:+.2f}  balance={self.balance:.2f}")
        closed_at = time.time() if exit_ts is None else float(exit_ts)
        duration_seconds = max(closed_at - self.position["opened_at"], 0.0)
        pnl_pct = ((price - entry) / entry * 100.0) if entry else 0.0
        exit_time = datetime.now(timezone.utc)
        ts_exit = exit_iso or exit_time.isoformat()
        risk_usd = abs(entry - self.position["stop"]) * size
        trade = {
            "trade_id": self.position["trade_id"],
            "symbol": self.position["symbol"],
            "ts_entry": self.position["opened_at_iso"],
            "ts_exit": ts_exit,
            "entry": entry,
            "exit": price,
            "size": size,
            "stop": self.position["stop"],
            "tp": self.position["tp"],
            "reason": reason,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "risk_usd": risk_usd,
            "status": "CLOSED",
            "drop_pct": self.position["drop_pct"],
            "zscore": self.position["zscore"],
            "duration_seconds": duration_seconds,
            "ts": ts_exit,
        }
        self.trades.append(trade)
        self.position = None
        return trade

    def position_age_minutes(self) -> float:
        if self.position is None:
            return 0.0
        return (time.time() - self.position["opened_at"]) / 60.0
