"""
CRYPTO SQUID v2 — WebSocket-driven paper trading bot.

Architecture:
  CoinbaseWS (background thread) → BarBuilder (shared state) → SignalEngineV2
  SignalEngineV2 → PaperEngineV2 + EventCollector → RuntimeStore

Run: python src/bot_v2.py

Phase: event study + paper validation
  - Logs ALL candidate events to data/events/events.csv
  - Paper-trades every valid signal
  - Does NOT place real orders

Go-live criteria (from docs/ANTI_OVERFITTING_PROTOCOL.md):
  - 300+ candidate events logged
  - 80+ paper trades closed
  - Positive net expectancy in chronological validation
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import structlog
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))
load_dotenv(ROOT / ".env")

from bar_builder import BarBuilder
from coinbase_ws import CoinbaseWS
from event_collector import EventCollector
from paper_engine_v2 import PaperEngineV2
from params_v2 import DEFAULT_V2_PARAMS
from risk import position_size
from runtime_store import RuntimeStore
from signal_v2 import SignalEngineV2
from trade_history import TradeHistoryStore

log = structlog.get_logger("bot_v2")

SYMBOLS = ["BTC-USD", "ETH-USD"]
ACCOUNT_CAPITAL = float(os.getenv("ACCOUNT_CAPITAL_USD", "1000"))
PARAMS = DEFAULT_V2_PARAMS


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _mode_from_env() -> dict:
    return {
        "trading_enabled": _as_bool(os.getenv("TRADING_ENABLED", "true"), default=True),
        "log_only": _as_bool(os.getenv("LOG_ONLY", "false"), default=False),
        "paper_mode": _as_bool(os.getenv("PAPER_MODE", "true"), default=True),
        "enable_live_trading": _as_bool(os.getenv("ENABLE_LIVE_TRADING", "false"), default=False),
        "use_testnet": _as_bool(os.getenv("USE_TESTNET", "true"), default=True),
    }


def _stats_from_trades(trades: list[dict]) -> dict:
    wins = sum(1 for trade in trades if trade.get("pnl", 0.0) > 0)
    losses = sum(1 for trade in trades if trade.get("pnl", 0.0) < 0)
    total = len(trades)
    pnl_values = [trade.get("pnl", 0.0) for trade in trades]
    gross_profit = sum(pnl for pnl in pnl_values if pnl > 0)
    gross_loss = abs(sum(pnl for pnl in pnl_values if pnl < 0))
    realized_pnl = sum(pnl_values)
    return {
        "trades_closed": total,
        "wins": wins,
        "losses": losses,
        "win_rate_pct": round((wins / total * 100.0), 2) if total else 0.0,
        "expectancy_usd_per_trade": round((realized_pnl / total), 4) if total else 0.0,
        "profit_factor": round((gross_profit / gross_loss), 4) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0),
    }


def _build_runtime_state(
    engine: PaperEngineV2,
    bars_builder: BarBuilder,
    signal_engine: SignalEngineV2,
    event_count: int,
    started_at: str,
    mode: dict,
) -> dict:
    symbols = {}
    for symbol in SYMBOLS:
        bars, bid, ask, current_price, _ = bars_builder.snapshot(symbol)
        history = [
            {"ts": datetime.fromtimestamp(b.ts, tz=timezone.utc).isoformat(), "price": b.close}
            for b in bars[-180:]
        ]
        symbols[symbol] = {
            "price": current_price,
            "drop_pct": BarBuilder.return_pct(bars, 180),
            "zscore": BarBuilder.zscore(bars),
            "spread_bps": BarBuilder.current_spread_bps(bid, ask),
            "history": history,
        }

    account = {
        "starting_balance": engine.start_balance,
        "balance": engine.balance,
        "realized_pnl": round(engine.balance - engine.start_balance, 4),
        "realized_pnl_pct": round(
            (engine.balance - engine.start_balance) / engine.start_balance * 100, 4
        ) if engine.start_balance else 0.0,
    }

    active_positions = []
    for pos in engine.positions.values():
        symbol = pos["symbol"]
        bars, bid, ask, current_price, _ = bars_builder.snapshot(symbol)
        unreal = (current_price - pos["entry"]) * (
            pos["size_total"] if not pos["tp1_hit"] else pos["size2"]
        )
        active_positions.append({
            **pos,
            "size": pos.get("size2") if pos.get("tp1_hit") else pos.get("size_total"),
            "tp": pos.get("tp2"),
            "mark_price": current_price,
            "age_minutes": engine.position_age_minutes(symbol),
            "current_price": current_price,
            "unrealized_pnl": round(unreal, 4),
        })

    position = active_positions[0] if active_positions else None

    unrealized_pnl = round(sum(p.get("unrealized_pnl", 0.0) for p in active_positions), 4)
    total_pnl = account["realized_pnl"] + unrealized_pnl
    account["unrealized_pnl"] = round(unrealized_pnl, 4)
    account["total_pnl"] = round(total_pnl, 4)
    account["total_pnl_pct"] = round((total_pnl / engine.start_balance * 100.0), 4) if engine.start_balance else 0.0
    account["leverage_factor"] = 1.0
    account["leveraged_total_pnl"] = account["total_pnl"]
    account["leveraged_total_pnl_pct"] = account["total_pnl_pct"]

    stats = _stats_from_trades(engine.trades)

    return {
        "status": "running",
        "started_at": started_at,
        "mode": mode,
        "version": "v2",
        "event_count": event_count,
        "account": account,
        "position": position,
        "active_position": position,
        "positions": active_positions,
        "symbols": symbols,
        "stats": stats,
        "trades": engine.trades[-50:],
    }


def _max_drawdown_pct(start_balance: float, trades: list[dict]) -> float:
    peak = start_balance
    equity = start_balance
    max_dd = 0.0
    for t in trades:
        equity += t.get("pnl", 0.0)
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak * 100.0)
    return round(max_dd, 4)


def _write_session_report(
    started_at: str,
    engine: "PaperEngineV2",
    event_count: int,
    mode: dict,
) -> tuple[Path, Path]:
    trades = engine.trades
    wins = sum(1 for t in trades if t.get("pnl", 0.0) > 0)
    losses = sum(1 for t in trades if t.get("pnl", 0.0) < 0)
    total = len(trades)
    realized_pnl = engine.balance - engine.start_balance
    gross_profit = sum(t.get("pnl", 0.0) for t in trades if t.get("pnl", 0.0) > 0)
    gross_loss = abs(sum(t.get("pnl", 0.0) for t in trades if t.get("pnl", 0.0) < 0))

    ended_at = datetime.now(timezone.utc).isoformat()
    started_dt = datetime.fromisoformat(started_at)
    ended_dt = datetime.fromisoformat(ended_at)
    elapsed_minutes = round((ended_dt - started_dt).total_seconds() / 60.0, 2)

    summary = {
        "started_at": started_at,
        "ended_at": ended_at,
        "elapsed_minutes": elapsed_minutes,
        "mode": mode,
        "event_count": event_count,
        "stats": {
            "trades_closed": total,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(wins / total * 100.0, 2) if total else 0.0,
            "realized_pnl_usd": round(realized_pnl, 4),
            "realized_pnl_pct": round(realized_pnl / engine.start_balance * 100.0, 4) if engine.start_balance else 0.0,
            "expectancy_usd_per_trade": round(realized_pnl / total, 4) if total else 0.0,
            "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0),
            "max_drawdown_pct": _max_drawdown_pct(engine.start_balance, trades),
            "starting_balance": engine.start_balance,
            "ending_balance": round(engine.balance, 4),
        },
        "trades": trades,
    }

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = ROOT / "reports" / "daily"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"session-{stamp}.json"
    md_path = out_dir / f"session-{stamp}.md"

    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    s = summary["stats"]
    lines = [
        "# Crypto Squid Paper Session Report",
        "",
        f"- Started (UTC): {summary['started_at']}",
        f"- Ended (UTC): {summary['ended_at']}",
        f"- Elapsed: {elapsed_minutes} min",
        f"- Mode: paper={mode.get('paper_mode')} / live={mode.get('enable_live_trading')}",
        f"- Events logged: {event_count}",
        "",
        "## Stats",
        f"- Closed trades: {s['trades_closed']}",
        f"- Wins / Losses: {s['wins']} / {s['losses']}",
        f"- Win rate: {s['win_rate_pct']}%",
        f"- Realized P/L: ${s['realized_pnl_usd']}",
        f"- Realized P/L %: {s['realized_pnl_pct']}%",
        f"- Expectancy (EV): ${s['expectancy_usd_per_trade']} / trade",
        f"- Profit factor: {s['profit_factor']}",
        f"- Max drawdown: {s['max_drawdown_pct']}%",
        f"- Starting balance: ${s['starting_balance']}",
        f"- Ending balance: ${s['ending_balance']}",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> None:
    bar_builder = BarBuilder()
    ws = CoinbaseWS(
        symbols=SYMBOLS,
        on_trade=bar_builder.on_trade,
        on_spread=bar_builder.update_spread,
    )
    event_collector = EventCollector(ROOT)
    signal_engine = SignalEngineV2(PARAMS, event_collector)
    paper_engine = PaperEngineV2(balance=ACCOUNT_CAPITAL)
    trade_history = TradeHistoryStore(ROOT)
    trade_history.sync_existing()
    runtime_store = RuntimeStore(ROOT)
    started_at = datetime.now(timezone.utc).isoformat()
    strategy_version = os.getenv("STRATEGY_VERSION", "coinbase-v2-paper")
    mode = _mode_from_env()

    print("=== CRYPTO SQUID v2 — PAPER + EVENT STUDY ===")
    print(f"Symbols: {SYMBOLS}")
    print(f"Capital: ${ACCOUNT_CAPITAL:,.2f}")
    print(f"Events logged so far: {event_collector.count()}")
    print("Starting WebSocket...\n")

    ws.start()
    print("WebSocket connected. Warming up (30 sec)...\n")
    time.sleep(30)  # allow bar history to accumulate before signal checks begin

    # ── Staleness tracking — detect WS disconnect ──────────────────────────────
    _last_bar_ts: dict[str, int] = {}
    WS_STALE_SECONDS = 5.0  # flatten open position if no new bar data for this long

    try:
        while True:
            for symbol in SYMBOLS:
                bars, bid, ask, current_price, spread_hist = bar_builder.snapshot(symbol)

                if not bars:
                    continue

                # ── Track bar freshness (detect WebSocket disconnect) ──────────
                latest_ts = bars[-1].ts
                if symbol not in _last_bar_ts or latest_ts > _last_bar_ts[symbol]:
                    _last_bar_ts[symbol] = latest_ts
                data_age = time.time() - _last_bar_ts.get(symbol, time.time())
                data_stale = data_age > WS_STALE_SECONDS

                # ── Disconnect flatten: core rule — WS disconnect > 5s during open position
                if data_stale and paper_engine.has_open_position(symbol):
                    log.error("ws.stale_flatten", symbol=symbol, age_seconds=f"{data_age:.1f}")
                    trades = paper_engine.force_close(symbol, current_price, "WS_DISCONNECT")
                    for trade in trades:
                        signal_engine.register_trade_close(trade["pnl"])
                        trade_history.write_trade(trade, strategy_version=strategy_version)
                        print(f"[WS-DISCONNECT] Force-closed {symbol}  pnl={trade['pnl']:+.2f}")
                    continue  # skip normal exit/entry logic while stale

                # ── Check exits on open position ──────────────────────────────
                if paper_engine.has_open_position(symbol):
                    closed = paper_engine.on_price(symbol, current_price)
                    for trade in closed:
                        if trade.get("reason") in {"SL", "SL_BREAKEVEN", "TP2", "TIME_STOP"}:
                            signal_engine.register_trade_close(trade["pnl"])
                        trade_history.write_trade(trade, strategy_version=strategy_version)
                        log.info(
                            "trade.closed",
                            symbol=symbol,
                            reason=trade["reason"],
                            pnl=trade["pnl"],
                            pnl_pct=trade["pnl_pct"],
                            balance=paper_engine.balance,
                        )

                # ── Kill switch: TRADING_ENABLED=false halts all new entries ──
                if not mode["trading_enabled"]:
                    continue

                # ── Block entries when market data is stale ────────────────────
                if data_stale:
                    continue

                # ── Check entry signal ─────────────────────────────────────────
                if not paper_engine.has_open_position(symbol):
                    signal = signal_engine.check(
                        symbol=symbol,
                        bars=bars,
                        bid=bid,
                        ask=ask,
                        spread_hist=spread_hist,
                        account_equity=paper_engine.balance,
                    )
                    if signal:
                        sp = PARAMS.for_symbol(symbol)
                        size = position_size(
                            paper_engine.balance,
                            signal.entry_limit,
                            signal.stop,
                            risk_per_trade_pct=PARAMS.risk_per_trade_pct,
                        )
                        max_exp_pct = (
                            PARAMS.max_gross_exposure_btc_pct
                            if symbol == "BTC-USD"
                            else PARAMS.max_gross_exposure_eth_pct
                        )
                        max_size = (paper_engine.balance * max_exp_pct / 100) / signal.entry_limit
                        size = min(size, max_size)

                        if size > 0:
                            paper_engine.enter(
                                symbol=symbol,
                                entry=signal.entry_limit,
                                size=size,
                                stop=signal.stop,
                                tp1=signal.tp1,
                                tp1_size_frac=sp.tp1_size_frac,
                                tp2=signal.tp2,
                                time_stop_minutes=sp.time_stop_minutes,
                                fast_reduce_minutes=sp.fast_reduce_minutes,
                            )

            # ── Status print every ~10 seconds ────────────────────────────────
            if int(time.time()) % 10 == 0:
                event_count = event_collector.count()
                kill = "" if mode["trading_enabled"] else "  [KILL-SWITCH]"
                for symbol in SYMBOLS:
                    bars, bid, ask, price, _ = bar_builder.snapshot(symbol)
                    if bars:
                        drop = BarBuilder.return_pct(bars, 180)
                        z = BarBuilder.zscore(bars)
                        vol = BarBuilder.volume_ratio(bars)
                        spread = BarBuilder.current_spread_bps(bid, ask)
                        age = time.time() - _last_bar_ts.get(symbol, time.time())
                        stale_tag = f"  [STALE {age:.0f}s]" if age > WS_STALE_SECONDS else ""
                        print(
                            f"{symbol}  {price:.2f}  drop={drop:+.3f}%  z={z:.2f}"
                            f"  vol={vol:.2f}x  spread={spread:.1f}bps"
                            f"  events={event_count}{stale_tag}{kill}",
                            flush=True,
                        )

            # ── Write runtime state ────────────────────────────────────────────
            runtime_store.write(
                _build_runtime_state(
                    paper_engine,
                    bar_builder,
                    signal_engine,
                    event_collector.count(),
                    started_at,
                    mode,
                )
            )

            time.sleep(0.25)  # 250ms main loop (4× per second)

    except KeyboardInterrupt:
        print("\nBot stopped.")
        ws.stop()
        json_path, md_path = _write_session_report(
            started_at, paper_engine, event_collector.count(), mode
        )
        s = paper_engine
        trades = s.trades
        total = len(trades)
        wins = sum(1 for t in trades if t.get("pnl", 0.0) > 0)
        realized = s.balance - s.start_balance
        print(f"Final balance:   ${s.balance:.2f}")
        print(f"Realized P/L:    ${realized:.2f}  ({realized / s.start_balance * 100:.2f}%)")
        print(f"Closed trades:   {total}  |  Wins: {wins}  |  Win rate: {wins / total * 100:.1f}%" if total else "Closed trades:   0")
        print(f"Events logged:   {event_collector.count()}")
        print(f"Session JSON:    {json_path}")
        print(f"Session report:  {md_path}")


if __name__ == "__main__":
    main()
