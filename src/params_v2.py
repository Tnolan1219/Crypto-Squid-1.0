"""
CRYPTO SQUID v2 — Strategy parameters.

Layer 1 (immutable): edit only with explicit user approval.
Layer 2 (tunable):   propose changes via strategy/hypotheses.md → approve → update here.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SymbolParamsV2:
    name: str
    # Signal thresholds (Layer 2)
    drop_threshold_pct: float       # 180-second return must be <= -this
    zscore_threshold: float         # z-score must be <= this (vs 30-min distribution)
    # Spread filter (Layer 2)
    max_spread_bps: float           # reject if spread > this
    # Exits (Layer 2)
    tp1_pct: float                  # first target %
    tp1_size_frac: float            # fraction of position to exit at tp1 (0.5 = 50%)
    tp2_pct: float                  # second target %
    sl_pct: float                   # fixed stop % below entry
    sl_structure_bps: float         # structure stop: N bps below panic low
    time_stop_minutes: float        # hard time stop
    fast_reduce_minutes: float      # partial reduce if still open and P&L is marginal


# ── DEFAULT INSTANCES ─────────────────────────────────────────────────────────

BTC_V2 = SymbolParamsV2(
    name="BTC-USD",
    drop_threshold_pct=0.90,        # stricter than v1 (was 0.75)
    zscore_threshold=-2.25,         # stricter than v1 (was -2.0)
    max_spread_bps=4.0,
    tp1_pct=0.55,
    tp1_size_frac=0.50,
    tp2_pct=0.95,
    sl_pct=0.45,                    # tighter than v1 (was 0.55)
    sl_structure_bps=8.0,           # 0.08% below panic low
    time_stop_minutes=15.0,         # much tighter than v1 (was 90)
    fast_reduce_minutes=5.0,
)

ETH_V2 = SymbolParamsV2(
    name="ETH-USD",
    drop_threshold_pct=1.20,        # stricter than v1 (was 1.00)
    zscore_threshold=-2.25,
    max_spread_bps=6.0,
    tp1_pct=0.70,
    tp1_size_frac=0.50,
    tp2_pct=1.15,
    sl_pct=0.55,
    sl_structure_bps=8.0,
    time_stop_minutes=15.0,
    fast_reduce_minutes=5.0,
)


@dataclass(frozen=True)
class V2Params:
    # ── RISK (Layer 1) ────────────────────────────────────────────────────────
    risk_per_trade_pct: float = 1.00            # increased for expanded paper validation
    max_trades_per_day: int = 6                 # less restrictive daily cap
    max_signals_evaluated_per_asset: int = 4    # cap signal evaluations per symbol/day
    max_consecutive_losses: int = 2
    daily_loss_limit_pct: float = 1.0           # tighter than v1 (was 2.0)
    max_gross_exposure_btc_pct: float = 20.0    # max 20% of equity in BTC
    max_gross_exposure_eth_pct: float = 15.0
    max_rejected_fills_in_row: int = 3          # stop if spread keeps rejecting entries

    # ── ENTRY (Layer 2) ───────────────────────────────────────────────────────
    entry_order_lifetime_seconds: float = 15.0  # cancel unfilled limit after 15s (was 30)
    entry_offset_bps: float = 3.0               # limit = best_bid + 1 tick OR signal - 3bps

    # ── VOLUME / IMBALANCE (Layer 2) ──────────────────────────────────────────
    volume_ratio_threshold: float = 2.0         # 180s vol >= 2× 30-min median
    volume_percentile_35_threshold: float = 0.35 # 60s volume >= 35th pct of 30-min dist
    trade_imbalance_sell_threshold: float = 0.60 # seller-initiated >= 60% of 180s vol

    # ── DISORDER FILTER (Layer 2) ─────────────────────────────────────────────
    disorder_spread_multiple: float = 2.0       # reject if spread > 2× its recent median
    disorder_new_low_bps: float = 15.0          # reject if new low > 15bps below panic low

    # ── STABILIZATION (Layer 2) ───────────────────────────────────────────────
    stab_min_wait_seconds: float = 20.0         # minimum wait after panic low
    stab_no_new_low_seconds: float = 20.0       # panic low must hold for 20s
    stab_seller_share_max: float = 0.55         # seller vol < 55% in last 10s
    stab_timeout_seconds: float = 90.0          # abort if not stabilized in 90s

    # ── ROLLING WINDOWS ───────────────────────────────────────────────────────
    zscore_window_seconds: int = 1800           # 30 minutes for z-score baseline
    volume_baseline_seconds: int = 1800         # 30 minutes for volume baseline

    # ── PER-SYMBOL ────────────────────────────────────────────────────────────
    btc: SymbolParamsV2 = field(default_factory=lambda: BTC_V2)
    eth: SymbolParamsV2 = field(default_factory=lambda: ETH_V2)

    def for_symbol(self, symbol: str) -> SymbolParamsV2:
        if symbol == "BTC-USD":
            return self.btc
        return self.eth


# ── SINGLETON ─────────────────────────────────────────────────────────────────
# Import this in other modules. Override fields to test parameter changes.
DEFAULT_V2_PARAMS = V2Params()
