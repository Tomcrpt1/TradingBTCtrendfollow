from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import UTC, datetime

from config import AppConfig, load_config
from data import HyperliquidDataClient, latest_closed_daily_candle
from execution import HyperliquidExecutionClient, PaperExecutor, Position
from risk import compute_order_size
from state import BotState, StateStore
from strategy import SignalSnapshot, compute_signal


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(log_level: str, log_path: str) -> None:
    logger = logging.getLogger()
    logger.setLevel(log_level.upper())
    formatter = JsonFormatter()

    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    fh = logging.FileHandler(log_path)
    fh.setFormatter(formatter)
    logger.addHandler(fh)


def get_equity_usd(cfg: AppConfig, data_client: HyperliquidDataClient) -> float:
    if cfg.runtime.mode == "paper":
        return float(os.getenv("PAPER_EQUITY_USD", "10000"))
    info = data_client._post_info({"type": "clearinghouseState", "user": cfg.credentials.account_address})
    return float(info.get("marginSummary", {}).get("accountValue", 0.0))


def update_trailing_stop(state: BotState, position: Position, sig: SignalSnapshot, trail_mult: float) -> None:
    if position.side == "long":
        new_trail = sig.close - trail_mult * sig.atr
        state.trailing_stop = new_trail if state.trailing_stop is None else max(state.trailing_stop, new_trail)
        state.trailing_side = "long"
    elif position.side == "short":
        new_trail = sig.close + trail_mult * sig.atr
        state.trailing_stop = new_trail if state.trailing_stop is None else min(state.trailing_stop, new_trail)
        state.trailing_side = "short"
    else:
        state.trailing_stop = None
        state.trailing_side = "flat"


def intraday_stop_check(cfg: AppConfig, data_client: HyperliquidDataClient, executor, state: BotState) -> None:
    pos = executor.get_open_position(cfg.strategy.symbol)
    if pos.side == "flat" or state.trailing_stop is None:
        return
    px = data_client.get_mid_price(cfg.strategy.symbol)
    if pos.side == "long" and px <= state.trailing_stop:
        logging.info("Intraday trailing stop hit for long at px=%s stop=%s", px, state.trailing_stop)
        executor.place_market_order(cfg.strategy.symbol, "sell", pos.size, reduce_only=True, price=px)
        state.trailing_stop = None
        state.trailing_side = "flat"
    elif pos.side == "short" and px >= state.trailing_stop:
        logging.info("Intraday trailing stop hit for short at px=%s stop=%s", px, state.trailing_stop)
        executor.place_market_order(cfg.strategy.symbol, "buy", pos.size, reduce_only=True, price=px)
        state.trailing_stop = None
        state.trailing_side = "flat"


