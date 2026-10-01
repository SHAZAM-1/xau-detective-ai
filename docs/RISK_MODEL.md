# XAU Detective AI — Risk Model

## Default research assumption

Risk per trade: 1% of account equity.

This is a configurable research parameter, not a promise of safety.

## Core calculation

risk_amount = equity × risk_percent
sl_distance = abs(entry - stop)
effective_sl_distance = sl_distance + expected_slippage
loss_per_lot = (effective_sl_distance / tick_size) × tick_value
required_lots = risk_amount / loss_per_lot

## Hard vetoes

Return **NO TRADE** when executable size is below minimum lot, effective risk exceeds the configured limit, margin is insufficient, broker specifications are invalid, spread is above the configured threshold, expected slippage exceeds its threshold, expected slippage makes the setup infeasible, daily loss plus the proposed trade loss exceeds the daily loss limit, stop distance is invalid, or broker lot granularity cannot express the desired risk.

## Execution snapshot

The MT5 adapter can provide current bid/ask, spread, expected slippage budget, and broker-calculated one-lot margin. The core risk engine never invents these values. If a configured spread/slippage gate is active without an execution snapshot, the result is **NO TRADE**.

## Daily loss circuit breaker

The caller can provide today's realized and unrealized P&L. The proposed trade loss is included in projected daily loss before allowing the trade.

## Important

Leverage can change margin requirements but does not reduce monetary loss per price movement for a given position size.

The system must never solve a minimum-lot risk violation by increasing leverage.

## Position sizing

Sizing is derived from stop distance. The system must not use fixed lots, loss-based lot increases, Martingale, Grid recovery, or averaging down.

## Account-size research

The system must calculate feasibility for $20, $50, $100, $500, and $1,000. These are test cases, not assumptions about live deployment.
