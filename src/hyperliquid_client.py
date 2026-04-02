"""Hyperliquid market data and optional live execution wrappers."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Awaitable, Callable, Optional

import structlog
import websockets

from config import Config

log = structlog.get_logger()


class HyperliquidMarketData:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._running = False

    async def run(self, on_trade: Callable[[str, float, float, float], Awaitable[None]]) -> None:
        self._running = True
        backoff = 1
        while self._running:
            try:
                log.info("ws.connect", url=self.cfg.ws_base_url)
                async with websockets.connect(self.cfg.ws_base_url, ping_interval=20) as ws:
                    await self._subscribe(ws)
                    backoff = 1
                    async for raw in ws:
                        if not self._running:
                            break
                        await self._handle_message(raw, on_trade)
            except (websockets.ConnectionClosed, OSError, TimeoutError) as exc:
                log.warning("ws.disconnected", error=str(exc), retry_in=backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 20)

    def stop(self) -> None:
        self._running = False

    async def _subscribe(self, ws: websockets.WebSocketClientProtocol) -> None:
        for symbol in self.cfg.symbols:
            payload = {
                "method": "subscribe",
                "subscription": {
                    "type": "trades",
                    "coin": symbol,
                },
            }
            await ws.send(json.dumps(payload))

    async def _handle_message(
        self,
        raw: str,
        on_trade: Callable[[str, float, float, float], Awaitable[None]],
    ) -> None:
        msg = json.loads(raw)
        channel = msg.get("channel") or msg.get("topic")
        if channel != "trades":
            return
        data = msg.get("data")
        if not isinstance(data, list):
            return

        for event in data:
            symbol = str(event.get("coin", "")).upper()
            if symbol not in self.cfg.symbols:
                continue
            px = event.get("px") if event.get("px") is not None else event.get("price")
            sz = event.get("sz") if event.get("sz") is not None else event.get("size")
            ts_ms = event.get("time") or event.get("timestamp")
            if px is None or sz is None:
                continue
            ts = float(ts_ms) / 1000.0 if ts_ms is not None else time.time()
            await on_trade(symbol, ts, float(px), float(sz))


class HyperliquidLiveClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._info = None
        self._exchange = None
        self.account_address = cfg.hyperliquid_account_address
        self._ready_error = ""
        self._init_client()

    def healthy(self) -> tuple[bool, str]:
        if self._exchange is None or self._info is None:
            return False, self._ready_error or "live_client_not_initialized"
        return True, ""

    def place_limit_order(self, symbol: str, is_buy: bool, size: float, price: float, reduce_only: bool = False) -> Optional[str]:
        ok, _ = self.healthy()
        if not ok:
            return None

        response = self._exchange.order(
            symbol,
            is_buy,
            size,
            price,
            {"limit": {"tif": "Gtc"}},
            reduce_only=reduce_only,
        )
        return self._extract_order_id(response)

    def cancel_order(self, symbol: str, order_id: str) -> None:
        ok, _ = self.healthy()
        if not ok:
            return
        self._exchange.cancel(symbol, int(order_id))

    def order_status(self, user: str, order_id: str) -> Optional[str]:
        ok, _ = self.healthy()
        if not ok:
            return None
        response = self._info.query_order_by_oid(user, int(order_id))
        return self._extract_status(response)

    def _init_client(self) -> None:
        if not self.cfg.hyperliquid_secret_key:
            self._ready_error = "HYPERLIQUID_SECRET_KEY missing"
            return
        try:
            from eth_account import Account
            from hyperliquid.exchange import Exchange
            from hyperliquid.info import Info
            from hyperliquid.utils import constants
        except Exception as exc:
            self._ready_error = f"hyperliquid_sdk_unavailable: {exc}"
            return

        api_url = constants.TESTNET_API_URL if self.cfg.use_testnet else constants.MAINNET_API_URL
        wallet = Account.from_key(self.cfg.hyperliquid_secret_key)
        account_address = self.cfg.hyperliquid_account_address or wallet.address
        self.account_address = account_address
        try:
            self._info = Info(api_url, skip_ws=True)
            self._exchange = Exchange(wallet, api_url, account_address=account_address)
        except Exception as exc:
            self._ready_error = f"live_client_init_failed: {exc}"

    @staticmethod
    def _extract_order_id(response: object) -> Optional[str]:
        if not isinstance(response, dict):
            return None
        statuses = (
            response.get("response", {})
            .get("data", {})
            .get("statuses", [])
        )
        if not statuses:
            return None
        first = statuses[0]
        if "resting" in first:
            return str(first["resting"].get("oid"))
        if "filled" in first:
            return str(first["filled"].get("oid"))
        return None

    @staticmethod
    def _extract_status(response: object) -> Optional[str]:
        if not isinstance(response, dict):
            return None
        status = response.get("status")
        if isinstance(status, str):
            return status.upper()
        order = response.get("order", {})
        if isinstance(order, dict) and isinstance(order.get("status"), str):
            return order["status"].upper()
        return None
