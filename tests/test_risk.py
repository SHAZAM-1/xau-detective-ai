from decimal import Decimal

from xau_detective.models import AccountSnapshot, BrokerSpec, RiskRequest
from xau_detective.risk import calculate_position_size


def broker(min_lot="0.01"):
    return BrokerSpec(
        symbol="XAUUSD", contract_size=Decimal("100"),
        volume_min=Decimal(min_lot), volume_max=Decimal("100"),
        volume_step=Decimal("0.01"), tick_size=Decimal("0.01"),
        tick_value=Decimal("1"), point=Decimal("0.01"),
    )


def test_infeasible_minimum_lot_is_no_trade():
    result = calculate_position_size(RiskRequest(
        AccountSnapshot(Decimal("20"), Decimal("20"), Decimal("20")),
        broker(), Decimal("4000"), Decimal("3990"), Decimal("0.01")
    ))
    assert not result.executable
    assert result.reason == "MIN_LOT_EXCEEDS_RISK_BUDGET"


def test_position_is_sized_below_risk_budget():
    result = calculate_position_size(RiskRequest(
        AccountSnapshot(Decimal("1000"), Decimal("1000"), Decimal("1000")),
        broker(), Decimal("4000"), Decimal("3990"), Decimal("0.01")
    ))
    assert result.executable
    assert result.volume == Decimal("0.90")
    assert result.estimated_loss == Decimal("900") * Decimal("0.01")
