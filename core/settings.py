from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class RuntimeSettings:
    env: str
    trading_enabled: bool
    loop_seconds: float
    control_poll_seconds: float
    warmup_seconds: float
    account_capital_usd: float
    max_daily_loss_usd: float
    max_position_default: float
    enabled_strategies: tuple[str, ...]
    supabase_url: str
    supabase_key: str
    coinbase_api_key_name: str
    coinbase_private_key: str


def load_settings() -> RuntimeSettings:
    enabled = tuple(
        s.strip() for s in os.getenv("ENABLED_STRATEGIES", "coinbase_v3").split(",") if s.strip()
    )
    return RuntimeSettings(
        env=os.getenv("ENV", "production"),
        trading_enabled=_as_bool(os.getenv("TRADING_ENABLED", "true"), default=True),
        loop_seconds=float(os.getenv("GLOBAL_LOOP_SECONDS", "2.0")),
        control_poll_seconds=float(os.getenv("CONTROL_POLL_SECONDS", "3.0")),
        warmup_seconds=float(os.getenv("STRATEGY_WARMUP_SECONDS", "30")),
        account_capital_usd=float(os.getenv("ACCOUNT_CAPITAL_USD", "1000")),
        max_daily_loss_usd=float(os.getenv("MAX_DAILY_LOSS_USD", "50")),
        max_position_default=float(os.getenv("MAX_POSITION_DEFAULT", "0.20")),
        enabled_strategies=enabled if enabled else ("coinbase_v3",),
        supabase_url=os.getenv("SUPABASE_URL", "").strip(),
        supabase_key=os.getenv("SUPABASE_KEY", "").strip(),
        coinbase_api_key_name=os.getenv("COINBASE_API_KEY_NAME", "").strip(),
        coinbase_private_key=os.getenv("COINBASE_PRIVATE_KEY", "").strip(),
    )
