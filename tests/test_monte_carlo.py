from decimal import Decimal

import pytest

from xau_detective.monte_carlo import run_monte_carlo


def test_monte_carlo_is_deterministic_with_seed():
    returns = (Decimal("2"), Decimal("-1"), Decimal("1"))
    first = run_monte_carlo(
        returns,
        simulations=100,
        trades_per_simulation=20,
        initial_equity=Decimal("100"),
        ruin_threshold=Decimal("10"),
        seed=7,
    )
    second = run_monte_carlo(
        returns,
        simulations=100,
        trades_per_simulation=20,
        initial_equity=Decimal("100"),
        ruin_threshold=Decimal("10"),
        seed=7,
    )
    assert first == second
    assert first.simulations == 100
    assert Decimal(0) <= first.ruin_frequency <= Decimal(1)


def test_all_positive_returns_have_no_ruin():
    result = run_monte_carlo(
        (Decimal("1"),),
        simulations=50,
        trades_per_simulation=10,
        initial_equity=Decimal("100"),
        ruin_threshold=Decimal("1"),
    )
    assert result.ruin_count == 0
    assert result.worst_final_equity == Decimal("110")


def test_invalid_inputs_are_rejected():
    with pytest.raises(ValueError):
        run_monte_carlo(())
    with pytest.raises(ValueError):
        run_monte_carlo((Decimal("1"),), simulations=0)


def test_backtest_monte_carlo_uses_trade_pnl_and_r_as_paired_observations():
    from xau_detective.backtest import BacktestResult, BacktestTrade
    from xau_detective.models import Direction

    trade = BacktestTrade(
        signal_index=0,
        entry_index=1,
        exit_index=2,
        direction=Direction.BUY,
        entry_price=Decimal("100"),
        exit_price=Decimal("102"),
        volume=Decimal("1"),
        gross_pnl=Decimal("2"),
        risk_amount=Decimal("1"),
        commission=Decimal("0"),
        net_pnl=Decimal("2"),
        exit_reason="TAKE_PROFIT",
    )
    result = BacktestResult(
        trades=(trade,),
        net_pnl=Decimal("2"),
        wins=1,
        losses=0,
        breakevens=0,
        max_drawdown=Decimal("0"),
    )

    from xau_detective.monte_carlo import run_backtest_monte_carlo

    monte_carlo = run_backtest_monte_carlo(
        result,
        simulations=10,
        trades_per_simulation=1,
        initial_equity=Decimal("100"),
        ruin_threshold=Decimal("10"),
        seed=7,
    )

    assert monte_carlo.worst_final_equity == Decimal("102")
    assert monte_carlo.average_r == Decimal("2")
    assert monte_carlo.median_r == Decimal("2")
    assert monte_carlo.worst_r == Decimal("2")


def test_backtest_monte_carlo_rejects_missing_trade_risk():
    from xau_detective.backtest import BacktestResult, BacktestTrade
    from xau_detective.models import Direction

    trade = BacktestTrade(
        signal_index=0,
        entry_index=1,
        exit_index=2,
        direction=Direction.BUY,
        entry_price=Decimal("100"),
        exit_price=Decimal("99"),
        volume=Decimal("1"),
        gross_pnl=Decimal("-1"),
        risk_amount=Decimal("0"),
        commission=Decimal("0"),
        net_pnl=Decimal("-1"),
        exit_reason="STOP_LOSS",
    )
    result = BacktestResult(
        trades=(trade,),
        net_pnl=Decimal("-1"),
        wins=0,
        losses=1,
        breakevens=0,
        max_drawdown=Decimal("1"),
    )

    from xau_detective.monte_carlo import run_backtest_monte_carlo

    with pytest.raises(ValueError, match="positive risk_amount"):
        run_backtest_monte_carlo(result)
