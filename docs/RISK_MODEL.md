# XAU Detective AI — Risk Model

## Default research assumption

Risk per trade: 1% of account equity.

This is a configurable research parameter, not a promise of safety.

## Core calculation

```
risk_amount = equity × risk_percent

sl_distance = abs(entry - stop)

loss_per_lot =
    (sl_distance / tick_size) × tick_value

required_lots =
    risk_amount / loss_per_lot
```

The executable quantity must then respect broker constraints.

## Hard vetoes

Return **NO TRADE** when:

- executable size is below minimum lot,
- effective risk exceeds the configured limit,
- margin is insufficient,
- broker symbol specifications are missing or invalid,
- spread is above the configured execution threshold,
- expected slippage makes the setup infeasible,
- stop distance is invalid,
- or the account cannot express the desired risk with the broker's lot granularity.

## Important

Leverage can change margin requirements but does not reduce the monetary loss per price movement for a given position size.

The system must never solve a minimum-lot risk violation by increasing leverage.

## Position sizing

Sizing must be derived from stop distance.

The system must not use:
- fixed lot sizing,
- loss-based lot increases,
- Martingale,
- Grid recovery,
- averaging down.

## Account-size research

The system must calculate feasibility for:
- $20
- $50
- $100
- $500
- $1,000

These are test cases, not assumptions about live deployment.
