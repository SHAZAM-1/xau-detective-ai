from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from xau_detective.demo_execution import TradeIntent, TradeSource
from xau_detective.models import Direction, RiskResult
from xau_detective.trade_journal import InMemoryTradeJournal, TradeJournalEntry, journal_entry_from_intent


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



def test_jsonl_trade_journal_persists_and_reloads(tmp_path):
    from xau_detective.trade_journal import JsonlTradeJournal
    intent = TradeIntent(
        symbol="XAUUSD", direction=Direction.SELL, volume=Decimal("0.02"),
        entry=Decimal("4000"), stop_loss=Decimal("4010"), take_profit=Decimal("3980"),
        source=TradeSource.USER_DEFINED, idempotency_key="persist-1",
        risk=RiskResult(True, Decimal("0.01"), Decimal("2"), Decimal("1"), "OK"),
    )
    entry = journal_entry_from_intent(
        intent=intent, status="REJECTED", reason="TEST",
        timestamp=datetime(2026, 9, 26, 12, tzinfo=UTC),
    )
    path = tmp_path / "journal.jsonl"
    journal = JsonlTradeJournal(path)
    journal.append(entry)
    restored = JsonlTradeJournal(path)
    assert restored.entries() == (entry,)
    assert path.read_text(encoding="utf-8").count("\n") == 1


def test_jsonl_trade_journal_rejects_corrupt_records(tmp_path):
    from xau_detective.trade_journal import JsonlTradeJournal
    path = tmp_path / "journal.jsonl"
    path.write_text('{"broken":true}\\n', encoding="utf-8")
    with pytest.raises(ValueError, match="INVALID_TRADE_JOURNAL_RECORD:1"):
        JsonlTradeJournal(path)


def test_journal_returns_latest_entry_for_idempotency_key():
    journal = InMemoryTradeJournal()
    first = TradeJournalEntry(
        timestamp=datetime(2026, 9, 27, tzinfo=UTC),
        idempotency_key="k1",
        symbol="XAUUSD",
        direction="BUY",
        volume=Decimal("0.01"),
        entry=Decimal("4000"),
        stop_loss=Decimal("3990"),
        take_profit=Decimal("4020"),
        source="BOT_SUGGESTION",
        status="PENDING_SUBMISSION",
        reason="BROKER_SUBMISSION_PENDING",
    )
    second = TradeJournalEntry(
        **{**asdict(first), "status": "SUBMITTED", "reason": "DEMO_ORDER_SUBMITTED", "order_id": "123"}
    )
    journal.append(first)
    journal.append(second)
    assert journal.latest_for_idempotency_key("k1").status == "SUBMITTED"
    assert journal.latest_for_idempotency_key("missing") is None
