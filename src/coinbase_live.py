from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Optional

from coinbase.rest import RESTClient


@dataclass
class OrderInfo:
    order_id: str
    status: str
    filled_size: float
    average_filled_price: float


class CoinbaseLiveClient:
    def __init__(self, api_key: str, api_secret: str):
        self._client = RESTClient(api_key=api_key, api_secret=api_secret)
        self._product_cache: dict[str, dict] = {}

    def _product(self, product_id: str) -> dict:
        if product_id not in self._product_cache:
            result = self._client.get_product(product_id=product_id)
            if isinstance(result, dict):
                self._product_cache[product_id] = result
            else:
                self._product_cache[product_id] = result.__dict__
        return self._product_cache[product_id]

    def _format_size(self, product_id: str, size: float) -> str:
        product = self._product(product_id)
        inc = product.get("base_increment") or "0.00000001"
        qty = Decimal(str(size)).quantize(Decimal(inc), rounding=ROUND_DOWN)
        if qty <= 0:
            return "0"
        return format(qty, "f")

    def _format_price(self, product_id: str, price: float) -> str:
        product = self._product(product_id)
        inc = product.get("quote_increment") or "0.01"
        p = Decimal(str(price)).quantize(Decimal(inc), rounding=ROUND_DOWN)
        if p <= 0:
            return "0"
        return format(p, "f")

    def limit_buy_gtc(self, product_id: str, size: float, limit_price: float, post_only: bool = True) -> Optional[str]:
        size_str = self._format_size(product_id, size)
        price_str = self._format_price(product_id, limit_price)
        if size_str == "0" or price_str == "0":
            return None
        resp = self._client.limit_order_gtc_buy(
            client_order_id="",
            product_id=product_id,
            base_size=size_str,
            limit_price=price_str,
            post_only=post_only,
        )
        return self._extract_order_id(resp)

    def limit_sell_gtc(self, product_id: str, size: float, limit_price: float, post_only: bool = True) -> Optional[str]:
        size_str = self._format_size(product_id, size)
        price_str = self._format_price(product_id, limit_price)
        if size_str == "0" or price_str == "0":
            return None
        resp = self._client.limit_order_gtc_sell(
            client_order_id="",
            product_id=product_id,
            base_size=size_str,
            limit_price=price_str,
            post_only=post_only,
        )
        return self._extract_order_id(resp)

    def limit_sell_ioc(self, product_id: str, size: float, limit_price: float) -> Optional[str]:
        size_str = self._format_size(product_id, size)
        price_str = self._format_price(product_id, limit_price)
        if size_str == "0" or price_str == "0":
            return None
        resp = self._client.limit_order_ioc_sell(
            client_order_id="",
            product_id=product_id,
            base_size=size_str,
            limit_price=price_str,
        )
        return self._extract_order_id(resp)

    def stop_limit_sell_gtc(
        self,
        product_id: str,
        size: float,
        stop_price: float,
        limit_price: float,
    ) -> Optional[str]:
        size_str = self._format_size(product_id, size)
        stop_str = self._format_price(product_id, stop_price)
        limit_str = self._format_price(product_id, limit_price)
        if size_str == "0" or stop_str == "0" or limit_str == "0":
            return None
        resp = self._client.stop_limit_order_gtc_sell(
            client_order_id="",
            product_id=product_id,
            base_size=size_str,
            limit_price=limit_str,
            stop_price=stop_str,
            stop_direction="STOP_DIRECTION_STOP_DOWN",
        )
        return self._extract_order_id(resp)

    def get_order(self, order_id: str) -> Optional[OrderInfo]:
        resp = self._client.get_order(order_id=order_id)
        order = getattr(resp, "order", None)
        if order is None:
            return None
        status = str(getattr(order, "status", "")).upper()
        filled_size = float(getattr(order, "filled_size", 0.0) or 0.0)
        avg = getattr(order, "average_filled_price", 0.0) or 0.0
        try:
            avg_price = float(avg)
        except (TypeError, ValueError):
            avg_price = 0.0
        return OrderInfo(order_id=order.order_id, status=status, filled_size=filled_size, average_filled_price=avg_price)

    def cancel_order(self, order_id: str) -> None:
        self._client.cancel_orders(order_ids=[order_id])

    @staticmethod
    def _extract_order_id(resp: object) -> Optional[str]:
        order_id = getattr(resp, "order_id", None)
        if order_id:
            return order_id
        success = getattr(resp, "success_response", None)
        if success is not None:
            return getattr(success, "order_id", None)
        return None
