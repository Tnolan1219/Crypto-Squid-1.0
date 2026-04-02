"""
Coinbase Advanced Trade WebSocket client.

Subscribes to:
  - market_trades  → trade ticks (price, size, side)
  - level2         → best bid/ask for spread calculation

Runs in a background thread. Callbacks are thread-safe via the GIL.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Callable, Optional

import structlog
from coinbase.websocket import WSClient
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
log = structlog.get_logger("coinbase_ws")

# ── Book state per symbol (top-of-book only) ──────────────────────────────────
_TOP_BOOK: dict[str, dict[str, float]] = {}   # symbol → {bid: float, ask: float}
_BOOK_LOCK = threading.Lock()


def _update_book(symbol: str, updates: list[dict]) -> tuple[float, float]:
    with _BOOK_LOCK:
        book = _TOP_BOOK.setdefault(symbol, {"bid": 0.0, "ask": 0.0})
        for u in updates:
            side = u.get("side", "")
            price = float(u.get("price_level") or u.get("price") or 0)
            qty = float(u.get("new_quantity") or u.get("qty") or 0)
            if side in {"bid", "buy"}:
                if qty > 0:
                    book["bid"] = max(book["bid"], price)
                else:
                    book["bid"] = price  # snapshot entry replaces
            elif side in {"offer", "ask", "sell"}:
                if qty > 0:
                    book["ask"] = price if book["ask"] == 0 else min(book["ask"], price)
                else:
                    book["ask"] = price
        return book["bid"], book["ask"]


class CoinbaseWS:
    """
    Wraps coinbase-advanced-py WSClient.

    Parameters
    ----------
    symbols : list of Coinbase product IDs, e.g. ["BTC-USD", "ETH-USD"]
    on_trade : callback(symbol, price, size, side) — called for each trade tick
    on_spread : callback(symbol, bid, ask) — called when top-of-book updates
    """

    def __init__(
        self,
        symbols: list[str],
        on_trade: Callable[[str, float, float, str], None],
        on_spread: Callable[[str, float, float], None],
    ):
        self._symbols = symbols
        self._on_trade = on_trade
        self._on_spread = on_spread
        self._connected = threading.Event()
        self._client: Optional[WSClient] = None

    def start(self) -> None:
        self._client = WSClient(
            api_key=os.getenv("COINBASE_API_KEY_NAME", ""),
            api_secret=os.getenv("COINBASE_PRIVATE_KEY", ""),
            on_message=self._dispatch,
            on_open=self._on_open,
            on_close=self._on_close,
            retry=True,
        )
        self._client.open()
        self._connected.wait(timeout=10)
        self._client.subscribe(
            product_ids=self._symbols,
            channels=["market_trades", "level2"],
        )
        log.info("ws.subscribed", symbols=self._symbols)

    def stop(self) -> None:
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass

    def _on_open(self) -> None:
        self._connected.set()
        log.info("ws.connected")

    def _on_close(self) -> None:
        log.warning("ws.disconnected")

    def _dispatch(self, msg: str) -> None:
        try:
            data = json.loads(msg)
        except (json.JSONDecodeError, TypeError):
            return

        channel = data.get("channel", "")
        events = data.get("events") or []

        if channel == "market_trades":
            for event in events:
                for trade in event.get("trades", []):
                    symbol = trade.get("product_id", "")
                    if symbol not in self._symbols:
                        continue
                    try:
                        price = float(trade["price"])
                        size = float(trade["size"])
                        side = str(trade.get("side", "BUY")).upper()
                        self._on_trade(symbol, price, size, side)
                    except (KeyError, ValueError):
                        pass

        elif channel in {"l2_data", "level2"}:
            for event in events:
                symbol = event.get("product_id", "")
                if symbol not in self._symbols:
                    continue
                updates = event.get("updates", [])
                if updates:
                    bid, ask = _update_book(symbol, updates)
                    if bid > 0 and ask > 0:
                        self._on_spread(symbol, bid, ask)
