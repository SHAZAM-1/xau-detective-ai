"""Trade memory and outcome learning primitives.

The bot records every closed trade with the evidence available at decision time
and the realized outcome. This prevents hindsight from contaminating the
decision snapshot. Statistical model updates should consume these closed
observations offline and pass validation before becoming live configuration.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from enum import Enum
import json
from pathlib import Path
from typing import Iterable

from .models import Direction


class TradeOutcome(str, Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    BREAKEVEN = "BREAKEVEN"


@dataclass(frozen=True)
class TradeRecord:
    trade_id: str
    timestamp: str
    symbol: str
    direction: Direction
    entry: Decimal
    stop_loss: Decimal
    take_profit: Decimal | None
    setup_score: int
    evidence: tuple[str, ...]
    warnings: tuple[str, ...]
    regime: str
    entry_reason: str
    outcome: TradeOutcome | None = None
    pnl: Decimal | None = None
    pnl_r: Decimal | None = None
    exit_reason: str | None = None
    mae_r: Decimal | None = None
    mfe_r: Decimal | None = None

    def close(
        self,
        *,
        outcome: TradeOutcome,
        pnl: Decimal,
        pnl_r: Decimal,
        exit_reason: str,
        mae_r: Decimal | None = None,
        mfe_r: Decimal | None = None,
    ) -> "TradeRecord":
        return TradeRecord(
            **{
                **asdict(self),
                "outcome": outcome,
                "pnl": pnl,
                "pnl_r": pnl_r,
                "exit_reason": exit_reason,
                "mae_r": mae_r,
                "mfe_r": mfe_r,
            }
        )


@dataclass(frozen=True)
class LearningStats:
    closed_trades: int
    wins: int
    losses: int
    breakevens: int
    win_rate: Decimal
    expectancy_r: Decimal
    average_win_r: Decimal
    average_loss_r: Decimal


def summarize_closed(records: Iterable[TradeRecord]) -> LearningStats:
    closed = [r for r in records if r.outcome is not None and r.pnl_r is not None]
    wins = [r.pnl_r for r in closed if r.outcome is TradeOutcome.WIN]
    losses = [r.pnl_r for r in closed if r.outcome is TradeOutcome.LOSS]
    breakevens = [r for r in closed if r.outcome is TradeOutcome.BREAKEVEN]
    count = len(closed)

    def avg(values: list[Decimal]) -> Decimal:
        return sum(values, Decimal("0")) / Decimal(len(values)) if values else Decimal("0")

    return LearningStats(
        closed_trades=count,
        wins=len(wins),
        losses=len(losses),
        breakevens=len(breakevens),
        win_rate=Decimal(len(wins)) / Decimal(count) if count else Decimal("0"),
        expectancy_r=avg([r.pnl_r for r in closed]),
        average_win_r=avg(wins),
        average_loss_r=avg(losses),
    )


class JsonlTradeMemory:
    """Append-only trade memory for research and later model training."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, record: TradeRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(record)
        payload["direction"] = record.direction.value
        payload["outcome"] = record.outcome.value if record.outcome else None
        for key in ("entry", "stop_loss", "take_profit", "pnl", "pnl_r", "mae_r", "mfe_r"):
            if payload[key] is not None:
                payload[key] = str(payload[key])
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, separators=(",", ":")) + "\n")

    def read_all(self) -> tuple[TradeRecord, ...]:
        if not self.path.exists():
            return ()
        records: list[TradeRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            for key in ("entry", "stop_loss", "take_profit", "pnl", "pnl_r", "mae_r", "mfe_r"):
                if raw.get(key) is not None:
                    raw[key] = Decimal(raw[key])
            raw["direction"] = Direction(raw["direction"])
            raw["outcome"] = TradeOutcome(raw["outcome"]) if raw.get("outcome") else None
            raw["evidence"] = tuple(raw.get("evidence", ()))
            raw["warnings"] = tuple(raw.get("warnings", ()))
            records.append(TradeRecord(**raw))
        return tuple(records)
