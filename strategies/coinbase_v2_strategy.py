from __future__ import annotations

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
from event_collector import EventCollector
from paper_engine_v2 import PaperEngineV2
from params_v2 import DEFAULT_V2_PARAMS
from risk import position_size
from runtime_store import RuntimeStore
from signal_v2 import SignalEngineV2
from trade_history import TradeHistoryStore


class CoinbaseV2Strategy(Strategy):
    SYMBOLS = ["BTC-USD", "ETH-USD"]
    LIVE_SUPPORTED = False

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
        self._started = False
        self._started_at = datetime.now(timezone.utc).isoformat()
        self._strategy_version = "coinbase-v2-paper"
        self._last_start_attempt = 0.0

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
        if mode == "live" and not self.LIVE_SUPPORTED:
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
            "mode": {
                "trading_enabled": True,
                "paper_mode": self.config.get("mode", "paper") == "paper",
                "enable_live_trading": self.config.get("mode", "paper") == "live",
                "live_supported": self.LIVE_SUPPORTED,
            },
            "version": "v2",
            "event_count": self._events.count(),
            "account": {
                "starting_balance": self._paper_engine.start_balance,
                "balance": self._paper_engine.balance,
                "realized_pnl": round(self.current_pnl(), 4),
            },
            "position": self._paper_engine.position,
            "active_position": self._paper_engine.position,
            "positions": list(self._paper_engine.positions.values()),
            "symbols": symbols,
            "trades": self._paper_engine.trades[-50:],
            "stats": {
                "trades_closed": len(self._paper_engine.trades),
            },
        }
        self._runtime_store.write(payload)
