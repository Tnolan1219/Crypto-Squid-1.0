from __future__ import annotations

import os
import time
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


def _as_float(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


@dataclass
class CoinbaseReport:
    ok: bool
    payload: dict


class CoinbaseReportingClient:
    def __init__(self):
        self._enabled = os.getenv("COINBASE_REPORTING_ENABLED", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self._cache_seconds = int(float(os.getenv("COINBASE_REPORTING_CACHE_SECONDS", "10")))
        self._last_ts = 0.0
        self._last_payload: dict = {
            "ok": False,
            "enabled": self._enabled,
            "reason": "not_polled",
        }
        self._client: RESTClient | None = None

        api_key = os.getenv("COINBASE_API_KEY_NAME", "").strip()
        private_key = os.getenv("COINBASE_PRIVATE_KEY", "").strip()
        if self._enabled and api_key and private_key:
            self._client = RESTClient(api_key=api_key, api_secret=private_key)

    def snapshot(self) -> CoinbaseReport:
        now = time.time()
        if now - self._last_ts < self._cache_seconds:
            return CoinbaseReport(ok=bool(self._last_payload.get("ok")), payload=self._last_payload)

        self._last_ts = now

        if not self._enabled:
            self._last_payload = {"ok": False, "enabled": False, "reason": "disabled"}
            return CoinbaseReport(ok=False, payload=self._last_payload)

        if self._client is None:
            self._last_payload = {
                "ok": False,
                "enabled": True,
                "reason": "missing_api_credentials",
            }
            return CoinbaseReport(ok=False, payload=self._last_payload)

        try:
            btc_px = _as_float(_to_dict(self._client.get_product("BTC-USD")).get("price"))
            eth_px = _as_float(_to_dict(self._client.get_product("ETH-USD")).get("price"))

            raw_accounts = _to_dict(self._client.get_accounts(limit=250))
            accounts = raw_accounts.get("accounts") or raw_accounts.get("data") or []

            balances: dict[str, float] = {}
            for item in accounts:
                d = _to_dict(item)
                ccy = str(d.get("currency") or "").upper()
                if not ccy:
                    continue
                available = _as_float(d.get("available_balance", {}).get("value") if isinstance(d.get("available_balance"), dict) else d.get("available_balance"))
                hold = _as_float(d.get("hold", {}).get("value") if isinstance(d.get("hold"), dict) else d.get("hold"))
                balances[ccy] = balances.get(ccy, 0.0) + available + hold

            usd = balances.get("USD", 0.0)
            btc = balances.get("BTC", 0.0)
            eth = balances.get("ETH", 0.0)
            est_usd = usd + btc * btc_px + eth * eth_px

            open_orders: list[dict] = []
            try:
                order_resp = _to_dict(
                    self._client.list_orders(
                        product_ids=["BTC-USD", "ETH-USD"],
                        order_status=["OPEN", "PENDING"],
                        limit=50,
                    )
                )
            except Exception:
                order_resp = _to_dict(self._client.list_orders(product_ids=["BTC-USD", "ETH-USD"], limit=50))

            for item in order_resp.get("orders") or order_resp.get("data") or []:
                d = _to_dict(item)
                status = str(d.get("status") or d.get("order_status") or "").upper()
                if status and status not in {"OPEN", "PENDING", "ACTIVE"}:
                    continue
                cfg = _to_dict(d.get("order_configuration"))
                open_orders.append(
                    {
                        "order_id": str(d.get("order_id") or d.get("id") or ""),
                        "product_id": str(d.get("product_id") or ""),
                        "side": str(d.get("side") or ""),
                        "status": status or "UNKNOWN",
                        "created_time": str(d.get("created_time") or d.get("created_at") or ""),
                        "limit_price": str(cfg.get("limit_limit_gtc", {}).get("limit_price") if isinstance(cfg.get("limit_limit_gtc"), dict) else d.get("limit_price") or ""),
                        "base_size": str(cfg.get("limit_limit_gtc", {}).get("base_size") if isinstance(cfg.get("limit_limit_gtc"), dict) else d.get("base_size") or d.get("filled_size") or ""),
                    }
                )

            fills_resp = _to_dict(self._client.get_fills(product_ids=["BTC-USD", "ETH-USD"], limit=25))
            fills: list[dict] = []
            for item in fills_resp.get("fills") or fills_resp.get("data") or []:
                d = _to_dict(item)
                fills.append(
                    {
                        "product_id": str(d.get("product_id") or ""),
                        "side": str(d.get("side") or ""),
                        "price": str(d.get("price") or ""),
                        "size": str(d.get("size") or d.get("base_size") or ""),
                        "commission": str(d.get("commission") or ""),
                        "trade_time": str(d.get("trade_time") or d.get("created_time") or ""),
                    }
                )

            self._last_payload = {
                "ok": True,
                "enabled": True,
                "as_of_unix": int(now),
                "prices": {"BTC-USD": btc_px, "ETH-USD": eth_px},
                "balances": {"USD": usd, "BTC": btc, "ETH": eth},
                "estimated_total_usd": round(est_usd, 2),
                "open_orders_count": len(open_orders),
                "open_orders": open_orders[:20],
                "recent_fills": fills[:20],
            }
            return CoinbaseReport(ok=True, payload=self._last_payload)
        except Exception as exc:
            self._last_payload = {
                "ok": False,
                "enabled": True,
                "reason": f"report_failed:{exc}",
            }
            return CoinbaseReport(ok=False, payload=self._last_payload)
