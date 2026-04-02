"""
Event study collector.

Logs ALL candidate panic events to data/events/events.csv — including those
that were rejected by the disorder filter or stabilization timeout.

This is the primary data source for the anti-overfitting research protocol:
  Phase 1: collect 300+ events before touching any thresholds.
  Phase 3: chronological train/validate/test split on this data.

Schema (one row per candidate event):
  ts, symbol, state (candidate|rejected_regime|rejected_disorder|rejected_stab|fired),
  drop_180s_pct, zscore, volume_ratio_180s, trade_imbalance_180s,
  spread_bps, spread_vs_median,
  panic_low, trigger_price,
  stab_method (n/a if not fired),
  reject_reason (empty if fired),
  -- outcome columns filled later by post-processor or propose-experiments --
  outcome_10s, outcome_30s, outcome_60s, outcome_180s, outcome_300s, outcome_900s,
  mae, mfe
"""

from __future__ import annotations

import csv
import threading
from datetime import datetime, timezone
from pathlib import Path


_FIELDNAMES = [
    "ts", "symbol", "state",
    "drop_180s_pct", "zscore", "volume_ratio_180s", "trade_imbalance_180s",
    "spread_bps", "spread_vs_median",
    "panic_low", "trigger_price",
    "stab_method", "reject_reason",
    "outcome_10s", "outcome_30s", "outcome_60s",
    "outcome_180s", "outcome_300s", "outcome_900s",
    "mae", "mfe",
]


class EventCollector:
    def __init__(self, root: Path):
        self._path = root / "data" / "events" / "events.csv"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        if not self._path.exists():
            self._write_header()

    def _write_header(self) -> None:
        with open(self._path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=_FIELDNAMES).writeheader()

    def log(
        self,
        *,
        symbol: str,
        state: str,
        drop_180s_pct: float,
        zscore: float,
        volume_ratio_180s: float,
        trade_imbalance_180s: float,
        spread_bps: float,
        spread_vs_median: float,
        panic_low: float,
        trigger_price: float,
        stab_method: str = "",
        reject_reason: str = "",
    ) -> None:
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "state": state,
            "drop_180s_pct": round(drop_180s_pct, 4),
            "zscore": round(zscore, 4),
            "volume_ratio_180s": round(volume_ratio_180s, 4),
            "trade_imbalance_180s": round(trade_imbalance_180s, 4),
            "spread_bps": round(spread_bps, 2),
            "spread_vs_median": round(spread_vs_median, 3),
            "panic_low": round(panic_low, 4),
            "trigger_price": round(trigger_price, 4),
            "stab_method": stab_method,
            "reject_reason": reject_reason,
            "outcome_10s": "", "outcome_30s": "", "outcome_60s": "",
            "outcome_180s": "", "outcome_300s": "", "outcome_900s": "",
            "mae": "", "mfe": "",
        }
        with self._lock:
            with open(self._path, "a", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=_FIELDNAMES).writerow(row)

    def count(self) -> int:
        """Total events logged so far."""
        if not self._path.exists():
            return 0
        with open(self._path, encoding="utf-8") as f:
            return max(0, sum(1 for _ in f) - 1)  # subtract header
