from datetime import UTC, datetime, timedelta
from decimal import Decimal

from xau_detective.market import Candle
from xau_detective.models import AccountSnapshot, BrokerSpec, Direction
from xau_detective.pipeline import AnalysisConfig, analyze_market


def test_pipeline_rejects_bad_data_before_analysis():
    result = analyze_market(
        d1=(),
        h4=(),
        h1=(),
        m15=(),
        m5=(),
        account=AccountSnapshot(Decimal(20), Decimal(20), Decimal(20)),
        broker=BrokerSpec(
            symbol="XAUUSD",
            contract_size=Decimal(100),
            volume_min=Decimal("0.01"),
            volume_max=Decimal(100),
            volume_step=Decimal("0.01"),
            tick_size=Decimal("0.01"),
            tick_value=Decimal(1),
            point=Decimal("0.01"),
        ),
        now=datetime(2026, 9, 26, 14, 0, tzinfo=UTC),
    )
    assert result.decision.direction is Direction.NO_TRADE
    assert result.decision.reason == "DATA_QUALITY:D1:NO_CANDLES"


def test_pipeline_never_executes_an_order():
    assert not hasattr(analyze_market, "execute")


def test_analysis_config_keeps_score_weights_explicitly_provisional():
    config = AnalysisConfig()
    assert config.score_evidence_weight == 25
    assert config.score_reward_risk_weight == 15
    assert config.score_session_weight == 10


def test_pipeline_enforces_allowed_session_before_market_analysis():
    result = analyze_market(
        d1=(), h4=(), h1=(), m15=(), m5=(),
        account=AccountSnapshot(Decimal(20), Decimal(20), Decimal(20)),
        broker=BrokerSpec(
            symbol="XAUUSD", contract_size=Decimal(100), volume_min=Decimal("0.01"),
            volume_max=Decimal(100), volume_step=Decimal("0.01"), tick_size=Decimal("0.01"),
            tick_value=Decimal(1), point=Decimal("0.01"),
        ),
        now=datetime(2026, 9, 26, 4, 0, tzinfo=UTC),
    )
    assert result.decision.direction is Direction.NO_TRADE
    assert result.decision.reason == "SESSION_NOT_ALLOWED:ASIA"


def _pipeline_broker():
    return BrokerSpec(
        symbol="XAUUSD",
        contract_size=Decimal(100),
        volume_min=Decimal("0.01"),
        volume_max=Decimal(100),
        volume_step=Decimal("0.01"),
        tick_size=Decimal("0.01"),
        tick_value=Decimal(1),
        point=Decimal("0.01"),
    )


def _pipeline_candles(start, step, *, gap_after=None):
    candles = []
    timestamp = start
    for index in range(20):
        if gap_after is not None and index == gap_after:
            timestamp += step * 2
        price = Decimal(4000 + index)
        candles.append(
            Candle(
                timestamp=timestamp,
                open=price,
                high=price + Decimal("2"),
                low=price - Decimal("2"),
                close=price + Decimal("1"),
                volume=Decimal(100),
            )
        )
        timestamp += step
    return tuple(candles)


def test_pipeline_uses_broker_gap_policy_for_expected_rollovers():
    now = datetime(2026, 9, 26, 14, tzinfo=UTC)
    d1 = _pipeline_candles(datetime(2026, 9, 1, tzinfo=UTC), timedelta(days=1), gap_after=10)
    h4 = _pipeline_candles(datetime(2026, 9, 23, tzinfo=UTC), timedelta(hours=4))
    h1 = _pipeline_candles(datetime(2026, 9, 25, tzinfo=UTC), timedelta(hours=1))
    m15 = _pipeline_candles(datetime(2026, 9, 26, 0, tzinfo=UTC), timedelta(minutes=15))
    m5 = _pipeline_candles(datetime(2026, 9, 26, 8, tzinfo=UTC), timedelta(minutes=5))
    account = AccountSnapshot(Decimal(20000), Decimal(20000), Decimal(20000))
    broker = _pipeline_broker()

    generic = analyze_market(
        d1=d1, h4=h4, h1=h1, m15=m15, m5=m5,
        account=account, broker=broker, now=now,
    )
    assert generic.decision.reason == "DATA_QUALITY:D1:DATA_GAP"

    broker_aware = analyze_market(
        d1=d1, h4=h4, h1=h1, m15=m15, m5=m5,
        account=account, broker=broker, now=now,
        gap_is_expected=lambda previous, current: True,
    )
    assert not broker_aware.decision.reason.startswith("DATA_QUALITY:")
