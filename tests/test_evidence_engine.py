from decimal import Decimal

from datetime import UTC, datetime

from xau_detective.cross_market import CrossMarketObservation, classify_cross_market_context
from xau_detective.evidence_engine import build_evidence
from xau_detective.macro_events import MacroEvent, MacroEventType, classify_macro_event
from xau_detective.liquidity import LiquiditySnapshot
from xau_detective.mean_reversion import MeanReversionSignal
from xau_detective.models import Direction
from xau_detective.regime import RegimeSnapshot, TrendState, VolatilityState
from xau_detective.structure import StructureSnapshot
from xau_detective.volume import VolumeAnalysis
from xau_detective.zones import PriceZone, ZoneAnalysis


def snapshot(trend=TrendState.UP):
    return RegimeSnapshot(
        trend=trend,
        volatility=VolatilityState.NORMAL,
        trend_strength=Decimal(1),
        volatility_pct=Decimal(1),
        ema_fast=Decimal(101),
        ema_slow=Decimal(100),
        ema_slope_pct=Decimal("0.2"),
    )


def structure(direction=Direction.BUY):
    return StructureSnapshot(
        direction,
        True,
        True,
        False,
        False,
        True,
        Decimal(105),
        Decimal(95),
    )


def test_evidence_requires_independent_families():
    ledger = build_evidence(Direction.BUY, snapshot(), structure(), momentum=0.01)
    assert ledger.independent_evidence_count == 3
    assert not ledger.has_conflict


def test_evidence_records_conflict():
    ledger = build_evidence(
        Direction.BUY,
        snapshot(TrendState.DOWN),
        structure(),
        momentum=-0.01,
    )
    assert ledger.has_conflict
    assert "regime_trend_conflict" in ledger.contradicting


def test_research_families_are_auditable_but_not_decision_evidence():
    ledger = build_evidence(
        Direction.BUY,
        snapshot(),
        structure(),
        momentum=Decimal("0.01"),
        mean_reversion=MeanReversionSignal(
            "BUY", Decimal("-2.1"), Decimal("100"), Decimal("2"), ("re-entry",)
        ),
        liquidity=LiquiditySnapshot(
            Decimal("105"), Decimal("95"), False, True, False, False
        ),
        volume=VolumeAnalysis(
            "TICK", Decimal("200"), Decimal("100"), Decimal("2"),
            "EXPANSION", "BULLISH_PROXY", ("tick-volume",)
        ),
        zones=ZoneAnalysis(
            (PriceZone("SUPPORT", Decimal("99"), Decimal("101"), Decimal("100"), 2),),
            (),
        ),
        current_price=Decimal("100"),
    )

    assert "mean_reversion_alignment" in ledger.research_supporting
    assert "liquidity_sweep_low" in ledger.research_supporting
    assert "volume_bullish_proxy" in ledger.research_supporting
    assert "support_zone_location" in ledger.research_supporting
    assert ledger.independent_evidence_count == 3
    assert not ledger.has_conflict


def test_research_families_record_conflicts_without_gating_decisions():
    ledger = build_evidence(
        Direction.BUY,
        snapshot(),
        structure(),
        momentum=Decimal("0.01"),
        mean_reversion=MeanReversionSignal(
            "SELL", Decimal("2.1"), Decimal("100"), Decimal("2"), ("re-entry",)
        ),
        liquidity=LiquiditySnapshot(
            Decimal("105"), Decimal("95"), True, False, False, False
        ),
        volume=VolumeAnalysis(
            "TICK", Decimal("200"), Decimal("100"), Decimal("2"),
            "EXPANSION", "BEARISH_PROXY", ("tick-volume",)
        ),
        zones=ZoneAnalysis(
            (),
            (PriceZone("RESISTANCE", Decimal("99"), Decimal("101"), Decimal("100"), 2),),
        ),
        current_price=Decimal("100"),
    )

    assert "mean_reversion_conflict" in ledger.research_contradicting
    assert "liquidity_sweep_high_conflict" in ledger.research_contradicting
    assert "volume_pressure_conflict" in ledger.research_contradicting
    assert "resistance_zone_conflict" in ledger.research_contradicting
    assert not ledger.has_conflict


def test_cross_market_context_stays_research_only():
    context = classify_cross_market_context(
        CrossMarketObservation(
            timestamp=datetime(2026, 10, 1, tzinfo=UTC),
            dxy_return=Decimal("-0.2"),
            real_yield_change=Decimal("-0.05"),
        )
    )
    ledger = build_evidence(
        Direction.BUY,
        snapshot(),
        structure(),
        momentum=Decimal("0.01"),
        cross_market=context,
    )
    assert "cross_market:GOLD_CONTEXT=GOLD_SUPPORTIVE_CONTEXT" in ledger.research_warnings
    assert ledger.independent_evidence_count == 3
    assert not ledger.has_conflict

def test_macro_context_stays_research_only():
    context = classify_macro_event(
        MacroEvent(
            MacroEventType.CPI,
            datetime(2026, 10, 1, 12, tzinfo=UTC),
            actual=3.2,
            consensus=3.0,
        ),
        now=datetime(2026, 10, 1, 12, 1, tzinfo=UTC),
    )
    ledger = build_evidence(
        Direction.BUY,
        snapshot(),
        structure(),
        momentum=Decimal("0.01"),
        macro_events=(context,),
    )
    assert "macro:EVENT=CPI" in ledger.research_warnings
    assert ledger.independent_evidence_count == 3
    assert not ledger.has_conflict
