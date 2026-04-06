from __future__ import annotations

from dataclasses import dataclass

from core.strategy_interface import Strategy


@dataclass
class ManagedStrategy:
    strategy: Strategy
    enabled: bool
    mode: str
    max_position: float


class StrategyManager:
    def __init__(self):
        self._strategies: dict[str, ManagedStrategy] = {}

    def register(self, name: str, strategy: Strategy, mode: str = "paper", max_position: float = 0.2) -> None:
        self._strategies[name] = ManagedStrategy(
            strategy=strategy,
            enabled=True,
            mode=mode,
            max_position=max_position,
        )

    def apply_control(self, control_rows: dict[str, dict]) -> None:
        for name, managed in self._strategies.items():
            row = control_rows.get(name)
            if not row:
                continue
            managed.enabled = bool(row.get("enabled", True))
            managed.mode = str(row.get("mode", managed.mode))
            if managed.mode == "off":
                managed.enabled = False
            raw_max = row.get("max_position", managed.max_position)
            try:
                managed.max_position = float(raw_max)
            except (TypeError, ValueError):
                pass
            managed.strategy.config["mode"] = managed.mode
            managed.strategy.config["max_position"] = managed.max_position

    def step_all(self) -> None:
        for managed in self._strategies.values():
            if not managed.enabled:
                managed.strategy.cancel_orders()
                continue
            managed.strategy.fetch_data()
            actions = managed.strategy.generate_signals()
            managed.strategy.manage_risk()
            managed.strategy.execute(actions)

    def cancel_all(self) -> None:
        for managed in self._strategies.values():
            managed.strategy.cancel_orders()

    def stop_all(self) -> None:
        for managed in self._strategies.values():
            managed.strategy.stop()

    def names(self) -> list[str]:
        return list(self._strategies.keys())

    def daily_loss(self) -> float:
        total = 0.0
        for managed in self._strategies.values():
            pnl = managed.strategy.current_pnl()
            if pnl < 0:
                total += abs(pnl)
        return total
