# XAU Detective AI — Validation Plan

## Required sequence

1. Historical backtest
2. Out-of-sample holdout
3. Walk-forward validation
4. Monte Carlo analysis
5. Paper/demo trading
6. Controlled live execution validation

## Backtest realism

Include where data permits:
- historical spread,
- commission,
- slippage,
- execution delays,
- session effects,
- news periods,
- broker constraints.

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

It must demonstrate robustness outside the training period.
