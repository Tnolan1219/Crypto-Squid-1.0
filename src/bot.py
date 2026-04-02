"""Crypto Squid — Coinbase paper trading bot loop."""

import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from market_data import get_price
from paper_engine import PaperEngine
from risk import position_size
from runtime_store import RuntimeStore
from strategy import check_entry
from trade_history import TradeHistoryStore
from tracker import MarketTracker


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _mode_from_env() -> dict:
    return {
        "trading_enabled": _as_bool(os.getenv("TRADING_ENABLED", "true"), default=True),
        "log_only": _as_bool(os.getenv("LOG_ONLY", "true"), default=True),
        "paper_mode": _as_bool(os.getenv("PAPER_MODE", "false"), default=False),
        "enable_live_trading": _as_bool(os.getenv("ENABLE_LIVE_TRADING", "false"), default=False),
        "use_testnet": _as_bool(os.getenv("USE_TESTNET", "true"), default=True),
    }


def _leverage_factor_from_env() -> float:
    try:
        value = float(os.getenv("PAPER_LEVERAGE_FACTOR", "1.0"))
    except ValueError:
        return 1.0
    return max(value, 1.0)


def _stats_from_trades(trades: list[dict]) -> dict:
    wins = sum(1 for trade in trades if trade.get("pnl", 0.0) > 0)
    losses = sum(1 for trade in trades if trade.get("pnl", 0.0) < 0)
    total = len(trades)
    pnl_values = [trade.get("pnl", 0.0) for trade in trades]
    gross_profit = sum(pnl for pnl in pnl_values if pnl > 0)
    gross_loss = abs(sum(pnl for pnl in pnl_values if pnl < 0))
    realized_pnl = sum(pnl_values)
    return {
        "trades_closed": total,
        "wins": wins,
        "losses": losses,
        "win_rate_pct": (wins / total * 100.0) if total else 0.0,
        "expectancy_usd_per_trade": (realized_pnl / total) if total else 0.0,
        "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0),
    }


def _build_state(
    trackers: dict,
    prices: dict,
    engine: PaperEngine,
    active_symbol: str | None,
    started_at: str,
    mode: dict,
    leverage_factor: float,
) -> dict:
    symbols = {}
    for symbol, tracker in trackers.items():
        symbol_history = [
            {"ts": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(), "price": price}
            for ts, price in zip(tracker.timestamps, tracker.prices)
        ]
        symbols[symbol] = {
            "price": prices.get(symbol),
            "drop_pct": tracker.get_drop_pct(),
            "zscore": tracker.get_zscore(),
            "history": symbol_history,
        }

    realized_pnl = engine.balance - engine.start_balance
    active_position = None
    unrealized_pnl = 0.0
    if engine.position and active_symbol:
        mark_price = prices.get(active_symbol)
        if mark_price is not None:
            unrealized_pnl = (mark_price - engine.position["entry"]) * engine.position["size"]
        active_position = {
            **engine.position,
            "symbol": active_symbol,
            "age_minutes": engine.position_age_minutes(),
            "mark_price": mark_price,
            "unrealized_pnl": unrealized_pnl,
        }

    total_pnl = realized_pnl + unrealized_pnl
    leveraged_total_pnl = total_pnl * leverage_factor
    account = {
        "starting_balance": engine.start_balance,
        "balance": engine.balance,
        "realized_pnl": realized_pnl,
        "realized_pnl_pct": (realized_pnl / engine.start_balance * 100.0) if engine.start_balance else 0.0,
        "unrealized_pnl": unrealized_pnl,
        "total_pnl": total_pnl,
        "total_pnl_pct": (total_pnl / engine.start_balance * 100.0) if engine.start_balance else 0.0,
        "leverage_factor": leverage_factor,
        "leveraged_total_pnl": leveraged_total_pnl,
        "leveraged_total_pnl_pct": (leveraged_total_pnl / engine.start_balance * 100.0) if engine.start_balance else 0.0,
    }

    return {
        "started_at": started_at,
        "mode": mode,
        "account": account,
        "active_position": active_position,
        "symbols": symbols,
        "stats": _stats_from_trades(engine.trades),
        "trades": engine.trades[-100:],
    }

SYMBOLS = ["BTC-USD", "ETH-USD"]
MAX_HOLD_MINUTES = 90

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

trackers = {s: MarketTracker() for s in SYMBOLS}
engine = PaperEngine(balance=1000.0)
runtime_store = RuntimeStore(ROOT)
trade_history = TradeHistoryStore(ROOT)
trade_history.sync_existing()
mode = _mode_from_env()
leverage_factor = _leverage_factor_from_env()
started_at = datetime.now(timezone.utc).isoformat()
strategy_version = os.getenv("STRATEGY_VERSION", "coinbase-paper-v1")

# Active symbol being traded (one position max)
active_symbol = None

print("=== CRYPTO SQUID — PAPER MODE ===")
print(f"Symbols: {SYMBOLS}")
print(f"Balance: {engine.balance:.2f}")
print("Watching for panic flush signals...\n")

while True:
    try:
        prices = {}
        for symbol in SYMBOLS:
            price = get_price(symbol)
            prices[symbol] = price
            trackers[symbol].update(price)

            drop = trackers[symbol].get_drop_pct()
            z = trackers[symbol].get_zscore()

            print(f"{symbol}  {price:.2f}  drop={drop:+.2f}%  z={z:.2f}", flush=True)

            # --- Exit logic ---
            if engine.position and active_symbol == symbol:
                if engine.position_age_minutes() >= MAX_HOLD_MINUTES:
                    trade = engine.exit(price, "TIME_STOP")
                    if trade:
                        trade_history.write_trade(trade, strategy_version=strategy_version)
                    active_symbol = None
                elif price <= engine.position["stop"]:
                    trade = engine.exit(price, "SL")
                    if trade:
                        trade_history.write_trade(trade, strategy_version=strategy_version)
                    active_symbol = None
                elif price >= engine.position["tp"]:
                    trade = engine.exit(price, "TP")
                    if trade:
                        trade_history.write_trade(trade, strategy_version=strategy_version)
                    active_symbol = None

            # --- Entry logic ---
            if engine.position is None:
                if check_entry(symbol, drop, z):
                    entry = price * 0.9995   # limit 0.05% below signal
                    stop = price * 0.995     # stop 0.5% below
                    tp_pct = 1.01 if symbol == "BTC-USD" else 1.012
                    tp = price * tp_pct
                    size = position_size(engine.balance, entry, stop)
                    if size > 0:
                        engine.enter(symbol, entry, size, stop, tp, drop, z)
                        active_symbol = symbol

        runtime_store.write(
            _build_state(
                trackers=trackers,
                prices=prices,
                engine=engine,
                active_symbol=active_symbol,
                started_at=started_at,
                mode=mode,
                leverage_factor=leverage_factor,
            )
        )

        time.sleep(2)

    except KeyboardInterrupt:
        print("\nBot stopped.")
        print(f"Final balance: {engine.balance:.2f}")
        print(f"Trades closed: {len(engine.trades)}")
        break
    except Exception as e:
        print(f"ERROR: {e}")
        time.sleep(5)
