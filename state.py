from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(slots=True)
class PaperPosition:
    side: str = "flat"
    size: float = 0.0
    entry_price: float = 0.0


@dataclass(slots=True)
class BotState:
    last_processed_candle_ts: int = 0
    trailing_stop: float | None = None
    trailing_side: str = "flat"
    last_signal: str = "none"
    last_stop_order_id: str | None = None
    paper_position: PaperPosition = field(default_factory=PaperPosition)


class StateStore:
    def __init__(self, path: str):
        self.path = Path(path)

    def load(self) -> BotState:
        if not self.path.exists():
            return BotState()
        raw = json.loads(self.path.read_text())
        paper = raw.get("paper_position", {})
        return BotState(
            last_processed_candle_ts=int(raw.get("last_processed_candle_ts", 0)),
            trailing_stop=raw.get("trailing_stop"),
            trailing_side=raw.get("trailing_side", "flat"),
            last_signal=raw.get("last_signal", "none"),
            last_stop_order_id=raw.get("last_stop_order_id"),
            paper_position=PaperPosition(
                side=paper.get("side", "flat"),
                size=float(paper.get("size", 0.0)),
                entry_price=float(paper.get("entry_price", 0.0)),
            ),
        )

    def save(self, state: BotState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(state), indent=2, sort_keys=True))
