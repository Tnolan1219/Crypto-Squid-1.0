"""Shared dataclasses for signal and trade lifecycles."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SignalDecision:
    ts: datetime
    symbol: str
    price: float
    drop_pct: float
    volume_ratio: float
    zscore: float
    stabilization: str
    passed: bool
    reject_reason: str


@dataclass
class TradeRecord:
    trade_id: str
    signal: SignalDecision
    mode: str
    strategy_version: str
    entry_time: Optional[datetime] = None
    entry_price: Optional[float] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    size: Optional[float] = None
    risk_usd: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl_usd: Optional[float] = None
    hold_seconds: Optional[int] = None
    exit_reason: str = ""
    status: str = "PENDING"
    notes: str = ""
