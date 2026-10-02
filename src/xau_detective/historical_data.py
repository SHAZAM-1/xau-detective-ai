"""Timestamp-safe historical OHLCV dataset loading for research.

This module only loads and validates user-supplied historical data. It never
downloads, fabricates, interpolates, or forward-fills market prices.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .data_quality import DataQuality, validate_candles
from .market import Candle
from .timeframes import Timeframe, expected_interval


_REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close")
_VOLUME_COLUMN = "volume"


@dataclass(frozen=True)
class HistoricalDataset:
    symbol: str
    timeframe: Timeframe
    source: str
    candles: tuple[Candle, ...]
    quality: DataQuality


def _parse_timestamp(value: str, *, line_number: int) -> datetime:
    text = value.strip()
    if not text:
        raise ValueError(f"line {line_number}: timestamp is required")
    try:
        timestamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"line {line_number}: invalid ISO-8601 timestamp") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"line {line_number}: timestamp must include timezone")
    return timestamp.astimezone(timezone.utc)


def _parse_decimal(value: str, *, field: str, line_number: int) -> Decimal:
    text = value.strip()
    if not text:
        raise ValueError(f"line {line_number}: {field} is required")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"line {line_number}: invalid {field}") from exc


def load_historical_csv(
    path: str | Path,
    *,
    symbol: str,
    timeframe: Timeframe,
    source: str,
    strict_interval: bool = False,
) -> HistoricalDataset:
    """Load a normalized OHLCV CSV without inventing missing market data.

    Required columns are timestamp, open, high, low, close. Volume is optional
    and defaults to zero when the source does not provide it. Timestamps must
    be timezone-aware ISO-8601 values and are normalized to UTC. Rows must
    already be chronological; the loader never sorts them, because silently
    reordering a source can hide upstream data corruption.
    """

    if not symbol.strip():
        raise ValueError("symbol must not be empty")
    if not source.strip():
        raise ValueError("source must not be empty")

    candles: list[Candle] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = tuple(reader.fieldnames or ())
        timestamp_column = (
            "timestamp" if "timestamp" in columns
            else "datetime" if "datetime" in columns
            else None
        )
        missing = [
            column for column in _REQUIRED_COLUMNS
            if column != "timestamp" and column not in columns
        ]
        if timestamp_column is None:
            missing.insert(0, "timestamp")
        if missing:
            raise ValueError(f"missing required columns: {', '.join(missing)}")

        for line_number, row in enumerate(reader, start=2):
            if row.get(None):
                raise ValueError(f"line {line_number}: unexpected extra CSV fields")
            timestamp = _parse_timestamp(row[timestamp_column], line_number=line_number)
            candles.append(
                Candle(
                    timestamp=timestamp,
                    open=_parse_decimal(row["open"], field="open", line_number=line_number),
                    high=_parse_decimal(row["high"], field="high", line_number=line_number),
                    low=_parse_decimal(row["low"], field="low", line_number=line_number),
                    close=_parse_decimal(row["close"], field="close", line_number=line_number),
                    volume=(
                        _parse_decimal(row[_VOLUME_COLUMN], field="volume", line_number=line_number)
                        if _VOLUME_COLUMN in row and row[_VOLUME_COLUMN] is not None and row[_VOLUME_COLUMN].strip()
                        else Decimal(0)
                    ),
                )
            )

    normalized = tuple(candles)
    quality = validate_candles(
        normalized,
        expected_interval(timeframe) if strict_interval else None,
    )
    return HistoricalDataset(symbol, timeframe, source, normalized, quality)
