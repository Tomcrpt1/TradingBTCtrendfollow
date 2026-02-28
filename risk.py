from __future__ import annotations

from math import floor

from config import RiskConfig


def round_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    return floor(value / step) * step


def compute_order_size(
    equity_usd: float,
    price: float,
    atr: float,
    trail_atr_mult: float,
    risk_cfg: RiskConfig,
) -> float:
    if risk_cfg.use_fixed_notional:
        notional = risk_cfg.fixed_notional_usd
    else:
        risk_usd = equity_usd * (risk_cfg.risk_per_trade_pct / 100.0)
        stop_distance = max(atr * trail_atr_mult, 1e-9)
        notional = risk_usd * price / stop_distance

    max_notional = equity_usd * risk_cfg.max_leverage
    notional = min(notional, max_notional)
    size = notional / price if price > 0 else 0.0
    size = max(size, risk_cfg.min_order_size)
    size = round_step(size, risk_cfg.size_step)
    return max(size, 0.0)
