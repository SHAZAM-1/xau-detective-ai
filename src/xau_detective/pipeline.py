"""End-to-end deterministic XAUUSD analysis pipeline for V1.

The pipeline intentionally produces a trade proposal only when independent
evidence, data quality, reward/risk, and broker-aware sizing all pass.
It does not place orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from .data_quality import validate_candles
from .evidence_engine import build_evidence
from .evidence_gate import decide_from_evidence
from .features import compute_features
from .liquidity import analyze_liquidity
from .models import AccountSnapshot, BrokerSpec, Decision, Direction, RiskRequest, Scenario
from .regime import classify_regime
from .risk import calculate_position_size
from .session import classify_session
from .structure import analyze_structure
from .timeframes import Timeframe


@dataclass(frozen=True)
class AnalysisConfig:
    risk_fraction: Decimal = Decimal("0.01")
    safety_margin: Decimal = Decimal("0.90")
    min_reward_risk: Decimal = Decimal("2.0")
    min_evidence_families: int = 3
    atr_period: int = 14
    stop_atr_multiple: Decimal = Decimal("1.5")


@dataclass(frozen=True)
class MarketAnalysis:
    decision: Decision
    timestamp: datetime
    entry: Decimal | None
    stop_loss: Decimal | None
    take_profit: Decimal | None
    session: str
    evidence_supporting: tuple[str, ...]
    evidence_contradicting: tuple[str, ...]
    evidence_warnings: tuple[str, ...]
    reward_risk: Decimal | None


def _no_trade(
    reason: str,
    timestamp: datetime,
    *,
    session: str = "UNKNOWN",
    entry: Decimal | None = None,
    stop_loss: Decimal | None = None,
    take_profit: Decimal | None = None,
    reward_risk: Decimal | None = None,
) -> MarketAnalysis:
    scenario = Scenario(Direction.NO_TRADE, (reason,), reason)
    decision = Decision(Direction.NO_TRADE, 0, reason, scenario, None)
    return MarketAnalysis(
        decision,
        timestamp,
        entry,
        stop_loss,
        take_profit,
        session,
        (),
        (),
        (reason,),
        reward_risk,
    )


def analyze_market(
    *,
    d1: tuple,
    h4: tuple,
    h1: tuple,
    m15: tuple,
    m5: tuple,
    account: AccountSnapshot,
    broker: BrokerSpec,
    now: datetime | None = None,
    config: AnalysisConfig = AnalysisConfig(),
) -> MarketAnalysis:
    """Analyze closed XAUUSD candles and return an auditable decision.

    Inputs must already be normalized OHLC candles. The current forming candle
    should be excluded by the ingestion layer before calling this function.
    """
    timestamp = now or datetime.now(timezone.utc)
    session = classify_session(timestamp).label

    datasets = (
        (Timeframe.D1, d1),
        (Timeframe.H4, h4),
        (Timeframe.H1, h1),
        (Timeframe.M15, m15),
        (Timeframe.M5, m5),
    )
    for timeframe, candles in datasets:
        quality = validate_candles(candles)
        if not quality.usable:
            return _no_trade(
                f"DATA_QUALITY:{timeframe.value}:{quality.reasons[0]}",
                timestamp,
                session=session,
            )

    if not m5 or not m15 or not h4 or not h1:
        return _no_trade("INSUFFICIENT_DATA", timestamp, session=session)

    h4_features = compute_features(h4)
    h4_regime = classify_regime(h4)
    h1_structure = analyze_structure(h1)
    m15_features = compute_features(m15, ema_fast_period=9, ema_slow_period=21)
    m15_liquidity = analyze_liquidity(m15)

    direction = Direction.NO_TRADE
    if h4_regime.trend.value == "UP" and h1_structure.direction is Direction.BUY:
        direction = Direction.BUY
    elif h4_regime.trend.value == "DOWN" and h1_structure.direction is Direction.SELL:
        direction = Direction.SELL

    if direction is Direction.NO_TRADE:
        return _no_trade("NO_ALIGNED_H4_H1_DIRECTION", timestamp, session=session)

    if m15_features.momentum is None or m15_features.atr is None:
        return _no_trade("M15_FEATURES_UNAVAILABLE", timestamp, session=session)

    if direction is Direction.BUY and m15_features.momentum <= 0:
        return _no_trade("M15_MOMENTUM_CONFLICT", timestamp, session=session)
    if direction is Direction.SELL and m15_features.momentum >= 0:
        return _no_trade("M15_MOMENTUM_CONFLICT", timestamp, session=session)

    entry = m5[-1].close
    atr_value = m15_features.atr
    stop_distance = atr_value * config.stop_atr_multiple
    if stop_distance <= 0:
        return _no_trade("INVALID_STOP_DISTANCE", timestamp, session=session, entry=entry)

    if direction is Direction.BUY:
        stop_loss = entry - stop_distance
        take_profit = entry + stop_distance * config.min_reward_risk
    else:
        stop_loss = entry + stop_distance
        take_profit = entry - stop_distance * config.min_reward_risk

    reward_risk = config.min_reward_risk
    regime = h4_regime
    ledger = build_evidence(
        direction,
        regime,
        h1_structure,
        momentum=m15_features.momentum,
        min_independent_families=config.min_evidence_families,
    )
    if m15_liquidity.swept_high or m15_liquidity.swept_low:
        ledger.add_warning("RECENT_LIQUIDITY_SWEEP")
    if session == "OFF_SESSION":
        ledger.add_warning("OFF_SESSION")

    setup_score = min(
        100,
        ledger.independent_evidence_count * 25
        + (15 if reward_risk >= config.min_reward_risk else 0)
        + (10 if session != "OFF_SESSION" else 0)
        + (5 if h4_features.atr is not None else 0),
    )

    risk = calculate_position_size(
        RiskRequest(
            account=account,
            broker=broker,
            entry=entry,
            stop_loss=stop_loss,
            risk_fraction=config.risk_fraction,
            safety_margin=config.safety_margin,
        )
    )
    scenario = Scenario(
        direction,
        tuple(ledger.supporting),
        f"{direction.value}_THESIS_INVALIDATED_AT_STOP",
        take_profit,
    )
    decision = decide_from_evidence(
        scenario,
        risk,
        ledger,
        setup_score,
        min_independent_families=config.min_evidence_families,
    )
    return MarketAnalysis(
        decision,
        timestamp,
        entry,
        stop_loss,
        take_profit,
        session,
        tuple(ledger.supporting),
        tuple(ledger.contradicting),
        tuple(ledger.warnings),
        reward_risk,
    )
