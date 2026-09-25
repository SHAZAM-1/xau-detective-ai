from datetime import datetime, timedelta
from decimal import Decimal

from xau_detective.backtest import BacktestConfig, TradePlan, run_backtest
from xau_detective.market import Candle
from xau_detective.models import Direction


def candle(i, open_, high, low, close):
    return Candle(
        datetime(2026, 1, 1) + timedelta(hours=i),
        Decimal(str(open_)),
        Decimal(str(high)),
        Decimal(str(low)),
        Decimal(str(close)),
    )


def test_backtest_enters_next_bar_and_applies_friction():
    candles = (
        candle(0, 100, 101, 99, 100),
        candle(1, 100, 104, 100, 103),
        candle(2, 103, 106, 102, 105),
    )

    def signal(index, _history):
        if index == 0:
            return TradePlan(Direction.BUY, Decimal("99"), Decimal("104"), Decimal("1"))
        return None

    result = run_backtest(
        candles,
        signal,
        BacktestConfig(
            tick_size=Decimal("1"),
            tick_value=Decimal("1"),
            spread=Decimal("1"),
            slippage=Decimal("0.5"),
            commission_per_lot_per_side=Decimal("0.25"),
        ),
    )

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_index == 1
    assert trade.exit_reason == "TAKE_PROFIT"
    assert trade.entry_price == Decimal("101")
    assert trade.exit_price == Decimal("103")
    assert trade.gross_pnl == Decimal("2")
    assert trade.commission == Decimal("0.5")
    assert trade.net_pnl == Decimal("1.5")


def test_stop_wins_tie_against_target_when_both_touch():
    candles = (
        candle(0, 100, 101, 99, 100),
        candle(1, 100, 105, 95, 100),
    )

    def signal(index, _history):
        if index == 0:
            return TradePlan(Direction.BUY, Decimal("97"), Decimal("104"), Decimal("1"))
        return None

    result = run_backtest(
        candles,
        signal,
        BacktestConfig(tick_size=Decimal("1"), tick_value=Decimal("1")),
    )
    assert result.trades[0].exit_reason == "STOP_LOSS"
