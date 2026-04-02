"""Risk controls and stop-aware position sizing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from config import Config


def position_size(balance: float, entry: float, stop: float) -> float:
    """Module-level helper used by the Coinbase paper bot loop."""
    risk = balance * 0.005  # 0.5% per trade
    distance = abs(entry - stop)
    if distance == 0:
        return 0.0
    return risk / distance


@dataclass
class RiskCheckResult:
    allowed: bool
    reason: str


class RiskEngine:
    def __init__(self, cfg: Config, today_provider: Callable[[], date] | None = None):
        self.cfg = cfg
        self._today_provider = today_provider or date.today
        self._day = self._today_provider()
        self._trades_today = 0
        self._consecutive_losses = 0
        self._realized_pnl_usd = 0.0

    def can_open_trade(self, has_open_position: bool, market_data_healthy: bool, exchange_healthy: bool) -> RiskCheckResult:
        self._roll_day_if_needed()
        if has_open_position:
            return RiskCheckResult(False, "position_already_open")
        if self._trades_today >= self.cfg.max_trades_per_day:
            return RiskCheckResult(False, "max_trades_per_day_hit")
        if self._consecutive_losses >= self.cfg.max_consecutive_losses:
            return RiskCheckResult(False, "max_consecutive_losses_hit")

        equity = self.cfg.account_capital_usd
        if equity > 0 and (-self._realized_pnl_usd / equity * 100.0) >= self.cfg.daily_loss_limit_pct:
            return RiskCheckResult(False, "daily_loss_limit_hit")

        if not market_data_healthy:
            return RiskCheckResult(False, "market_data_stale")
        if not exchange_healthy:
            return RiskCheckResult(False, "exchange_unhealthy")
        return RiskCheckResult(True, "")

    def register_trade_close(self, pnl_usd: float) -> None:
        self._roll_day_if_needed()
        self._trades_today += 1
        self._realized_pnl_usd += pnl_usd
        if pnl_usd < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

    def risk_usd(self) -> float:
        return self.cfg.account_capital_usd * (self.cfg.risk_per_trade_pct / 100.0)

    def position_size(self, entry_price: float, stop_price: float) -> float:
        risk = self.risk_usd()
        stop_distance = max(entry_price - stop_price, 0.0)
        if risk <= 0 or stop_distance <= 0:
            return 0.0
        return round(risk / stop_distance, 6)

    def _roll_day_if_needed(self) -> None:
        today = self._today_provider()
        if today == self._day:
            return
        self._day = today
        self._trades_today = 0
        self._consecutive_losses = 0
        self._realized_pnl_usd = 0.0
