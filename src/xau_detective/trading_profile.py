"""User-configurable trading preferences with immutable safety boundaries."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class TradingProfile:
    """User preferences applied to analysis and execution policy.

    Safety controls remain owned by the engine. A profile can change trading
    preferences, but cannot disable broker/risk validation or unlock live V1.
    """

    risk_fraction: Decimal = Decimal("0.01")
    min_reward_risk: Decimal = Decimal("2.0")
    bot_suggestions_enabled: bool = True
    auto_analysis_enabled: bool = True
    auto_execution_enabled: bool = False
    max_spread: Decimal | None = None
    max_slippage: Decimal | None = None
    stop_atr_multiple: Decimal = Decimal("1.5")
    allowed_sessions: tuple[str, ...] = ("LONDON", "NEW_YORK")

    def validate(self) -> None:
        """Reject invalid user preferences before they reach the engine."""
        if self.risk_fraction <= 0 or self.risk_fraction >= 1:
            raise ValueError("risk_fraction must be greater than 0 and below 1")
        if self.min_reward_risk <= 0:
            raise ValueError("min_reward_risk must be greater than 0")
        if self.stop_atr_multiple <= 0:
            raise ValueError("stop_atr_multiple must be greater than 0")
        if self.max_spread is not None and self.max_spread <= 0:
            raise ValueError("max_spread must be greater than 0")
        if self.max_slippage is not None and self.max_slippage < 0:
            raise ValueError("max_slippage cannot be negative")

    def to_analysis_overrides(self) -> dict[str, object]:
        """Return only strategy preferences consumed by the analysis layer."""
        self.validate()
        return {
            "risk_fraction": self.risk_fraction,
            "min_reward_risk": self.min_reward_risk,
            "max_spread": self.max_spread,
            "max_slippage": self.max_slippage,
            "stop_atr_multiple": self.stop_atr_multiple,
        }
