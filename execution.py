from __future__ import annotations

import logging
from dataclasses import dataclass

from config import AppConfig
from data import HyperliquidDataClient
from state import BotState

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Position:
    side: str
    size: float
    entry_price: float


class HyperliquidExecutionClient:
    """
    Live wrapper.

    Uses Hyperliquid official SDK if available. Method names in SDK can vary by version,
    so this wrapper isolates the surface that may need adaptation.
    """

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self._sdk_exchange = None
        self.data_client = HyperliquidDataClient(
            cfg.runtime.base_url, cfg.runtime.retry_count, cfg.runtime.retry_backoff_sec
        )
        if cfg.runtime.mode == "live":
            self._init_sdk()

    def _init_sdk(self) -> None:
        try:
            from hyperliquid.exchange import Exchange  # type: ignore
            from hyperliquid.utils import constants  # type: ignore
            from eth_account import Account  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "Hyperliquid SDK unavailable. Install compatible package or adapt HTTP signing wrapper in execution.py"
            ) from exc

        if not self.cfg.credentials.secret_key or not self.cfg.credentials.account_address:
            raise RuntimeError("Live mode requires HYPERLIQUID_SECRET_KEY and HYPERLIQUID_ACCOUNT_ADDRESS")

        account = Account.from_key(self.cfg.credentials.secret_key)
        self._sdk_exchange = Exchange(account, self.cfg.runtime.base_url, account_address=self.cfg.credentials.account_address)
        logger.info("Hyperliquid SDK initialized for live trading")
        _ = constants

    def get_mid_price(self, symbol: str) -> float:
        return self.data_client.get_mid_price(symbol)

    def get_open_position(self, symbol: str) -> Position:
        if self.cfg.runtime.mode == "paper":
            raise RuntimeError("Paper position is managed by PaperExecutor")
        info = self.data_client._post_info({"type": "clearinghouseState", "user": self.cfg.credentials.account_address})
        asset_positions = info.get("assetPositions", [])
        for row in asset_positions:
            pos = row.get("position", row)
            if pos.get("coin") == symbol and abs(float(pos.get("szi", 0.0))) > 0:
                szi = float(pos.get("szi"))
                return Position(side="long" if szi > 0 else "short", size=abs(szi), entry_price=float(pos.get("entryPx", 0.0)))
        return Position(side="flat", size=0.0, entry_price=0.0)

    def place_market_order(self, symbol: str, side: str, size: float, reduce_only: bool = False) -> dict:
        if self._sdk_exchange is None:
            raise RuntimeError("Live exchange not initialized")
        is_buy = side.lower() == "buy"
        # NOTE: SDK signature can differ by version; adapt here if needed.
        resp = self._sdk_exchange.market_open(symbol, is_buy, size, reduce_only=reduce_only)
        logger.info("live market order: %s", resp)
        return resp

    def place_stop_order(self, symbol: str, side: str, stop_price: float, size: float) -> dict:
        if self._sdk_exchange is None:
            raise RuntimeError("Live exchange not initialized")
        is_buy = side.lower() == "buy"
        # NOTE: SDK signature can differ by version; adapt here if needed.
        resp = self._sdk_exchange.order(
            name=symbol,
            is_buy=is_buy,
            sz=size,
            limit_px=stop_price,
            order_type={"trigger": {"triggerPx": stop_price, "isMarket": True, "tpsl": "sl"}},
            reduce_only=True,
        )
        logger.info("live stop order: %s", resp)
        return resp

    def cancel_existing_stops(self, symbol: str) -> None:
        if self._sdk_exchange is None:
            raise RuntimeError("Live exchange not initialized")
        # NOTE: exact open-orders/cancel API may differ. Keep adaptation localized.
        opens = self._sdk_exchange.open_orders(self.cfg.credentials.account_address)
        for order in opens:
            if order.get("coin") == symbol and order.get("triggerCondition") is not None:
                self._sdk_exchange.cancel(symbol, order["oid"])


class PaperExecutor:
    def __init__(self, state: BotState):
        self.state = state

    def get_open_position(self, symbol: str) -> Position:
        _ = symbol
        p = self.state.paper_position
        return Position(side=p.side, size=p.size, entry_price=p.entry_price)

    def place_market_order(self, symbol: str, side: str, size: float, reduce_only: bool = False, price: float | None = None) -> dict:
        _ = symbol
        _ = reduce_only
        fill_price = float(price or 0.0)
        pos = self.state.paper_position
        if side == "buy":
            if pos.side == "short":
                pos.side = "flat"
                pos.size = 0.0
                pos.entry_price = 0.0
            else:
                pos.side = "long"
                pos.size = size
                pos.entry_price = fill_price
        elif side == "sell":
            if pos.side == "long":
                pos.side = "flat"
                pos.size = 0.0
                pos.entry_price = 0.0
            else:
                pos.side = "short"
                pos.size = size
                pos.entry_price = fill_price
        logger.info("paper market order: side=%s size=%s fill=%s", side, size, fill_price)
        return {"status": "filled", "side": side, "size": size, "price": fill_price}

    def place_stop_order(self, symbol: str, side: str, stop_price: float, size: float) -> dict:
        logger.info("paper stop order set %s %s @ %s (%s)", symbol, side, stop_price, size)
        return {"status": "accepted", "stop": stop_price}

    def cancel_existing_stops(self, symbol: str) -> None:
        logger.info("paper stop orders canceled for %s", symbol)
