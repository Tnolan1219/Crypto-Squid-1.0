"""Config loader for the Hyperliquid-only Crypto Squid MVP."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_symbols(raw: str) -> tuple[str, ...]:
    values = [s.strip().upper() for s in raw.split(",") if s.strip()]
    if not values:
        return ("BTC", "ETH")
    allowed = [s for s in values if s in {"BTC", "ETH", "SOL"}]
    return tuple(allowed) if allowed else ("BTC", "ETH")


@dataclass(frozen=True)
class SymbolParams:
    drop_threshold_pct: float
    tp_pct: float
    sl_pct: float


@dataclass(frozen=True)
class Config:
    use_testnet: bool
    log_only: bool
    paper_mode: bool
    enable_live_trading: bool
    trading_enabled: bool
    symbols: tuple[str, ...]

    account_capital_usd: float
    risk_per_trade_pct: float
    max_trades_per_day: int
    max_consecutive_losses: int
    daily_loss_limit_pct: float

    order_timeout_seconds: int
    max_slippage_bps: float
    limit_offset_bps: float
    max_hold_minutes: int

    drop_lookback_seconds: int
    volume_window_seconds: int
    volume_baseline_periods: int
    zscore_lookback_ticks: int
    zscore_threshold: float
    volume_spike_multiplier: float
    stabilization_wait_seconds: int
    stabilization_hold_seconds: int
    stabilization_max_seconds: int

    hyperliquid_secret_key: str
    hyperliquid_account_address: str

    strategy_version: str
    log_level: str

    db_path: Path
    journal_path: Path
    reports_path: Path

    btc: SymbolParams
    eth: SymbolParams

    @property
    def rest_base_url(self) -> str:
        if self.use_testnet:
            return "https://api.hyperliquid-testnet.xyz"
        return "https://api.hyperliquid.xyz"

    @property
    def ws_base_url(self) -> str:
        if self.use_testnet:
            return "wss://api.hyperliquid-testnet.xyz/ws"
        return "wss://api.hyperliquid.xyz/ws"

    def symbol_params(self, symbol: str) -> SymbolParams:
        if symbol.upper() == "BTC":
            return self.btc
        if symbol.upper() == "ETH":
            return self.eth
        return SymbolParams(drop_threshold_pct=1.20, tp_pct=1.40, sl_pct=0.70)


def load_config() -> Config:
    root = Path(__file__).parent.parent
    log_only = _as_bool(os.getenv("LOG_ONLY", "true"), default=True)
    paper_mode = _as_bool(os.getenv("PAPER_MODE", "false"), default=False)
    enable_live = _as_bool(os.getenv("ENABLE_LIVE_TRADING", "false"), default=False)

    if enable_live:
        log_only = False
        paper_mode = False

    return Config(
        use_testnet=_as_bool(os.getenv("USE_TESTNET", "true"), default=True),
        log_only=log_only,
        paper_mode=paper_mode,
        enable_live_trading=enable_live,
        trading_enabled=_as_bool(os.getenv("TRADING_ENABLED", "true"), default=True),
        symbols=_as_symbols(os.getenv("SYMBOLS", "BTC,ETH")),
        account_capital_usd=float(os.getenv("ACCOUNT_CAPITAL_USD", "1000")),
        risk_per_trade_pct=float(os.getenv("RISK_PER_TRADE_PCT", "0.50")),
        max_trades_per_day=int(os.getenv("MAX_TRADES_PER_DAY", "3")),
        max_consecutive_losses=int(os.getenv("MAX_CONSECUTIVE_LOSSES", "2")),
        daily_loss_limit_pct=float(os.getenv("DAILY_LOSS_LIMIT_PCT", "2.0")),
        order_timeout_seconds=int(os.getenv("ORDER_TIMEOUT_SECONDS", "30")),
        max_slippage_bps=float(os.getenv("MAX_SLIPPAGE_BPS", "10")),
        limit_offset_bps=float(os.getenv("LIMIT_OFFSET_BPS", "5")),
        max_hold_minutes=int(os.getenv("MAX_HOLD_MINUTES", "90")),
        drop_lookback_seconds=int(os.getenv("DROP_LOOKBACK_SECONDS", "180")),
        volume_window_seconds=int(os.getenv("VOLUME_WINDOW_SECONDS", "180")),
        volume_baseline_periods=int(os.getenv("VOLUME_BASELINE_PERIODS", "20")),
        zscore_lookback_ticks=int(os.getenv("ZSCORE_LOOKBACK_TICKS", "120")),
        zscore_threshold=float(os.getenv("ZSCORE_THRESHOLD", "-2.0")),
        volume_spike_multiplier=float(os.getenv("VOLUME_SPIKE_MULTIPLIER", "2.0")),
        stabilization_wait_seconds=int(os.getenv("STABILIZATION_WAIT_SECONDS", "30")),
        stabilization_hold_seconds=int(os.getenv("STABILIZATION_HOLD_SECONDS", "30")),
        stabilization_max_seconds=int(os.getenv("STABILIZATION_MAX_SECONDS", "180")),
        hyperliquid_secret_key=os.getenv("HYPERLIQUID_SECRET_KEY", "").strip(),
        hyperliquid_account_address=os.getenv("HYPERLIQUID_ACCOUNT_ADDRESS", "").strip(),
        strategy_version=os.getenv("STRATEGY_VERSION", "hyperliquid-mvp-v1"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        db_path=root / "data" / "trades" / "trades.db",
        journal_path=root / "journal" / "raw-trades",
        reports_path=root / "reports" / "daily",
        btc=SymbolParams(
            drop_threshold_pct=float(os.getenv("BTC_DROP_THRESHOLD_PCT", "0.75")),
            tp_pct=float(os.getenv("BTC_TP_PCT", "1.0")),
            sl_pct=float(os.getenv("BTC_SL_PCT", "0.55")),
        ),
        eth=SymbolParams(
            drop_threshold_pct=float(os.getenv("ETH_DROP_THRESHOLD_PCT", "1.00")),
            tp_pct=float(os.getenv("ETH_TP_PCT", "1.2")),
            sl_pct=float(os.getenv("ETH_SL_PCT", "0.65")),
        ),
    )
