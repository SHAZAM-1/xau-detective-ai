# XAU Detective AI — Scoring Specification

## Goal

Create a setup-quality score only after establishing that the underlying evidence features have measurable value.

## Required separation

Do not collapse these into one number:

- Setup Quality
- Historical Edge
- Data Quality
- Execution Quality
- Uncertainty

## Anti-double-counting

Related features must be investigated for redundancy.

Examples:
- BOS and CHoCH
- Trend indicators measuring the same regime
- Multiple volatility measures derived from the same range

Correlation and feature-importance analysis must precede final weighting.

## Candidate modelling path

1. Establish deterministic baseline.
2. Generate timestamp-safe historical examples.
3. Define outcome labels using net R-multiple.
4. Use time-ordered train/validation/test splits.
5. Train a regularized baseline.
6. Compare with gradient-boosted trees.
7. Calibrate probabilities only on held-out data.
8. Monitor calibration drift.

## Score interpretation

A 100/100 score means all defined score conditions are satisfied.

It must never be displayed as:
- 100% win probability,
- guaranteed profit,
- guaranteed accuracy.

## Decision policy

A high score cannot override a hard risk or execution veto.
