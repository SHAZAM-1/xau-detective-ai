# XAU Detective AI — Strategy V1

## Status

**Draft — research specification, not a live trading strategy.**

## Objective

Develop a selective XAUUSD strategy whose primary decision is whether sufficient evidence exists to justify a trade.

## Evidence families

1. Higher-timeframe regime
2. Market structure
3. Price action
4. Liquidity/session context
5. Momentum
6. Volatility
7. Macro/news context
8. Execution conditions
9. Risk/reward feasibility

## Scenario model

### Bullish
Requires a defined bullish thesis, supporting evidence, invalidation, and feasible targets.

### Bearish
Requires a defined bearish thesis, supporting evidence, invalidation, and feasible targets.

### No Trade
Used when:
- evidence conflicts,
- data quality is inadequate,
- risk constraints cannot be satisfied,
- execution quality is poor,
- expected reward is inadequate,
- major event risk is unresolved,
- or no validated setup exists.

## Signal discipline

Signals must use information available at the decision timestamp.

Closed-candle confirmation is preferred where possible.

No repainting or future-data references are permitted.

## Setup score

A 0–100 setup-quality score may be introduced after feature validation.

It is **not** a probability of winning.

Weights must be validated using historical data rather than chosen solely by intuition.

## Initial research questions

- Which timeframe hierarchy is robust?
- Which evidence families add independent predictive value?
- Which features are redundant?
- Which market regimes support the strategy?
- How does spread/volatility affect expectancy?
- What is the smallest account size that can execute the strategy under its risk limits?
