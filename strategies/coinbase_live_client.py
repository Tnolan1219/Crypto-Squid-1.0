from __future__ import annotations

import uuid
from dataclasses import dataclass

from coinbase.rest import RESTClient


def _to_dict(obj) -> dict:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict"):
        try:
            out = obj.to_dict()
            return out if isinstance(out, dict) else {}
        except Exception:
            return {}
    data = getattr(obj, "__dict__", None)
    return data if isinstance(data, dict) else {}


def _order_payload(resp) -> dict:
    data = _to_dict(resp)
    if data.get("order"):
        nested = _to_dict(data.get("order"))
        return nested if nested else data
    nested = _to_dict(getattr(resp, "order", None))
    return nested if nested else data


@dataclass
class LiveOrderResult:
    ok: bool
    order_id: str
    client_order_id: str
    status: str
    details: dict


class CoinbaseLiveClient:
    def __init__(self, api_key_name: str, private_key: str):
        self._client = RESTClient(api_key=api_key_name, api_secret=private_key)

    def healthy(self) -> tuple[bool, str]:
        try:
            self._client.get_products(limit=1)
            return True, "ok"
        except Exception as exc:
            return False, str(exc)

    def place_entry_gtc_buy(self, symbol: str, size: float, limit_price: float, post_only: bool = True) -> LiveOrderResult:
        cid = str(uuid.uuid4())
        resp = self._client.limit_order_gtc_buy(
            client_order_id=cid,
            product_id=symbol,
            base_size=f"{size:.8f}",
            limit_price=f"{limit_price:.8f}",
            post_only=post_only,
        )
        payload = _order_payload(resp)
        order_id = str(payload.get("order_id") or payload.get("orderId") or payload.get("id") or "")
        status = str(payload.get("status") or payload.get("order_status") or "submitted")
        return LiveOrderResult(ok=bool(order_id), order_id=order_id, client_order_id=cid, status=status, details=payload)

    def place_exit_ioc_sell(self, symbol: str, size: float, limit_price: float) -> LiveOrderResult:
        cid = str(uuid.uuid4())
        resp = self._client.limit_order_ioc_sell(
            client_order_id=cid,
            product_id=symbol,
            base_size=f"{size:.8f}",
            limit_price=f"{limit_price:.8f}",
        )
        payload = _order_payload(resp)
        order_id = str(payload.get("order_id") or payload.get("orderId") or payload.get("id") or "")
        status = str(payload.get("status") or payload.get("order_status") or "submitted")
        return LiveOrderResult(ok=bool(order_id), order_id=order_id, client_order_id=cid, status=status, details=payload)

    def get_order(self, order_id: str) -> dict:
        resp = self._client.get_order(order_id)
        payload = _order_payload(resp)
        payload["order_id"] = str(payload.get("order_id") or payload.get("orderId") or order_id)
        return payload

    def cancel(self, order_id: str) -> bool:
        try:
            self._client.cancel_orders([order_id])
            return True
        except Exception:
            return False
