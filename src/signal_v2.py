"""
CRYPTO SQUID v2 — Signal engine.

State machine per symbol:
  IDLE         → watching for regime + panic conditions
  TRIGGERED    → panic threshold met; checking disorder filter
  STABILIZING  → disorder filter passed; waiting for bounce confirmation
  (fires)      → signal emitted; resets to IDLE

Anti-overfitting: ALL candidate events are logged to event_collector regardless
of whether they pass the full filter stack. This data feeds the research protocol.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Optional

import structlog

from bar_builder import BarBuilder
from event_collector import EventCollector
from params_v2 import V2Params

log = structlog.get_logger("signal_v2")


@dataclass
class SignalResult:
    symbol: str
    price: float
    entry_limit: float      # suggested limit price
    stop: float
    tp1: float
    tp2: float
    drop_pct: float
    zscore: float
    volume_ratio: float
    imbalance: float
    spread_bps: float
    stab_method: str


@dataclass
class _SymbolState:
    phase: str = "IDLE"         # IDLE | TRIGGERED | STABILIZING
    trigger_ts: float = 0.0
    panic_low: float = 0.0
    trigger_price: float = 0.0
    trigger_drop: float = 0.0
    trigger_zscore: float = 0.0
    trigger_volratio: float = 0.0
    trigger_imbalance: float = 0.0
    trigger_spread: float = 0.0
    trigger_spread_vs_median: float = 0.0
    stab_start_ts: float = 0.0
    last_new_low_ts: float = 0.0
    _no_new_low_since: float = 0.0


class SignalEngineV2:
    def __init__(self, params: V2Params, event_collector: EventCollector):
        self.params = params
        self._events = event_collector
        self._states: dict[str, _SymbolState] = {}
        self._daily_evaluated: dict[str, int] = {}
        self._daily_trades: int = 0
        self._consecutive_losses: int = 0
        self._day: date = date.today()
        # Daily loss limit tracking
        self._daily_realized_pnl: float = 0.0
        self._last_equity: float = 0.0
        # Spread rejection counter (per symbol, reset on new tick data)
        self._spread_reject_count: dict[str, int] = {}

    # ── External state updates ────────────────────────────────────────────────

    def register_trade_close(self, pnl: float) -> None:
        self._roll_day()
        self._daily_trades += 1
        self._daily_realized_pnl += pnl
        self._consecutive_losses = 0 if pnl >= 0 else self._consecutive_losses + 1

    # ── Main entry point ─────────────────────────────────────────────────────

    def check(
        self,
        symbol: str,
        bars: list,
        bid: float,
        ask: float,
        spread_hist: list[float],
        account_equity: float,
    ) -> Optional[SignalResult]:
        """
        Call once per main-loop tick with fresh bar snapshot data.
        Returns SignalResult if all conditions are met, else None.
        """
        self._roll_day()
        self._last_equity = account_equity
        state = self._states.setdefault(symbol, _SymbolState())
        params = self.params.for_symbol(symbol)

        if not bars:
            return None

        price = bars[-1].close if bars else 0.0
        if price <= 0:
            return None

        spread_bps = BarBuilder.current_spread_bps(bid, ask)
        median_spread = BarBuilder.median_spread_bps(spread_hist)

        # ── IDLE: look for panic trigger ──────────────────────────────────────
        if state.phase == "IDLE":
            return self._check_idle(symbol, state, bars, price, spread_bps, median_spread, account_equity)

        # ── TRIGGERED: check disorder filter ─────────────────────────────────
        if state.phase == "TRIGGERED":
            return self._check_triggered(symbol, state, bars, price, spread_bps, median_spread)

        # ── STABILIZING: check bounce confirmation ────────────────────────────
        if state.phase == "STABILIZING":
            return self._check_stabilizing(symbol, state, params, bars, price, spread_bps)

        return None

    # ── Phase handlers ────────────────────────────────────────────────────────

    def _check_idle(
        self, symbol: str, state: _SymbolState, bars: list, price: float,
        spread_bps: float, median_spread: float, equity: float,
    ) -> None:
        params = self.params.for_symbol(symbol)

        # ── Regime filter ─────────────────────────────────────────────────────
        if not self._regime_ok(symbol, spread_bps, bars):
            return None

        # ── Panic trigger ─────────────────────────────────────────────────────
        drop = BarBuilder.return_pct(bars, 180)           # 180-second return
        zscore = BarBuilder.zscore(bars)
        vol_ratio = BarBuilder.volume_ratio(bars)
        imbalance = BarBuilder.trade_imbalance(bars, 180)

        drop_triggered = drop <= -params.drop_threshold_pct
        z_triggered = zscore <= params.zscore_threshold
        vol_triggered = vol_ratio >= self.params.volume_ratio_threshold
        imb_triggered = imbalance >= self.params.trade_imbalance_sell_threshold

        if not (drop_triggered and z_triggered and vol_triggered and imb_triggered):
            if drop_triggered:
                # Partial trigger: log for event study (regime_rejected)
                self._events.log(
                    symbol=symbol, state="rejected_regime",
                    drop_180s_pct=drop, zscore=zscore, volume_ratio_180s=vol_ratio,
                    trade_imbalance_180s=imbalance, spread_bps=spread_bps,
                    spread_vs_median=spread_bps / max(median_spread, 0.01),
                    panic_low=price, trigger_price=price,
                    reject_reason=self._base_reject(drop_triggered, z_triggered, vol_triggered, imb_triggered),
                )
            return None

        # All triggered — advance to TRIGGERED phase
        log.info("signal.triggered", symbol=symbol, drop=f"{drop:.3f}", z=f"{zscore:.3f}", vol=f"{vol_ratio:.2f}")
        state.phase = "TRIGGERED"
        state.trigger_ts = time.time()
        state.panic_low = price
        state.trigger_price = price
        state.trigger_drop = drop
        state.trigger_zscore = zscore
        state.trigger_volratio = vol_ratio
        state.trigger_imbalance = imbalance
        state.trigger_spread = spread_bps
        state.trigger_spread_vs_median = spread_bps / max(median_spread, 0.01)
        state._no_new_low_since = time.time()

        self._events.log(
            symbol=symbol, state="candidate",
            drop_180s_pct=drop, zscore=zscore, volume_ratio_180s=vol_ratio,
            trade_imbalance_180s=imbalance, spread_bps=spread_bps,
            spread_vs_median=state.trigger_spread_vs_median,
            panic_low=price, trigger_price=price,
        )
        return None

    def _check_triggered(
        self, symbol: str, state: _SymbolState, bars: list, price: float,
        spread_bps: float, median_spread: float,
    ) -> None:
        params = self.params.for_symbol(symbol)

        # Track new lows
        if price < state.panic_low:
            state.panic_low = price
            state._no_new_low_since = time.time()

        # ── Disorder filter ───────────────────────────────────────────────────
        spread_ratio = spread_bps / max(median_spread, 0.01)
        spread_spiked = spread_ratio >= self.params.disorder_spread_multiple

        new_low_depth_bps = (state.trigger_price - state.panic_low) / state.trigger_price * 10_000
        continuing_down = new_low_depth_bps > self.params.disorder_new_low_bps

        elapsed = time.time() - state.trigger_ts

        if spread_spiked or continuing_down:
            reject_reason = "spread_spike" if spread_spiked else "continuing_down"
            log.info("signal.disorder_rejected", symbol=symbol, reason=reject_reason,
                     spread_ratio=f"{spread_ratio:.2f}", new_low_bps=f"{new_low_depth_bps:.1f}")
            self._events.log(
                symbol=symbol, state="rejected_disorder",
                drop_180s_pct=state.trigger_drop, zscore=state.trigger_zscore,
                volume_ratio_180s=state.trigger_volratio, trade_imbalance_180s=state.trigger_imbalance,
                spread_bps=spread_bps, spread_vs_median=spread_ratio,
                panic_low=state.panic_low, trigger_price=state.trigger_price,
                reject_reason=reject_reason,
            )
            state.phase = "IDLE"
            return None

        # Advance to STABILIZING after min wait
        if elapsed >= self.params.stab_min_wait_seconds:
            state.phase = "STABILIZING"
            state.stab_start_ts = time.time()
            log.info("signal.stabilizing", symbol=symbol, panic_low=state.panic_low)

        return None

    def _check_stabilizing(
        self, symbol: str, state: _SymbolState, params, bars: list, price: float, spread_bps: float,
    ) -> Optional[SignalResult]:
        # Track new lows
        if price < state.panic_low:
            state.panic_low = price
            state._no_new_low_since = time.time()

        stab_elapsed = time.time() - state.stab_start_ts

        # ── Stabilization timeout ─────────────────────────────────────────────
        if stab_elapsed >= self.params.stab_timeout_seconds:
            log.info("signal.stab_timeout", symbol=symbol)
            self._events.log(
                symbol=symbol, state="rejected_stab",
                drop_180s_pct=state.trigger_drop, zscore=state.trigger_zscore,
                volume_ratio_180s=state.trigger_volratio, trade_imbalance_180s=state.trigger_imbalance,
                spread_bps=spread_bps, spread_vs_median=state.trigger_spread_vs_median,
                panic_low=state.panic_low, trigger_price=state.trigger_price,
                reject_reason="stab_timeout",
            )
            state.phase = "IDLE"
            return None

        no_new_low_for = time.time() - state._no_new_low_since
        seller_share = BarBuilder.trade_imbalance(bars, 10)  # last 10 bars (10 seconds)

        no_low_ok = no_new_low_for >= self.params.stab_no_new_low_seconds
        seller_ok = seller_share < self.params.stab_seller_share_max

        if not (no_low_ok and seller_ok):
            return None

        # ── All conditions met — fire signal ──────────────────────────────────
        stab_method = f"no_new_low_{no_new_low_for:.0f}s+seller_{seller_share:.2f}"
        entry_limit = price * (1 - self.params.entry_offset_bps / 10_000)
        sp = params

        stop_fixed = entry_limit * (1 - sp.sl_pct / 100)
        stop_structure = state.panic_low * (1 - sp.sl_structure_bps / 10_000)
        stop = max(stop_fixed, stop_structure)

        tp1 = entry_limit * (1 + sp.tp1_pct / 100)
        tp2 = entry_limit * (1 + sp.tp2_pct / 100)

        log.info(
            "signal.fired", symbol=symbol, price=price,
            entry=f"{entry_limit:.4f}", stop=f"{stop:.4f}",
            tp1=f"{tp1:.4f}", tp2=f"{tp2:.4f}", stab=stab_method,
        )

        self._daily_evaluated[symbol] = self._daily_evaluated.get(symbol, 0) + 1

        self._events.log(
            symbol=symbol, state="fired",
            drop_180s_pct=state.trigger_drop, zscore=state.trigger_zscore,
            volume_ratio_180s=state.trigger_volratio, trade_imbalance_180s=state.trigger_imbalance,
            spread_bps=spread_bps, spread_vs_median=state.trigger_spread_vs_median,
            panic_low=state.panic_low, trigger_price=state.trigger_price,
            stab_method=stab_method,
        )

        state.phase = "IDLE"
        return SignalResult(
            symbol=symbol, price=price, entry_limit=entry_limit, stop=stop,
            tp1=tp1, tp2=tp2,
            drop_pct=state.trigger_drop, zscore=state.trigger_zscore,
            volume_ratio=state.trigger_volratio, imbalance=state.trigger_imbalance,
            spread_bps=spread_bps, stab_method=stab_method,
        )

    # ── Regime filter ─────────────────────────────────────────────────────────

    def _regime_ok(self, symbol: str, spread_bps: float, bars: list) -> bool:
        params = self.params.for_symbol(symbol)

        if self._consecutive_losses >= self.params.max_consecutive_losses:
            return False
        if self._daily_trades >= self.params.max_trades_per_day:
            return False
        if self._daily_evaluated.get(symbol, 0) >= self.params.max_signals_evaluated_per_asset:
            return False

        # Daily loss limit (Layer 1)
        if self._daily_realized_pnl < 0 and self._last_equity > 0:
            loss_pct = -self._daily_realized_pnl / self._last_equity * 100.0
            if loss_pct >= self.params.daily_loss_limit_pct:
                log.warning("signal.daily_loss_limit", loss_pct=f"{loss_pct:.3f}")
                return False

        # Spread check + consecutive rejection counter
        if spread_bps < 999 and spread_bps > params.max_spread_bps:
            count = self._spread_reject_count.get(symbol, 0) + 1
            self._spread_reject_count[symbol] = count
            if count >= self.params.max_rejected_fills_in_row:
                log.warning("signal.spread_halt", symbol=symbol, count=count)
                # Force evaluated cap to block further entries for the day
                self._daily_evaluated[symbol] = self.params.max_signals_evaluated_per_asset
            return False
        else:
            self._spread_reject_count[symbol] = 0

        # Liquidity: 60-second volume >= 35th percentile of 30-minute distribution
        vol_35 = BarBuilder.volume_percentile(bars)
        current_60s = BarBuilder.current_60s_volume(bars)
        if vol_35 > 0 and current_60s < vol_35:
            return False

        return True

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _base_reject(drop: bool, z: bool, vol: bool, imb: bool) -> str:
        missing = []
        if not z:
            missing.append("zscore")
        if not vol:
            missing.append("volume")
        if not imb:
            missing.append("imbalance")
        return "+".join(missing) or "unknown"

    def _roll_day(self) -> None:
        today = date.today()
        if today != self._day:
            self._day = today
            self._daily_evaluated.clear()
            self._daily_trades = 0
            self._consecutive_losses = 0
            self._daily_realized_pnl = 0.0
            self._spread_reject_count.clear()
