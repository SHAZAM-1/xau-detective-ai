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
