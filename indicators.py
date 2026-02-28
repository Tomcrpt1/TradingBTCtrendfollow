from __future__ import annotations

from typing import Iterable


def ema(values: Iterable[float], length: int) -> list[float | None]:
    vals = list(values)
    out: list[float | None] = [None] * len(vals)
    if not vals or length <= 0 or len(vals) < length:
        return out
    alpha = 2 / (length + 1)
    sma = sum(vals[:length]) / length
    out[length - 1] = sma
    prev = sma
    for i in range(length, len(vals)):
        prev = (vals[i] - prev) * alpha + prev
        out[i] = prev
    return out


def rma(values: Iterable[float], length: int) -> list[float | None]:
    vals = list(values)
    out: list[float | None] = [None] * len(vals)
    if not vals or length <= 0 or len(vals) < length:
        return out
    avg = sum(vals[:length]) / length
    out[length - 1] = avg
    prev = avg
    for i in range(length, len(vals)):
        prev = (prev * (length - 1) + vals[i]) / length
        out[i] = prev
    return out


def rsi_wilder(close: Iterable[float], length: int = 14) -> list[float | None]:
    c = list(close)
    if len(c) < 2:
        return [None] * len(c)
    gains = [0.0]
    losses = [0.0]
    for i in range(1, len(c)):
        diff = c[i] - c[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = rma(gains, length)
    avg_loss = rma(losses, length)
    out: list[float | None] = [None] * len(c)
    for i in range(len(c)):
        if avg_gain[i] is None or avg_loss[i] is None:
            continue
        if avg_loss[i] == 0:
            out[i] = 100.0
        else:
            rs = avg_gain[i] / avg_loss[i]
            out[i] = 100 - (100 / (1 + rs))
    return out


def true_range(high: list[float], low: list[float], close: list[float]) -> list[float]:
    tr = []
    for i in range(len(close)):
        if i == 0:
            tr.append(high[i] - low[i])
        else:
            tr.append(max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1])))
    return tr


def atr_wilder(high: list[float], low: list[float], close: list[float], length: int = 14) -> list[float | None]:
    return rma(true_range(high, low, close), length)


def adx_wilder(high: list[float], low: list[float], close: list[float], length: int = 14) -> list[float | None]:
    n = len(close)
    if n == 0:
        return []
    tr = true_range(high, low, close)
    plus_dm = [0.0]
    minus_dm = [0.0]
    for i in range(1, n):
        up = high[i] - high[i - 1]
        down = low[i - 1] - low[i]
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)

    atr = rma(tr, length)
    plus_sm = rma(plus_dm, length)
    minus_sm = rma(minus_dm, length)

    dx: list[float] = [0.0] * n
    for i in range(n):
        if atr[i] is None or plus_sm[i] is None or minus_sm[i] is None or atr[i] == 0:
            dx[i] = 0.0
            continue
        plus_di = 100 * plus_sm[i] / atr[i]
        minus_di = 100 * minus_sm[i] / atr[i]
        denom = plus_di + minus_di
        dx[i] = 0.0 if denom == 0 else 100 * abs(plus_di - minus_di) / denom

    adx = rma(dx, length)
    return adx


def donchian_high(high: list[float], length: int) -> list[float | None]:
    out: list[float | None] = [None] * len(high)
    for i in range(length - 1, len(high)):
        out[i] = max(high[i - length + 1 : i + 1])
    return out


def donchian_low(low: list[float], length: int) -> list[float | None]:
    out: list[float | None] = [None] * len(low)
    for i in range(length - 1, len(low)):
        out[i] = min(low[i - length + 1 : i + 1])
    return out


def percent_rank(values: list[float], lookback: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    for i in range(lookback - 1, len(values)):
        window = values[i - lookback + 1 : i + 1]
        if not window:
            continue
        current = window[-1]
        le_count = sum(1 for v in window if v <= current)
        out[i] = 100.0 * le_count / len(window)
    return out
