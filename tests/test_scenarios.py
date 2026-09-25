from decimal import Decimal

from xau_detective.models import Direction
from xau_detective.scenarios import ScenarioInput, generate_scenarios

def test_aligned_buy_scenario():
    result = generate_scenarios(ScenarioInput(
        Direction.BUY, Direction.BUY, Direction.BUY, True, Decimal("2.5")
    ))
    assert result[0].direction is Direction.BUY


def test_bad_rr_is_no_trade():
    result = generate_scenarios(ScenarioInput(
        Direction.BUY, Direction.BUY, Direction.BUY, True, Decimal("1.5")
    ))
    assert result[0].direction is Direction.NO_TRADE
