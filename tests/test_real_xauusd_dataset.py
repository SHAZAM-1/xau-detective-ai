from pathlib import Path

from xau_detective.historical_data import load_historical_csv
from xau_detective.timeframes import Timeframe


DATASET = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "historical"
    / "XAUUSD_1h.csv"
)


def test_real_xauusd_snapshot_is_usable():
    dataset = load_historical_csv(
        DATASET,
        symbol="XAUUSD",
        timeframe=Timeframe.H1,
        source="getdata-finance-2026-10-02-snapshot",
        strict_interval=False,
    )

    assert dataset.quality.usable
    assert len(dataset.candles) == 3006
    assert dataset.candles[0].timestamp.isoformat() == "2026-03-26T03:00:00+00:00"
    assert dataset.candles[-1].timestamp.isoformat() == "2026-09-25T20:00:00+00:00"
