from datetime import UTC, datetime
from decimal import Decimal

from xau_detective.demo_execution import TradeIntent, TradeSource
from xau_detective.models import Direction, RiskResult
from xau_detective.trade_journal import InMemoryTradeJournal, journal_entry_from_intent


def test_trade_journal_records_execution_fact():
    intent = TradeIntent(
        symbol="XAUUSD",
        direction=Direction.BUY,
        volume=Decimal("0.01"),
        entry=Decimal("4000.10"),
        stop_loss=Decimal("3995.10"),
        take_profit=Decimal("4010.10"),
        source=TradeSource.BOT_SUGGESTION,
        idempotency_key="journal-test-1",
        risk=RiskResult(True, Decimal("0.01"), Decimal("1"), Decimal("1"), "OK"),
    )
    entry = journal_entry_from_intent(
        intent=intent,
        status="SUBMITTED",
        reason="DEMO_ORDER_SUBMITTED",
        order_id="123",
        timestamp=datetime(2026, 9, 26, tzinfo=UTC),
    )
    journal = InMemoryTradeJournal()
    journal.append(entry)

    assert journal.entries() == (entry,)
    assert journal.entries()[0].order_id == "123"
