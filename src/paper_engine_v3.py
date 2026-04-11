"""
Paper trading engine v3 with staged exits and trailing stop after TP1.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4


class PaperEngineV3:
    def __init__(self, balance: float = 1000.0):
        self.balance = balance
        self.start_balance = balance
        self.positions: dict[str, dict] = {}
        self.trades: list[dict] = []

    @property
    def position(self) -> Optional[dict]:
        if not self.positions:
            return None
        return next(iter(self.positions.values()))

    def has_open_position(self, symbol: str) -> bool:
        return symbol in self.positions

    def enter(
        self,
        symbol: str,
        entry: float,
        size: float,
        stop: float,
        tp1: float,
        tp1_size_frac: float,
        tp2: float,
        time_stop_minutes: float,
        fast_reduce_minutes: float,
        trailing_stop_pct: float,
    ) -> None:
        if symbol in self.positions:
            return
        size1 = round(size * tp1_size_frac, 8)
        size2 = round(size - size1, 8)
        self.positions[symbol] = {
            "trade_id": f"paper-v3-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}",
            "symbol": symbol,
            "entry": entry,
            "size_total": size,
            "size1": size1,
            "size2": size2,
            "stop": stop,
            "stop_original": stop,
            "tp1": tp1,
            "tp2": tp2,
            "tp1_hit": False,
            "opened_at": time.time(),
            "opened_at_iso": datetime.now(timezone.utc).isoformat(),
            "leg_index": 0,
            "time_stop_minutes": time_stop_minutes,
            "fast_reduce_minutes": fast_reduce_minutes,
            "trailing_stop_pct": trailing_stop_pct,
            "peak_after_tp1": entry,
        }

    def on_price(self, symbol: str, price: float) -> list[dict]:
        pos = self.positions.get(symbol)
        if pos is None:
            return []
        age_minutes = (time.time() - pos["opened_at"]) / 60.0
        closed: list[dict] = []

        if not pos["tp1_hit"] and price >= pos["tp1"]:
            closed.append(self._partial_exit(pos, pos["tp1"], pos["size1"], "TP1"))
            pos["tp1_hit"] = True
            pos["peak_after_tp1"] = max(price, pos["entry"])
            pos["stop"] = max(pos["stop"], pos["entry"] * 1.0002)
            if pos["size2"] <= 0:
                self.positions.pop(symbol, None)
                return closed

        if symbol not in self.positions:
            return closed

        if pos["tp1_hit"]:
            pos["peak_after_tp1"] = max(pos.get("peak_after_tp1", pos["entry"]), price)
            trail = pos["peak_after_tp1"] * (1 - float(pos.get("trailing_stop_pct", 0.0)) / 100.0)
            pos["stop"] = max(pos["stop"], trail)

        if price <= pos["stop"]:
            remaining_size = pos["size2"] if pos["tp1_hit"] else pos["size_total"]
            reason = "SL_TRAIL" if pos["tp1_hit"] else "SL"
            closed.append(self._full_exit(pos, pos["stop"], remaining_size, reason))
            self.positions.pop(symbol, None)
            return closed

        if pos["tp1_hit"] and price >= pos["tp2"]:
            closed.append(self._full_exit(pos, pos["tp2"], pos["size2"], "TP2"))
            self.positions.pop(symbol, None)
            return closed

        if age_minutes >= pos["time_stop_minutes"]:
            remaining_size = pos["size2"] if pos["tp1_hit"] else pos["size_total"]
            closed.append(self._full_exit(pos, price, remaining_size, "TIME_STOP"))
            self.positions.pop(symbol, None)
            return closed

        if (not pos["tp1_hit"]) and age_minutes >= pos["fast_reduce_minutes"]:
            unrealized_pct = (price - pos["entry"]) / pos["entry"] * 100.0
            if -0.10 <= unrealized_pct <= 0.20:
                half = round(pos["size_total"] * 0.50, 8)
                if half > 0:
                    closed.append(self._partial_exit(pos, price, half, "FAST_REDUCE"))
                    pos["size1"] = 0
                    pos["size2"] = round(pos["size_total"] - half, 8)
                    pos["tp1_hit"] = True
                    pos["peak_after_tp1"] = price
                    pos["stop"] = max(pos["stop"], pos["entry"] * 1.0002)

        return closed

    def position_age_minutes(self, symbol: Optional[str] = None) -> float:
        pos = self.positions.get(symbol) if symbol else self.position
        if pos is None:
            return 0.0
        return (time.time() - pos["opened_at"]) / 60.0

    def _partial_exit(self, pos: dict, price: float, size: float, reason: str) -> dict:
        pnl = (price - pos["entry"]) * size
        self.balance += pnl
        pnl_pct = (price - pos["entry"]) / pos["entry"] * 100.0
        trade = self._trade_record(pos, pos["symbol"], pos["entry"], price, size, reason, pnl, pnl_pct)
        self.trades.append(trade)
        return trade

    def _full_exit(self, pos: dict, price: float, size: float, reason: str) -> dict:
        pnl = (price - pos["entry"]) * size
        self.balance += pnl
        pnl_pct = (price - pos["entry"]) / pos["entry"] * 100.0
        trade = self._trade_record(pos, pos["symbol"], pos["entry"], price, size, reason, pnl, pnl_pct)
        self.trades.append(trade)
        return trade

    def _trade_record(
        self,
        pos: dict,
        symbol: str,
        entry: float,
        exit_price: float,
        size: float,
        reason: str,
        pnl: float,
        pnl_pct: float,
    ) -> dict:
        pos["leg_index"] += 1
        leg = pos["leg_index"]
        return {
            "trade_id": f"{pos['trade_id']}-L{leg}",
            "symbol": symbol,
            "ts_entry": pos.get("opened_at_iso"),
            "ts_exit": datetime.now(timezone.utc).isoformat(),
            "entry": entry,
            "exit": exit_price,
            "size": size,
            "stop": pos.get("stop_original"),
            "tp": pos.get("tp2"),
            "reason": reason,
            "risk_usd": abs(entry - (pos.get("stop_original") or entry)) * size,
            "pnl": round(pnl, 4),
            "pnl_pct": round(pnl_pct, 4),
            "status": "CLOSED",
            "ts": datetime.now(timezone.utc).isoformat(),
        }
