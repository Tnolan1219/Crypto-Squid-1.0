from __future__ import annotations

from datetime import datetime, timezone

import requests


class NOAAClient:
    BASE_URL = "https://api.weather.gov"

    def __init__(self, timeout_seconds: int = 10):
        self.timeout_seconds = timeout_seconds

    def get_forecast_point(self, lat: float, lon: float) -> dict:
        point_resp = requests.get(
            f"{self.BASE_URL}/points/{lat},{lon}",
            headers={"User-Agent": "cryptosquid/1.0"},
            timeout=self.timeout_seconds,
        )
        point_resp.raise_for_status()
        forecast_url = point_resp.json().get("properties", {}).get("forecast")
        if not forecast_url:
            return self._empty()

        forecast_resp = requests.get(
            forecast_url,
            headers={"User-Agent": "cryptosquid/1.0"},
            timeout=self.timeout_seconds,
        )
        forecast_resp.raise_for_status()
        periods = forecast_resp.json().get("properties", {}).get("periods", [])
        if not periods:
            return self._empty()
        first = periods[0]
        return {
            "temperature": first.get("temperature"),
            "precip_probability": (first.get("probabilityOfPrecipitation") or {}).get("value"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _empty(self) -> dict:
        return {
            "temperature": None,
            "precip_probability": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
