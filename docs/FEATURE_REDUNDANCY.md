# Feature Redundancy Analysis

## Purpose

The scoring engine should not count several correlated measurements as independent evidence. EMA fast, EMA slow, and trend slope can all encode the same underlying trend regime.

This module flags highly correlated feature pairs and groups them into deterministic redundancy clusters. It never deletes features and never creates a trade signal.

## Method
- Point-in-time feature series are aligned by timestamp and timeframe.
- Pearson correlation is computed only on the supplied window.
- Default absolute-correlation threshold is 0.85.
- Default minimum overlap is 30 observations.
- Positive and negative correlation both count as redundancy.
- Same-family pairs receive an explicit warning.
- Cross-family high correlation is flagged for review, not automatically rejected.
- Clusters are connected components of flagged pairs.
- Representatives are deterministic, with optional explicit feature priority.

## Leakage control

Call the analyzer with training-window observations only. Freeze the resulting redundancy structure while scoring OOS/test data. This prevents future correlation structure from influencing feature selection.

## Interpretation

A flagged pair means the measurements were highly correlated in the training sample. It does not prove that the features are identical, causally redundant, or that one must be deleted. Any reduction should be validated on held-out data.

## Safety behavior

If aligned observations are below the minimum, the pair is not promoted to a redundancy decision and is counted as insufficient. The analyzer is deterministic and produces no BUY/SELL/NO_TRADE decision.