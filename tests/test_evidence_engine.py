from decimal import Decimal

from xau_detective.evidence_engine import build_evidence
from xau_detective.models import Direction
from xau_detective.regime import RegimeSnapshot, TrendState, VolatilityState
from xau_detective.structure import StructureSnapshot


def snapshot(trend=TrendState.UP):
    return RegimeSnapshot(
        trend=trend,
        volatility=VolatilityState.NORMAL,
        trend_strength=Decimal("1"),
        volatility_pct=Decimal("1"),
        ema_fast=Decimal("101"),
        ema_slow=Decimal("100"),
        ema_slope_pct=Decimal("0.2"),
    )


def structure(direction=Direction.BUY):
    return StructureSnapshot(direction, True, True, False, False, True, Decimal("105"), Decimal("95"))


def test_evidence_requires_independent_families():
    ledger = build_evidence(Direction.BUY, snapshot(), structure(), momentum=0.01)
    assert ledger.independent_evidence_count == 3
    assert not ledger.has_conflict


def test_evidence_records_conflict():
    ledger = build_evidence(Direction.BUY, snapshot(TrendState.DOWN), structure(), momentum=-0.01)
    assert ledger.has_conflict
    assert "regime_trend_conflict" in ledger.contradicting
