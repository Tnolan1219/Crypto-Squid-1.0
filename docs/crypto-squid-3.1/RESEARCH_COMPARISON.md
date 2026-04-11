# Crypto-Squid 3.1 vs Research Spec

## Implemented Exactly or Near-Exactly

- Conditional panic-reversion structure with regime gate, panic trigger, disorder veto, and stabilization phase
- Multi-asset scanning with BTC/ETH core and liquid alt expansion
- Cross-asset risk gate for alt entries when BTC is stressed
- Per-asset spread thresholds, drop thresholds, and differentiated TP/SL sizing
- Conservative risk controls and gross exposure caps
- Live trading double-confirmation safety controls

## Intentionally Adapted for VPS Practicality

- Timing moved away from fragile 20-30 second dependence:
  - panic window uses 5 minutes
  - stabilization requires 45s minimum wait and 75s no-new-low
- Entry is still limit-first, but clip-order choreography is not modeled in paper as exchange-accurate queue simulation is not available
- Microprice edge is not used as a hard gate because top-of-book size quality from the current lightweight feed is not robust enough for production decisions in this VPS profile

## Deferred / Not Implemented in 3.1

- Full queue-position fill modeling for maker backtesting (requires order-by-order depth and is compute/data expensive)
- External derivatives liquidation/funding feeds as hard gates (data vendor/API dependency not currently wired)
- Full synthetic OCO management at exchange object level for every leg (current stop/TP orchestration remains software-managed)

## Why These Tradeoffs

- Keeps strategy robust on 1 vCPU VPS
- Preserves reliability over theoretical precision
- Aligns with project constraint: practical deployment and safety-first operation over overfitted complexity
