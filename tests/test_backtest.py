from datetime import UTC, datetime, timedelta
from decimal import Decimal

from xau_detective.backtest import BacktestConfig, TradePlan, run_backtest
from xau_detective.market import Candle
from xau_detective.models import Direction


def candle(i, open_, high, low, close):
    return Candle(
        datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=i),
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
            return TradePlan(Direction.BUY, Decimal(99), Decimal(104), Decimal(1))
        return None

    result = run_backtest(
        candles,
        signal,
        BacktestConfig(
            tick_size=Decimal(1),
            tick_value=Decimal(1),
            spread=Decimal(1),
            slippage=Decimal("0.5"),
            commission_per_lot_per_side=Decimal("0.25"),
        ),
    )

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_index == 1
    assert trade.exit_reason == "TAKE_PROFIT"
    assert trade.entry_price == Decimal(101)
    assert trade.exit_price == Decimal(103)
    assert trade.gross_pnl == Decimal(2)
    assert trade.commission == Decimal("0.5")
    assert trade.net_pnl == Decimal("1.5")


def test_stop_wins_tie_against_target_when_both_touch():
    candles = (
        candle(0, 100, 101, 99, 100),
        candle(1, 100, 105, 95, 100),
    )

    def signal(index, _history):
        if index == 0:
            return TradePlan(Direction.BUY, Decimal(97), Decimal(104), Decimal(1))
        return None

    result = run_backtest(
        candles,
        signal,
        BacktestConfig(tick_size=Decimal(1), tick_value=Decimal(1)),
    )
    assert result.trades[0].exit_reason == "STOP_LOSS"


def test_validation_metrics_calculate_supported_summary():
    from xau_detective.validation_metrics import calculate_backtest_metrics

    candles = (
        candle(0, 100, 101, 99, 100),
        candle(1, 100, 104, 100, 103),
        candle(2, 103, 106, 102, 105),
        candle(3, 105, 106, 101, 102),
        candle(4, 102, 103, 100, 101),
    )

    def signal(index, _history):
        if index == 0:
            return TradePlan(Direction.BUY, Decimal(99), Decimal(104), Decimal(1))
        if index == 2:
            return TradePlan(Direction.BUY, Decimal(104), Decimal(110), Decimal(1))
        return None

    result = run_backtest(
        candles,
        signal,
        BacktestConfig(tick_size=Decimal(1), tick_value=Decimal(1)),
    )
    metrics = calculate_backtest_metrics(result)

    assert metrics.trade_count == 2
    assert metrics.net_pnl == Decimal(3)
    assert metrics.expectancy == Decimal("1.5")
    assert metrics.profit_factor == Decimal(4)
    assert metrics.max_drawdown == Decimal(1)
    assert metrics.win_rate == Decimal("0.5")
    assert metrics.max_loss_streak == 1
    assert metrics.average_r == Decimal("1.5")
    assert metrics.exposure_bars == 2


def test_validation_metrics_handle_empty_results_without_inference():
    from xau_detective.backtest import BacktestResult
    from xau_detective.validation_metrics import calculate_backtest_metrics

    metrics = calculate_backtest_metrics(
        BacktestResult((), Decimal(0), 0, 0, 0, Decimal(0))
    )

    assert metrics.trade_count == 0
    assert metrics.expectancy == Decimal(0)
    assert metrics.profit_factor is None
    assert metrics.win_rate == Decimal(0)
    assert metrics.max_loss_streak == 0
    assert metrics.average_r is None
    assert metrics.exposure_bars == 0


def test_invalid_buy_geometry_is_rejected_before_simulation():
    candles = (
        candle(0, 100, 101, 99, 100),
        candle(1, 100, 104, 99, 102),
    )

    def signal(index, _history):
        if index == 0:
            return TradePlan(Direction.BUY, Decimal("101"), Decimal("110"), Decimal(1))
        return None

    result = run_backtest(
        candles,
        signal,
        BacktestConfig(tick_size=Decimal(1), tick_value=Decimal(1)),
    )
    assert result.trades == ()


def test_invalid_sell_geometry_is_rejected_before_simulation():
    candles = (
        candle(0, 100, 101, 99, 100),
        candle(1, 100, 104, 99, 102),
    )

    def signal(index, _history):
        if index == 0:
            return TradePlan(Direction.SELL, Decimal("90"), Decimal("95"), Decimal(1))
        return None

    result = run_backtest(
        candles,
        signal,
        BacktestConfig(tick_size=Decimal(1), tick_value=Decimal(1)),
    )
    assert result.trades == ()


def test_zero_risk_geometry_is_rejected_before_trade_recording():
    candles = (
        candle(0, 100, 101, 99, 100),
        candle(1, 100, 100, 100, 100),
    )

    def signal(index, _history):
        if index == 0:
            return TradePlan(Direction.BUY, Decimal("99"), Decimal("101"), Decimal(1))
        return None

    result = run_backtest(
        candles,
        signal,
        BacktestConfig(tick_size=Decimal(1), tick_value=Decimal(1)),
    )
    assert result.trades == ()
