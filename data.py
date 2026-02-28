from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

import requests

logger = logging.getLogger(__name__)


class HyperliquidDataClient:
    def __init__(self, base_url: str, retry_count: int = 3, retry_backoff_sec: float = 1.5):
        self.base_url = base_url.rstrip("/")
        self.retry_count = retry_count
        self.retry_backoff_sec = retry_backoff_sec
        self.session = requests.Session()

    def _post_info(self, payload: dict) -> dict:
        last_err = None
        for attempt in range(1, self.retry_count + 1):
            try:
                resp = self.session.post(f"{self.base_url}/info", json=payload, timeout=15)
                if resp.status_code == 429:
                    raise RuntimeError("Rate limited by Hyperliquid info API")
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:
                last_err = exc
                sleep = self.retry_backoff_sec * attempt
                logger.warning("info API attempt %s failed: %s", attempt, exc)
                time.sleep(sleep)
        raise RuntimeError(f"info request failed after retries: {last_err}")

    def fetch_daily_candles(self, symbol: str, limit: int = 400) -> list[dict]:
        now_ms = int(time.time() * 1000)
        start_ms = now_ms - limit * 24 * 60 * 60 * 1000
        payload = {
            "type": "candleSnapshot",
            "req": {
                "coin": symbol,
                "interval": "1d",
                "startTime": start_ms,
                "endTime": now_ms,
            },
        }
        rows = self._post_info(payload)
        if not isinstance(rows, list):
            raise RuntimeError(f"Unexpected candle response: {rows}")
        candles = []
        for r in rows:
            candles.append(
                {
                    "t": int(r.get("t") or r.get("T")),
                    "o": float(r["o"]),
                    "h": float(r["h"]),
                    "l": float(r["l"]),
                    "c": float(r["c"]),
                    "v": float(r.get("v", 0.0)),
                }
            )
        candles.sort(key=lambda x: x["t"])
        return candles[-limit:]

    def get_mid_price(self, symbol: str) -> float:
        payload = {"type": "allMids"}
        mids = self._post_info(payload)
        if symbol not in mids:
            raise RuntimeError(f"{symbol} not found in allMids payload")
        return float(mids[symbol])


def latest_closed_daily_candle(candles: list[dict]) -> dict:
    if not candles:
        raise ValueError("No candles")
    utc_now = datetime.now(UTC)
    today_start_ms = int(datetime(utc_now.year, utc_now.month, utc_now.day, tzinfo=UTC).timestamp() * 1000)
    closed = [c for c in candles if int(c["t"]) < today_start_ms]
    if not closed:
        raise ValueError("No closed daily candle yet")
    return closed[-1]
