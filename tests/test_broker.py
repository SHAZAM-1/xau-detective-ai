from decimal import Decimal
from xau_detective.broker import validate_broker_spec
from xau_detective.models import BrokerSpec


def test_invalid_tick_spec_is_rejected():
    spec = BrokerSpec("XAUUSD", Decimal("100"), Decimal("0.01"), Decimal("100"), Decimal("0.01"), Decimal("0"), Decimal("1"), Decimal("0.01"))
    ok, errors = validate_broker_spec(spec)
    assert not ok
    assert "INVALID_TICK_SPEC" in errors
