# XAU Detective AI

Evidence-driven XAUUSD trading research and decision-support system.

> **Status:** Phase 0 — foundation and specification.

## Mission

XAU Detective AI investigates the Gold market across multiple timeframes and evidence families, generates competing market scenarios, applies deterministic risk/execution vetoes, and returns either a fully specified trade proposal or **NO TRADE**.

It is designed for robustness and auditability, not guaranteed returns.

## Core principles

- Evidence before action.
- Multi-timeframe context.
- Competing Bullish / Bearish / No-Trade scenarios.
- Capital-aware position sizing.
- Hard risk and execution vetoes.
- No Martingale, Grid, or averaging down.
- No autonomous live execution in V1.
- Backtest and out-of-sample validation before deployment.
- Every decision should be auditable.

## Current architecture

```
Data Ingestion
    ↓
Data Quality
    ↓
Feature Engineering
    ↓
Market Regime
    ↓
Scenario Engine
    ↓
Evidence / Conflict Analysis
    ↓
Risk & Execution Gate
    ↓
Decision Report
    ↓
Audit Log
```

## Repository map

- [Project Charter](docs/PROJECT_CHARTER.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Strategy V1](docs/STRATEGY_V1.md)
- [Risk Model](docs/RISK_MODEL.md)
- [Scoring Specification](docs/SCORING_SPEC.md)
- [Validation Plan](docs/VALIDATION_PLAN.md)
- [Roadmap](docs/ROADMAP.md)
- [Example Configuration](config/defaults.example.yaml)
- [Testing Notes](tests/README.md)

## Initial platform

The research direction is **MetaTrader 5 + Python**.

MT5 is intended for market/execution connectivity and broker specifications. Python is intended for research, feature engineering, validation, backtesting, and later statistical/ML components.

## Important risk statement

This repository is a research and engineering project. It does not promise profitable trades or 100% accuracy.

A setup score is not a win probability.

If the requested position cannot be executed while respecting the configured risk limit and broker constraints, the correct output is **NO TRADE**.

## Development status

### Phase 0 — Foundation
- [x] Repository created
- [x] Architecture specification
- [x] Strategy V1 specification
- [x] Risk model specification
- [x] Scoring specification
- [x] Validation plan
- [x] Roadmap
- [ ] MT5 data adapter
- [ ] Deterministic risk engine
- [ ] Backtest engine
- [ ] Paper-trading pipeline

See [Roadmap](docs/ROADMAP.md) for the planned sequence.
