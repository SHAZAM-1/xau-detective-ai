"""End-to-end deterministic XAUUSD analysis pipeline for V1."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from .candlestick import detect_candlestick_patterns, detect_price_action_moves, interpret_pattern_read
from .data_quality import validate_candles
from .evidence_engine import build_evidence
from .evidence_gate import decide_from_evidence
from .features import compute_features
from .liquidity import analyze_liquidity
from .models import (
    AccountSnapshot,
    BrokerSpec,
    DailyRiskState,
    Decision,
    Direction,
    ExecutionSnapshot,
    RiskRequest,
    Scenario,
)
from .regime import TrendState, classify_regime
from .risk import calculate_position_size
from .session import classify_session
from .structure import analyze_structure
from .timeframes import Timeframe, expected_interval
from .trading_profile import TradingProfile


@dataclass(frozen=True)
class AnalysisConfig:
    risk_fraction: Decimal = Decimal("0.01")
    safety_margin: Decimal = Decimal("0.90")
    max_daily_loss: Decimal | None = Decimal("0.02")
    max_spread: Decimal | None = None
    max_slippage: Decimal | None = None
    min_reward_risk: Decimal = Decimal("2.0")
    min_evidence_families: int = 3
    atr_period: int = 14
    stop_atr_multiple: Decimal = Decimal("1.5")
    require_closed_candle_confirmation: bool = True
    score_evidence_weight: int = 25
    score_reward_risk_weight: int = 15
    score_session_weight: int = 10
    allowed_sessions: tuple[str, ...] = ("LONDON", "NEW_YORK")

    @classmethod
    def from_profile(cls, profile: TradingProfile, *, safety_margin: Decimal = Decimal("0.90"), max_daily_loss: Decimal | None = Decimal("0.02")) -> AnalysisConfig:
        """Build analysis settings from a user's preferences.

        Profile settings never alter hard safety gates or live-execution policy.
        """
        profile.validate()
        return cls(
            risk_fraction=profile.risk_fraction,
            safety_margin=safety_margin,
            max_daily_loss=max_daily_loss,
            max_spread=profile.max_spread,
            max_slippage=profile.max_slippage,
            min_reward_risk=profile.min_reward_risk,
            stop_atr_multiple=profile.stop_atr_multiple,
            allowed_sessions=profile.allowed_sessions,
        )


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
    candlestick_patterns: tuple[str, ...] = ()
    price_action_moves: tuple[str, ...] = ()


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
    config: AnalysisConfig | None = None,
    execution: ExecutionSnapshot | None = None,
    daily_risk: DailyRiskState | None = None,
) -> MarketAnalysis:
    config = config or AnalysisConfig()
    timestamp = now or datetime.now(UTC)
    session = classify_session(timestamp).label
    if session not in config.allowed_sessions:
        return _no_trade(f"SESSION_NOT_ALLOWED:{session}", timestamp, session=session)
    datasets = (
        (Timeframe.D1, d1),
        (Timeframe.H4, h4),
        (Timeframe.H1, h1),
        (Timeframe.M15, m15),
        (Timeframe.M5, m5),
    )
    for timeframe, candles in datasets:
        if (
            config.require_closed_candle_confirmation
            and candles
            and candles[-1].timestamp + expected_interval(timeframe) > timestamp
        ):
            return _no_trade(f"OPEN_CANDLE:{timeframe.value}", timestamp, session=session)
        quality = validate_candles(candles, expected_interval(timeframe))
        if not quality.usable:
            return _no_trade(
                f"DATA_QUALITY:{timeframe.value}:{quality.reasons[0]}",
                timestamp,
                session=session,
            )

    if not m5 or not m15 or not h4 or not h1 or not d1:
        return _no_trade("INSUFFICIENT_DATA", timestamp, session=session)

    d1_regime = classify_regime(d1)
    h4_regime = classify_regime(h4)
    h1_structure = analyze_structure(h1)
    m15_features = compute_features(m15, ema_fast_period=9, ema_slow_period=21)
    m15_liquidity = analyze_liquidity(m15)
    m15_patterns = detect_candlestick_patterns(m15)
    m15_moves = detect_price_action_moves(m15)
    m15_pattern_read = interpret_pattern_read(m15)

    direction = Direction.NO_TRADE
    if h4_regime.trend is TrendState.UP and h1_structure.direction is Direction.BUY:
        direction = Direction.BUY
    elif h4_regime.trend is TrendState.DOWN and h1_structure.direction is Direction.SELL:
        direction = Direction.SELL
    if direction is Direction.NO_TRADE:
        return _no_trade("NO_ALIGNED_H4_H1_DIRECTION", timestamp, session=session)

    if (
        direction is Direction.BUY
        and d1_regime.trend is TrendState.DOWN
        or direction is Direction.SELL
        and d1_regime.trend is TrendState.UP
    ):
        return _no_trade("D1_CONTEXT_CONFLICT", timestamp, session=session)

    if "PATTERN_CONFLICT_LATEST_CANDLE" in m15_pattern_read.warnings:
        return _no_trade("PATTERN_CONFLICT_LATEST_CANDLE", timestamp, session=session)
    if m15_pattern_read.direction == "BULLISH" and direction is not Direction.BUY:
        return _no_trade("M15_PATTERN_DIRECTION_CONFLICT", timestamp, session=session)
    if m15_pattern_read.direction == "BEARISH" and direction is not Direction.SELL:
        return _no_trade("M15_PATTERN_DIRECTION_CONFLICT", timestamp, session=session)

    if m15_features.momentum is None or m15_features.atr is None:
        return _no_trade("M15_FEATURES_UNAVAILABLE", timestamp, session=session)
    if direction is Direction.BUY and m15_features.momentum <= 0:
        return _no_trade("M15_MOMENTUM_CONFLICT", timestamp, session=session)
    if direction is Direction.SELL and m15_features.momentum >= 0:
        return _no_trade("M15_MOMENTUM_CONFLICT", timestamp, session=session)

    entry = (
        execution.ask
        if execution is not None and direction is Direction.BUY
        else execution.bid
        if execution is not None and direction is Direction.SELL
        else m5[-1].close
    )
    stop_distance = m15_features.atr * config.stop_atr_multiple
    if stop_distance <= 0:
        return _no_trade("INVALID_STOP_DISTANCE", timestamp, session=session, entry=entry)
    if direction is Direction.BUY:
        stop_loss = entry - stop_distance
        take_profit = entry + stop_distance * config.min_reward_risk
    else:
        stop_loss = entry + stop_distance
        take_profit = entry - stop_distance * config.min_reward_risk

    ledger = build_evidence(
        direction,
        h4_regime,
        h1_structure,
        momentum=m15_features.momentum,
        min_independent_families=config.min_evidence_families,
    )
    if d1_regime.trend is TrendState.UP:
        ledger.add_warning("D1_CONTEXT_UP")
    elif d1_regime.trend is TrendState.DOWN:
        ledger.add_warning("D1_CONTEXT_DOWN")
    if m15_liquidity.swept_high or m15_liquidity.swept_low:
        ledger.add_warning("RECENT_LIQUIDITY_SWEEP")
    if session == "OFF_SESSION":
        ledger.add_warning("OFF_SESSION")

    setup_score = min(
        100,
        ledger.independent_evidence_count * config.score_evidence_weight
        + (
            config.score_reward_risk_weight
            if config.min_reward_risk >= Decimal("2.0")
            else 0
        )
        + (config.score_session_weight if session != "OFF_SESSION" else 0),
    )
    risk = calculate_position_size(
        RiskRequest(
            account=account,
            broker=broker,
            entry=entry,
            stop_loss=stop_loss,
            risk_fraction=config.risk_fraction,
            safety_margin=config.safety_margin,
            direction=direction,
            execution=execution,
            max_spread=config.max_spread,
            max_slippage=config.max_slippage,
            daily_risk=daily_risk,
            max_daily_loss_fraction=config.max_daily_loss,
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
        config.min_reward_risk,
        tuple(pattern.name for pattern in m15_patterns[-8:]),
        tuple(move.move.value for move in m15_moves[-8:]),
    )
