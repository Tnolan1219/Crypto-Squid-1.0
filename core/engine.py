from __future__ import annotations

import json
import time
from pathlib import Path

from core.execution_router import ExecutionRouter
from core.logger import setup_logging
from core.settings import ROOT, load_settings
from core.strategy_manager import StrategyManager
from core.supabase_control import SupabaseControl
from strategies.coinbase_v2_strategy import CoinbaseV2Strategy
from strategies.coinbase_v3_strategy import CoinbaseV3Strategy


class Engine:
    def __init__(self):
        self.root = Path(ROOT)
        self.settings = load_settings()
        self.log = setup_logging(self.root)
        self.execution_router = ExecutionRouter()
        self.control = SupabaseControl(
            url=self.settings.supabase_url,
            key=self.settings.supabase_key,
        )
        self.manager = StrategyManager()
        self._last_control_poll = 0.0
        self._failsafe_latched = False
        self._runtime_control_path = self.root / "data" / "control" / "runtime_control.json"
        self._ensure_runtime_control_file()
        self._register_strategies()

    def _ensure_runtime_control_file(self) -> None:
        self._runtime_control_path.parent.mkdir(parents=True, exist_ok=True)
        if self._runtime_control_path.exists():
            return
        self._write_runtime_control(self.settings.trading_enabled, reason="bootstrap")

    def _read_runtime_control(self) -> bool:
        if not self._runtime_control_path.exists():
            return self.settings.trading_enabled
        try:
            payload = json.loads(self._runtime_control_path.read_text(encoding="utf-8"))
            return bool(payload.get("trading_enabled", self.settings.trading_enabled))
        except Exception:
            return self.settings.trading_enabled

    def _write_runtime_control(self, enabled: bool, reason: str) -> None:
        payload = {
            "trading_enabled": bool(enabled),
            "reason": reason,
            "updated_at_unix": int(time.time()),
        }
        temp = self._runtime_control_path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        temp.replace(self._runtime_control_path)

    def _register_strategies(self) -> None:
        if "coinbase_v3" in self.settings.enabled_strategies:
            strategy = CoinbaseV3Strategy(
                config={
                    "mode": "paper",
                    "max_position": self.settings.max_position_default,
                    "warmup_seconds": self.settings.warmup_seconds,
                    "account_capital_usd": self.settings.account_capital_usd,
                },
                execution_router=self.execution_router,
                root=self.root,
            )
            self.manager.register("coinbase_v3", strategy)

        if "coinbase_v2" in self.settings.enabled_strategies:
            strategy = CoinbaseV2Strategy(
                config={
                    "mode": "paper",
                    "max_position": self.settings.max_position_default,
                    "warmup_seconds": self.settings.warmup_seconds,
                    "account_capital_usd": self.settings.account_capital_usd,
                },
                execution_router=self.execution_router,
                root=self.root,
            )
            self.manager.register("coinbase_v2", strategy)

    def _refresh_control(self) -> None:
        now = time.time()
        if now - self._last_control_poll < self.settings.control_poll_seconds:
            return
        self._last_control_poll = now
        control_rows = self.control.fetch_strategy_control()
        self.manager.apply_control(control_rows)

    def _failsafe_check(self) -> None:
        if self._failsafe_latched:
            return
        if self.manager.daily_loss() > self.settings.max_daily_loss_usd:
            self._failsafe_latched = True
            self._write_runtime_control(False, reason="max_daily_loss_breached")
            self.log.error("MAX_DAILY_LOSS breached; trading halted")

    def _trading_enabled(self) -> bool:
        manual_enabled = self._read_runtime_control()
        return self.settings.trading_enabled and manual_enabled and not self._failsafe_latched

    def run(self) -> None:
        self.log.info("Engine starting")
        try:
            while True:
                self._refresh_control()
                self._failsafe_check()

                if not self._trading_enabled():
                    self.manager.cancel_all()
                    self.execution_router.cancel_all_orders()
                    for name in self.manager.names():
                        self.control.update_heartbeat(name)
                    time.sleep(self.settings.loop_seconds)
                    continue

                self.manager.step_all()
                for name in self.manager.names():
                    self.control.update_heartbeat(name)
                time.sleep(self.settings.loop_seconds)
        finally:
            self.manager.stop_all()
            self.log.info("Engine stopped")
