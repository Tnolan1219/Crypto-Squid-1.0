"""Backtest Crypto Squid strategy on Coinbase public candles."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path

from coinbase.rest import RESTClient

from paper_engine import PaperEngine
from config import load_config
from risk import RiskEngine, position_size
from strategy import check_entry
from tracker import MarketTracker


DEFAULT_SYMBOLS = ["BTC-USD", "ETH-USD"]
MAX_HOLD_MINUTES = 90
GRANULARITY_TO_SECONDS = {
    "ONE_MINUTE": 60,
    "FIVE_MINUTE": 300,
    "FIFTEEN_MINUTE": 900,
    "THIRTY_MINUTE": 1800,
    "ONE_HOUR": 3600,
    "TWO_HOUR": 7200,
    "SIX_HOUR": 21600,
    "ONE_DAY": 86400,
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _parse_symbols(raw: str) -> list[str]:
    symbols = [item.strip().upper() for item in raw.split(",") if item.strip()]
    return symbols or DEFAULT_SYMBOLS


def _fetch_candles(client: RESTClient, symbol: str, start_ts: int, end_ts: int, granularity: str) -> list[dict]:
    step_seconds = GRANULARITY_TO_SECONDS[granularity] * 300
    rows_by_start = {}
    cursor = start_ts
    while cursor < end_ts:
        window_end = min(cursor + step_seconds, end_ts)
        response = client.get_public_candles(
            product_id=symbol,
            start=str(cursor),
            end=str(window_end),
            granularity=granularity,
            limit=300,
        )
        for candle in (response.candles or []):
            start_value = int(candle.start)
            rows_by_start[start_value] = {
                "start": start_value,
                "open": float(candle.open),
                "high": float(candle.high),
                "low": float(candle.low),
                "close": float(candle.close),
                "volume": float(candle.volume),
            }
        cursor = window_end
    return [rows_by_start[key] for key in sorted(rows_by_start.keys())]


def _equity(balance: float, position: dict | None, mark_price: float | None) -> float:
    if not position or mark_price is None:
        return balance
    return balance + (mark_price - position["entry"]) * position["size"]


def _max_drawdown_pct(equity_curve: list[dict], start_balance: float) -> float:
    if not equity_curve:
        return 0.0
    peak = max(float(start_balance), float(equity_curve[0]["equity"]))
    max_dd = 0.0
    for row in equity_curve:
        equity = float(row["equity"])
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak * 100.0)
    return max_dd


def _stats(engine: PaperEngine, start_balance: float, equity_curve: list[dict], leverage_factor: float) -> dict:
    trades = engine.trades
    wins = sum(1 for trade in trades if trade.get("pnl", 0.0) > 0)
    losses = sum(1 for trade in trades if trade.get("pnl", 0.0) < 0)
    pnl = engine.balance - start_balance
    total = len(trades)
    gross_profit = sum(trade.get("pnl", 0.0) for trade in trades if trade.get("pnl", 0.0) > 0)
    gross_loss = abs(sum(trade.get("pnl", 0.0) for trade in trades if trade.get("pnl", 0.0) < 0))
    realized_pnl_pct = (pnl / start_balance * 100.0) if start_balance else 0.0
    return {
        "trades_closed": total,
        "wins": wins,
        "losses": losses,
        "win_rate_pct": (wins / total * 100.0) if total else 0.0,
        "realized_pnl_usd": pnl,
        "realized_pnl_pct": realized_pnl_pct,
        "leveraged_realized_pnl_usd": pnl * leverage_factor,
        "leveraged_realized_pnl_pct": realized_pnl_pct * leverage_factor,
        "expectancy_usd_per_trade": (pnl / total) if total else 0.0,
        "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0),
        "max_drawdown_pct": _max_drawdown_pct(equity_curve, start_balance),
        "ending_balance": engine.balance,
    }


def _write_csv(path: Path, rows: list[dict], headers: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _gate_report(stats: dict, min_trades: int, max_drawdown_pct: float) -> dict:
    drawdown_pct = stats.get("max_drawdown_pct", 0.0)
    gates: dict[str, object] = {
        "minimum_trades": {"passed": stats["trades_closed"] >= min_trades, "actual": stats["trades_closed"], "required": min_trades},
        "drawdown_guard": {"passed": drawdown_pct <= max_drawdown_pct, "actual_pct": drawdown_pct, "max_allowed_pct": max_drawdown_pct},
    }
    gate_values = [value for value in gates.values() if isinstance(value, dict)]
    gates["ready_for_live_execution_code"] = all(bool(value.get("passed")) for value in gate_values)
    return gates


def _run(symbols: list[str], candles_by_symbol: dict[str, list[dict]], start_balance: float) -> tuple[PaperEngine, list[dict]]:
    trackers = {symbol: MarketTracker() for symbol in symbols}
    last_price = {symbol: None for symbol in symbols}
    events = []
    symbol_order = {symbol: idx for idx, symbol in enumerate(symbols)}
    for symbol in symbols:
        for candle in candles_by_symbol[symbol]:
            events.append((candle["start"], symbol_order[symbol], symbol, candle["close"]))
    events.sort(key=lambda row: (row[0], row[1]))

    engine = PaperEngine(balance=start_balance)
    simulated_day = _utc_now().date()

    def _simulated_today() -> date:
        return simulated_day

    cfg = replace(load_config(), account_capital_usd=float(start_balance))
    risk_engine = RiskEngine(cfg, today_provider=_simulated_today)

    active_symbol = None
    equity_curve = []
    for ts, _, symbol, price in events:
        simulated_day = datetime.fromtimestamp(ts, tz=timezone.utc).date()
        last_price[symbol] = price
        trackers[symbol].update(price)
        drop = trackers[symbol].get_drop_pct()
        zscore = trackers[symbol].get_zscore()

        if engine.position and active_symbol == symbol:
            opened_ts = int(engine.position.get("opened_at_candle_ts", ts))
            age_minutes = (ts - opened_ts) / 60.0
            if age_minutes >= MAX_HOLD_MINUTES:
                closed = engine.exit(price, "TIME_STOP", exit_ts=float(ts), exit_iso=_iso(ts))
                risk_engine.register_trade_close(float(closed.get("pnl", 0.0)))
                active_symbol = None
            elif price <= engine.position["stop"]:
                closed = engine.exit(price, "SL", exit_ts=float(ts), exit_iso=_iso(ts))
                risk_engine.register_trade_close(float(closed.get("pnl", 0.0)))
                active_symbol = None
            elif price >= engine.position["tp"]:
                closed = engine.exit(price, "TP", exit_ts=float(ts), exit_iso=_iso(ts))
                risk_engine.register_trade_close(float(closed.get("pnl", 0.0)))
                active_symbol = None

        risk_check = risk_engine.can_open_trade(
            has_open_position=engine.position is not None,
            market_data_healthy=True,
            exchange_healthy=True,
        )
        if risk_check.allowed and engine.position is None and check_entry(symbol, drop, zscore):
            entry = price * 0.9995
            stop = price * 0.995
            tp = price * (1.01 if symbol == "BTC-USD" else 1.012)
            size = position_size(engine.balance, entry, stop)
            if size > 0:
                engine.enter(
                    symbol,
                    entry,
                    size,
                    stop,
                    tp,
                    drop,
                    zscore,
                    opened_at_ts=float(ts),
                    opened_at_iso=_iso(ts),
                )
                if engine.position:
                    engine.position["opened_at_candle_ts"] = ts
                active_symbol = symbol

        mark = last_price.get(active_symbol) if active_symbol else None
        equity_curve.append({"ts": _iso(ts), "equity": _equity(engine.balance, engine.position, mark)})

    if engine.position and active_symbol:
        final_price = last_price.get(active_symbol) or engine.position["entry"]
        final_ts = max((row[0] for row in events), default=int(_utc_now().timestamp()))
        closed = engine.exit(final_price, "BACKTEST_END", exit_ts=float(final_ts), exit_iso=_iso(final_ts))
        risk_engine.register_trade_close(float(closed.get("pnl", 0.0)))
    return engine, equity_curve


def _write_outputs(root: Path, metadata: dict, stats: dict, gates: dict, trades: list[dict], equity_curve: list[dict], candles_by_symbol: dict[str, list[dict]]) -> Path:
    stamp = _utc_now().strftime("%Y%m%d-%H%M%S")
    out_dir = root / "backtests" / "runs" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {"metadata": metadata, "stats": stats, "gates": gates}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md_lines = [
        "# Backtest Summary",
        "",
        f"- Generated: {metadata['generated_at']}",
        f"- Symbols: {', '.join(metadata['symbols'])}",
        f"- Window: {metadata['start_utc']} -> {metadata['end_utc']}",
        f"- Granularity: {metadata['granularity']}",
        f"- Closed trades: {stats['trades_closed']}",
        f"- Win rate: {stats['win_rate_pct']:.2f}%",
        f"- Realized P/L: ${stats['realized_pnl_usd']:.2f} ({stats['realized_pnl_pct']:.2f}%)",
        f"- Leveraged Realized P/L: ${stats['leveraged_realized_pnl_usd']:.2f} ({stats['leveraged_realized_pnl_pct']:.2f}%)",
        f"- Expectancy: ${stats['expectancy_usd_per_trade']:.2f} per trade",
        f"- Profit factor: {stats['profit_factor']:.3f}",
        f"- Max drawdown: {stats['max_drawdown_pct']:.2f}%",
        "",
        "## Gates",
        f"- minimum_trades: {'PASS' if gates['minimum_trades']['passed'] else 'FAIL'}",
        f"- drawdown_guard: {'PASS' if gates['drawdown_guard']['passed'] else 'FAIL'}",
        f"- ready_for_live_execution_code: {'PASS' if gates['ready_for_live_execution_code'] else 'FAIL'}",
    ]
    (out_dir / "summary.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    _write_csv(
        out_dir / "trades.csv",
        trades,
        ["ts", "symbol", "entry", "exit", "size", "stop", "tp", "reason", "pnl", "pnl_pct", "duration_seconds"],
    )
    _write_csv(out_dir / "equity.csv", equity_curve, ["ts", "equity"])

    for symbol, rows in candles_by_symbol.items():
        _write_csv(out_dir / f"candles-{symbol}.csv", rows, ["start", "open", "high", "low", "close", "volume"])
    return out_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest Crypto Squid using Coinbase public candles.")
    parser.add_argument("--symbols", default="BTC-USD,ETH-USD", help="Comma separated product ids.")
    parser.add_argument("--days", type=float, default=3.0, help="How many days to backtest from now.")
    parser.add_argument("--granularity", default="ONE_MINUTE", choices=sorted(GRANULARITY_TO_SECONDS.keys()))
    parser.add_argument("--start-balance", type=float, default=1000.0)
    parser.add_argument("--leverage-factor", type=float, default=1.0)
    parser.add_argument("--min-trades", type=int, default=20)
    parser.add_argument("--max-drawdown-pct", type=float, default=2.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(__file__).parent.parent
    end_ts = int(_utc_now().timestamp())
    start_ts = end_ts - int(args.days * 86400)
    symbols = _parse_symbols(args.symbols)

    client = RESTClient()
    candles_by_symbol = {symbol: _fetch_candles(client, symbol, start_ts, end_ts, args.granularity) for symbol in symbols}
    leverage_factor = max(float(args.leverage_factor), 1.0)
    engine, equity_curve = _run(symbols, candles_by_symbol, args.start_balance)
    stats = _stats(engine, args.start_balance, equity_curve, leverage_factor)
    gates = _gate_report(stats, min_trades=args.min_trades, max_drawdown_pct=args.max_drawdown_pct)

    metadata = {
        "generated_at": _utc_now().isoformat(),
        "symbols": symbols,
        "start_utc": _iso(start_ts),
        "end_utc": _iso(end_ts),
        "granularity": args.granularity,
        "start_balance": args.start_balance,
        "leverage_factor": leverage_factor,
    }
    out_dir = _write_outputs(root, metadata, stats, gates, engine.trades, equity_curve, candles_by_symbol)

    print("=== BACKTEST COMPLETE ===")
    print(f"Output folder: {out_dir}")
    print(f"Closed trades: {stats['trades_closed']}")
    print(f"Win rate: {stats['win_rate_pct']:.2f}%")
    print(f"Realized P/L %: {stats['realized_pnl_pct']:.2f}%")
    print(f"ready_for_live_execution_code: {gates['ready_for_live_execution_code']}")


if __name__ == "__main__":
    main()
