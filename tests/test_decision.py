from decimal import Decimal
from xau_detective.decision import decide
from xau_detective.models import Direction, RiskResult, Scenario


def test_risk_veto_overrides_signal():
    scenario = Scenario(Direction.BUY, ("trend",), "invalidated")
    risk = RiskResult(False, Decimal("0"), Decimal("0.20"), Decimal("0"), "MIN_LOT_EXCEEDS_RISK_BUDGET")
    decision = decide(scenario, risk, 85)
    assert decision.direction is Direction.NO_TRADE
    assert decision.reason.startswith("RISK_VETO:")
