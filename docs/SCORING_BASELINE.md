# Statistical Scoring — Phase 1 Baseline

## Purpose

The scoring layer converts historical directional evidence into a conservative setup-quality score.

It is **not** a win-probability predictor and it cannot override a hard risk, data-quality, execution, or evidence-conflict veto.

## Phase 1 model

The baseline groups historical observations by:

- timeframe
- detected pattern
- pattern direction
- forward horizon

For each bucket it calculates:

- observation count
- directional wins
- raw directional rate
- smoothed directional rate
- directional expectancy

The smoothed rate uses a training-only global prior so tiny samples do not produce extreme scores.

## Safety gates

- Training rows are the only rows used to fit the baseline.
- Test rows are scored after fitting and cannot change the fitted statistics.
- Unseen contexts receive a neutral score.
- Contexts below the minimum sample size receive a neutral score.
- A score from 0–100 describes setup quality only.
- A score of 100 does not mean 100% win probability.
- The final evidence/risk pipeline remains the authority for NO_TRADE decisions.

## Why this is only Phase 1

The baseline is intentionally simple and auditable. Before using a more complex model we need:

1. feature redundancy analysis;
2. independent context features beyond candlestick identity;
3. net-R outcome labels including execution friction;
4. chronological train/validation/test evaluation;
5. walk-forward stability;
6. probability calibration on held-out data;
7. calibration-drift monitoring.

Only after those checks should a regularized ML model or gradient-boosted model be considered.
