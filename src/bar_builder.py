"""
1-second OHLCV bar builder with rolling window statistics.

Thread-safe: on_trade() is called from the WebSocket thread;
stat methods are called from the main bot thread.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Optional


@dataclass
class Bar:
    ts: int             # unix second
    open: float
    high: float
    low: float
    close: float
    volume: float       # dollar volume (price × size)
    buy_volume: float   # taker-buy dollar volume
    sell_volume: float  # taker-sell dollar volume
    trade_count: int


class SymbolBars:
    MAX_BARS = 1810  # ~30 minutes of 1-second bars

    def __init__(self):
        self.bars: deque[Bar] = deque(maxlen=self.MAX_BARS)
        self._current: Optional[dict] = None
        self.best_bid: float = 0.0
        self.best_ask: float = 0.0
        # Spread history for median calculation (one entry per bar)
        self._spread_bps_history: deque[float] = deque(maxlen=self.MAX_BARS)

    def feed(self, price: float, size: float, side: str, ts: Optional[float] = None) -> Optional[Bar]:
        now = int(ts or time.time())
        dollar = price * size

        if self._current is None:
            self._current = _new_bar(now, price, dollar, side)
            return None

        c = self._current
        if now > c["ts"]:
            completed = Bar(
                ts=c["ts"], open=c["open"], high=c["high"],
                low=c["low"], close=c["close"], volume=c["volume"],
                buy_volume=c["buy_volume"], sell_volume=c["sell_volume"],
                trade_count=c["trade_count"],
            )
            self.bars.append(completed)
            if self.best_bid > 0 and self.best_ask > 0:
                mid = (self.best_bid + self.best_ask) / 2
                self._spread_bps_history.append(
                    (self.best_ask - self.best_bid) / mid * 10_000 if mid > 0 else 0.0
                )
            self._current = _new_bar(now, price, dollar, side)
            return completed

        c["high"] = max(c["high"], price)
        c["low"] = min(c["low"], price)
        c["close"] = price
        c["volume"] += dollar
        c["trade_count"] += 1
        if side.upper() in {"BUY", "B"}:
            c["buy_volume"] += dollar
        else:
            c["sell_volume"] += dollar
        return None

    def last_bars(self, n: int) -> list[Bar]:
        return list(self.bars)[-n:]

    def current_price(self) -> float:
        if self._current:
            return self._current["close"]
        if self.bars:
            return self.bars[-1].close
        return 0.0


def _new_bar(ts: int, price: float, dollar: float, side: str) -> dict:
    is_buy = side.upper() in {"BUY", "B"}
    return {
        "ts": ts, "open": price, "high": price, "low": price,
        "close": price, "volume": dollar, "trade_count": 1,
        "buy_volume": dollar if is_buy else 0.0,
        "sell_volume": dollar if not is_buy else 0.0,
    }


class BarBuilder:
    """Thread-safe bar manager for all tracked symbols."""

    def __init__(self):
        self._lock = threading.Lock()
        self._symbols: dict[str, SymbolBars] = {}

    def _get(self, symbol: str) -> SymbolBars:
        if symbol not in self._symbols:
            self._symbols[symbol] = SymbolBars()
        return self._symbols[symbol]

    def on_trade(self, symbol: str, price: float, size: float, side: str, ts: Optional[float] = None) -> None:
        with self._lock:
            self._get(symbol).feed(price, size, side, ts)

    def update_spread(self, symbol: str, bid: float, ask: float) -> None:
        with self._lock:
            sb = self._get(symbol)
            sb.best_bid = bid
            sb.best_ask = ask

    # ── Snapshot for signal checks (releases lock immediately) ────────────────

    def snapshot(self, symbol: str) -> tuple[list[Bar], float, float, float, list[float]]:
        """Returns (bars[-1800:], best_bid, best_ask, current_price, spread_history) under lock."""
        with self._lock:
            sb = self._get(symbol)
            bars = list(sb.bars)
            spread_hist = list(sb._spread_bps_history)
            return bars, sb.best_bid, sb.best_ask, sb.current_price(), spread_hist

    # ── Stat helpers (operate on data already copied out of lock) ─────────────

    @staticmethod
    def return_pct(bars: list[Bar], seconds: int) -> float:
        tail = bars[-seconds:] if len(bars) >= seconds else bars
        if len(tail) < 2:
            return 0.0
        return (tail[-1].close - tail[0].open) / tail[0].open * 100.0

    @staticmethod
    def zscore(bars: list[Bar], window: int = 1800) -> float:
        tail = bars[-window:]
        if len(tail) < 20:
            return 0.0
        returns = [(b.close - b.open) / b.open * 100.0 if b.open else 0.0 for b in tail]
        mu = mean(returns)
        sigma = pstdev(returns)
        if sigma < 1e-10:
            return 0.0
        return (returns[-1] - mu) / sigma

    @staticmethod
    def volume_ratio(bars: list[Bar], window_s: int = 180, baseline_s: int = 1800) -> float:
        if len(bars) < window_s + 1:
            return 0.0
        recent_vol = sum(b.volume for b in bars[-window_s:])
        baseline_bars = bars[-(baseline_s + window_s):-window_s]
        if len(baseline_bars) < window_s:
            return 0.0
        # Chunked median of N-second periods in baseline
        chunks = []
        for i in range(0, len(baseline_bars) - window_s, window_s):
            chunks.append(sum(b.volume for b in baseline_bars[i:i + window_s]))
        if not chunks:
            return 0.0
        median_vol = sorted(chunks)[len(chunks) // 2]
        return (recent_vol / median_vol) if median_vol > 0 else 0.0

    @staticmethod
    def trade_imbalance(bars: list[Bar], seconds: int = 180) -> float:
        """Fraction of dollar volume that is seller-initiated. >0.5 = sellers dominant."""
        tail = bars[-seconds:]
        total = sum(b.volume for b in tail)
        sell = sum(b.sell_volume for b in tail)
        return (sell / total) if total > 0 else 0.5

    @staticmethod
    def current_spread_bps(bid: float, ask: float) -> float:
        if bid <= 0 or ask <= 0:
            return 999.0
        mid = (bid + ask) / 2.0
        return (ask - bid) / mid * 10_000 if mid > 0 else 999.0

    @staticmethod
    def median_spread_bps(spread_hist: list[float]) -> float:
        if not spread_hist:
            return 0.0
        s = sorted(spread_hist)
        return s[len(s) // 2]

    @staticmethod
    def volume_percentile(bars: list[Bar], pct: float = 0.35, window_s: int = 60, baseline_s: int = 1800) -> float:
        """N-th percentile of 60-second volume over last 30 minutes."""
        baseline = bars[-(baseline_s + window_s):-window_s]
        chunks = []
        for i in range(0, len(baseline) - window_s, window_s):
            chunks.append(sum(b.volume for b in baseline[i:i + window_s]))
        if not chunks:
            return 0.0
        chunks.sort()
        idx = max(0, int(len(chunks) * pct) - 1)
        return chunks[idx]

    @staticmethod
    def current_60s_volume(bars: list[Bar]) -> float:
        return sum(b.volume for b in bars[-60:])

    @staticmethod
    def vwap(bars: list[Bar], seconds: int = 900) -> float:
        tail = bars[-seconds:]
        notional = sum(b.close * b.volume for b in tail)
        volume = sum(b.volume for b in tail)
        if volume <= 0:
            return 0.0
        return notional / volume

    @staticmethod
    def ema_slope_bps(
        bars: list[Bar],
        seconds: int = 900,
        ema_period_seconds: int = 120,
        lookback_seconds: int = 30,
    ) -> float:
        tail = bars[-seconds:]
        if len(tail) < max(ema_period_seconds, lookback_seconds + 2):
            return 0.0
        closes = [b.close for b in tail]
        alpha = 2.0 / (ema_period_seconds + 1.0)
        ema_values: list[float] = []
        ema = closes[0]
        for px in closes:
            ema = alpha * px + (1.0 - alpha) * ema
            ema_values.append(ema)
        prev_idx = max(0, len(ema_values) - lookback_seconds - 1)
        prev = ema_values[prev_idx]
        last = ema_values[-1]
        if prev <= 0:
            return 0.0
        return (last - prev) / prev * 10_000

    @staticmethod
    def buy_sell_volume(bars: list[Bar], seconds: int = 10) -> tuple[float, float]:
        tail = bars[-seconds:]
        buy = sum(b.buy_volume for b in tail)
        sell = sum(b.sell_volume for b in tail)
        return buy, sell

    @staticmethod
    def micro_higher_low(bars: list[Bar], recent_seconds: int = 10, prior_seconds: int = 10) -> bool:
        need = recent_seconds + prior_seconds
        if len(bars) < need:
            return False
        prior = bars[-need:-recent_seconds]
        recent = bars[-recent_seconds:]
        if not prior or not recent:
            return False
        prior_low = min(b.low for b in prior)
        recent_low = min(b.low for b in recent)
        return recent_low > prior_low
