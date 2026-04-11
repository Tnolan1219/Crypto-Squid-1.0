"""
Crypto-Squid 3.1 - Adaptive panic reversion parameters.

This is the current source-of-truth strategy parameter set.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SymbolParamsV3:
    name: str
    drop_threshold_pct: float
    zscore_threshold: float
    max_spread_bps: float
    entry_offset_bps: float
    tp1_pct: float
    tp1_size_frac: float
    tp2_pct: float
    sl_pct: float
    sl_structure_bps: float
    disorder_new_low_bps: float
    capital_per_trade_pct: float
    time_stop_minutes: float
    fast_reduce_minutes: float
    trailing_stop_pct: float
    stop_ioc_guard_bps: float
    max_gross_exposure_pct: float


BTC_V3 = SymbolParamsV3(
    name="BTC-USD",
    drop_threshold_pct=0.80,
    zscore_threshold=-2.25,
    max_spread_bps=4.0,
    entry_offset_bps=2.0,
    tp1_pct=0.50,
    tp1_size_frac=0.50,
    tp2_pct=0.90,
    sl_pct=0.45,
    sl_structure_bps=8.0,
    disorder_new_low_bps=25.0,
    capital_per_trade_pct=10.0,
    time_stop_minutes=15.0,
    fast_reduce_minutes=7.0,
    trailing_stop_pct=0.35,
    stop_ioc_guard_bps=2.0,
    max_gross_exposure_pct=20.0,
)

ETH_V3 = SymbolParamsV3(
    name="ETH-USD",
    drop_threshold_pct=1.05,
    zscore_threshold=-2.25,
    max_spread_bps=6.0,
    entry_offset_bps=3.0,
    tp1_pct=0.60,
    tp1_size_frac=0.50,
    tp2_pct=1.05,
    sl_pct=0.55,
    sl_structure_bps=8.0,
    disorder_new_low_bps=30.0,
    capital_per_trade_pct=8.0,
    time_stop_minutes=15.0,
    fast_reduce_minutes=7.0,
    trailing_stop_pct=0.45,
    stop_ioc_guard_bps=3.0,
    max_gross_exposure_pct=15.0,
)

SOL_V3 = SymbolParamsV3(
    name="SOL-USD",
    drop_threshold_pct=1.40,
    zscore_threshold=-2.10,
    max_spread_bps=12.0,
    entry_offset_bps=5.0,
    tp1_pct=0.90,
    tp1_size_frac=0.50,
    tp2_pct=1.50,
    sl_pct=0.80,
    sl_structure_bps=10.0,
    disorder_new_low_bps=50.0,
    capital_per_trade_pct=6.0,
    time_stop_minutes=12.0,
    fast_reduce_minutes=6.0,
    trailing_stop_pct=0.60,
    stop_ioc_guard_bps=6.0,
    max_gross_exposure_pct=10.0,
)

DOGE_V3 = SymbolParamsV3(
    name="DOGE-USD",
    drop_threshold_pct=1.60,
    zscore_threshold=-2.00,
    max_spread_bps=15.0,
    entry_offset_bps=7.0,
    tp1_pct=1.00,
    tp1_size_frac=0.50,
    tp2_pct=1.80,
    sl_pct=0.90,
    sl_structure_bps=11.0,
    disorder_new_low_bps=60.0,
    capital_per_trade_pct=4.0,
    time_stop_minutes=12.0,
    fast_reduce_minutes=6.0,
    trailing_stop_pct=0.80,
    stop_ioc_guard_bps=6.0,
    max_gross_exposure_pct=7.0,
)

ADA_V3 = SymbolParamsV3(
    name="ADA-USD",
    drop_threshold_pct=1.30,
    zscore_threshold=-2.05,
    max_spread_bps=15.0,
    entry_offset_bps=7.0,
    tp1_pct=0.90,
    tp1_size_frac=0.50,
    tp2_pct=1.60,
    sl_pct=0.85,
    sl_structure_bps=10.0,
    disorder_new_low_bps=60.0,
    capital_per_trade_pct=4.0,
    time_stop_minutes=12.0,
    fast_reduce_minutes=6.0,
    trailing_stop_pct=0.70,
    stop_ioc_guard_bps=6.0,
    max_gross_exposure_pct=7.0,
)

AVAX_V3 = SymbolParamsV3(
    name="AVAX-USD",
    drop_threshold_pct=1.50,
    zscore_threshold=-2.00,
    max_spread_bps=18.0,
    entry_offset_bps=8.0,
    tp1_pct=1.00,
    tp1_size_frac=0.50,
    tp2_pct=1.80,
    sl_pct=1.00,
    sl_structure_bps=11.0,
    disorder_new_low_bps=70.0,
    capital_per_trade_pct=3.0,
    time_stop_minutes=12.0,
    fast_reduce_minutes=6.0,
    trailing_stop_pct=0.75,
    stop_ioc_guard_bps=6.0,
    max_gross_exposure_pct=6.0,
)

POL_V3 = SymbolParamsV3(
    name="POL-USD",
    drop_threshold_pct=1.40,
    zscore_threshold=-2.00,
    max_spread_bps=18.0,
    entry_offset_bps=8.0,
    tp1_pct=1.00,
    tp1_size_frac=0.50,
    tp2_pct=1.70,
    sl_pct=0.95,
    sl_structure_bps=10.0,
    disorder_new_low_bps=70.0,
    capital_per_trade_pct=3.0,
    time_stop_minutes=12.0,
    fast_reduce_minutes=6.0,
    trailing_stop_pct=0.70,
    stop_ioc_guard_bps=6.0,
    max_gross_exposure_pct=6.0,
)

MATIC_V3 = SymbolParamsV3(
    name="MATIC-USD",
    drop_threshold_pct=1.40,
    zscore_threshold=-2.00,
    max_spread_bps=18.0,
    entry_offset_bps=8.0,
    tp1_pct=1.00,
    tp1_size_frac=0.50,
    tp2_pct=1.70,
    sl_pct=0.95,
    sl_structure_bps=10.0,
    disorder_new_low_bps=70.0,
    capital_per_trade_pct=3.0,
    time_stop_minutes=12.0,
    fast_reduce_minutes=6.0,
    trailing_stop_pct=0.70,
    stop_ioc_guard_bps=6.0,
    max_gross_exposure_pct=6.0,
)


@dataclass(frozen=True)
class V3Params:
    strategy_name: str = "Crypto-Squid 3.1"
    risk_per_trade_pct: float = 0.50
    max_trades_per_day: int = 3
    max_signals_evaluated_per_asset: int = 6
    max_consecutive_losses: int = 2
    daily_loss_limit_pct: float = 1.0
    max_rejected_fills_in_row: int = 3

    entry_order_lifetime_seconds: float = 20.0

    volume_ratio_threshold: float = 1.70
    volume_percentile_35_threshold: float = 0.30
    trade_imbalance_sell_threshold: float = 0.58

    disorder_spread_multiple: float = 2.0

    stab_min_wait_seconds: float = 45.0
    stab_no_new_low_seconds: float = 75.0
    stab_timeout_seconds: float = 300.0
    stab_bid_over_ask_seconds: int = 45
    stab_higher_low_recent_seconds: int = 45
    stab_higher_low_prior_seconds: int = 45

    panic_drop_lookback_seconds: int = 300
    panic_volume_window_seconds: int = 60
    panic_imbalance_window_seconds: int = 60

    trend_vwap_seconds: int = 1800
    trend_ema_seconds: int = 1800
    trend_ema_period_seconds: int = 300
    trend_ema_slope_lookback_seconds: int = 120

    cascade_reject_lookback_seconds: int = 120
    cascade_reject_drop_multiplier: float = 1.40

    alt_btc_stress_drop_pct: float = 0.30

    high_vol_ratio_threshold: float = 3.0
    high_vol_stop_widen_mult: float = 1.15

    max_total_exposure_pct: float = 40.0

    trading_enabled_default: bool = False
    live_trading_confirm_value: str = "YES"

    zscore_window_seconds: int = 1800
    volume_baseline_seconds: int = 1800

    symbol_params: tuple[SymbolParamsV3, ...] = field(
        default_factory=lambda: (
            BTC_V3,
            ETH_V3,
            SOL_V3,
            DOGE_V3,
            ADA_V3,
            AVAX_V3,
            POL_V3,
            MATIC_V3,
        )
    )

    def for_symbol(self, symbol: str) -> SymbolParamsV3:
        for item in self.symbol_params:
            if item.name == symbol:
                return item
        raise ValueError(f"Unsupported symbol: {symbol}")

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.symbol_params)

    @property
    def max_gross_exposure_pct_by_symbol(self) -> dict[str, float]:
        return {item.name: item.max_gross_exposure_pct for item in self.symbol_params}


DEFAULT_V3_PARAMS = V3Params()
