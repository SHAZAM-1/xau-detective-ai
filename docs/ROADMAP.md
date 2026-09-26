# XAU Detective AI — Roadmap

## Phase 0 — Foundation
- Repository structure
- Architecture specification
- Risk specification
- Strategy specification
- Validation plan
- Testing conventions

## V1 — Deterministic Research Engine
- MT5 data adapter
- Broker specification adapter
- OHLCV/tick normalization
- Data-quality checks
- Regime engine
- Volatility engine
- Session engine
- Structure engine
- Scenario engine
- Deterministic risk engine
- Decision report
- Audit logging
- Historical backtest

## V1.5 — Demo / Validation
- Explicit RESEARCH / DEMO / LIVE environment model
- MT5 demo account capability discovery
- Demo paper/order-execution boundary
- Out-of-sample evaluation
- Walk-forward testing
- Monte Carlo analysis
- Paper trading
- Execution-quality measurements
- Broker-aware execution simulator

## V2 — Statistical Scoring
- Feature redundancy analysis
- Baseline statistical model
- Calibrated setup scoring
- Regime-conditioned historical edge
- News/calendar integration

## V3 — Advanced Evidence
- Cross-market context
- Carefully validated ML refinement
- Anomaly detection
- Additional data sources only when justified by measurable incremental value

## Live deployment gate

No autonomous live execution until the full validation pipeline and explicit risk controls have passed review. Live remains locked in V1/V1.5 even when an MT5 live account is connected.
