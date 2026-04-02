"""
Paper trading engine v2 — staged exits with breakeven stop management.

Supports:
  - Two-target exits (tp1 at 50%, tp2 at 100%)
  - Breakeven stop after tp1 hit
  - Fast-reduce (partial exit) after time threshold if PnL is marginal
  - Hard time stop
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4


class PaperEngineV2:
    def __init__(self, balance: float = 1000.0):
        self.balance = balance
        self.start_balance = balance
        self.position: Optional[dict] = None
        self.trades: list[dict] = []

    # ── Entry ─────────────────────────────────────────────────────────────────

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
    ) -> None:
        size1 = round(size * tp1_size_frac, 8)
        size2 = round(size - size1, 8)
        self.position = {
            "trade_id": f"paper-v2-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}",
            "symbol": symbol,
            "entry": entry,
            "size_total": size,
            "size1": size1,         # exits at tp1
            "size2": size2,         # exits at tp2 or time/stop
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
        }
        print(
            f"[ENTER-v2] {symbol}  entry={entry:.4f}  size={size:.6f}"
            f"  stop={stop:.4f}  tp1={tp1:.4f}  tp2={tp2:.4f}"
        )

    # ── Per-tick update ───────────────────────────────────────────────────────

    def on_price(self, price: float) -> list[dict]:
        """
        Call on every tick with current price.
        Returns list of closed trade records (empty until something closes).
        """
        if self.position is None:
            return []

        pos = self.position
        age_minutes = (time.time() - pos["opened_at"]) / 60.0
        closed: list[dict] = []

        # ── TP1 partial exit ─────────────────────────────────────────────────
        if not pos["tp1_hit"] and price >= pos["tp1"]:
            trade = self._partial_exit(pos["tp1"], pos["size1"], "TP1")
            closed.append(trade)
            pos["tp1_hit"] = True
            # Move stop to breakeven (entry + estimated fee buffer ~2bps)
            pos["stop"] = pos["entry"] * 1.0002
            if pos["size2"] <= 0:
                self.position = None
                return closed

        if self.position is None:
            return closed

        # ── Stop hit ─────────────────────────────────────────────────────────
        if price <= pos["stop"]:
            remaining_size = pos["size2"] if pos["tp1_hit"] else pos["size_total"]
            reason = "SL_BREAKEVEN" if pos["tp1_hit"] else "SL"
            trade = self._full_exit(pos["stop"], remaining_size, reason)
            closed.append(trade)
            self.position = None
            return closed

        # ── TP2 full exit ─────────────────────────────────────────────────────
        if pos["tp1_hit"] and price >= pos["tp2"]:
            trade = self._full_exit(pos["tp2"], pos["size2"], "TP2")
            closed.append(trade)
            self.position = None
            return closed

        # ── Hard time stop ────────────────────────────────────────────────────
        if age_minutes >= pos["time_stop_minutes"]:
            remaining_size = pos["size2"] if pos["tp1_hit"] else pos["size_total"]
            trade = self._full_exit(price, remaining_size, "TIME_STOP")
            closed.append(trade)
            self.position = None
            return closed

        # ── Fast-reduce: partial exit if PnL is marginal at fast_reduce_minutes
        if (
            not pos["tp1_hit"]
            and age_minutes >= pos["fast_reduce_minutes"]
        ):
            unrealized_pct = (price - pos["entry"]) / pos["entry"] * 100.0
            if -0.10 <= unrealized_pct <= 0.20:  # marginal zone
                half = round(pos["size_total"] * 0.50, 8)
                if half > 0:
                    trade = self._partial_exit(price, half, "FAST_REDUCE")
                    closed.append(trade)
                    pos["size1"] = 0
                    pos["size2"] = round(pos["size_total"] - half, 8)
                    pos["tp1_hit"] = True  # treat as if tp1 was taken; use stop for remainder
                    pos["stop"] = pos["entry"] * 1.0002

        return closed

    def position_age_minutes(self) -> float:
        if self.position is None:
            return 0.0
        return (time.time() - self.position["opened_at"]) / 60.0

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _partial_exit(self, price: float, size: float, reason: str) -> dict:
        assert self.position is not None
        pnl = (price - self.position["entry"]) * size
        self.balance += pnl
        pnl_pct = (price - self.position["entry"]) / self.position["entry"] * 100.0
        trade = self._trade_record(self.position["symbol"], self.position["entry"], price, size, reason, pnl, pnl_pct)
        print(f"[PARTIAL] {reason}  price={price:.4f}  size={size:.6f}  pnl={pnl:+.2f}  bal={self.balance:.2f}")
        self.trades.append(trade)
        return trade

    def _full_exit(self, price: float, size: float, reason: str) -> dict:
        assert self.position is not None
        pnl = (price - self.position["entry"]) * size
        self.balance += pnl
        pnl_pct = (price - self.position["entry"]) / self.position["entry"] * 100.0
        trade = self._trade_record(self.position["symbol"], self.position["entry"], price, size, reason, pnl, pnl_pct)
        print(f"[EXIT-v2] {reason}  price={price:.4f}  size={size:.6f}  pnl={pnl:+.2f}  bal={self.balance:.2f}")
        self.trades.append(trade)
        return trade

    def _trade_record(
        self,
        symbol: str,
        entry: float,
        exit_price: float,
        size: float,
        reason: str, pnl: float, pnl_pct: float,
    ) -> dict:
        pos = self.position
        assert pos is not None
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
