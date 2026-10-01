from datetime import UTC, datetime
from decimal import Decimal

from xau_detective.market import Candle
from xau_detective.models import BrokerSpec, Direction
from xau_detective.paper_trading import PaperTradePlan, PaperTradingConfig, run_paper_trading


BROKER = BrokerSpec(
    symbol="XAUUSD",
    contract_size=Decimal("100"),
    volume_min=Decimal("0.01"),
    volume_max=Decimal("100"),
    volume_step=Decimal("0.01"),
    tick_size=Decimal("0.01"),
    tick_value=Decimal("1"),
    point=Decimal("0.01"),
    min_stop_distance=Decimal("0.10"),
)


def _candles():
    return (
        Candle(datetime(2026, 1, 1, 0, 0, tzinfo=UTC), Decimal("3000"), Decimal("3001"), Decimal("2999"), Decimal("3000"), 1),
        Candle(datetime(2026, 1, 1, 0, 1, tzinfo=UTC), Decimal("3000"), Decimal("3015"), Decimal("3000"), Decimal("3010"), 1),
        Candle(datetime(2026, 1, 1, 0, 2, tzinfo=UTC), Decimal("3010"), Decimal("3025"), Decimal("3005"), Decimal("3020"), 1),
    )


def test_paper_trade_uses_next_bar_and_target():
    def signal(index, history):
        if index == 0:
            return PaperTradePlan(Direction.BUY, Decimal("2995"), Decimal("3020"), Decimal("0.015"))
        return None

    result = run_paper_trading(
        _candles(), signal, BROKER,
        PaperTradingConfig(spread=Decimal("0.20"), initial_equity=Decimal("1000")),
    )
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_index == 1
    assert trade.filled_volume == Decimal("0.01")
    assert trade.exit_reason == "TAKE_PROFIT"
    assert result.net_pnl > 0


def test_invalid_stop_is_rejected_before_trade():
    def signal(index, history):
        if index == 0:
            return PaperTradePlan(Direction.BUY, Decimal("2999.95"), Decimal("3020"), Decimal("0.01"))
        return None

    result = run_paper_trading(_candles(), signal, BROKER, PaperTradingConfig())
    assert result.rejected_signals == 1
    assert result.rejection_reasons == ("STOP_DISTANCE_BELOW_BROKER_MINIMUM",)
    assert not result.trades


def test_negative_friction_is_rejected():
    try:
        run_paper_trading(
            _candles(),
            lambda index, history: None,
            BROKER,
            PaperTradingConfig(spread=Decimal("-0.1")),
        )
    except ValueError as exc:
        assert "frictions" in str(exc)
    else:
        raise AssertionError("negative friction should fail")
