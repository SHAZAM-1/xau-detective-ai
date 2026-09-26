from decimal import Decimal
from types import SimpleNamespace

from xau_detective.mt5_adapter import execution_snapshot_from_mt5


def test_execution_snapshot_from_mt5_maps_tick_and_margin():
    snapshot = execution_snapshot_from_mt5(
        SimpleNamespace(bid=3999.9, ask=4000.1),
        margin_per_lot=Decimal(1500),
        estimated_slippage=Decimal("0.03"),
    )
    assert snapshot.bid == Decimal("3999.9")
    assert snapshot.ask == Decimal("4000.1")
    assert snapshot.spread == Decimal("0.2")
    assert snapshot.margin_per_lot == Decimal(1500)
    assert snapshot.estimated_slippage == Decimal("0.03")
