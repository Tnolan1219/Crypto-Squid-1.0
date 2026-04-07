from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional
from uuid import uuid4

from coinbase_live import CoinbaseLiveClient, OrderInfo


@dataclass
class PendingEntry:
    trade_id: str
    symbol: str
    entry_limit: float
    stop: float
    tp1: float
    tp2: float
    size: float
    tp1_size_frac: float
    time_stop_minutes: float
    fast_reduce_minutes: float
    submitted_at: float
    order_id: str
    drop_pct: float
    zscore: float


@dataclass
class LivePosition:
    trade_id: str
    symbol: str
    entry: float
    size_total: float
    size1: float
    size2: float
    stop: float
    stop_original: float
    tp1: float
    tp2: float
    tp1_hit: bool
    opened_at: float
    opened_at_iso: str
    time_stop_minutes: float
    fast_reduce_minutes: float
    drop_pct: float
    zscore: float
    entry_order_id: str
    tp1_order_id: str = ""
    tp2_order_id: str = ""
    sl_order_id: str = ""
    last_exit_attempt: float = 0.0


class LiveExecutionEngineV2:
    def __init__(
        self,
        client: CoinbaseLiveClient,
        risk_per_trade_pct: float,
        max_trades_per_day: int,
        max_consecutive_losses: int,
        daily_loss_limit_pct: float,
        account_capital_usd: float,
        entry_order_timeout_seconds: float,
        stop_limit_offset_bps: float,
    ):
        self._client = client
        self._risk_per_trade_pct = risk_per_trade_pct
        self._max_trades_per_day = max_trades_per_day
        self._max_consecutive_losses = max_consecutive_losses
        self._daily_loss_limit_pct = daily_loss_limit_pct
        self._account_capital_usd = account_capital_usd
        self._entry_order_timeout_seconds = entry_order_timeout_seconds
        self._stop_limit_offset_bps = stop_limit_offset_bps

        self._pending: dict[str, PendingEntry] = {}
        self._positions: dict[str, LivePosition] = {}
        self._trades: list[dict] = []

        self._day = date.today()
        self._trades_today = 0
        self._consecutive_losses = 0
        self._realized_pnl_usd = 0.0

    @property
    def trades(self) -> list[dict]:
        return self._trades

    @property
    def realized_pnl(self) -> float:
        return self._realized_pnl_usd

    @property
    def position(self) -> Optional[dict]:
        if not self._positions:
            return None
        return next(iter(self._positions.values())).__dict__

    @property
    def positions(self) -> dict[str, dict]:
        return {k: v.__dict__ for k, v in self._positions.items()}

    def has_open_position(self, symbol: str) -> bool:
        return symbol in self._positions or symbol in self._pending

    def can_open_trade(self) -> tuple[bool, str]:
        self._roll_day()
        if self._trades_today >= self._max_trades_per_day:
            return False, "max_trades_per_day"
        if self._consecutive_losses >= self._max_consecutive_losses:
            return False, "max_consecutive_losses"
        equity = self._account_capital_usd
        if equity > 0 and (-self._realized_pnl_usd / equity * 100.0) >= self._daily_loss_limit_pct:
            return False, "daily_loss_limit"
        return True, ""

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
        drop_pct: float,
        zscore: float,
    ) -> Optional[str]:
        if self.has_open_position(symbol):
            return None
        allowed, _ = self.can_open_trade()
        if not allowed:
            return None
        order_id = self._client.limit_buy_gtc(symbol, size=size, limit_price=entry, post_only=True)
        if not order_id:
            return None
        trade_id = f"live-v2-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
        self._pending[symbol] = PendingEntry(
            trade_id=trade_id,
            symbol=symbol,
            entry_limit=entry,
            stop=stop,
            tp1=tp1,
            tp2=tp2,
            size=size,
            tp1_size_frac=tp1_size_frac,
            time_stop_minutes=time_stop_minutes,
            fast_reduce_minutes=fast_reduce_minutes,
            submitted_at=time.time(),
            order_id=order_id,
            drop_pct=drop_pct,
            zscore=zscore,
        )
        return trade_id

    def on_price(self, symbol: str, current_price: float) -> list[dict]:
        closed: list[dict] = []
        pending = self._pending.get(symbol)
        if pending:
            closed += self._check_entry(pending)
        pos = self._positions.get(symbol)
        if pos:
            closed += self._check_position(pos, current_price)
        return closed

    def cancel_all(self) -> None:
        for pending in list(self._pending.values()):
            self._client.cancel_order(pending.order_id)
        for pos in list(self._positions.values()):
            self._cancel_exit_orders(pos)
        self._pending.clear()
        self._positions.clear()

    # ── Internal handlers ──────────────────────────────────────────────────

    def _check_entry(self, pending: PendingEntry) -> list[dict]:
        now = time.time()
        if now - pending.submitted_at > self._entry_order_timeout_seconds:
            self._client.cancel_order(pending.order_id)
            self._pending.pop(pending.symbol, None)
            return []

        info = self._client.get_order(pending.order_id)
        if info is None:
            return []

        if info.status in {"CANCELLED", "CANCELED", "EXPIRED", "FAILED", "REJECTED"}:
            self._pending.pop(pending.symbol, None)
            return []

        if info.filled_size <= 0 and info.status != "FILLED":
            return []

        filled_size = info.filled_size if info.filled_size > 0 else pending.size
        fill_price = info.average_filled_price if info.average_filled_price > 0 else pending.entry_limit

        if info.status != "FILLED" and info.filled_size > 0:
            self._client.cancel_order(pending.order_id)

        size1 = round(filled_size * pending.tp1_size_frac, 8)
        size2 = round(filled_size - size1, 8)
        pos = LivePosition(
            trade_id=pending.trade_id,
            symbol=pending.symbol,
            entry=fill_price,
            size_total=filled_size,
            size1=size1,
            size2=size2,
            stop=pending.stop,
            stop_original=pending.stop,
            tp1=pending.tp1,
            tp2=pending.tp2,
            tp1_hit=False,
            opened_at=time.time(),
            opened_at_iso=datetime.now(timezone.utc).isoformat(),
            time_stop_minutes=pending.time_stop_minutes,
            fast_reduce_minutes=pending.fast_reduce_minutes,
            drop_pct=pending.drop_pct,
            zscore=pending.zscore,
            entry_order_id=pending.order_id,
        )

        self._pending.pop(pending.symbol, None)
        self._positions[pending.symbol] = pos
        self._place_exit_orders(pos)
        return []

    def _check_position(self, pos: LivePosition, current_price: float) -> list[dict]:
        closed: list[dict] = []
        age_minutes = (time.time() - pos.opened_at) / 60.0

        if not pos.tp1_hit and pos.tp1_order_id:
            info = self._client.get_order(pos.tp1_order_id)
            if info and self._is_filled(info, pos.size1):
                trade = self._partial_exit(pos, pos.tp1, pos.size1, "TP1")
                closed.append(trade)
                pos.tp1_hit = True
                pos.stop = pos.entry * 1.0002
                if pos.size2 <= 0:
                    self._positions.pop(pos.symbol, None)
                    return closed
                self._replace_stop(pos)

        if pos.sl_order_id:
            info = self._client.get_order(pos.sl_order_id)
            if info and info.status == "FILLED":
                remaining = pos.size2 if pos.tp1_hit else pos.size_total
                reason = "SL_BREAKEVEN" if pos.tp1_hit else "SL"
                trade = self._full_exit(pos, info.average_filled_price or pos.stop, remaining, reason)
                closed.append(trade)
                self._cancel_exit_orders(pos, skip_sl=True)
                self._positions.pop(pos.symbol, None)
                return closed

        if pos.tp1_hit and pos.tp2_order_id:
            info = self._client.get_order(pos.tp2_order_id)
            if info and info.status == "FILLED":
                trade = self._full_exit(pos, info.average_filled_price or pos.tp2, pos.size2, "TP2")
                closed.append(trade)
                self._cancel_exit_orders(pos, skip_tp2=True)
                self._positions.pop(pos.symbol, None)
                return closed

        if age_minutes >= pos.time_stop_minutes:
            if time.time() - pos.last_exit_attempt > 5:
                pos.last_exit_attempt = time.time()
                remaining = pos.size2 if pos.tp1_hit else pos.size_total
                if remaining > 0:
                    exit_id = self._client.limit_sell_ioc(pos.symbol, remaining, current_price)
                    if exit_id:
                        info = self._client.get_order(exit_id)
                        if info and info.status == "FILLED":
                            trade = self._full_exit(pos, info.average_filled_price or current_price, remaining, "TIME_STOP")
                            closed.append(trade)
                            self._cancel_exit_orders(pos)
                            self._positions.pop(pos.symbol, None)
                            return closed

        if not pos.tp1_hit and age_minutes >= pos.fast_reduce_minutes:
            unrealized_pct = (current_price - pos.entry) / pos.entry * 100.0
            if -0.10 <= unrealized_pct <= 0.20 and time.time() - pos.last_exit_attempt > 5:
                pos.last_exit_attempt = time.time()
                half = round(pos.size_total * 0.50, 8)
                if half > 0:
                    exit_id = self._client.limit_sell_ioc(pos.symbol, half, current_price)
                    if exit_id:
                        info = self._client.get_order(exit_id)
                        if info and info.status == "FILLED":
                            trade = self._partial_exit(pos, info.average_filled_price or current_price, half, "FAST_REDUCE")
                            closed.append(trade)
                            pos.size1 = 0
                            pos.size2 = round(pos.size_total - half, 8)
                            pos.tp1_hit = True
                            pos.stop = pos.entry * 1.0002
                            self._replace_stop(pos)
        return closed

    def _place_exit_orders(self, pos: LivePosition) -> None:
        if pos.size1 > 0:
            pos.tp1_order_id = self._client.limit_sell_gtc(pos.symbol, pos.size1, pos.tp1, post_only=True) or ""
        if pos.size2 > 0:
            pos.tp2_order_id = self._client.limit_sell_gtc(pos.symbol, pos.size2, pos.tp2, post_only=True) or ""
        limit_price = pos.stop * (1 - self._stop_limit_offset_bps / 10_000)
        pos.sl_order_id = self._client.stop_limit_sell_gtc(pos.symbol, pos.size_total, pos.stop, limit_price) or ""

    def _replace_stop(self, pos: LivePosition) -> None:
        if pos.sl_order_id:
            self._client.cancel_order(pos.sl_order_id)
        remaining = pos.size2 if pos.tp1_hit else pos.size_total
        if remaining <= 0:
            return
        limit_price = pos.stop * (1 - self._stop_limit_offset_bps / 10_000)
        pos.sl_order_id = self._client.stop_limit_sell_gtc(pos.symbol, remaining, pos.stop, limit_price) or ""

    def _cancel_exit_orders(self, pos: LivePosition, skip_sl: bool = False, skip_tp2: bool = False) -> None:
        if pos.tp1_order_id:
            self._client.cancel_order(pos.tp1_order_id)
        if pos.tp2_order_id and not skip_tp2:
            self._client.cancel_order(pos.tp2_order_id)
        if pos.sl_order_id and not skip_sl:
            self._client.cancel_order(pos.sl_order_id)

    def _is_filled(self, info: OrderInfo, target_size: float) -> bool:
        if info.status == "FILLED":
            return True
        return info.filled_size >= max(target_size * 0.99, 0.0) and info.filled_size > 0

    def _partial_exit(self, pos: LivePosition, price: float, size: float, reason: str) -> dict:
        pnl = (price - pos.entry) * size
        self._realized_pnl_usd += pnl
        trade = self._trade_record(pos, pos.entry, price, size, reason, pnl)
        self._trades.append(trade)
        return trade

    def _full_exit(self, pos: LivePosition, price: float, size: float, reason: str) -> dict:
        pnl = (price - pos.entry) * size
        self._realized_pnl_usd += pnl
        self._trades_today += 1
        if pnl < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0
        trade = self._trade_record(pos, pos.entry, price, size, reason, pnl)
        self._trades.append(trade)
        return trade

    def _trade_record(
        self,
        pos: LivePosition,
        entry: float,
        exit_price: float,
        size: float,
        reason: str,
        pnl: float,
    ) -> dict:
        return {
            "trade_id": f"{pos.trade_id}-{uuid4().hex[:6]}",
            "symbol": pos.symbol,
            "ts_entry": pos.opened_at_iso,
            "ts_exit": datetime.now(timezone.utc).isoformat(),
            "entry": entry,
            "exit": exit_price,
            "size": size,
            "stop": pos.stop_original,
            "tp": pos.tp2,
            "reason": reason,
            "risk_usd": abs(entry - pos.stop_original) * size,
            "pnl": round(pnl, 4),
            "status": "CLOSED",
            "mode": "live",
            "drop_pct": pos.drop_pct,
            "zscore": pos.zscore,
        }

    def _roll_day(self) -> None:
        today = date.today()
        if today != self._day:
            self._day = today
            self._trades_today = 0
            self._consecutive_losses = 0
            self._realized_pnl_usd = 0.0
