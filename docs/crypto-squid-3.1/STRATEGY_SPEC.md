# Crypto-Squid 3.1 Strategy Spec

## Objective

Trade short-term panic overshoots in liquid, retail-driven crypto pairs with strict risk controls and limit-first execution.

## Universe

- Core: BTC-USD, ETH-USD
- Expansion: SOL-USD, DOGE-USD, ADA-USD, AVAX-USD, POL-USD, MATIC-USD
- Runtime keeps only symbols that Coinbase reports as active/tradable.
- If both POL-USD and MATIC-USD are active, POL-USD is preferred to avoid duplicate exposure.

## Signal Logic

1. Regime gate (must pass)
   - Spread <= symbol max spread
   - 60s volume >= 30th percentile of rolling 30m baseline
   - Trend context: price above 30m VWAP OR EMA slope non-negative
2. Panic trigger (all required)
   - 5m return <= negative symbol drop threshold
   - 30m z-score <= symbol threshold
   - 60s volume ratio >= 1.7 vs baseline
   - 60s sell share >= 0.58
3. Disorder veto
   - Spread blowout >= 2.0x median spread OR
   - Trigger-to-panic continuation extension > symbol disorder bps
4. Stabilization confirmation
   - Minimum wait 45s after trigger
   - No new low for 75s
   - Buy volume > sell volume over 45s
   - Recent micro higher-low structure present

## Cross-Asset Guard

- New alt entries are disabled when BTC is stressed:
  - BTC 5m drop <= -0.30% OR
  - BTC spread above BTC spread cap

## Execution

- Limit-only entry/target flow is preserved.
- Stops are software-triggered; live exits use IOC limit with a symbol-specific guard bps.
- Paper engine supports:
  - TP1/TP2 staged exits
  - trailing stop after TP1
  - time stop and fast-reduce logic

## Risk Management

- Immutable core enforced:
  - Risk per trade: 0.50%
  - Max trades/day: 3
  - Max consecutive losses: 2
- Daily loss limit: 1.0%
- Per-symbol capital-per-trade cap + per-symbol gross exposure cap
- Portfolio total gross exposure cap: 40%

## Live Safety Gates

- `TRADING_ENABLED` must be true
- `ENABLE_LIVE_TRADING` must be true
- `LIVE_TRADING_CONFIRM=YES` must be set
- Otherwise strategy remains non-live.
