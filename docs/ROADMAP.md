# XAU Detective AI — Roadmap

## Phase 0 — Foundation
- [x] Repository structure
- [x] Architecture specification
- [x] Risk specification
- [x] Strategy specification
- [x] Validation plan
- [x] Testing conventions

## V1 — Deterministic Research Engine
- [x] MT5 data adapter
- [x] Broker specification adapter
- [x] OHLCV/tick normalization
- [x] Data-quality checks
- [x] Regime engine
- [x] Volatility engine
- [x] Session engine
- [x] Structure engine
- [x] Scenario engine
- [x] Deterministic risk engine
- [x] Decision report
- [x] Audit logging
- [x] Historical backtest

## V1.5 — Demo / Validation
- [x] Explicit RESEARCH / DEMO / LIVE environment model
- [x] MT5 demo account capability discovery
- [x] Demo paper/order-execution boundary
- [x] Out-of-sample evaluation
- [x] Walk-forward testing
- [x] Monte Carlo analysis
- [x] Paper trading
- [x] Execution-quality measurements
- [x] Broker-aware execution simulator

## V2 — Statistical Scoring
- [x] Feature redundancy analysis
- [x] Phase 1 leakage-safe calibrated baseline scoring
- [ ] Regularized statistical model
- [ ] Held-out probability calibration
- [ ] Calibration drift monitoring
- [ ] Regime-conditioned historical edge
- [ ] News/calendar integration

## V3 — Advanced Evidence
- [ ] Cross-market context expansion
- [ ] Carefully validated ML refinement
- [ ] Anomaly detection
- [ ] Additional data sources only when justified by measurable incremental value

## Engineering Guardian / Self-Repair
- [x] Adaptive runtime guard
- [x] Project Guardian diagnosis
- [x] Guarded repair planning
- [x] Repair validation coordinator
- [x] Policy-bounded controlled repair executor
- [ ] Atomic multi-change repair / rollback protection
- [ ] Single-source project capability/status contract

## Live deployment gate

No autonomous live execution until the full validation pipeline and explicit risk controls have passed review. Live remains locked even when an MT5 live account is connected.

The Guardian and repair system may improve engineering quality, tests, validation, observability, documentation, and infrastructure within approved safe domains. It must never modify strategy, risk policy, SL/TP model, NO_TRADE policy, live-execution lock, or this roadmap autonomously.
