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

## MT5 Demo runtime boundary

The operational runtime is a thin loop around the existing service, not a second strategy engine. It:

- obtains closed D1/H4/H1/M15/M5 candles and rejects malformed, missing, duplicate, out-of-order, or stale snapshots;
- checks that the terminal tick clock is timezone-aware, no more than two minutes stale, and not more than 30 seconds in the future before using wall-clock UTC for candle closure;
- evaluates at most once per newly closed M5 candle and derives a deterministic idempotency key from symbol, timeframe, and candle timestamp;
- persists the audit stream and trade journal as JSONL under the configured runtime log directory; corrupt persistence data must stop initialization rather than silently falling back to memory;
- keeps uncertain broker submissions pending for reconciliation instead of blindly retrying the same key;
- latches an execution block after account/server/environment changes until an explicit acknowledgement of the exact Demo identity.

The default runtime mode does not send orders. Demo execution requires the explicit `--execute-demo` option and still passes the existing Demo/account, symbol, broker, risk, margin, and execution gates. Live execution remains locked.

The market-hours evidence collector uses read-only candle-history APIs and never calls order submission/modification/closure APIs. Each window/timeframe has a minimum evidence sample threshold; insufficient history is recorded in the output and makes the report incomplete. Its output must be reviewed against the actual broker terminal before market-gap/DST policy is treated as verified.

CI proves deterministic test and static-check behavior only. It does not prove broker availability, live market sessions, or real MT5 order/reconciliation behavior. Until the read-only Demo integration and broker-session evidence are reviewed, those external checks remain unverified.

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
