"""Core domain models used by the deterministic trading engine."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class Direction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NO_TRADE = "NO_TRADE"


@dataclass(frozen=True)
class BrokerSpec:
    symbol: str
    contract_size: Decimal
    volume_min: Decimal
    volume_max: Decimal
    volume_step: Decimal
    tick_size: Decimal
    tick_value: Decimal
    point: Decimal
    min_stop_distance: Decimal = Decimal(0)


@dataclass(frozen=True)
class ExecutionSnapshot:
    bid: Decimal
    ask: Decimal
    estimated_slippage: Decimal = Decimal(0)
    margin_per_lot: Decimal | None = None

    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid


@dataclass(frozen=True)
class DailyRiskState:
    realized_pnl_today: Decimal
    unrealized_pnl_today: Decimal = Decimal(0)


@dataclass(frozen=True)
class AccountSnapshot:
    balance: Decimal
    equity: Decimal
    free_margin: Decimal


@dataclass(frozen=True)
class RiskRequest:
    account: AccountSnapshot
    broker: BrokerSpec
    entry: Decimal
    stop_loss: Decimal
    risk_fraction: Decimal
    safety_margin: Decimal = Decimal("0.90")
    direction: Direction = Direction.NO_TRADE
    execution: ExecutionSnapshot | None = None
    max_spread: Decimal | None = None
    max_slippage: Decimal | None = None
    daily_risk: DailyRiskState | None = None
    max_daily_loss_fraction: Decimal | None = None


@dataclass(frozen=True)
class RiskResult:
    executable: bool
    volume: Decimal
    risk_amount: Decimal
    estimated_loss: Decimal
    reason: str


@dataclass(frozen=True)
class Scenario:
    direction: Direction
    evidence: tuple[str, ...]
    invalidation: str
    target: Decimal | None = None


@dataclass(frozen=True)
class Decision:
    direction: Direction
    setup_score: int
    reason: str
    scenario: Scenario | None = None
    risk: RiskResult | None = None
