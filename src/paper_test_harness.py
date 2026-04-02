"""Timed paper-trading harness with readiness gates."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from market_data import get_price
from paper_engine import PaperEngine
from risk import position_size
from strategy import check_entry
from tracker import MarketTracker


SYMBOLS = ["BTC-USD", "ETH-USD"]
MAX_HOLD_MINUTES = 90


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: float) -> float:
    return round(float(value), 6)


def _max_drawdown_pct_from_trades(start_balance: float, trades: list[dict]) -> float:
    peak = start_balance
    equity = start_balance
    max_dd = 0.0
    for trade in trades:
        equity += trade.get("pnl", 0.0)
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak * 100.0)
    return max_dd


def run_harness(minutes: float, interval_seconds: float, start_balance: float, leverage_factor: float) -> dict:
    trackers = {symbol: MarketTracker() for symbol in SYMBOLS}
    engine = PaperEngine(balance=start_balance)
    active_symbol = None

    started_at = _utc_now()
    started_ts = time.time()
    end_ts = started_ts + minutes * 60.0
    tick_count = 0
    data_errors = 0

    print("=== CRYPTO SQUID PAPER TEST HARNESS ===")
    print(f"Duration: {minutes:.2f} min | Interval: {interval_seconds:.2f}s")
    print(f"Symbols: {SYMBOLS}")
    print("Running...\n")

    while time.time() < end_ts:
        for symbol in SYMBOLS:
            try:
                price = get_price(symbol)
                trackers[symbol].update(price)
                tick_count += 1

                drop = trackers[symbol].get_drop_pct()
                zscore = trackers[symbol].get_zscore()

                if engine.position and active_symbol == symbol:
                    if engine.position_age_minutes() >= MAX_HOLD_MINUTES:
                        engine.exit(price, "TIME_STOP")
                        active_symbol = None
                    elif price <= engine.position["stop"]:
                        engine.exit(price, "SL")
                        active_symbol = None
                    elif price >= engine.position["tp"]:
                        engine.exit(price, "TP")
                        active_symbol = None

                if engine.position is None and check_entry(symbol, drop, zscore):
                    entry = price * 0.9995
                    stop = price * 0.995
                    tp = price * (1.01 if symbol == "BTC-USD" else 1.012)
                    size = position_size(engine.balance, entry, stop)
                    if size > 0:
                        engine.enter(symbol, entry, size, stop, tp, drop, zscore)
                        active_symbol = symbol
            except Exception as exc:
                data_errors += 1
                print(f"[WARN] {symbol} data/execution error: {exc}")

        time.sleep(interval_seconds)

    if engine.position and active_symbol:
        try:
            final_price = get_price(active_symbol)
            engine.exit(final_price, "HARNESS_END")
        except Exception as exc:
            data_errors += 1
            print(f"[WARN] could not close open position at harness end: {exc}")

    trades = engine.trades
    wins = sum(1 for trade in trades if trade.get("pnl", 0.0) > 0)
    losses = sum(1 for trade in trades if trade.get("pnl", 0.0) < 0)
    gross_profit = sum(trade.get("pnl", 0.0) for trade in trades if trade.get("pnl", 0.0) > 0)
    gross_loss = abs(sum(trade.get("pnl", 0.0) for trade in trades if trade.get("pnl", 0.0) < 0))

    realized_pnl = engine.balance - engine.start_balance
    total_trades = len(trades)
    win_rate_pct = (wins / total_trades * 100.0) if total_trades else 0.0
    expectancy_usd = (realized_pnl / total_trades) if total_trades else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

    elapsed_minutes = max((time.time() - started_ts) / 60.0, 0.0)
    summary = {
        "started_at": started_at,
        "ended_at": _utc_now(),
        "elapsed_minutes": _safe_float(elapsed_minutes),
        "settings": {
            "symbols": SYMBOLS,
            "max_hold_minutes": MAX_HOLD_MINUTES,
            "interval_seconds": interval_seconds,
            "start_balance": start_balance,
            "leverage_factor": leverage_factor,
        },
        "runtime": {
            "ticks": tick_count,
            "data_errors": data_errors,
        },
        "stats": {
            "trades_closed": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": _safe_float(win_rate_pct),
            "realized_pnl_usd": _safe_float(realized_pnl),
            "realized_pnl_pct": _safe_float((realized_pnl / start_balance * 100.0) if start_balance else 0.0),
            "leveraged_realized_pnl_usd": _safe_float(realized_pnl * leverage_factor),
            "leveraged_realized_pnl_pct": _safe_float(((realized_pnl / start_balance * 100.0) if start_balance else 0.0) * leverage_factor),
            "expectancy_usd_per_trade": _safe_float(expectancy_usd),
            "profit_factor": _safe_float(profit_factor),
            "max_drawdown_pct": _safe_float(_max_drawdown_pct_from_trades(start_balance, trades)),
            "ending_balance": _safe_float(engine.balance),
        },
        "trades": trades,
    }
    return summary


def _evaluate_gates(summary: dict, min_trades: int, max_errors: int, max_drawdown_pct: float) -> dict:
    trades_closed = summary["stats"]["trades_closed"]
    data_errors = summary["runtime"]["data_errors"]
    drawdown_pct = summary["stats"].get("max_drawdown_pct", 0.0)

    gates: dict[str, object] = {
        "minimum_trades": {
            "passed": trades_closed >= min_trades,
            "actual": trades_closed,
            "required": min_trades,
        },
        "data_health": {
            "passed": data_errors <= max_errors,
            "actual": data_errors,
            "max_allowed": max_errors,
        },
        "drawdown_guard": {
            "passed": drawdown_pct <= max_drawdown_pct,
            "actual_pct": _safe_float(drawdown_pct),
            "max_allowed_pct": max_drawdown_pct,
        },
    }
    gate_values = [value for value in gates.values() if isinstance(value, dict)]
    gates["ready_for_live_execution_code"] = all(bool(value.get("passed")) for value in gate_values)
    return gates


def _write_outputs(summary: dict, gates: dict, root: Path) -> tuple[Path, Path]:
    out_dir = root / "reports" / "daily"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    json_path = out_dir / f"paper-test-{stamp}.json"
    md_path = out_dir / f"paper-test-{stamp}.md"

    payload = {"summary": summary, "gates": gates}
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Paper Test Report",
        "",
        f"- Started (UTC): {summary['started_at']}",
        f"- Ended (UTC): {summary['ended_at']}",
        f"- Elapsed minutes: {summary['elapsed_minutes']}",
        f"- Ticks: {summary['runtime']['ticks']}",
        f"- Data errors: {summary['runtime']['data_errors']}",
        f"- Closed trades: {summary['stats']['trades_closed']}",
        f"- Win rate: {summary['stats']['win_rate_pct']}%",
        f"- Realized P/L: ${summary['stats']['realized_pnl_usd']}",
        f"- Realized P/L %: {summary['stats']['realized_pnl_pct']}%",
        f"- Leveraged Realized P/L: ${summary['stats']['leveraged_realized_pnl_usd']}",
        f"- Leveraged Realized P/L %: {summary['stats']['leveraged_realized_pnl_pct']}%",
        f"- Expectancy: ${summary['stats']['expectancy_usd_per_trade']} per trade",
        f"- Profit factor: {summary['stats']['profit_factor']}",
        f"- Max drawdown: {summary['stats']['max_drawdown_pct']}%",
        "",
        "## Gates",
        f"- minimum_trades: {'PASS' if gates['minimum_trades']['passed'] else 'FAIL'}",
        f"- data_health: {'PASS' if gates['data_health']['passed'] else 'FAIL'}",
        f"- drawdown_guard: {'PASS' if gates['drawdown_guard']['passed'] else 'FAIL'}",
        f"- ready_for_live_execution_code: {'PASS' if gates['ready_for_live_execution_code'] else 'FAIL'}",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a timed paper-trading validation harness.")
    parser.add_argument("--minutes", type=float, default=30.0, help="Run duration in minutes.")
    parser.add_argument("--interval", type=float, default=2.0, help="Loop interval in seconds.")
    parser.add_argument("--start-balance", type=float, default=1000.0, help="Starting paper balance.")
    parser.add_argument("--leverage-factor", type=float, default=1.0, help="Tracking multiplier for leveraged P/L reporting.")
    parser.add_argument("--min-trades", type=int, default=1, help="Gate: minimum closed trades.")
    parser.add_argument("--max-errors", type=int, default=0, help="Gate: max data/execution errors.")
    parser.add_argument(
        "--max-drawdown-pct",
        type=float,
        default=2.0,
        help="Gate: maximum allowed negative realized drawdown percent.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(__file__).parent.parent

    leverage_factor = max(float(args.leverage_factor), 1.0)
    summary = run_harness(
        minutes=args.minutes,
        interval_seconds=args.interval,
        start_balance=args.start_balance,
        leverage_factor=leverage_factor,
    )
    gates = _evaluate_gates(
        summary,
        min_trades=args.min_trades,
        max_errors=args.max_errors,
        max_drawdown_pct=args.max_drawdown_pct,
    )
    json_path, md_path = _write_outputs(summary, gates, root)

    print("\n=== HARNESS RESULT ===")
    print(f"ready_for_live_execution_code: {gates['ready_for_live_execution_code']}")
    print(f"Closed trades: {summary['stats']['trades_closed']}")
    print(f"Data errors: {summary['runtime']['data_errors']}")
    print(f"Realized P/L %: {summary['stats']['realized_pnl_pct']:.2f}%")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
