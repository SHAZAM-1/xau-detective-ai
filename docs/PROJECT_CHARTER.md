# XAU Detective AI — Project Charter

## Mission

Build an evidence-driven trading research and decision-support system specialized in XAUUSD.

The system is designed to investigate market conditions, generate competing scenarios, enforce deterministic risk constraints, and produce either a fully specified trade proposal or **NO TRADE**.

## Non-goals

- No guaranteed profits or 100% win rate.
- No Martingale, Grid, averaging down, or recovery sizing.
- No live autonomous execution in V1.
- No unvalidated AI model controlling risk or execution.
- No hardcoded broker assumptions.

## Core principles

1. Evidence before action.
2. Independent evidence families before directional conviction.
3. Risk constraints are hard vetoes.
4. Capital-aware sizing is mandatory.
5. NO TRADE is a valid successful outcome.
6. Backtest claims must survive out-of-sample and walk-forward validation.
7. Every decision must be auditable after the fact.

## Initial target

Instrument: XAUUSD only.

Initial platform direction: MetaTrader 5 for execution/data access, with Python for research, feature engineering, validation, and later ML.

## V1 philosophy

V1 is deterministic and research-first. Machine learning is not allowed to modify risk limits or bypass execution safeguards.
