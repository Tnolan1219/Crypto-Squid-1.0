"""
CRYPTO SQUID 3.0 - Adaptive panic reversion signal engine.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from typing import Optional

import structlog

from bar_builder import BarBuilder
from event_collector import EventCollector
from params_v3 import V3Params

log = structlog.get_logger("signal_v3")


@dataclass
class SignalResult:
    symbol: str
    price: float
    entry_limit: float
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
    phase: str = "IDLE"
    trigger_ts: float = 0.0
    panic_low: float = 0.0
    trigger_price: float = 0.0
    trigger_drop: float = 0.0
    trigger_zscore: float = 0.0
    trigger_volratio: float = 0.0
    trigger_imbalance: float = 0.0
    trigger_spread_vs_median: float = 0.0
    stab_start_ts: float = 0.0
    no_new_low_since: float = 0.0


class SignalEngineV3:
    def __init__(self, params: V3Params, event_collector: EventCollector):
        self.params = params
        self._events = event_collector
        self._states: dict[str, _SymbolState] = {}
        self._daily_evaluated: dict[str, int] = {}
        self._daily_trades: int = 0
        self._consecutive_losses: int = 0
        self._day: date = date.today()

    def register_trade_close(self, pnl: float) -> None:
        self._roll_day()
        self._daily_trades += 1
        self._consecutive_losses = 0 if pnl >= 0 else self._consecutive_losses + 1

    def check(
        self,
        symbol: str,
        bars: list,
        bid: float,
        ask: float,
        spread_hist: list[float],
        account_equity: float,
    ) -> Optional[SignalResult]:
        del account_equity
        self._roll_day()
        state = self._states.setdefault(symbol, _SymbolState())
        sp = self.params.for_symbol(symbol)

        if not bars:
            return None
        price = bars[-1].close
        if price <= 0:
            return None

        spread_bps = BarBuilder.current_spread_bps(bid, ask)
        median_spread = BarBuilder.median_spread_bps(spread_hist)

        if state.phase == "IDLE":
            return self._check_idle(symbol, state, bars, price, spread_bps, median_spread, sp)
        if state.phase == "TRIGGERED":
            return self._check_triggered(symbol, state, price, spread_bps, median_spread)
        if state.phase == "STABILIZING":
            return self._check_stabilizing(symbol, state, sp, bars, price, spread_bps)
        return None

    def _check_idle(
        self,
        symbol: str,
        state: _SymbolState,
        bars: list,
        price: float,
        spread_bps: float,
        median_spread: float,
        sp,
    ) -> Optional[SignalResult]:
        if not self._regime_ok(symbol, spread_bps, bars, price, sp):
            return None

        drop = BarBuilder.return_pct(bars, self.params.panic_drop_lookback_seconds)
        zscore = BarBuilder.zscore(bars, self.params.zscore_window_seconds)
        vol_ratio = BarBuilder.volume_ratio(
            bars,
            self.params.panic_volume_window_seconds,
            self.params.volume_baseline_seconds,
        )
        imbalance = BarBuilder.trade_imbalance(bars, self.params.panic_imbalance_window_seconds)

        drop_triggered = drop <= -sp.drop_threshold_pct
        z_triggered = zscore <= sp.zscore_threshold
        vol_triggered = vol_ratio >= self.params.volume_ratio_threshold
        imb_triggered = imbalance >= self.params.trade_imbalance_sell_threshold

        if not (drop_triggered and z_triggered and vol_triggered and imb_triggered):
            if drop_triggered:
                self._events.log(
                    symbol=symbol,
                    state="rejected_trigger",
                    drop_180s_pct=drop,
                    zscore=zscore,
                    volume_ratio_180s=vol_ratio,
                    trade_imbalance_180s=imbalance,
                    spread_bps=spread_bps,
                    spread_vs_median=spread_bps / max(median_spread, 0.01),
                    panic_low=price,
                    trigger_price=price,
                    reject_reason=self._base_reject(drop_triggered, z_triggered, vol_triggered, imb_triggered),
                )
            return None

        state.phase = "TRIGGERED"
        state.trigger_ts = time.time()
        state.panic_low = price
        state.trigger_price = price
        state.trigger_drop = drop
        state.trigger_zscore = zscore
        state.trigger_volratio = vol_ratio
        state.trigger_imbalance = imbalance
        state.trigger_spread_vs_median = spread_bps / max(median_spread, 0.01)
        state.no_new_low_since = time.time()
        self._events.log(
            symbol=symbol,
            state="candidate",
            drop_180s_pct=drop,
            zscore=zscore,
            volume_ratio_180s=vol_ratio,
            trade_imbalance_180s=imbalance,
            spread_bps=spread_bps,
            spread_vs_median=state.trigger_spread_vs_median,
            panic_low=price,
            trigger_price=price,
        )
        return None

    def _check_triggered(
        self,
        symbol: str,
        state: _SymbolState,
        price: float,
        spread_bps: float,
        median_spread: float,
    ) -> Optional[SignalResult]:
        if price < state.panic_low:
            state.panic_low = price
            state.no_new_low_since = time.time()

        spread_ratio = spread_bps / max(median_spread, 0.01)
        spread_spiked = spread_ratio >= self.params.disorder_spread_multiple
        new_low_depth_bps = (state.trigger_price - state.panic_low) / max(state.trigger_price, 1e-9) * 10_000
        sp = self.params.for_symbol(symbol)
        continuing_down = new_low_depth_bps > sp.disorder_new_low_bps

        if spread_spiked or continuing_down:
            reason = "spread_spike" if spread_spiked else "continuing_down"
            self._events.log(
                symbol=symbol,
                state="rejected_disorder",
                drop_180s_pct=state.trigger_drop,
                zscore=state.trigger_zscore,
                volume_ratio_180s=state.trigger_volratio,
                trade_imbalance_180s=state.trigger_imbalance,
                spread_bps=spread_bps,
                spread_vs_median=spread_ratio,
                panic_low=state.panic_low,
                trigger_price=state.trigger_price,
                reject_reason=reason,
            )
            state.phase = "IDLE"
            return None

        elapsed = time.time() - state.trigger_ts
        if elapsed >= self.params.stab_min_wait_seconds:
            state.phase = "STABILIZING"
            state.stab_start_ts = time.time()
        return None

    def _check_stabilizing(
        self,
        symbol: str,
        state: _SymbolState,
        sp,
        bars: list,
        price: float,
        spread_bps: float,
    ) -> Optional[SignalResult]:
        if price < state.panic_low:
            state.panic_low = price
            state.no_new_low_since = time.time()

        if (time.time() - state.stab_start_ts) >= self.params.stab_timeout_seconds:
            self._events.log(
                symbol=symbol,
                state="rejected_stab",
                drop_180s_pct=state.trigger_drop,
                zscore=state.trigger_zscore,
                volume_ratio_180s=state.trigger_volratio,
                trade_imbalance_180s=state.trigger_imbalance,
                spread_bps=spread_bps,
                spread_vs_median=state.trigger_spread_vs_median,
                panic_low=state.panic_low,
                trigger_price=state.trigger_price,
                reject_reason="stab_timeout",
            )
            state.phase = "IDLE"
            return None

        no_new_low_for = time.time() - state.no_new_low_since
        buy_vol, sell_vol = BarBuilder.buy_sell_volume(bars, self.params.stab_bid_over_ask_seconds)
        higher_low_ok = BarBuilder.micro_higher_low(
            bars,
            recent_seconds=self.params.stab_higher_low_recent_seconds,
            prior_seconds=self.params.stab_higher_low_prior_seconds,
        )

        no_low_ok = no_new_low_for >= self.params.stab_no_new_low_seconds
        bid_over_ask_ok = buy_vol > sell_vol

        if not (no_low_ok and bid_over_ask_ok and higher_low_ok):
            return None

        entry_limit = price * (1 - sp.entry_offset_bps / 10_000)
        stop_widen_mult = (
            self.params.high_vol_stop_widen_mult
            if state.trigger_volratio >= self.params.high_vol_ratio_threshold
            else 1.0
        )
        stop_fixed = entry_limit * (1 - (sp.sl_pct * stop_widen_mult) / 100)
        stop_structure = state.panic_low * (1 - (sp.sl_structure_bps * stop_widen_mult) / 10_000)
        stop = max(stop_fixed, stop_structure)
        tp1 = entry_limit * (1 + sp.tp1_pct / 100)
        tp2 = entry_limit * (1 + sp.tp2_pct / 100)

        stab_method = (
            f"no_new_low_{no_new_low_for:.0f}s"
            f"+buy_gt_sell_{buy_vol > sell_vol}"
            f"+higher_low_{higher_low_ok}"
        )
        self._daily_evaluated[symbol] = self._daily_evaluated.get(symbol, 0) + 1
        self._events.log(
            symbol=symbol,
            state="fired",
            drop_180s_pct=state.trigger_drop,
            zscore=state.trigger_zscore,
            volume_ratio_180s=state.trigger_volratio,
            trade_imbalance_180s=state.trigger_imbalance,
            spread_bps=spread_bps,
            spread_vs_median=state.trigger_spread_vs_median,
            panic_low=state.panic_low,
            trigger_price=state.trigger_price,
            stab_method=stab_method,
        )
        state.phase = "IDLE"
        return SignalResult(
            symbol=symbol,
            price=price,
            entry_limit=entry_limit,
            stop=stop,
            tp1=tp1,
            tp2=tp2,
            drop_pct=state.trigger_drop,
            zscore=state.trigger_zscore,
            volume_ratio=state.trigger_volratio,
            imbalance=state.trigger_imbalance,
            spread_bps=spread_bps,
            stab_method=stab_method,
        )

    def _regime_ok(self, symbol: str, spread_bps: float, bars: list, price: float, sp) -> bool:
        if self._consecutive_losses >= self.params.max_consecutive_losses:
            return False
        if self._daily_trades >= self.params.max_trades_per_day:
            return False
        if self._daily_evaluated.get(symbol, 0) >= self.params.max_signals_evaluated_per_asset:
            return False

        if spread_bps < 999 and spread_bps > sp.max_spread_bps:
            return False

        vol_35 = BarBuilder.volume_percentile(bars, self.params.volume_percentile_35_threshold)
        current_60s = BarBuilder.current_60s_volume(bars)
        if vol_35 > 0 and current_60s < vol_35:
            return False

        vwap_15m = BarBuilder.vwap(bars, self.params.trend_vwap_seconds)
        ema_slope_bps = BarBuilder.ema_slope_bps(
            bars,
            seconds=self.params.trend_ema_seconds,
            ema_period_seconds=self.params.trend_ema_period_seconds,
            lookback_seconds=self.params.trend_ema_slope_lookback_seconds,
        )
        trend_ok = (vwap_15m > 0 and price > vwap_15m) or (ema_slope_bps >= 0)
        if not trend_ok:
            return False

        drop_recent = BarBuilder.return_pct(bars, self.params.cascade_reject_lookback_seconds)
        cascade_cutoff = -sp.drop_threshold_pct * self.params.cascade_reject_drop_multiplier
        if drop_recent <= cascade_cutoff:
            return False

        return True

    @staticmethod
    def _base_reject(drop: bool, z: bool, vol: bool, imb: bool) -> str:
        del drop
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
