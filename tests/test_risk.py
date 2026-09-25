from decimal import Decimal

from xau_detective.models import AccountSnapshot, BrokerSpec, RiskRequest
from xau_detective.risk import calculate_position_size


def broker(min_lot="0.01"):
    return BrokerSpec(
        symbol="XAUUSD",
        contract_size=Decimal(100),
        volume_min=Decimal(min_lot),
        volume_max=Decimal(100),
        volume_step=Decimal("0.01"),
        tick_size=Decimal("0.01"),
        tick_value=Decimal(1),
        point=Decimal("0.01"),
    )


def test_infeasible_minimum_lot_is_no_trade():
    result = calculate_position_size(
        RiskRequest(
            AccountSnapshot(Decimal(20), Decimal(20), Decimal(20)),
            broker(),
            Decimal(4000),
            Decimal(3990),
            Decimal("0.01"),
        )
    )
    assert not result.executable
    assert result.reason == "MIN_LOT_EXCEEDS_RISK_BUDGET"


def test_position_size_uses_broker_tick_value():
    # $1,000 balance -> $10 risk budget.
    # A $10 gold stop is 1,000 ticks; at $1/tick/lot,
    # 0.01 lot would risk $10 before the safety margin.
    result = calculate_position_size(
        RiskRequest(
            AccountSnapshot(Decimal(1000), Decimal(1000), Decimal(1000)),
            broker(),
            Decimal(4000),
            Decimal(3990),
            Decimal("0.01"),
        )
    )
    # 90% safety margin makes the executable size 0.00 after lot-step rounding,
    # so the correct deterministic outcome is NO TRADE.
    assert not result.executable
    assert result.reason == "MIN_LOT_EXCEEDS_RISK_BUDGET"


def test_smaller_stop_can_make_minimum_lot_feasible():
    result = calculate_position_size(
        RiskRequest(
            AccountSnapshot(Decimal(1000), Decimal(1000), Decimal(1000)),
            broker(),
            Decimal(4000),
            Decimal("3999.90"),
            Decimal("0.01"),
        )
    )
    assert result.executable
    assert result.volume == Decimal("0.90")
    assert result.estimated_loss == Decimal("9.00")
