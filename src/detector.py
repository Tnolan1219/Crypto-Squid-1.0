"""Signal engine for downside overreaction reversals on Hyperliquid."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean, pstdev
from typing import Dict, List

from config import Config
from models import SignalDecision


@dataclass
class TradeTick:
    ts: float
    price: float
    size: float


@dataclass
class TriggerState:
    start_ts: float
    panic_low: float
    last_low_ts: float
    drop_pct: float
    volume_ratio: float
    zscore: float


@dataclass
class SymbolState:
    trades: deque = field(default_factory=lambda: deque(maxlen=12000))
    buckets: deque = field(default_factory=lambda: deque(maxlen=30))
    active_trigger: TriggerState | None = None
    candle_closes: deque = field(default_factory=lambda: deque(maxlen=20))
    current_candle_bucket: int = -1
    current_candle_close: float = 0.0


class SignalEngine:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._state: Dict[str, SymbolState] = {symbol: SymbolState() for symbol in cfg.symbols}

    def on_tick(self, symbol: str, ts: float, price: float, size: float) -> List[SignalDecision]:
        state = self._state[symbol]
        state.trades.append(TradeTick(ts=ts, price=price, size=size))
        self._update_candles(state, ts, price)
        self._prune_old(symbol, ts)

        decisions: List[SignalDecision] = []
        drop_pct = self._price_drop_pct(state, ts)
        volume_ratio = self._volume_ratio(symbol, state, ts)
        zscore = self._price_zscore(state)
        params = self.cfg.symbol_params(symbol)

        has_sharp_drop = drop_pct >= params.drop_threshold_pct
        has_volume = volume_ratio >= self.cfg.volume_spike_multiplier
        has_overextension = zscore <= self.cfg.zscore_threshold

        if state.active_trigger is None and has_sharp_drop:
            if not has_volume or not has_overextension:
                decisions.append(
                    self._decision(
                        symbol=symbol,
                        price=price,
                        drop_pct=drop_pct,
                        volume_ratio=volume_ratio,
                        zscore=zscore,
                        stabilization="n/a",
                        passed=False,
                        reject_reason=self._base_reject_reason(has_volume, has_overextension),
                    )
                )
                return decisions

            state.active_trigger = TriggerState(
                start_ts=ts,
                panic_low=price,
                last_low_ts=ts,
                drop_pct=drop_pct,
                volume_ratio=volume_ratio,
                zscore=zscore,
            )
            return decisions

        trigger = state.active_trigger
        if trigger is None:
            return decisions

        if price < trigger.panic_low:
            trigger.panic_low = price
            trigger.last_low_ts = ts

        elapsed = ts - trigger.start_ts
        if elapsed < self.cfg.stabilization_wait_seconds:
            return decisions

        hold_ok = (ts - trigger.last_low_ts) >= self.cfg.stabilization_hold_seconds
        candles_ok = self._has_downside_deceleration(state)

        if hold_ok or candles_ok:
            stabilization = "panic-low-hold" if hold_ok else "downside-deceleration"
            decisions.append(
                self._decision(
                    symbol=symbol,
                    price=price,
                    drop_pct=trigger.drop_pct,
                    volume_ratio=trigger.volume_ratio,
                    zscore=trigger.zscore,
                    stabilization=stabilization,
                    passed=True,
                    reject_reason="",
                )
            )
            state.active_trigger = None
            return decisions

        if elapsed >= self.cfg.stabilization_max_seconds:
            decisions.append(
                self._decision(
                    symbol=symbol,
                    price=price,
                    drop_pct=trigger.drop_pct,
                    volume_ratio=trigger.volume_ratio,
                    zscore=trigger.zscore,
                    stabilization="timeout",
                    passed=False,
                    reject_reason="stabilization_timeout",
                )
            )
            state.active_trigger = None

        return decisions

    def _base_reject_reason(self, has_volume: bool, has_overextension: bool) -> str:
        if not has_volume and not has_overextension:
            return "volume_and_zscore_failed"
        if not has_volume:
            return "volume_spike_failed"
        return "zscore_failed"

    def _update_candles(self, state: SymbolState, ts: float, price: float) -> None:
        bucket = int(ts // 15)
        if state.current_candle_bucket == -1:
            state.current_candle_bucket = bucket
            state.current_candle_close = price
            return
        if bucket != state.current_candle_bucket:
            state.candle_closes.append(state.current_candle_close)
            state.current_candle_bucket = bucket
        state.current_candle_close = price

    def _has_downside_deceleration(self, state: SymbolState) -> bool:
        if len(state.candle_closes) < 3:
            return False
        c0, c1, c2 = state.candle_closes[-3], state.candle_closes[-2], state.candle_closes[-1]
        move1 = c1 - c0
        move2 = c2 - c1
        return move1 < 0 and move2 < 0 and abs(move2) < abs(move1)

    def _prune_old(self, symbol: str, now_ts: float) -> None:
        state = self._state[symbol]
        keep_after = now_ts - max(self.cfg.drop_lookback_seconds * 3, 3600)
        while state.trades and state.trades[0].ts < keep_after:
            state.trades.popleft()

        current_bucket = int(now_ts // self.cfg.volume_window_seconds)
        if state.buckets and state.buckets[-1][0] == current_bucket:
            return

        if state.trades:
            prev_bucket = current_bucket - 1
            vol = 0.0
            bucket_start = prev_bucket * self.cfg.volume_window_seconds
            bucket_end = bucket_start + self.cfg.volume_window_seconds
            for tick in state.trades:
                if bucket_start <= tick.ts < bucket_end:
                    vol += tick.price * tick.size
            if not state.buckets or state.buckets[-1][0] != prev_bucket:
                state.buckets.append((prev_bucket, vol))

    def _price_drop_pct(self, state: SymbolState, now_ts: float) -> float:
        if not state.trades:
            return 0.0
        current = state.trades[-1].price
        lookback_ts = now_ts - self.cfg.drop_lookback_seconds
        older_price = None
        for tick in reversed(state.trades):
            if tick.ts <= lookback_ts:
                older_price = tick.price
                break
        if older_price is None or older_price <= 0:
            return 0.0
        return max(0.0, (older_price - current) / older_price * 100.0)

    def _volume_ratio(self, symbol: str, state: SymbolState, now_ts: float) -> float:
        if len(state.trades) < 2:
            return 0.0

        window_start = now_ts - self.cfg.volume_window_seconds
        current_vol = sum(t.price * t.size for t in state.trades if t.ts >= window_start)

        baseline_buckets = [v for _, v in list(state.buckets)[-self.cfg.volume_baseline_periods :]]
        if len(baseline_buckets) < 5:
            return 0.0
        baseline = mean(baseline_buckets)
        if baseline <= 0:
            return 0.0
        return current_vol / baseline

    def _price_zscore(self, state: SymbolState) -> float:
        prices = [t.price for t in list(state.trades)[-self.cfg.zscore_lookback_ticks :]]
        if len(prices) < 20:
            return 0.0
        mu = mean(prices)
        sigma = pstdev(prices)
        if sigma <= 1e-9:
            return 0.0
        return (prices[-1] - mu) / sigma

    def _decision(
        self,
        symbol: str,
        price: float,
        drop_pct: float,
        volume_ratio: float,
        zscore: float,
        stabilization: str,
        passed: bool,
        reject_reason: str,
    ) -> SignalDecision:
        return SignalDecision(
            ts=datetime.now(timezone.utc),
            symbol=symbol,
            price=price,
            drop_pct=drop_pct,
            volume_ratio=volume_ratio,
            zscore=zscore,
            stabilization=stabilization,
            passed=passed,
            reject_reason=reject_reason,
        )
