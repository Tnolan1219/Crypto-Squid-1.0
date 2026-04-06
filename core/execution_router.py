from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExecutionRequest:
    venue: str
    symbol: str
    size: float
    limit_price: float
    mode: str
    max_position: float
    slippage_bps: float
    maker_only: bool = True


@dataclass
class ExecutionDecision:
    accepted: bool
    size: float
    reason: str


class ExecutionRouter:
    def __init__(self):
        self._open_orders: dict[str, list[dict]] = {}

    def route(self, req: ExecutionRequest) -> ExecutionDecision:
        if req.size <= 0:
            return ExecutionDecision(False, 0.0, "invalid_size")
        if req.max_position > 0 and req.size > req.max_position:
            return ExecutionDecision(True, req.max_position, "clamped_max_position")
        if req.slippage_bps < 0:
            return ExecutionDecision(False, 0.0, "invalid_slippage")
        if req.maker_only and req.limit_price <= 0:
            return ExecutionDecision(False, 0.0, "maker_requires_limit")
        return ExecutionDecision(True, req.size, "accepted")

    def track_order(self, strategy_name: str, order: dict) -> None:
        self._open_orders.setdefault(strategy_name, []).append(order)

    def cancel_all_orders(self, strategy_name: str | None = None) -> None:
        if strategy_name is None:
            self._open_orders.clear()
            return
        self._open_orders[strategy_name] = []
