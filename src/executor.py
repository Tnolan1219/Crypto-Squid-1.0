"""Execution engine supporting log-only, paper, and live-ready paths."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog

from config import Config
from hyperliquid_client import HyperliquidLiveClient
from models import SignalDecision, TradeRecord
from risk import RiskEngine

log = structlog.get_logger()


@dataclass
class PendingEntry:
    record: TradeRecord
    symbol: str
    limit_price: float
    expires_at: float


@dataclass
class OpenPosition:
    record: TradeRecord
    symbol: str
    stop_price: float
    target_price: float
    expires_at: datetime
    size: float
    entry_order_id: str = ""
    tp_order_id: str = ""
    sl_order_id: str = ""


class ExecutionEngine:
    def __init__(self, cfg: Config, risk: RiskEngine):
        self.cfg = cfg
        self.risk = risk
        self.mode = self._resolve_mode()
        self.pending_entry: Optional[PendingEntry] = None
        self.open_position: Optional[OpenPosition] = None
        self.last_trade_ts: float = 0.0
        self._live = HyperliquidLiveClient(cfg) if self.mode == "live" else None

    def exchange_healthy(self) -> bool:
        if self.mode != "live":
            return True
        ok, _ = self._live.healthy()
        return ok

    def start_trade(self, signal: SignalDecision) -> Optional[TradeRecord]:
        params = self.cfg.symbol_params(signal.symbol)
        entry_price = signal.price * (1.0 - self.cfg.limit_offset_bps / 10000.0)
        stop_price = self._compute_stop(entry_price, signal.price, params.sl_pct)
        target_price = round(entry_price * (1 + params.tp_pct / 100.0), 4)
        size = self.risk.position_size(entry_price, stop_price)
        if size <= 0:
            return None

        trade_id = f"{signal.symbol}-{int(signal.ts.timestamp())}"
        record = TradeRecord(
            trade_id=trade_id,
            signal=signal,
            mode=self.mode,
            strategy_version=self.cfg.strategy_version,
            entry_price=round(entry_price, 4),
            stop_price=stop_price,
            target_price=target_price,
            size=size,
            risk_usd=self.risk.risk_usd(),
            status="PENDING",
        )

        if self.mode == "log-only":
            record.status = "SKIPPED"
            record.notes = "log_only_mode"
            return record

        now = time.time()
        self.pending_entry = PendingEntry(
            record=record,
            symbol=signal.symbol,
            limit_price=entry_price,
            expires_at=now + self.cfg.order_timeout_seconds,
        )
        log.info(
            "entry.submitted",
            trade_id=trade_id,
            symbol=signal.symbol,
            mode=self.mode,
            limit_price=entry_price,
            stop=stop_price,
            target=target_price,
            size=size,
        )

        if self.mode == "live":
            oid = self._live.place_limit_order(signal.symbol, True, size, entry_price, reduce_only=False)
            if not oid:
                self.pending_entry = None
                record.status = "CANCELLED"
                record.notes = "live_entry_submit_failed"
                return record
            self.pending_entry.record.notes = f"entry_oid={oid}"
        return None

    def on_price(self, symbol: str, ts: float, price: float) -> Optional[TradeRecord]:
        completed = self._update_pending_entry(symbol, ts, price)
        if completed:
            return completed
        return self._update_open_position(symbol, ts, price)

    def has_open_or_pending(self) -> bool:
        return self.pending_entry is not None or self.open_position is not None

    def _update_pending_entry(self, symbol: str, ts: float, price: float) -> Optional[TradeRecord]:
        pending = self.pending_entry
        if pending is None or pending.symbol != symbol:
            return None

        if self.mode == "live":
            entry_oid = self._extract_note_oid(pending.record.notes)
            if entry_oid:
                status = self._live.order_status(self._live.account_address, entry_oid)
                if status in {"FILLED", "FILLED_PARTIAL"}:
                    return self._mark_filled(symbol, pending, pending.limit_price)
                if status in {"CANCELED", "REJECTED", "EXPIRED"}:
                    record = pending.record
                    record.status = "CANCELLED"
                    record.notes = f"entry_{status.lower()}"
                    self.pending_entry = None
                    return record

        if ts >= pending.expires_at:
            if self.mode == "live":
                entry_oid = self._extract_note_oid(pending.record.notes)
                if entry_oid:
                    self._live.cancel_order(symbol, entry_oid)
            record = pending.record
            record.status = "MISSED"
            record.notes = "entry_timeout"
            self.pending_entry = None
            return record

        if price > pending.limit_price:
            return None
        return self._mark_filled(symbol, pending, pending.limit_price)

    def _mark_filled(self, symbol: str, pending: PendingEntry, fill_price: float) -> Optional[TradeRecord]:
        record = pending.record
        entry_time = datetime.now(timezone.utc)
        record.entry_time = entry_time
        record.entry_price = fill_price
        record.status = "OPEN"
        self.open_position = OpenPosition(
            record=record,
            symbol=symbol,
            stop_price=record.stop_price,
            target_price=record.target_price,
            expires_at=entry_time + timedelta(minutes=self.cfg.max_hold_minutes),
            size=record.size,
        )
        self.pending_entry = None

        if self.mode == "live":
            self._place_live_exit_orders(self.open_position)

        log.info("entry.filled", trade_id=record.trade_id, entry_price=record.entry_price)
        return None

    def _update_open_position(self, symbol: str, ts: float, price: float) -> Optional[TradeRecord]:
        open_pos = self.open_position
        if open_pos is None or open_pos.symbol != symbol:
            return None

        now_dt = datetime.now(timezone.utc)
        if price <= open_pos.stop_price:
            return self._close_position(open_pos, exit_price=open_pos.stop_price, reason="SL", now_dt=now_dt)
        if price >= open_pos.target_price:
            return self._close_position(open_pos, exit_price=open_pos.target_price, reason="TP", now_dt=now_dt)
        if now_dt >= open_pos.expires_at:
            return self._close_position(open_pos, exit_price=price, reason="TIME_STOP", now_dt=now_dt)
        return None

    def _close_position(self, pos: OpenPosition, exit_price: float, reason: str, now_dt: datetime) -> TradeRecord:
        if self.mode == "live":
            if pos.tp_order_id:
                self._live.cancel_order(pos.symbol, pos.tp_order_id)
            if pos.sl_order_id:
                self._live.cancel_order(pos.symbol, pos.sl_order_id)
            self._live.place_limit_order(pos.symbol, False, pos.size, exit_price, reduce_only=True)

        rec = pos.record
        rec.exit_time = now_dt
        rec.exit_price = round(exit_price, 4)
        rec.exit_reason = reason
        rec.status = reason
        if rec.entry_time:
            rec.hold_seconds = int((rec.exit_time - rec.entry_time).total_seconds())
        rec.pnl_usd = (rec.exit_price - rec.entry_price) * rec.size
        self.risk.register_trade_close(rec.pnl_usd)
        self.last_trade_ts = time.time()
        self.open_position = None
        return rec

    def _compute_stop(self, entry_price: float, panic_price: float, sl_pct: float) -> float:
        fixed_stop = entry_price * (1 - sl_pct / 100.0)
        structure_stop = panic_price * (1 - 0.001)
        stop = max(fixed_stop, structure_stop)
        return round(stop, 4)

    def _place_live_exit_orders(self, pos: OpenPosition) -> None:
        tp = self._live.place_limit_order(pos.symbol, False, pos.size, pos.target_price, reduce_only=True)
        sl = self._live.place_limit_order(pos.symbol, False, pos.size, pos.stop_price, reduce_only=True)
        pos.tp_order_id = tp or ""
        pos.sl_order_id = sl or ""

    @staticmethod
    def _extract_note_oid(notes: str) -> str:
        if not notes or "entry_oid=" not in notes:
            return ""
        return notes.split("entry_oid=", 1)[1].strip()

    def _resolve_mode(self) -> str:
        if self.cfg.enable_live_trading:
            return "live"
        if self.cfg.paper_mode:
            return "paper"
        return "log-only"
