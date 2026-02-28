from __future__ import annotations

from dataclasses import dataclass

from config import StrategyConfig
from indicators import adx_wilder, atr_wilder, donchian_high, donchian_low, ema, percent_rank, rsi_wilder


@dataclass(slots=True)
class SignalSnapshot:
    candle_ts: int
    close: float
    atr: float
    ema200: float
    ema_slope: float
    rsi: float
    adx: float
    vol_rank: float | None
    bull_regime: bool
    bear_regime: bool
    breakout_up: bool
    breakout_down: bool
    vol_ok: bool
    long_signal: bool
    short_signal: bool


def compute_signal(candles: list[dict], cfg: StrategyConfig) -> SignalSnapshot:
    if len(candles) < max(cfg.ema_len + cfg.ema_slope_lookback + 1, cfg.donchian_len + 2, cfg.vol_lookback + 1):
        raise ValueError("Not enough candles to compute strategy safely")

    t = [int(c["t"]) for c in candles]
    h = [float(c["h"]) for c in candles]
    l = [float(c["l"]) for c in candles]
    c = [float(c["c"]) for c in candles]

    ema_series = ema(c, cfg.ema_len)
    rsi_series = rsi_wilder(c, cfg.rsi_len)
    atr_series = atr_wilder(h, l, c, cfg.atr_len)
    adx_series = adx_wilder(h, l, c, cfg.adx_len)
    don_hi = donchian_high(h, cfg.donchian_len)
    don_lo = donchian_low(l, cfg.donchian_len)

    atr_pct = [(atr_series[i] / c[i]) if atr_series[i] is not None and c[i] != 0 else 0.0 for i in range(len(c))]
    vol_rank_series = percent_rank(atr_pct, cfg.vol_lookback)

    i = len(c) - 1
    e = ema_series[i]
    e_prev = ema_series[i - cfg.ema_slope_lookback]
    if None in (e, e_prev, rsi_series[i], atr_series[i], adx_series[i], don_hi[i - 1], don_lo[i - 1]):
        raise ValueError("Indicators still warming up")

    ema_slope = (e - e_prev) / cfg.ema_slope_lookback
    bull = c[i] > e and ema_slope > 0
    bear = c[i] < e and ema_slope < 0

    breakout_up = c[i] > float(don_hi[i - 1])
    breakout_down = c[i] < float(don_lo[i - 1])

    rsi_val = float(rsi_series[i])
    adx_val = float(adx_series[i])
    atr_val = float(atr_series[i])
    vr = vol_rank_series[i]

    vol_ok = True
    if cfg.vol_filter_enabled:
        vol_ok = vr is not None and float(vr) <= cfg.vol_max_pct

    long_signal = bull and breakout_up and rsi_val >= cfg.rsi_long_min and adx_val >= cfg.adx_min and vol_ok
    short_signal = bear and breakout_down and rsi_val <= cfg.rsi_short_max and adx_val >= cfg.adx_min and vol_ok

    return SignalSnapshot(
        candle_ts=t[i],
        close=c[i],
        atr=atr_val,
        ema200=float(e),
        ema_slope=float(ema_slope),
        rsi=rsi_val,
        adx=adx_val,
        vol_rank=None if vr is None else float(vr),
        bull_regime=bull,
        bear_regime=bear,
        breakout_up=breakout_up,
        breakout_down=breakout_down,
        vol_ok=vol_ok,
        long_signal=long_signal,
        short_signal=short_signal,
    )
