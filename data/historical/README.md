# XAUUSD historical research dataset

This directory contains a pinned 1-hour XAUUSD OHLCV research snapshot.

## Provenance

- Instrument: XAUUSD (Gold / US Dollar)
- Timeframe: 1 hour
- Timezone: UTC
- Snapshot source: getdata-finance XAUUSD 1H GitHub sample
- Source repository: https://github.com/getdata-finance/xauusd-1h-ohlcv-metals-historical-data
- Source file: XAUUSD_1h.csv
- Snapshot ref: main (captured 2026-10-02)
- Coverage in this snapshot: 2026-03-26 through 2026-09-25
- Rows including header: 3007

## Research-use rules

- This is a research snapshot, not a live market feed.
- The source contains normal market-session gaps (for example weekends and daily breaks), so validation of this dataset must use `strict_interval=False`.
- Do not interpolate, forward-fill, or reorder rows.
- Re-run data-quality validation before using the snapshot in any backtest or statistical study.
- Results from this sample must not be treated as proof of live trading performance.

The upstream project states that its 1H sample is an evaluation dataset and that its full archive covers a much longer historical period. The project should acquire a broader independently validated archive before final OOS/robustness conclusions.
