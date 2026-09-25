from decimal import Decimal


from xau_detective.evidence import EvidenceLedger
from xau_detective.evidence_gate import decide_from_evidence
from xau_detective.models import Direction, RiskResult, Scenario


def risk():
    return RiskResult(True, Decimal("0.01"), Decimal(1), Decimal("0.9"), "OK")


def scenario():
    return Scenario(Direction.BUY, ("trend",), "below_structure")


def test_conflicting_evidence_forces_no_trade():
    ledger = EvidenceLedger(Direction.BUY, ["trend"], ["momentum_opposes_direction"])
    decision = decide_from_evidence(scenario(), risk(), ledger, 90)
    assert decision.direction is Direction.NO_TRADE
    assert decision.reason == "EVIDENCE_CONFLICT"


def test_three_independent_families_allow_trade():
    ledger = EvidenceLedger(
        Direction.BUY,
        ["regime_trend_up", "structure_breakout_alignment", "momentum_positive"],
    )
    decision = decide_from_evidence(scenario(), risk(), ledger, 80)
    assert decision.direction is Direction.BUY
    assert decision.reason == "TRADE_ALLOWED"
