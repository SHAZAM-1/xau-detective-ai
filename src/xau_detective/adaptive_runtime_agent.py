"""Guarded runtime adaptation for MT5 operational conditions.

The agent observes broker/runtime state plus the append-only audit stream and
may recommend or enforce only operational adaptations. It cannot rewrite
strategy logic, risk limits, execution policy, or the project roadmap.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .audit_log import AuditEvent, AuditLog
from .environment import AccountCapabilities, TradingEnvironment
from .models import BrokerSpec, ExecutionSnapshot
from .trading_profile import TradingProfile


ALLOWED_ADAPTATIONS = frozenset(
    {
        "BROKER_SPEC_REFRESH",
        "DATA_QUALITY_GUARD",
        "CONNECTION_GUARD",
        "EXECUTION_ENVIRONMENT_GUARD",
        "SPREAD_GUARD",
        "STOP_DISTANCE_GUARD",
        "VOLUME_CONSTRAINT_REFRESH",
    }
)

FORBIDDEN_ADAPTATIONS = frozenset(
    {
        "CHANGE_STRATEGY",
        "CHANGE_SETUP_SCORE",
        "CHANGE_RISK_FRACTION",
        "CHANGE_STOP_MODEL",
        "CHANGE_TARGET_MODEL",
        "ENABLE_LIVE_EXECUTION",
        "DISABLE_NO_TRADE",
        "REWRITE_ROADMAP",
    }
)


@dataclass(frozen=True)
class MT5RuntimeObservation:
    capabilities: AccountCapabilities
    broker: BrokerSpec
    execution: ExecutionSnapshot


@dataclass(frozen=True)
class RuntimeAdaptation:
    action: str
    allowed: bool
    reason: str
    details: dict[str, object]


@dataclass(frozen=True)
class RuntimeAdaptationReport:
    safe: bool
    adaptations: tuple[RuntimeAdaptation, ...]
    repeated_failures: tuple[str, ...]
    blocked_changes: tuple[str, ...]


class AdaptiveRuntimeAgent:
    """Observe MT5 conditions and fail closed without changing trading strategy."""

    def __init__(
        self,
        audit_log: AuditLog,
        *,
        failure_window: int = 20,
        repeated_failure_threshold: int = 3,
    ) -> None:
        if failure_window < 1:
            raise ValueError("failure_window must be positive")
        if repeated_failure_threshold < 1:
            raise ValueError("repeated_failure_threshold must be positive")
        self._audit = audit_log
        self._failure_window = failure_window
        self._threshold = repeated_failure_threshold

    def assess(
        self,
        *,
        observation: MT5RuntimeObservation,
        profile: TradingProfile,
        trace_id: str,
        now: datetime,
    ) -> RuntimeAdaptationReport:
        """Return bounded operational adaptations and a fail-closed safety verdict."""
        recent = self._audit.events()[-self._failure_window :]
        reasons: dict[str, int] = {}
        operational_prefixes = (
            "MT5_",
            "SYMBOL_",
            "INVALID_",
            "EXECUTION_ERROR:",
            "DATA_",
        )
        for event in recent:
            # A deliberate account-switch lock is a policy hold, not a
            # recurring infrastructure failure; it remains blocked until
            # explicit acknowledgement and must not poison the post-ack guard.
            if event.reason == "MT5_SESSION_CHANGED_EXECUTION_BLOCKED":
                continue
            if (
                event.status in {"BLOCKED", "REJECTED"}
                and event.reason
                and event.reason.startswith(operational_prefixes)
            ):
                reasons[event.reason] = reasons.get(event.reason, 0) + 1

        repeated = tuple(
            reason
            for reason, count in sorted(reasons.items())
            if count >= self._threshold
        )
        adaptations: list[RuntimeAdaptation] = []
        capabilities = observation.capabilities
        broker = observation.broker
        execution = observation.execution

        adaptations.append(
            RuntimeAdaptation(
                action="BROKER_SPEC_REFRESH",
                allowed=True,
                reason="BROKER_SPEC_IS_RUNTIME_SOURCE_OF_TRUTH",
                details={
                    "symbol": broker.symbol,
                    "volume_min": broker.volume_min,
                    "volume_max": broker.volume_max,
                    "volume_step": broker.volume_step,
                    "tick_size": broker.tick_size,
                    "tick_value": broker.tick_value,
                    "point": broker.point,
                    "min_stop_distance": broker.min_stop_distance,
                },
            )
        )
        adaptations.append(
            RuntimeAdaptation(
                action="VOLUME_CONSTRAINT_REFRESH",
                allowed=True,
                reason="USE_BROKER_VOLUME_LIMITS",
                details={
                    "volume_min": broker.volume_min,
                    "volume_max": broker.volume_max,
                    "volume_step": broker.volume_step,
                },
            )
        )
        adaptations.append(
            RuntimeAdaptation(
                action="STOP_DISTANCE_GUARD",
                allowed=True,
                reason="RESPECT_BROKER_MIN_STOP_DISTANCE",
                details={"min_stop_distance": broker.min_stop_distance},
            )
        )

        if execution.spread < 0:
            adaptations.append(
                RuntimeAdaptation(
                    action="SPREAD_GUARD",
                    allowed=True,
                    reason="INVALID_NEGATIVE_SPREAD",
                    details={"spread": execution.spread},
                )
            )

        if not capabilities.connected or not capabilities.connection_healthy:
            adaptations.append(
                RuntimeAdaptation(
                    action="CONNECTION_GUARD",
                    allowed=True,
                    reason="MT5_CONNECTION_NOT_HEALTHY",
                    details={"connected": capabilities.connected},
                )
            )

        if capabilities.environment is not TradingEnvironment.DEMO:
            adaptations.append(
                RuntimeAdaptation(
                    action="EXECUTION_ENVIRONMENT_GUARD",
                    allowed=True,
                    reason="V1_ONLY_DEMO_EXECUTION",
                    details={"environment": capabilities.environment.value},
                )
            )

        if not capabilities.symbol_available:
            adaptations.append(
                RuntimeAdaptation(
                    action="DATA_QUALITY_GUARD",
                    allowed=True,
                    reason="SYMBOL_UNAVAILABLE",
                    details={"symbol": capabilities.symbol},
                )
            )

        profile.validate()
        blocked = tuple(
            sorted(
                {
                    "CHANGE_RISK_FRACTION",
                    "CHANGE_SETUP_SCORE",
                    "CHANGE_STOP_MODEL",
                    "CHANGE_TARGET_MODEL",
                    "ENABLE_LIVE_EXECUTION",
                    "REWRITE_ROADMAP",
                }
            )
        )

        safe = (
            capabilities.environment is TradingEnvironment.DEMO
            and capabilities.connected
            and capabilities.connection_healthy
            and capabilities.symbol_available
            and broker.symbol == capabilities.symbol
            and broker.volume_step > 0
            and broker.volume_min > 0
            and broker.volume_max >= broker.volume_min
            and broker.tick_size > 0
            and broker.tick_value > 0
            and execution.bid > 0
            and execution.ask > 0
            and execution.ask >= execution.bid
            and not repeated
        )

        self._audit.append(
            AuditEvent(
                timestamp=now,
                trace_id=trace_id,
                event="adaptive_runtime",
                status="SAFE" if safe else "GUARDED",
                reason="MT5_RUNTIME_ADAPTATION_ASSESSED",
                symbol=capabilities.symbol,
                details={
                    "safe": safe,
                    "repeated_failures": list(repeated),
                    "allowed_adaptations": [item.action for item in adaptations],
                    "blocked_changes": list(blocked),
                },
            )
        )
        return RuntimeAdaptationReport(
            safe=safe,
            adaptations=tuple(adaptations),
            repeated_failures=repeated,
            blocked_changes=blocked,
        )

    @staticmethod
    def adaptation_actions(report: RuntimeAdaptationReport) -> tuple[str, ...]:
        return tuple(
            item.action
            for item in report.adaptations
            if item.allowed and item.action in ALLOWED_ADAPTATIONS
        )

    @staticmethod
    def is_strategy_change(action: str) -> bool:
        if not isinstance(action, str):
            return False
        normalized = "".join(action.split()).upper()
        return normalized in FORBIDDEN_ADAPTATIONS
