from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass(slots=True)
class StrategyConfig:
    symbol: str
    donchian_len: int
    ema_len: int
    ema_slope_lookback: int
    rsi_len: int
    rsi_long_min: float
    rsi_short_max: float
    adx_len: int
    adx_min: float
    atr_len: int
    trail_atr_mult: float
    vol_filter_enabled: bool
    vol_lookback: int
    vol_max_pct: float


@dataclass(slots=True)
class RiskConfig:
    risk_per_trade_pct: float
    use_fixed_notional: bool
    fixed_notional_usd: float
    max_leverage: float
    min_order_size: float
    size_step: float


@dataclass(slots=True)
class RuntimeConfig:
    mode: str
    base_url: str
    poll_interval_sec: int
    log_level: str
    state_path: str
    log_path: str
    use_exchange_stop: bool
    retry_count: int
    retry_backoff_sec: float


@dataclass(slots=True)
class Credentials:
    secret_key: str
    account_address: str


@dataclass(slots=True)
class AppConfig:
    strategy: StrategyConfig
    risk: RiskConfig
    runtime: RuntimeConfig
    credentials: Credentials


TRUE_VALUES = {"1", "true", "yes", "on"}


def _get_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in TRUE_VALUES


def load_config() -> AppConfig:
    load_dotenv()

    strategy = StrategyConfig(
        symbol=os.getenv("SYMBOL", "BTC"),
        donchian_len=int(os.getenv("DONCHIAN_LEN", "20")),
        ema_len=int(os.getenv("EMA_LEN", "200")),
        ema_slope_lookback=int(os.getenv("EMA_SLOPE_LOOKBACK", "20")),
        rsi_len=int(os.getenv("RSI_LEN", "14")),
        rsi_long_min=float(os.getenv("RSI_LONG_MIN", "55")),
        rsi_short_max=float(os.getenv("RSI_SHORT_MAX", "45")),
        adx_len=int(os.getenv("ADX_LEN", "14")),
        adx_min=float(os.getenv("ADX_MIN", "20")),
        atr_len=int(os.getenv("ATR_LEN", "14")),
        trail_atr_mult=float(os.getenv("TRAIL_ATR_MULT", "3.0")),
        vol_filter_enabled=_get_bool("VOL_FILTER_ENABLED", True),
        vol_lookback=int(os.getenv("VOL_LOOKBACK", "120")),
        vol_max_pct=float(os.getenv("VOL_MAX_PCT", "95")),
    )

    risk = RiskConfig(
        risk_per_trade_pct=float(os.getenv("RISK_PER_TRADE_PCT", "2.0")),
        use_fixed_notional=_get_bool("USE_FIXED_NOTIONAL", False),
        fixed_notional_usd=float(os.getenv("FIXED_NOTIONAL_USD", "500")),
        max_leverage=float(os.getenv("MAX_LEVERAGE", "3.0")),
        min_order_size=float(os.getenv("MIN_ORDER_SIZE", "0.001")),
        size_step=float(os.getenv("SIZE_STEP", "0.001")),
    )

    runtime = RuntimeConfig(
        mode=os.getenv("BOT_MODE", "paper").lower(),
        base_url=os.getenv("HYPERLIQUID_BASE_URL", "https://api.hyperliquid.xyz"),
        poll_interval_sec=int(os.getenv("POLL_INTERVAL_SEC", "15")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        state_path=os.getenv("STATE_PATH", "state.json"),
        log_path=os.getenv("LOG_PATH", "logs/bot.log"),
        use_exchange_stop=_get_bool("USE_EXCHANGE_STOP", True),
        retry_count=int(os.getenv("RETRY_COUNT", "3")),
        retry_backoff_sec=float(os.getenv("RETRY_BACKOFF_SEC", "1.5")),
    )

    credentials = Credentials(
        secret_key=os.getenv("HYPERLIQUID_SECRET_KEY", ""),
        account_address=os.getenv("HYPERLIQUID_ACCOUNT_ADDRESS", ""),
    )

    return AppConfig(strategy=strategy, risk=risk, runtime=runtime, credentials=credentials)
