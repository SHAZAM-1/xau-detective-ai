from decimal import Decimal

from xau_detective.models import DailyRiskState, ExecutionSnapshot


def test_execution_snapshot_derives_spread():
    snapshot = ExecutionSnapshot(
        bid=Decimal("3999.90"),
        ask=Decimal("4000.10"),
    )
    assert snapshot.spread == Decimal("0.20")


def test_daily_risk_state_defaults_unrealized_pnl_to_zero():
    state = DailyRiskState(realized_pnl_today=Decimal("-2"))
    assert state.unrealized_pnl_today == Decimal(0)
