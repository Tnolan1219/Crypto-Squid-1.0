"""
Environment + API connectivity validation script.

Run before every session:
    .venv/Scripts/python.exe scripts/test_env.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


# ── Required variables ────────────────────────────────────────────────────────
REQUIRED = [
    "COINBASE_API_KEY_NAME",
    "COINBASE_PRIVATE_KEY",
]

OPTIONAL = [
    "SUPABASE_URL",
    "SUPABASE_KEY",
]

_PASS = "[OK]"
_FAIL = "[FAIL]"
_WARN = "[WARN]"


def check_env() -> bool:
    print("\n-- ENV VARIABLES --------------------------------")
    ok = True
    for key in REQUIRED:
        val = os.getenv(key, "").strip()
        if val:
            print(f"  {_PASS}  {key}  ({len(val)} chars)")
        else:
            print(f"  {_FAIL} {key}  MISSING (required)")
            ok = False
    for key in OPTIONAL:
        val = os.getenv(key, "").strip()
        if val:
            print(f"  {_PASS}  {key}  ({len(val)} chars)")
        else:
            print(f"  {_WARN} {key}  not set (optional)")
    return ok


def check_coinbase_rest() -> bool:
    print("\n-- COINBASE REST --------------------------------")
    try:
        from coinbase.rest import RESTClient

        client = RESTClient(
            api_key=os.getenv("COINBASE_API_KEY_NAME"),
            api_secret=os.getenv("COINBASE_PRIVATE_KEY"),
        )
        result = client.get_product(product_id="BTC-USD")
        price = getattr(result, "price", None) or result.get("price", "?")
        print(f"  {_PASS}  REST connected  BTC-USD @ ${float(price):,.2f}")
        return True
    except Exception as exc:
        print(f"  {_FAIL} REST failed: {exc}")
        return False


def check_coinbase_ws() -> bool:
    print("\n-- COINBASE WEBSOCKET ---------------------------")
    try:
        from coinbase_ws import CoinbaseWS

        received: list[tuple] = []

        def on_trade(sym: str, price: float, size: float, side: str) -> None:
            received.append((sym, price))

        def on_spread(sym: str, bid: float, ask: float) -> None:
            pass

        ws = CoinbaseWS(
            symbols=["BTC-USD"],
            on_trade=on_trade,
            on_spread=on_spread,
        )
        ws.start()
        deadline = time.time() + 6
        while time.time() < deadline and not received:
            time.sleep(0.1)
        ws.stop()

        if received:
            sym, price = received[0]
            print(f"  {_PASS}  WS connected  first tick: {sym} @ ${price:,.2f}  ({len(received)} ticks/6s)")
            return True
        else:
            print(f"  {_FAIL} WS connected but no ticks received in 6s -- check permissions")
            return False
    except Exception as exc:
        print(f"  {_FAIL} WS failed: {exc}")
        return False


def check_supabase() -> bool:
    print("\n-- SUPABASE -------------------------------------")
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    if not url or not key:
        print(f"  {_WARN} Supabase not configured -- remote control disabled (optional)")
        return True
    try:
        from supabase import create_client

        client = create_client(url, key)
        rows = client.table("strategy_control").select("*").execute().data
        print(f"  {_PASS}  Supabase connected  {len(rows)} strategy_control rows")
        return True
    except Exception as exc:
        print(f"  {_FAIL} Supabase error: {exc}")
        return False


def check_dirs() -> bool:
    print("\n-- RUNTIME DIRECTORIES --------------------------")
    dirs = [
        ROOT / "logs",
        ROOT / "data" / "trades",
        ROOT / "data" / "events",
        ROOT / "journal" / "raw-trades",
        ROOT / "reports" / "daily",
        ROOT / "reports" / "weekly",
        ROOT / "memory",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  {_PASS}  {d.relative_to(ROOT)}")
    return True


def main() -> None:
    print("=" * 52)
    print("  CRYPTO SQUID  --  Environment Validation")
    print("=" * 52)

    results = {
        "env": check_env(),
        "dirs": check_dirs(),
        "rest": check_coinbase_rest(),
        "ws": check_coinbase_ws(),
        "supabase": check_supabase(),
    }

    print("\n-- SUMMARY --------------------------------------")
    all_ok = all(results.values())
    for name, passed in results.items():
        icon = _PASS if passed else _FAIL
        print(f"  {icon}  {name.upper()}")

    print()
    if all_ok:
        print("RESULT: ALL CHECKS PASSED -- ready to run")
        print()
        print("Start the bot:")
        print("  .venv\\Scripts\\python.exe scripts\\run_all.py")
    else:
        print("RESULT: SOME CHECKS FAILED -- fix errors above before starting")
    print()


if __name__ == "__main__":
    main()
