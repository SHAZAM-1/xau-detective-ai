# Tests

Testing is part of the trading system, not an afterthought.

Planned test layers:

1. Unit tests — deterministic calculations.
2. Property tests — risk and sizing invariants.
3. Data-quality tests — malformed/missing/stale data.
4. Backtest regression tests — strategy output stability.
5. Anti-lookahead tests — timestamp integrity.
6. Broker-spec tests — lot/tick/margin calculations.
7. Decision-engine tests — veto precedence.

A risk-engine test must prove that an infeasible minimum lot produces NO TRADE rather than silently increasing risk.
