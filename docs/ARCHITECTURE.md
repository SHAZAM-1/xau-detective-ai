# XAU Detective AI — Architecture

## High-level pipeline

```
Market/Data Ingestion
        ↓
Environment & Capability Gate
        ↓
Data Quality Checks
        ↓
Feature Engineering
        ↓
Market Regime
        ↓
Scenario Generation
        ↓
Evidence & Conflict Analysis
        ↓
Risk Gate
        ↓
Decision Report
        ↓
Immutable Decision Log
```

## Research validation pipeline

Historical research is separate from production execution:

```
Historical OHLCV
    ↓
Data-quality gate
    ↓
Pattern / feature observations
    ↓
Chronological OOS / walk-forward boundary
    ↓
Explicit point-in-time SignalFunction + BacktestConfig
    ↓
Existing run_backtest() / BacktestResult
    ↓
Optional closed-trade Monte Carlo
```

The historical integration does not invent a trading strategy. A caller must explicitly provide the signal function and backtest configuration. Signals receive only the current candle and prior candles, and execution is hard-gated until the OOS source-candle boundary. Future outcome labels are never supplied to the signal callback.

The OOS backtest reuses the existing research backtest engine and its `BacktestResult`; there is no second historical execution engine. Monte Carlo consumes only the closed `BacktestResult` and cannot generate signals or modify strategy, risk, or execution policy.

## Broker constraint contract

Broker symbol constraints are represented by the shared `BrokerSymbolConstraints` contract. It includes point size, minimum/maximum/step volume, and broker stop/freeze levels.

The same pure validation function is used by the live/demo `BrokerExecutionGate` and the research backtest when broker constraints are supplied. This prevents research from accepting trade geometry that the execution boundary would reject.

A broker-aware backtest rejects:
- invalid broker symbol specifications
- volume below minimum or above maximum
- volume not aligned to the broker step
- directional stop/target distances below the broker minimum

The backtest remains usable without broker metadata for generic research, but results produced without broker constraints must not be represented as broker-executable results.

## Environment and capability boundary

The system has three explicit environments:

- **RESEARCH** — historical/backtest analysis only; no order APIs.
- **DEMO** — MT5 demo connectivity is supported. Analysis can use live broker prices/specifications, and order execution is only permitted after an explicit execution opt-in plus all connection, trading, symbol, risk, and margin gates. The detected MT5 account environment is authoritative for this boundary.
- **LIVE** — connected-live-account support is architecturally represented, but autonomous live execution remains locked in V1.

The environment is never inferred from account balance, equity, or account size. MT5 account state is the source of truth for the detected environment. Callers may supply an explicit environment in controlled research/test contexts, but an explicit caller value must not override a conflicting MT5 account state. Policy gates decide what actions are permitted for the detected environment.

The capability layer records:
- connection state and health
- whether account trading is allowed
- whether execution was explicitly enabled
- symbol availability
- symbol identity
- broker/server identity when available

This separates **connected to a demo account** from **authorized to send orders**.

## Major modules

### 1. Ingestion
- MT5 price/tick data
- Broker symbol specifications
- Economic calendar
- Optional macro/cross-market feeds

### 2. Data quality
- Missing bars
- Stale timestamps
- Spread anomalies
- Feed gaps
- Invalid broker specifications
- Source latency

### 3. Features
- Multi-timeframe price action
- Trend/regime
- Market structure
- Volatility
- Momentum
- Sessions
- Liquidity concepts
- Macro context

Experimental concepts such as BOS, CHoCH, FVG and liquidity sweeps are hypotheses until validated.

### 4. Scenario engine

Generate independently:
- Bullish scenario
- Bearish scenario
- No-trade scenario

Every directional scenario must include evidence, contradictions, invalidation and targets.

### 5. Risk engine

The risk engine is deterministic and has veto authority.

It must calculate position size from:
- Account balance
- Risk percentage
- Entry
- Stop distance
- Tick size
- Tick value
- Lot step
- Minimum lot
- Margin requirements
- Execution costs

### 6. Decision layer

The final decision can be:
- TRADE
- NO TRADE
- DATA ERROR

A strong market setup that violates account or execution constraints remains NO TRADE.

## Timeframe hypothesis

Initial research hierarchy:
- D1: macro context
- H4: regime
- H1: structure
- M15: setup
- M5: entry refinement

This hierarchy is a testable hypothesis, not a permanent rule.

## AI boundary

AI/ML may later assist with feature scoring and narrative synthesis.

AI/ML must not:
- change maximum risk,
- bypass vetoes,
- alter broker constraints,
- directly execute a trade in V1.
