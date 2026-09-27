"""Runtime health telemetry for the Demo trading service.

This module is intentionally decision-neutral: it records operational state
and counters but never changes a trade decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class RuntimeHealthSnapshot:
    cycles: int
    successful_preflights: int
    analysis_attempts: int
    execution_attempts: int
    execution_successes: int
    rejected_cycles: int
    error_cycles: int
    reconciliation_checks: int
    active_exposure: bool
    last_cycle_at: datetime | None
    last_analysis_at: datetime | None
    last_execution_at: datetime | None
    last_reconciliation_at: datetime | None
    last_reason: str | None


class RuntimeHealthTracker:
    """Small in-process operational counter set for a long-running service."""

    def __init__(self) -> None:
        self._cycles = 0
        self._successful_preflights = 0
        self._analysis_attempts = 0
        self._execution_attempts = 0
        self._execution_successes = 0
        self._rejected_cycles = 0
        self._error_cycles = 0
        self._reconciliation_checks = 0
        self._active_exposure = False
        self._last_cycle_at = None
        self._last_analysis_at = None
        self._last_execution_at = None
        self._last_reconciliation_at = None
        self._last_reason = None

    def cycle_started(self, now: datetime) -> None:
        self._cycles += 1
        self._last_cycle_at = now.astimezone(UTC) if now.tzinfo else now.replace(tzinfo=UTC)

    def preflight_passed(self) -> None:
        self._successful_preflights += 1

    def analysis_attempted(self, now: datetime) -> None:
        self._analysis_attempts += 1
        self._last_analysis_at = now.astimezone(UTC) if now.tzinfo else now.replace(tzinfo=UTC)

    def execution_attempted(self, now: datetime) -> None:
        self._execution_attempts += 1
        self._last_execution_at = now.astimezone(UTC) if now.tzinfo else now.replace(tzinfo=UTC)

    def execution_succeeded(self) -> None:
        self._execution_successes += 1

    def reconciliation_checked(self, now: datetime, *, active_exposure: bool) -> None:
        self._reconciliation_checks += 1
        self._active_exposure = active_exposure
        self._last_reconciliation_at = now.astimezone(UTC) if now.tzinfo else now.replace(tzinfo=UTC)

    def rejected(self, reason: str) -> None:
        self._rejected_cycles += 1
        self._last_reason = reason

    def errored(self, reason: str) -> None:
        self._error_cycles += 1
        self._last_reason = reason

    def reason(self, reason: str) -> None:
        self._last_reason = reason

    def snapshot(self) -> RuntimeHealthSnapshot:
        return RuntimeHealthSnapshot(
            cycles=self._cycles,
            successful_preflights=self._successful_preflights,
            analysis_attempts=self._analysis_attempts,
            execution_attempts=self._execution_attempts,
            execution_successes=self._execution_successes,
            rejected_cycles=self._rejected_cycles,
            error_cycles=self._error_cycles,
            reconciliation_checks=self._reconciliation_checks,
            active_exposure=self._active_exposure,
            last_cycle_at=self._last_cycle_at,
            last_analysis_at=self._last_analysis_at,
            last_execution_at=self._last_execution_at,
            last_reconciliation_at=self._last_reconciliation_at,
            last_reason=self._last_reason,
        )
