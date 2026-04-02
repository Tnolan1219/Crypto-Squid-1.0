"""Localhost dashboard for Crypto Squid runtime monitoring."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).parent.parent
RUNTIME_STATE_PATH = ROOT / "data" / "trades" / "runtime_state.json"
HTML_PATH = Path(__file__).parent / "dashboard.html"


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


class DashboardHandler(BaseHTTPRequestHandler):
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
        if path == "/api/state":
            self._json(_read_state())
            return
        if path == "/":
            self._html(HTML_PATH.read_text(encoding="utf-8"))
            return
        self._json({"error": "not_found"}, status=404)

    def log_message(self, _format: str, *_args) -> None:
        return


def main(host: str = "127.0.0.1", port: int = 8787) -> None:
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"Dashboard running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