def process_daily(cfg: AppConfig, data_client: HyperliquidDataClient, executor, state: BotState, candles: list[dict]) -> None:
    latest_closed = latest_closed_daily_candle(candles)
    candle_ts = int(latest_closed["t"])
    if state.last_processed_candle_ts == candle_ts:
        logging.info("Daily candle already processed: %s", candle_ts)
        return

    closed_series = [c for c in candles if int(c["t"]) <= candle_ts]
    sig = compute_signal(closed_series, cfg.strategy)
    logging.info(
        "signal ts=%s close=%.2f long=%s short=%s bull=%s bear=%s rsi=%.2f adx=%.2f volOK=%s",
        sig.candle_ts,
        sig.close,
        sig.long_signal,
        sig.short_signal,
        sig.bull_regime,
        sig.bear_regime,
        sig.rsi,
        sig.adx,
        sig.vol_ok,
    )

    pos = executor.get_open_position(cfg.strategy.symbol)

    if pos.side == "long" and sig.bear_regime:
        logging.info("Regime invalidation: closing long")
        executor.place_market_order(cfg.strategy.symbol, "sell", pos.size, reduce_only=True, price=sig.close)
        pos = executor.get_open_position(cfg.strategy.symbol)
    elif pos.side == "short" and sig.bull_regime:
        logging.info("Regime invalidation: closing short")
        executor.place_market_order(cfg.strategy.symbol, "buy", pos.size, reduce_only=True, price=sig.close)
        pos = executor.get_open_position(cfg.strategy.symbol)

    if sig.long_signal and pos.side != "long":
        if pos.side == "short":
            executor.place_market_order(cfg.strategy.symbol, "buy", pos.size, reduce_only=True, price=sig.close)
        equity = get_equity_usd(cfg, data_client)
        size = compute_order_size(equity, sig.close, sig.atr, cfg.strategy.trail_atr_mult, cfg.risk)
        if size > 0:
            executor.place_market_order(cfg.strategy.symbol, "buy", size, reduce_only=False, price=sig.close)
            state.trailing_stop = sig.close - cfg.strategy.trail_atr_mult * sig.atr
            state.trailing_side = "long"
            state.last_signal = "long"

    elif sig.short_signal and pos.side != "short":
        if pos.side == "long":
            executor.place_market_order(cfg.strategy.symbol, "sell", pos.size, reduce_only=True, price=sig.close)
        equity = get_equity_usd(cfg, data_client)
        size = compute_order_size(equity, sig.close, sig.atr, cfg.strategy.trail_atr_mult, cfg.risk)
        if size > 0:
            executor.place_market_order(cfg.strategy.symbol, "sell", size, reduce_only=False, price=sig.close)
            state.trailing_stop = sig.close + cfg.strategy.trail_atr_mult * sig.atr
            state.trailing_side = "short"
            state.last_signal = "short"

    pos = executor.get_open_position(cfg.strategy.symbol)
    update_trailing_stop(state, pos, sig, cfg.strategy.trail_atr_mult)

    if cfg.runtime.use_exchange_stop:
        executor.cancel_existing_stops(cfg.strategy.symbol)
        if pos.side == "long" and state.trailing_stop is not None:
            executor.place_stop_order(cfg.strategy.symbol, "sell", state.trailing_stop, pos.size)
        elif pos.side == "short" and state.trailing_stop is not None:
            executor.place_stop_order(cfg.strategy.symbol, "buy", state.trailing_stop, pos.size)

    state.last_processed_candle_ts = candle_ts


def run_bot(cfg: AppConfig) -> None:
    setup_logging(cfg.runtime.log_level, cfg.runtime.log_path)
    store = StateStore(cfg.runtime.state_path)
    state = store.load()

    data_client = HyperliquidDataClient(cfg.runtime.base_url, cfg.runtime.retry_count, cfg.runtime.retry_backoff_sec)
    if cfg.runtime.mode == "paper":
        executor = PaperExecutor(state)
    else:
        executor = HyperliquidExecutionClient(cfg)

    logging.info("Bot started mode=%s symbol=%s", cfg.runtime.mode, cfg.strategy.symbol)
    while True:
        try:
            candles = data_client.fetch_daily_candles(cfg.strategy.symbol, limit=500)
            process_daily(cfg, data_client, executor, state, candles)
            if not cfg.runtime.use_exchange_stop:
                intraday_stop_check(cfg, data_client, executor, state)
            store.save(state)
        except Exception as exc:
            logging.exception("Main loop error: %s", exc)
        time.sleep(cfg.runtime.poll_interval_sec)


def run_diagnose(cfg: AppConfig, limit: int) -> None:
    setup_logging(cfg.runtime.log_level, cfg.runtime.log_path)
    dc = HyperliquidDataClient(cfg.runtime.base_url, cfg.runtime.retry_count, cfg.runtime.retry_backoff_sec)
    candles = dc.fetch_daily_candles(cfg.strategy.symbol, limit=limit)
    latest = latest_closed_daily_candle(candles)
    closed = [c for c in candles if int(c["t"]) <= int(latest["t"])]
    sig = compute_signal(closed, cfg.strategy)
    print(f"candles={len(closed)} latest_ts={sig.candle_ts} close={sig.close:.2f}")
    print(
        f"EMA={sig.ema200:.2f} slope={sig.ema_slope:.4f} RSI={sig.rsi:.2f} ADX={sig.adx:.2f} "
        f"ATR={sig.atr:.2f} volRank={sig.vol_rank}"
    )
    print(
        f"bull={sig.bull_regime} bear={sig.bear_regime} breakoutUp={sig.breakout_up} "
        f"breakoutDown={sig.breakout_down} volOK={sig.vol_ok} long={sig.long_signal} short={sig.short_signal}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnose", action="store_true", help="Fetch candles and print latest indicators/signal")
    parser.add_argument("--limit", type=int, default=400)
    args = parser.parse_args()

    cfg = load_config()
    if args.diagnose:
        run_diagnose(cfg, args.limit)
    else:
        run_bot(cfg)


if __name__ == "__main__":
    main()
