from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import structlog

from core.execution_router import ExecutionRequest, ExecutionRouter
from core.strategy_interface import Strategy
from strategies.coinbase_live_client import CoinbaseLiveClient

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bar_builder import BarBuilder
from coinbase_ws import CoinbaseWS
from event_collector import EventCollector
from paper_engine_v2 import PaperEngineV2
from params_v2 import DEFAULT_V2_PARAMS
from risk import position_size
from runtime_store import RuntimeStore
from signal_v2 import SignalEngineV2
from trade_history import TradeHistoryStore


class CoinbaseV2Strategy(Strategy):
    SYMBOLS = ["BTC-USD", "ETH-USD"]
    LIVE_SUPPORTED = True

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
        self._runtime_store = RuntimeStore(root)
        self._trade_history = TradeHistoryStore(root)
        self._trade_history.sync_existing()
        self._latest_snapshots: dict[str, tuple] = {}
        self._log = structlog.get_logger("coinbase_v2_strategy")
        self._started = False
        self._started_at = datetime.now(timezone.utc).isoformat()
        self._strategy_version = "coinbase-v2-paper"
        self._last_start_attempt = 0.0
        self._live_enabled = str(os.getenv("ENABLE_LIVE_TRADING", "false")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self._order_timeout_seconds = int(float(os.getenv("ORDER_TIMEOUT_SECONDS", "30")))
        self._live_client: CoinbaseLiveClient | None = None
        self._live_health_error = ""
        self._live_entry_order: dict | None = None
        self._live_position: dict | None = None
        self._live_trades: list[dict] = []

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
        for symbol in self.SYMBOLS:
            self._latest_snapshots[symbol] = self._bar_builder.snapshot(symbol)

    def generate_signals(self) -> list[dict]:
        actions: list[dict] = []
        for symbol in self.SYMBOLS:
            bars, bid, ask, _, spread_hist = self._latest_snapshots.get(symbol, ([], 0.0, 0.0, 0.0, []))
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
        mode = str(self.config.get("mode", "paper"))
        self._sync_live_mode(mode)
        if mode == "live":
            self._execute_live(actions)
            self._write_runtime_state()
            return

        for symbol in self.SYMBOLS:
            bars, _, _, current_price, _ = self._latest_snapshots.get(symbol, ([], 0.0, 0.0, 0.0, []))
            if not bars:
                continue
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
            if self._paper_engine.has_open_position(symbol):
                continue
            sp = DEFAULT_V2_PARAMS.for_symbol(symbol)
            size = position_size(
                self._paper_engine.balance,
                signal.entry_limit,
                signal.stop,
                risk_per_trade_pct=DEFAULT_V2_PARAMS.risk_per_trade_pct,
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

    def _sync_live_mode(self, mode: str) -> None:
        if mode != "live":
            return
        if not self.LIVE_SUPPORTED:
            self._live_health_error = "live_mode_not_supported"
            return
        if not self._live_enabled:
            self._live_health_error = "enable_live_trading_false"
            return
        if self._live_client is not None:
            return
        key_name = str(os.getenv("COINBASE_API_KEY_NAME", "")).strip()
        priv = str(os.getenv("COINBASE_PRIVATE_KEY", "")).strip()
        if not key_name or not priv:
            self._live_health_error = "missing_coinbase_credentials"
            return
        try:
            self._live_client = CoinbaseLiveClient(key_name, priv)
            ok, msg = self._live_client.healthy()
            if not ok:
                self._live_health_error = f"live_client_unhealthy:{msg}"
        except Exception as exc:
            self._live_health_error = f"live_client_init_failed:{exc}"

    def _execute_live(self, actions: list[dict]) -> None:
        if self._live_client is None:
            return
        self._reconcile_live_orders()
        if self._live_position is not None or self._live_entry_order is not None:
            return
        for action in actions:
            if action.get("type") != "entry":
                continue
            signal = action["signal"]
            symbol = action["symbol"]
            sp = DEFAULT_V2_PARAMS.for_symbol(symbol)
            size = position_size(
                self._paper_engine.balance,
                signal.entry_limit,
                signal.stop,
                risk_per_trade_pct=DEFAULT_V2_PARAMS.risk_per_trade_pct,
            )
            size = min(size, self._max_size_for_symbol(symbol, signal.entry_limit))
            decision = self._router.route(
                ExecutionRequest(
                    venue="coinbase",
                    symbol=symbol,
                    size=size,
                    limit_price=signal.entry_limit,
                    mode="live",
                    max_position=float(self.config.get("max_position", 0.20)),
                    slippage_bps=10.0,
                    maker_only=True,
                )
            )
            if not decision.accepted or decision.size <= 0:
                continue
            try:
                placed = self._live_client.place_entry_gtc_buy(symbol, decision.size, signal.entry_limit, post_only=True)
            except Exception as exc:
                self._live_health_error = f"live_entry_failed:{exc}"
                return
            if not placed.ok:
                self._live_health_error = "live_entry_rejected"
                return
            now = time.time()
            self._live_entry_order = {
                "order_id": placed.order_id,
                "symbol": symbol,
                "size": float(decision.size),
                "entry_limit": float(signal.entry_limit),
                "stop": float(signal.stop),
                "tp2": float(signal.tp2),
                "time_stop_minutes": int(sp.time_stop_minutes),
                "placed_at_unix": now,
            }
            self._log.info("live.entry_submitted", symbol=symbol, order_id=placed.order_id, size=decision.size)
            return

    def _reconcile_live_orders(self) -> None:
        if self._live_client is None:
            return
        if self._live_entry_order is not None:
            order_id = str(self._live_entry_order.get("order_id", ""))
            if order_id:
                payload: dict = {}
                try:
                    payload = self._live_client.get_order(order_id)
                    status = str(payload.get("status") or payload.get("order_status") or "").upper()
                except Exception as exc:
                    self._live_health_error = f"live_get_order_failed:{exc}"
                    status = ""
                if "FILLED" in status:
                    fill_price = float(payload.get("average_filled_price") or payload.get("limit_price") or self._live_entry_order["entry_limit"])
                    fill_size = float(payload.get("filled_size") or self._live_entry_order["size"])
                    self._live_position = {
                        "symbol": self._live_entry_order["symbol"],
                        "entry": fill_price,
                        "size": fill_size,
                        "stop": self._live_entry_order["stop"],
                        "tp2": self._live_entry_order["tp2"],
                        "opened_at_unix": time.time(),
                        "time_stop_minutes": self._live_entry_order["time_stop_minutes"],
                    }
                    self._live_entry_order = None
                elif time.time() - float(self._live_entry_order.get("placed_at_unix", 0)) > self._order_timeout_seconds:
                    self._live_client.cancel(order_id)
                    self._live_entry_order = None

        if self._live_position is None:
            return
        symbol = str(self._live_position["symbol"])
        _, bid, _, current_price, _ = self._latest_snapshots.get(symbol, ([], 0.0, 0.0, 0.0, []))
        entry = float(self._live_position["entry"])
        stop = float(self._live_position["stop"])
        tp2 = float(self._live_position["tp2"])
        age_min = (time.time() - float(self._live_position["opened_at_unix"])) / 60.0
        reason = None
        if current_price <= stop:
            reason = "SL"
        elif current_price >= tp2:
            reason = "TP2"
        elif age_min >= float(self._live_position["time_stop_minutes"]):
            reason = "TIME_STOP"
        if reason is None:
            return
        exit_limit = max(0.01, min(current_price, bid if bid > 0 else current_price) * 0.9995)
        try:
            placed = self._live_client.place_exit_ioc_sell(symbol, float(self._live_position["size"]), exit_limit)
            if not placed.ok:
                self._live_health_error = "live_exit_rejected"
                return
            payload = self._live_client.get_order(placed.order_id)
            status = str(payload.get("status") or payload.get("order_status") or "").upper()
            if "FILLED" not in status:
                self._live_health_error = "live_exit_not_filled"
                return
            exit_price = float(payload.get("average_filled_price") or exit_limit)
            size = float(payload.get("filled_size") or self._live_position["size"])
            pnl = (exit_price - entry) * size
            pnl_pct = (exit_price / entry - 1.0) * 100.0 if entry > 0 else 0.0
            trade = {
                "symbol": symbol,
                "entry": round(entry, 8),
                "exit": round(exit_price, 8),
                "size": round(size, 8),
                "pnl": round(pnl, 8),
                "pnl_pct": round(pnl_pct, 8),
                "reason": reason,
                "ts": datetime.now(timezone.utc).isoformat(),
                "mode": "live",
            }
            self._live_trades.append(trade)
            self._trade_history.write_trade(trade, strategy_version="coinbase-v2-live")
            self._signal_engine.register_trade_close(float(trade["pnl"]))
            self._paper_engine.balance += float(trade["pnl"])
            self._live_position = None
            self._log.info("live.trade_closed", symbol=symbol, reason=reason, pnl=trade["pnl"])
        except Exception as exc:
            self._live_health_error = f"live_exit_failed:{exc}"

    def manage_risk(self) -> None:
        return

    def cancel_orders(self) -> None:
        self._router.cancel_all_orders("coinbase_v2")

    def stop(self) -> None:
        if self._started:
            self._ws.stop()
            self._started = False

    def current_pnl(self) -> float:
        return self._paper_engine.balance - self._paper_engine.start_balance

    def _max_size_for_symbol(self, symbol: str, entry_limit: float) -> float:
        max_exp_pct = (
            DEFAULT_V2_PARAMS.max_gross_exposure_btc_pct
            if symbol == "BTC-USD"
            else DEFAULT_V2_PARAMS.max_gross_exposure_eth_pct
        )
        return (self._paper_engine.balance * max_exp_pct / 100.0) / max(entry_limit, 1e-9)

    def _write_runtime_state(self) -> None:
        symbols = {}
        for symbol in self.SYMBOLS:
            bars, bid, ask, current_price, _ = self._latest_snapshots.get(symbol, ([], 0.0, 0.0, 0.0, []))
            history = [
                {"ts": datetime.fromtimestamp(b.ts, tz=timezone.utc).isoformat(), "price": b.close}
                for b in bars[-180:]
            ]
            symbols[symbol] = {
                "price": current_price,
                "drop_pct": BarBuilder.return_pct(bars, 180),
                "zscore": BarBuilder.zscore(bars),
                "spread_bps": BarBuilder.current_spread_bps(bid, ask),
                "history": history,
            }
        payload = {
            "status": "running",
            "started_at": self._started_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "mode": {
                "trading_enabled": True,
                "paper_mode": self.config.get("mode", "paper") == "paper",
                "enable_live_trading": self.config.get("mode", "paper") == "live",
                "live_supported": self.LIVE_SUPPORTED,
                "live_armed": self._live_enabled,
            },
            "version": "v2",
            "event_count": self._events.count(),
            "account": {
                "starting_balance": self._paper_engine.start_balance,
                "balance": self._paper_engine.balance,
                "realized_pnl": round(self.current_pnl(), 4),
            },
            "position": self._live_position if self.config.get("mode", "paper") == "live" else self._paper_engine.position,
            "active_position": self._live_position if self.config.get("mode", "paper") == "live" else self._paper_engine.position,
            "positions": ([self._live_position] if self._live_position else []) if self.config.get("mode", "paper") == "live" else list(self._paper_engine.positions.values()),
            "symbols": symbols,
            "trades": (self._live_trades[-50:] if self.config.get("mode", "paper") == "live" else self._paper_engine.trades[-50:]),
            "stats": {
                "trades_closed": len(self._live_trades) if self.config.get("mode", "paper") == "live" else len(self._paper_engine.trades),
            },
            "live": {
                "health_error": self._live_health_error,
                "pending_entry_order": self._live_entry_order,
            },
        }
        self._runtime_store.write(payload)
