from decimal import Decimal

from xau_detective.evidence_engine import build_evidence
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


def test_research_families_add_directional_evidence():
    ledger = build_evidence(
        Direction.BUY,
        snapshot(),
        structure(),
        momentum=Decimal("0.01"),
        mean_reversion=MeanReversionSignal(
            "BUY",
            Decimal("-2.1"),
            Decimal("100"),
            Decimal("2"),
            ("re-entry",),
        ),
        liquidity=LiquiditySnapshot(
            Decimal("105"),
            Decimal("95"),
            False,
            True,
            False,
            False,
        ),
        volume=VolumeAnalysis(
            "TICK",
            Decimal("200"),
            Decimal("100"),
            Decimal("2"),
            "EXPANSION",
            "BULLISH_PROXY",
            ("tick-volume",),
        ),
        zones=ZoneAnalysis(
            (PriceZone("SUPPORT", Decimal("99"), Decimal("101"), Decimal("100"), 2),),
            (),
        ),
        current_price=Decimal("100"),
        min_independent_families=3,
    )

    assert "mean_reversion_alignment" in ledger.supporting
    assert "liquidity_sweep_low" in ledger.supporting
    assert "volume_bullish_proxy" in ledger.supporting
    assert "support_zone_location" in ledger.supporting
    assert ledger.independent_evidence_count >= 7


def test_research_families_record_conflicts_without_inventing_order_flow():
    ledger = build_evidence(
        Direction.BUY,
        snapshot(),
        structure(),
        momentum=Decimal("0.01"),
        mean_reversion=MeanReversionSignal(
            "SELL",
            Decimal("2.1"),
            Decimal("100"),
            Decimal("2"),
            ("re-entry",),
        ),
        liquidity=LiquiditySnapshot(
            Decimal("105"),
            Decimal("95"),
            True,
            False,
            False,
            False,
        ),
        volume=VolumeAnalysis(
            "TICK",
            Decimal("200"),
            Decimal("100"),
            Decimal("2"),
            "EXPANSION",
            "BEARISH_PROXY",
            ("tick-volume",),
        ),
        zones=ZoneAnalysis(
            (),
            (PriceZone("RESISTANCE", Decimal("99"), Decimal("101"), Decimal("100"), 2),),
        ),
        current_price=Decimal("100"),
        min_independent_families=3,
    )

    assert "mean_reversion_conflict" in ledger.contradicting
    assert "liquidity_sweep_high_conflict" in ledger.contradicting
    assert "volume_pressure_conflict" in ledger.contradicting
    assert "resistance_zone_conflict" in ledger.contradicting
