"""Localhost dashboard for Crypto Squid runtime monitoring."""

from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv
from coinbase_reporting import CoinbaseReportingClient


ROOT = Path(__file__).parent.parent
RUNTIME_STATE_PATH = ROOT / "data" / "trades" / "runtime_state.json"
RUNTIME_CONTROL_PATH = ROOT / "data" / "control" / "runtime_control.json"
HTML_PATH = Path(__file__).parent / "dashboard.html"

load_dotenv(ROOT / ".env")
REPORTING = CoinbaseReportingClient()


def _engine_running(state: dict) -> bool:
    updated = state.get("updated_at")
    if not updated:
        return False
    try:
        ts = updated.replace("Z", "+00:00")
        now = int(time.time())
        from datetime import datetime

        then = int(datetime.fromisoformat(ts).timestamp())
        return (now - then) <= 20
    except Exception:
        try:
            return (time.time() - RUNTIME_STATE_PATH.stat().st_mtime) <= 20
        except Exception:
            return False


def _control_token() -> str:
    return os.getenv("CONTROL_API_TOKEN", "").strip()


def _read_state() -> dict:
    if not RUNTIME_STATE_PATH.exists():
        return {
            "status": "waiting_for_bot",
            "message": "No runtime state yet. Start `python src/bot.py` first.",
            "trades": [],
            "symbols": {},
        }
    try:
        return json.loads(RUNTIME_STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "status": "invalid_state",
            "message": "runtime_state.json is currently being written. Retry in 1-2 seconds.",
            "trades": [],
            "symbols": {},
        }


def _read_control() -> dict:
    if not RUNTIME_CONTROL_PATH.exists():
        return {"trading_enabled": True, "reason": "default", "updated_at_unix": 0}
    try:
        payload = json.loads(RUNTIME_CONTROL_PATH.read_text(encoding="utf-8"))
        return {
            "trading_enabled": bool(payload.get("trading_enabled", True)),
            "reason": str(payload.get("reason", "manual")),
            "updated_at_unix": int(payload.get("updated_at_unix", 0)),
        }
    except Exception:
        return {"trading_enabled": True, "reason": "invalid_control_file", "updated_at_unix": 0}


def _write_control(enabled: bool, reason: str) -> dict:
    RUNTIME_CONTROL_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "trading_enabled": bool(enabled),
        "reason": reason,
        "updated_at_unix": int(time.time()),
    }
    temp = RUNTIME_CONTROL_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    temp.replace(RUNTIME_CONTROL_PATH)
    return payload


class DashboardHandler(BaseHTTPRequestHandler):
    def _authorized(self) -> bool:
        token = _control_token()
        if not token:
            return False
        auth_header = self.headers.get("Authorization", "")
        if auth_header == f"Bearer {token}":
            return True
        query = parse_qs(urlparse(self.path).query)
        query_token = (query.get("token") or [""])[0]
        return query_token == token

    def _json(self, body: dict, status: int = 200) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _html(self, html: str) -> None:
        payload = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            state = _read_state()
            coinbase = REPORTING.snapshot().payload
            self._json(
                {
                    "status": "ok",
                    "runtime_state_exists": RUNTIME_STATE_PATH.exists(),
                    "control_token_configured": bool(_control_token()),
                    "engine_running": _engine_running(state),
                    "coinbase_reporting_ok": bool(coinbase.get("ok")),
                }
            )
            return
        if path == "/snapshot":
            state = _read_state()
            self._json(
                {
                    "state": state,
                    "control": _read_control(),
                    "coinbase": REPORTING.snapshot().payload,
                    "engine_running": _engine_running(state),
                }
            )
            return
        if path == "/api/state":
            self._json(_read_state())
            return
        if path == "/control/status":
            if not self._authorized():
                self._json({"error": "unauthorized"}, status=401)
                return
            self._json(_read_control())
            return
        if path == "/control/start":
            if not self._authorized():
                self._json({"error": "unauthorized"}, status=401)
                return
            self._json(_write_control(True, reason="remote_start"))
            return
        if path == "/control/stop":
            if not self._authorized():
                self._json({"error": "unauthorized"}, status=401)
                return
            self._json(_write_control(False, reason="remote_stop"))
            return
        if path == "/":
            self._html(HTML_PATH.read_text(encoding="utf-8"))
            return
        self._json({"error": "not_found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/control/start", "/control/stop"}:
            if not self._authorized():
                self._json({"error": "unauthorized"}, status=401)
                return
            enabled = path.endswith("start")
            reason = "remote_start" if enabled else "remote_stop"
            self._json(_write_control(enabled, reason=reason))
            return
        self._json({"error": "not_found"}, status=404)

    def log_message(self, format: str, *args) -> None:
        return


def main(host: str = "127.0.0.1", port: int = 8787) -> None:
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"Dashboard running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    host = os.getenv("DASHBOARD_HOST", "127.0.0.1")
    port = int(os.getenv("DASHBOARD_PORT", "8787"))
    main(host=host, port=port)
