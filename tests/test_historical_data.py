from datetime import UTC, datetime
from pathlib import Path

import pytest

from xau_detective.historical_data import load_historical_csv
from xau_detective.timeframes import Timeframe


def test_load_historical_csv_normalizes_timezone_and_volume(tmp_path: Path):
    path = tmp_path / "xau.csv"
    path.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2026-01-01T00:00:00+01:00,4300,4310,4290,4305,12\n"
        "2026-01-01T01:00:00+01:00,4305,4320,4300,4315,15\n",
        encoding="utf-8",
    )

    dataset = load_historical_csv(
        path,
        symbol="XAUUSD",
        timeframe=Timeframe.H1,
        source="test-fixture",
        strict_interval=True,
    )

    assert dataset.quality.usable
    assert dataset.candles[0].timestamp == datetime(2025, 12, 31, 23, tzinfo=UTC)
    assert dataset.candles[1].volume == 15


def test_load_historical_csv_requires_timezone(tmp_path: Path):
    path = tmp_path / "xau.csv"
    path.write_text(
        "timestamp,open,high,low,close\n"
        "2026-01-01T00:00:00,4300,4310,4290,4305\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="timestamp must include timezone"):
        load_historical_csv(
            path,
            symbol="XAUUSD",
            timeframe=Timeframe.H1,
            source="test-fixture",
        )


def test_load_historical_csv_reports_data_gaps(tmp_path: Path):
    path = tmp_path / "xau.csv"
    path.write_text(
        "timestamp,open,high,low,close\n"
        "2026-01-01T00:00:00Z,4300,4310,4290,4305\n"
        "2026-01-01T03:00:00Z,4305,4320,4300,4315\n",
        encoding="utf-8",
    )

    dataset = load_historical_csv(
        path,
        symbol="XAUUSD",
        timeframe=Timeframe.H1,
        source="test-fixture",
        strict_interval=True,
    )

    assert not dataset.quality.usable
    assert "DATA_GAP" in dataset.quality.reasons


def test_load_historical_csv_rejects_missing_columns(tmp_path: Path):
    path = tmp_path / "xau.csv"
    path.write_text(
        "timestamp,open,high,low\n"
        "2026-01-01T00:00:00Z,4300,4310,4290\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing required columns: close"):
        load_historical_csv(
            path,
            symbol="XAUUSD",
            timeframe=Timeframe.H1,
            source="test-fixture",
        )
