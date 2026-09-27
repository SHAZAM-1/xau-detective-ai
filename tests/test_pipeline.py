from datetime import UTC, datetime
from decimal import Decimal

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
