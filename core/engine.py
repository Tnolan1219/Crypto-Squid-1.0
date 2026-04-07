from __future__ import annotations

import time
from pathlib import Path

from core.execution_router import ExecutionRouter
from core.logger import setup_logging
from core.settings import ROOT, load_settings
from core.strategy_manager import StrategyManager
from core.supabase_control import SupabaseControl
from strategies.coinbase_v2_strategy import CoinbaseV2Strategy


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
        self._trading_enabled = self.settings.trading_enabled
        self._register_strategies()

    def _register_strategies(self) -> None:
        if "coinbase_v2" in self.settings.enabled_strategies:
            mode = "paper"
            if self.settings.enable_live_trading and not self.settings.paper_mode:
                mode = "live"
            strategy = CoinbaseV2Strategy(
                config={
                    "mode": mode,
                    "max_position": self.settings.max_position_default,
                    "warmup_seconds": self.settings.warmup_seconds,
                    "account_capital_usd": self.settings.account_capital_usd,
                    "risk_per_trade_pct": self.settings.risk_per_trade_pct,
                    "stale_feed_seconds": self.settings.stale_feed_seconds,
                    "stop_limit_offset_bps": self.settings.stop_limit_offset_bps,
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
        if self.manager.daily_loss() > self.settings.max_daily_loss_usd:
            self._trading_enabled = False
            self.log.error("MAX_DAILY_LOSS breached; trading halted")

    def run(self) -> None:
        self.log.info("Engine starting")
        try:
            while True:
                self._refresh_control()
                self._failsafe_check()

                if not self._trading_enabled:
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
