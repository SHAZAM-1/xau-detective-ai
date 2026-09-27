from datetime import datetime, timedelta, timezone
from decimal import Decimal

from xau_detective.market import Candle
from xau_detective.models import BrokerSpec, Direction
from xau_detective.net_r_outcome import NetROutcomeConfig, label_trade_outcome

def candles():
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return tuple(Candle(t + timedelta(minutes=i), Decimal(str(p)), Decimal(str(h)), Decimal(str(l)), Decimal(str(p)), Decimal(1))
                 for i, (p, h, l) in enumerate([(100,101,99),(100,102,99),(100,103,100)]))

def broker():
    return BrokerSpec("XAUUSD", Decimal("100"), Decimal("0.01"), Decimal("10"), Decimal("0.01"), Decimal("0.01"), Decimal("1"), Decimal("0.01"))

def test_net_r_includes_commission_and_target():
    result = label_trade_outcome(candles(), signal_index=0, direction=Direction.BUY, stop_loss=99, take_profit=102, volume=1, broker=broker(), config=NetROutcomeConfig(commission_per_lot_per_side=Decimal("0.5")))
    assert result is not None
    assert result.exit_reason == "TAKE_PROFIT"
    assert result.net_r < result.gross_r

def test_stop_first_when_both_levels_touch():
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    cs = (Candle(t,Decimal("100"),Decimal("100"),Decimal("100"),Decimal("100"),Decimal("1")), Candle(t+timedelta(minutes=1),Decimal("100"),Decimal("103"),Decimal("98"),Decimal("100"),Decimal("1")))
    result = label_trade_outcome(cs, signal_index=0, direction=Direction.BUY, stop_loss=99, take_profit=102, volume=1, broker=broker())
    assert result is not None and result.exit_reason == "STOP_LOSS"
