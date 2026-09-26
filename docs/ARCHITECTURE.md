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

## Environment and capability boundary

The system has three explicit environments:

- **RESEARCH** — historical/backtest analysis only; no order APIs.
- **DEMO** — MT5 demo connectivity is supported. Analysis can use live broker prices/specifications, and order execution is only permitted after an explicit execution opt-in plus all connection, trading, symbol, risk, and margin gates.
- **LIVE** — connected-live-account support is architecturally represented, but autonomous live execution remains locked in V1.

The environment is never inferred from account balance, equity, or account size. The caller must explicitly select the environment.

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
