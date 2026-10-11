# XAU Detective AI

Evidence-driven XAUUSD trading research and decision-support system.

> **Status:** Deterministic research engine plus an opt-in MT5 Demo runtime. Automated execution is disabled by default and Live execution remains locked. A green CI suite does not replace read-only validation against the user's actual MT5 Demo terminal; broker session/DST behavior and end-to-end broker integration remain evidence-gated.

## Mission

XAU Detective AI investigates the Gold market across multiple timeframes and evidence families, generates competing market scenarios, applies deterministic risk/execution vetoes, and returns either a fully specified trade proposal or **NO TRADE**.

It is designed for robustness and auditability, not guaranteed returns.

## Core principles

- Evidence before action.
- Multi-timeframe context.
- Independent evidence families rather than one-indicator decisions.
- Competing Bullish / Bearish / No-Trade scenarios.
- Capital-aware position sizing from actual broker specifications.
- Hard risk and execution vetoes.
- No Martingale, Grid, or averaging down.
- Explicit RESEARCH / DEMO / LIVE environment model.
- Demo-account connectivity can be enabled separately from order execution.
- No autonomous live execution in V1.
- Backtest, out-of-sample, walk-forward and paper validation before deployment.
- Every decision and every closed trade should be auditable.
- Closed trades become learning data; a single trade never changes live strategy parameters.

## Current architecture

```
MT5 / Market Data
      ↓
Closed-Candle Filter
      ↓
Data Quality Gate
      ↓
Feature Engine
  ├─ Trend / EMA / Slope
  ├─ Volatility / ATR / Range
  ├─ Momentum / Returns
  └─ Structure / Liquidity hypotheses
      ↓
Market Regime
      ↓
Scenario Engine
      ↓
Evidence Ledger
  ├─ Supporting evidence
  ├─ Contradictions
  └─ Warnings
      ↓
Evidence Gate
      ↓
Risk / Execution Gate
      ↓
Decision Report
      ↓
Trade Memory (JSONL)
      ↓
Closed-Trade Outcome + MAE/MFE
      ↓
Learning / Postmortem Dataset
      ↓
Offline validation → approved model/config only
```

## Learning philosophy

The bot is built to **learn from every completed trade**, including failures, without contaminating the live decision with hindsight.

For each trade it records:

- decision-time evidence and warnings
- regime
- setup score
- entry / stop / target
- realized P&L and P&L in R
- exit reason
- MAE / MFE when available
- postmortem lesson tags

A loss can therefore become a research observation such as:

- contradictory-evidence review
- high-volatility execution review
- adverse-excursion review
- missed-exit/target review

The important safety rule is: **the bot does not blindly rewrite its strategy after one loss or one win**. Learning happens from a closed historical sample, then a new rule/model must survive out-of-sample and walk-forward validation before it can influence live configuration.

## MT5 Demo runtime and operational safety

The runtime wraps the existing trading service and evaluates only newly closed M5 candles after loading closed D1/H4/H1/M15/M5 data. Per-timeframe staleness limits, candle-quality checks, market-tick freshness checks, broker constraints, the execution gate, and durable JSONL audit/trade journals are applied before any explicitly enabled Demo order can be sent.

- Default invocation is non-executing; `--execute-demo` is an explicit Demo-only opt-in, not permission for Live execution.
- An uncertain order-submission result remains pending and must be reconciled; the same idempotency key is not blindly retried.
- Session/account switches latch an execution block until explicit acknowledgement of the verified Demo identity.
- The market-hours evidence collector is read-only and refuses to infer Demo mode when the MT5 Demo constant is unavailable. Thin historical samples are marked incomplete instead of being treated as sufficient evidence.
- Do not consider the runtime production-ready solely because tests pass. Actual MT5 Demo integration and broker-session/DST evidence must be reviewed separately.

Analysis-only one-shot example (does not opt into order execution):

```powershell
python -m xau_detective.mt5_demo_runtime --once
```

Read-only broker-session evidence collection:

```powershell
python -m xau_detective.market_hours_evidence --symbol XAUUSD
```

Both commands require an available MT5 terminal and an environment where the project and optional MetaTrader5 dependency are installed.

## Repository map

- [Project Charter](docs/PROJECT_CHARTER.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Strategy V1](docs/STRATEGY_V1.md)
- [Risk Model](docs/RISK_MODEL.md)
- [Scoring Specification](docs/SCORING_SPEC.md)
- [Statistical Scoring Baseline](docs/SCORING_BASELINE.md)
- [Feature Redundancy Analysis](docs/FEATURE_REDUNDANCY.md)
- [Validation Plan](docs/VALIDATION_PLAN.md)
- [Roadmap](docs/ROADMAP.md)
- [Example Configuration](config/defaults.example.yaml)
- [Testing Notes](tests/README.md)

## Initial platform

The research direction is **MetaTrader 5 + Python**.

MT5 is intended for market/execution connectivity and broker specifications. Python is intended for research, feature engineering, validation, backtesting, trade-memory analysis, and later statistical/ML components.

## Important risk statement

This repository is a research and engineering project. It does not promise profitable trades or 100% accuracy.

A setup score is not a win probability.

If the requested position cannot be executed while respecting the configured risk limit and broker constraints, the correct output is **NO TRADE**.

## Development status

### Implemented

- [x] Repository architecture and specifications
- [x] Deterministic risk engine
- [x] Broker specification validation
- [x] MT5 adapter boundary
- [x] MT5 candle source
- [x] Closed-candle multi-timeframe ingestion
- [x] Data-quality gate
- [x] Deterministic feature engine
- [x] Market-regime classifier
- [x] Evidence ledger and conflict gate
- [x] Append-only closed-trade memory
- [x] Learning statistics and postmortem lesson extraction
- [x] Event-driven backtest engine with spread/commission/slippage modeling
- [x] Session context features
- [x] Liquidity reference features
- [x] GitHub Actions project-health CI
- [x] Project-wide health check with commit impact reporting
- [x] Core-module import smoke test
- [x] Deterministic paper-trading engine with broker constraints, execution delay, spread, slippage, commission, and rejection audit
- [x] Friction-aware Net-R outcome labeling
- [x] Training-only feature redundancy analysis / anti-double-counting control

### Implemented environment boundary

- [x] Explicit RESEARCH / DEMO / LIVE environment model
- [x] MT5 account capability mapping without inferring demo/live from balance
- [x] Demo execution requires explicit enablement and healthy account/symbol gates
- [x] Live execution remains locked by the V1 policy

### Research / modeling status

- [x] Historical feature/outcome dataset builder
- [x] Candlestick pattern research lab (forward returns, directional win rate, MFE/MAE, expectancy)
- [x] Pattern + regime/session/volatility stratified study
- [x] Chronological out-of-sample and walk-forward validation
- [x] Monte Carlo drawdown / ruin stress testing
- [x] Broker-aware deterministic paper-trading / execution simulator
- [x] Phase 1 leakage-safe calibrated baseline scoring
- [x] Training-only feature redundancy analysis / anti-double-counting control
- [ ] Regularized statistical model
- [ ] Held-out probability calibration
- [ ] Calibration drift monitoring
- [ ] Live execution only after validation and risk review

See [Roadmap](docs/ROADMAP.md) for the planned sequence.
