# XAU Detective AI — Validation Plan

## Required sequence

1. Historical backtest
2. Out-of-sample holdout
3. Walk-forward validation
4. Monte Carlo analysis
5. Paper/demo trading
6. Controlled live execution validation

Historical OOS validation must use the existing `run_backtest()` engine and produce a `BacktestResult`. Monte Carlo consumes only the closed result; it is not a signal generator or strategy-tuning engine.

## Backtest realism

Include where data permits:
- historical spread,
- commission,
- slippage,
- execution delays,
- session effects,
- news periods,
- broker constraints.

When broker symbol specifications are available, backtests should supply the shared broker-constraint contract so volume and directional stop/target distance rules match the execution boundary. A backtest without broker metadata is generic research and must not be presented as proof that an order is executable on a specific broker.

## Bias controls

### Look-ahead bias
Features may only use information available at the decision timestamp.

### Repainting
Signal logic must be reproducible from closed historical data.

### Data leakage
Macro/news data must respect publication timestamps and point-in-time availability.

### Overfitting
Track:
- number of tunable parameters,
- number of independent trades,
- stability across periods,
- stability across market regimes.

### Temporal boundary integrity
Chronological and walk-forward folds must start and end on source-candle boundaries when multiple observations belong to the same source candle. Labels whose forward horizon reaches into the test window must be purged from training.

## Required metrics

- Expectancy
- Profit factor
- Maximum drawdown
- Average R
- Win rate
- Loss streaks
- Exposure
- Risk of ruin
- Stability by regime
- Out-of-sample performance

Win rate alone is insufficient.

## Acceptance rule

No strategy component becomes a live dependency merely because it improves in-sample profit.

It must demonstrate robustness outside the training period and remain compatible with the execution/risk gates.
