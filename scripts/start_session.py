"""
CRYPTO SQUID — Single-command session launcher.

Starts the dashboard HTTP server and the trading bot in parallel,
then opens the dashboard in the default browser.

Usage:
    python scripts/start_session.py

Stop:
    Ctrl+C  — cleanly terminates both processes.
"""

from __future__ import annotations

import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable
SRC = ROOT / "src"

DASHBOARD_URL = "http://127.0.0.1:8787"


def _launch(script: Path, label: str) -> subprocess.Popen:
    proc = subprocess.Popen(
        [PYTHON, str(script)],
        cwd=str(ROOT),
    )
    print(f"[start] {label}  (pid={proc.pid})")
    return proc


def main() -> None:
    print("=" * 52)
    print("  CRYPTO SQUID — PAPER TRADING SESSION STARTING")
    print("=" * 52)

    # 1. Start dashboard server
    dash = _launch(SRC / "dashboard.py", "dashboard")

    # 2. Wait briefly then open browser
    time.sleep(1.5)
    print(f"[start] Opening dashboard at {DASHBOARD_URL}")
    webbrowser.open(DASHBOARD_URL)

    # 3. Start trading bot (it has its own 30-second warmup)
    bot = _launch(SRC / "bot_v2.py", "bot_v2")

    print()
    print(f"  Dashboard : {DASHBOARD_URL}")
    print("  Bot       : warming up (30 sec)…")
    print("  Stop      : Ctrl+C")
    print()

    try:
        bot.wait()
    except KeyboardInterrupt:
        print("\n[stop] Shutting down…")
    finally:
        for proc, name in [(bot, "bot"), (dash, "dashboard")]:
            try:
                proc.terminate()
                proc.wait(timeout=5)
                print(f"[stop] {name} terminated")
            except Exception:
                proc.kill()

    print("[stop] Session ended.")


if __name__ == "__main__":
    main()
