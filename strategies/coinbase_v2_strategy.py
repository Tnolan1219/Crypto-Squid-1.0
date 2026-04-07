from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from core.execution_router import ExecutionRequest, ExecutionRouter
from core.strategy_interface import Strategy

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bar_builder import BarBuilder
from coinbase_ws import CoinbaseWS
from coinbase_live import CoinbaseLiveClient
from event_collector import EventCollector
from live_engine_v2 import LiveExecutionEngineV2
from paper_engine_v2 import PaperEngineV2
from params_v2 import DEFAULT_V2_PARAMS
from risk import position_size
from runtime_store import RuntimeStore
from signal_v2 import SignalEngineV2
from trade_history import TradeHistoryStore


class CoinbaseV2Strategy(Strategy):
    SYMBOLS = ["BTC-USD", "ETH-USD"]

    def __init__(self, config: dict, execution_router: ExecutionRouter, root: Path):
        super().__init__(config)
        self._root = root
        self._router = execution_router
        self._bar_builder = BarBuilder()
        self._ws = CoinbaseWS(
            symbols=self.SYMBOLS,
            on_trade=self._bar_builder.on_trade,
            on_spread=self._bar_builder.update_spread,
        )
        self._events = EventCollector(root)
        self._signal_engine = SignalEngineV2(DEFAULT_V2_PARAMS, self._events)
        self._paper_engine = PaperEngineV2(balance=float(config.get("account_capital_usd", 1000.0)))
        self._live_engine: LiveExecutionEngineV2 | None = None
        self._market_data_healthy = True
        self._runtime_store = RuntimeStore(root)
        self._trade_history = TradeHistoryStore(root)
        self._trade_history.sync_existing()
        self._latest_snapshots: dict[str, tuple] = {}
        self._started = False
        self._started_at = datetime.now(timezone.utc).isoformat()
        self._strategy_version = "coinbase-v2-live" if self._mode() == "live" else "coinbase-v2-paper"
        self._last_start_attempt = 0.0
        self._stale_feed_seconds = float(config.get("stale_feed_seconds", 20))

        if self._mode() == "live":
            api_key = os.getenv("COINBASE_API_KEY_NAME", "").strip()
            api_secret = os.getenv("COINBASE_PRIVATE_KEY", "").strip()
            client = CoinbaseLiveClient(api_key=api_key, api_secret=api_secret)
            self._live_engine = LiveExecutionEngineV2(
                client=client,
                risk_per_trade_pct=float(config.get("risk_per_trade_pct", 0.50)),
                max_trades_per_day=3,
                max_consecutive_losses=2,
                daily_loss_limit_pct=float(DEFAULT_V2_PARAMS.daily_loss_limit_pct),
                account_capital_usd=float(config.get("account_capital_usd", 1000.0)),
                entry_order_timeout_seconds=float(DEFAULT_V2_PARAMS.entry_order_lifetime_seconds),
                stop_limit_offset_bps=float(config.get("stop_limit_offset_bps", 5)),
            )

    def _ensure_started(self) -> None:
        if self._started:
            return
        now = time.time()
        if now - self._last_start_attempt < 10:
            return
        self._last_start_attempt = now
        try:
            self._ws.start()
            time.sleep(float(self.config.get("warmup_seconds", 30)))
            self._started = True
        except Exception:
            self._started = False

    def fetch_data(self) -> None:
        self._ensure_started()
        if not self._started:
            return
        now = time.time()
        stale = False
        for symbol in self.SYMBOLS:
            snapshot = self._bar_builder.snapshot(symbol)
            self._latest_snapshots[symbol] = snapshot
            last_trade_ts = snapshot[5]
            if last_trade_ts <= 0 or (now - last_trade_ts) > self._stale_feed_seconds:
                stale = True
        self._market_data_healthy = not stale

    def generate_signals(self) -> list[dict]:
        actions: list[dict] = []
        if not self._market_data_healthy:
            return actions
        for symbol in self.SYMBOLS:
            bars, bid, ask, _, spread_hist, _ = self._latest_snapshots.get(symbol, ([], 0.0, 0.0, 0.0, [], 0.0))
            if not bars:
                continue
            signal = self._signal_engine.check(
                symbol=symbol,
                bars=bars,
                bid=bid,
                ask=ask,
                spread_hist=spread_hist,
                account_equity=self._paper_engine.balance,
            )
            if signal:
                actions.append({"type": "entry", "symbol": symbol, "signal": signal})
        return actions

    def execute(self, actions: list[dict]) -> None:
        for symbol in self.SYMBOLS:
            bars, _, _, current_price, _, _ = self._latest_snapshots.get(symbol, ([], 0.0, 0.0, 0.0, [], 0.0))
            if not bars:
                continue
            if self._mode() == "live" and self._live_engine:
                closed = self._live_engine.on_price(symbol, current_price)
                for trade in closed:
                    if trade.get("reason") in {"SL", "SL_BREAKEVEN", "TP2", "TIME_STOP"}:
                        self._signal_engine.register_trade_close(trade["pnl"])
                    self._trade_history.write_trade(trade, strategy_version=self._strategy_version)
            else:
                if self._paper_engine.has_open_position(symbol):
                    closed = self._paper_engine.on_price(symbol, current_price)
                    for trade in closed:
                        if trade.get("reason") in {"SL", "SL_BREAKEVEN", "TP2", "TIME_STOP"}:
                            self._signal_engine.register_trade_close(trade["pnl"])
                        self._trade_history.write_trade(trade, strategy_version=self._strategy_version)

        for action in actions:
            if action.get("type") != "entry":
                continue
            signal = action["signal"]
            symbol = action["symbol"]
            if self._mode() == "live" and self._live_engine and self._live_engine.has_open_position(symbol):
                continue
            if self._mode() != "live" and self._paper_engine.has_open_position(symbol):
                continue
            sp = DEFAULT_V2_PARAMS.for_symbol(symbol)
            risk_pct = DEFAULT_V2_PARAMS.risk_per_trade_pct
            if self._mode() == "live":
                risk_pct = float(self.config.get("risk_per_trade_pct", 0.50))
            size = position_size(
                float(self.config.get("account_capital_usd", self._paper_engine.balance)),
                signal.entry_limit,
                signal.stop,
                risk_per_trade_pct=risk_pct,
            )
            max_size = self._max_size_for_symbol(symbol, signal.entry_limit)
            size = min(size, max_size)

            decision = self._router.route(
                ExecutionRequest(
                    venue="coinbase",
                    symbol=symbol,
                    size=size,
                    limit_price=signal.entry_limit,
                    mode=str(self.config.get("mode", "paper")),
                    max_position=float(self.config.get("max_position", 0.20)),
                    slippage_bps=10.0,
                    maker_only=True,
                )
            )
            if not decision.accepted or decision.size <= 0:
                continue
            if self._mode() == "live" and self._live_engine:
                self._live_engine.enter(
                    symbol=symbol,
                    entry=signal.entry_limit,
                    size=decision.size,
                    stop=signal.stop,
                    tp1=signal.tp1,
                    tp1_size_frac=sp.tp1_size_frac,
                    tp2=signal.tp2,
                    time_stop_minutes=sp.time_stop_minutes,
                    fast_reduce_minutes=sp.fast_reduce_minutes,
                    drop_pct=signal.drop_pct,
                    zscore=signal.zscore,
                )
            else:
                self._paper_engine.enter(
                    symbol=symbol,
                    entry=signal.entry_limit,
                    size=decision.size,
                    stop=signal.stop,
                    tp1=signal.tp1,
                    tp1_size_frac=sp.tp1_size_frac,
                    tp2=signal.tp2,
                    time_stop_minutes=sp.time_stop_minutes,
                    fast_reduce_minutes=sp.fast_reduce_minutes,
                )
        self._write_runtime_state()

    def manage_risk(self) -> None:
        return

    def cancel_orders(self) -> None:
        self._router.cancel_all_orders("coinbase_v2")
        if self._live_engine:
            self._live_engine.cancel_all()

    def stop(self) -> None:
        if self._started:
            self._ws.stop()
            self._started = False

    def current_pnl(self) -> float:
        if self._mode() == "live" and self._live_engine:
            return self._live_engine.realized_pnl
        return self._paper_engine.balance - self._paper_engine.start_balance

    def _max_size_for_symbol(self, symbol: str, entry_limit: float) -> float:
        max_exp_pct = (
            DEFAULT_V2_PARAMS.max_gross_exposure_btc_pct
            if symbol == "BTC-USD"
            else DEFAULT_V2_PARAMS.max_gross_exposure_eth_pct
        )
        equity = float(self.config.get("account_capital_usd", self._paper_engine.balance))
        return (equity * max_exp_pct / 100.0) / max(entry_limit, 1e-9)

    def _write_runtime_state(self) -> None:
        symbols = {}
        for symbol in self.SYMBOLS:
            bars, bid, ask, current_price, _, last_trade_ts = self._latest_snapshots.get(
                symbol, ([], 0.0, 0.0, 0.0, [], 0.0)
            )
            history = [
                {"ts": datetime.fromtimestamp(b.ts, tz=timezone.utc).isoformat(), "price": b.close}
                for b in bars[-180:]
            ]
            symbols[symbol] = {
                "price": current_price,
                "drop_pct": BarBuilder.return_pct(bars, 180),
                "zscore": BarBuilder.zscore(bars),
                "spread_bps": BarBuilder.current_spread_bps(bid, ask),
                "last_trade_ts": last_trade_ts,
                "history": history,
            }
        account_start = self._paper_engine.start_balance
        account_balance = self._paper_engine.balance
        trades = self._paper_engine.trades[-50:]
        positions = list(self._paper_engine.positions.values())
        position = self._paper_engine.position
        if self._mode() == "live" and self._live_engine:
            account_start = float(self.config.get("account_capital_usd", 0.0))
            account_balance = account_start + self._live_engine.realized_pnl
            trades = self._live_engine.trades[-50:]
            positions = list(self._live_engine.positions.values())
            position = self._live_engine.position
        payload = {
            "status": "running",
            "started_at": self._started_at,
            "mode": {
                "trading_enabled": True,
                "paper_mode": self.config.get("mode", "paper") == "paper",
                "enable_live_trading": self.config.get("mode", "paper") == "live",
            },
            "version": "v2",
            "event_count": self._events.count(),
            "heartbeat": {
                "ts": datetime.now(timezone.utc).isoformat(),
                "market_data_healthy": self._market_data_healthy,
            },
            "account": {
                "starting_balance": account_start,
                "balance": account_balance,
                "realized_pnl": round(self.current_pnl(), 4),
            },
            "position": position,
            "active_position": position,
            "positions": positions,
            "symbols": symbols,
            "trades": trades,
            "stats": {
                "trades_closed": len(trades),
            },
        }
        self._runtime_store.write(payload)

    def _mode(self) -> str:
        return str(self.config.get("mode", "paper"))
