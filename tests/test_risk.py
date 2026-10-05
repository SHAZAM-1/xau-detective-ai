from decimal import Decimal

from xau_detective.models import (
    AccountSnapshot,
    BrokerSpec,
    DailyRiskState,
    Direction,
    ExecutionSnapshot,
    RiskRequest,
)
from xau_detective.risk import calculate_position_size


def broker():
    return BrokerSpec(
        "XAUUSD",
        Decimal(100),
        Decimal("0.01"),
        Decimal(100),
        Decimal("0.01"),
        Decimal("0.01"),
        Decimal(1),
        Decimal("0.01"),
    )


def request(**kwargs):
    return RiskRequest(
        AccountSnapshot(Decimal(1000), Decimal(1000), Decimal(1000)),
        broker(),
        Decimal(4000),
        Decimal("3999.90"),
        Decimal("0.01"),
        direction=Direction.BUY,
        **kwargs,
    )


def test_infeasible_minimum_lot_is_no_trade():
    result = calculate_position_size(
        RiskRequest(
            AccountSnapshot(Decimal(20), Decimal(20), Decimal(20)),
            broker(),
            Decimal(4000),
            Decimal(3990),
            Decimal("0.01"),
            direction=Direction.BUY,
        )
    )
    assert not result.executable
    assert result.reason == "MIN_LOT_EXCEEDS_RISK_BUDGET"


def test_smaller_stop_can_make_minimum_lot_feasible():
    result = calculate_position_size(request())
    assert result.executable
    assert result.volume == Decimal("0.90")
    assert result.estimated_loss == Decimal("9.00")


def test_position_size_uses_equity_not_balance():
    result = calculate_position_size(
        RiskRequest(
            AccountSnapshot(Decimal(1000), Decimal(500), Decimal(500)),
            broker(),
            Decimal(4000),
            Decimal("3999.90"),
            Decimal("0.01"),
            direction=Direction.BUY,
        )
    )
    assert result.executable
    assert result.risk_amount == Decimal("5.00")
    assert result.volume == Decimal("0.45")
    assert result.estimated_loss == Decimal("4.50")


def test_spread_gate_rejects_wide_market():
    result = calculate_position_size(
        request(
            execution=ExecutionSnapshot(
                Decimal("3999.80"),
                Decimal("4000.20"),
            ),
            max_spread=Decimal("0.20"),
        )
    )
    assert not result.executable
    assert result.reason == "SPREAD_TOO_WIDE"


def test_slippage_is_added_to_effective_stop_distance():
    result = calculate_position_size(
        request(
            execution=ExecutionSnapshot(
                Decimal("3999.99"),
                Decimal("4000.01"),
                Decimal("0.05"),
            )
        )
    )
    assert result.executable
    assert result.volume == Decimal("0.60")
    assert result.estimated_loss == Decimal("9.00")


def test_margin_gate_rejects_when_free_margin_is_insufficient():
    result = calculate_position_size(
        request(
            execution=ExecutionSnapshot(
                Decimal("3999.99"),
                Decimal("4000.01"),
                margin_per_lot=Decimal(2000),
            )
        )
    )
    assert not result.executable
    assert result.reason == "INSUFFICIENT_FREE_MARGIN"


def test_daily_loss_gate_includes_projected_trade_loss():
    result = calculate_position_size(
        RiskRequest(
            AccountSnapshot(Decimal(1000), Decimal(1000), Decimal(1000)),
            broker(),
            Decimal(4000),
            Decimal("3999.90"),
            Decimal("0.01"),
            direction=Direction.BUY,
            daily_risk=DailyRiskState(Decimal(-8)),
            max_daily_loss_fraction=Decimal("0.01"),
        )
    )
    assert not result.executable
    assert result.reason == "DAILY_LOSS_LIMIT"


def test_execution_threshold_requires_snapshot():
    result = calculate_position_size(request(max_spread=Decimal("0.20")))
    assert not result.executable
    assert result.reason == "EXECUTION_SNAPSHOT_REQUIRED"


def test_invalid_safety_margin_is_no_trade():
    result = calculate_position_size(request(safety_margin=Decimal("1.01")))
    assert not result.executable
    assert result.reason == "INVALID_SAFETY_MARGIN"


def test_invalid_buy_stop_direction_is_no_trade():
    result = calculate_position_size(request(stop_loss=Decimal("4000.10")))
    assert not result.executable
    assert result.reason == "INVALID_STOP_DIRECTION"


def test_invalid_sell_stop_direction_is_no_trade():
    result = calculate_position_size(
        request(direction=Direction.SELL, stop_loss=Decimal("3999.90"))
    )
    assert not result.executable
    assert result.reason == "INVALID_STOP_DIRECTION"


def test_missing_direction_is_no_trade():
    result = calculate_position_size(
        RiskRequest(
            AccountSnapshot(Decimal(1000), Decimal(1000), Decimal(1000)),
            broker(),
            Decimal(4000),
            Decimal("3999.90"),
            Decimal("0.01"),
        )
    )
    assert not result.executable
    assert result.reason == "INVALID_DIRECTION"
