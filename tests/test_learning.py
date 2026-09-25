from decimal import Decimal



from xau_detective.learning import (
    JsonlTradeMemory,
    TradeOutcome,
    TradeRecord,
    extract_lessons,
    summarize_closed,
)
from xau_detective.models import Direction


def record(**kwargs):
    return TradeRecord(
        trade_id="T1",
        timestamp="2026-09-26T00:00:00Z",
        symbol="XAUUSD",
        direction=Direction.BUY,
        entry=Decimal(2500),
        stop_loss=Decimal(2490),
        take_profit=Decimal(2520),
        setup_score=82,
        evidence=("trend_up", "structure_breakout", "momentum_positive"),
        warnings=(),
        regime="TREND_UP",
        entry_reason="TRADE_ALLOWED",
        **kwargs,
    )


def test_closed_trade_is_stored_and_reloaded(tmp_path):
    memory = JsonlTradeMemory(tmp_path / "trades.jsonl")
    closed = record(contradictions=("momentum_opposes_direction",)).close(
        outcome=TradeOutcome.WIN,
        pnl=Decimal(2),
        pnl_r=Decimal(2),
        exit_reason="TAKE_PROFIT",
    )
    memory.append(closed)
    loaded = memory.read_all()
    assert loaded[0].outcome is TradeOutcome.WIN
    assert loaded[0].pnl_r == Decimal(2)
    assert loaded[0].contradictions == ("momentum_opposes_direction",)


def test_learning_stats_use_only_closed_trades():
    open_trade = record()
    win = record().close(
        outcome=TradeOutcome.WIN,
        pnl=Decimal(2),
        pnl_r=Decimal(2),
        exit_reason="TAKE_PROFIT",
    )
    loss = record().close(
        outcome=TradeOutcome.LOSS,
        pnl=Decimal(-1),
        pnl_r=Decimal(-1),
        exit_reason="STOP_LOSS",
    )
    stats = summarize_closed((open_trade, win, loss))
    assert stats.closed_trades == 2
    assert stats.win_rate == Decimal("0.5")
    assert stats.expectancy_r == Decimal("0.5")


def test_postmortem_detects_contradictory_evidence():
    closed = record(contradictions=("regime_trend_conflict",)).close(
        outcome=TradeOutcome.LOSS,
        pnl=Decimal(-1),
        pnl_r=Decimal(-1),
        exit_reason="STOP_LOSS",
    )
    lessons = extract_lessons(closed)
    assert "LOSS_REQUIRES_POSTMORTEM" in lessons.lessons
    assert "CONTRADICTORY_EVIDENCE_REVIEW" in lessons.lessons
