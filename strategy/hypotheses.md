# Strategy Hypotheses - Hyperliquid MVP

## Template
```
### H-XXX: [short title]
- Hypothesis:
- Parameter:
- Test window:
- Success metric:
- Status: PENDING | TESTING | ADOPTED | REJECTED
- Result:
- Decision:
```

## Active

### H-001: BTC drop threshold sensitivity
- Hypothesis: Raising `BTC_DROP_THRESHOLD_PCT` from 0.75 to 0.90 reduces low-quality churn without degrading expectancy.
- Parameter: `BTC_DROP_THRESHOLD_PCT`
- Test window: next 30 paper trades
- Success metric: equal or higher average PnL per trade with fewer entries
- Status: PENDING

### H-002: Stabilization wait tightening
- Hypothesis: `STABILIZATION_WAIT_SECONDS=45` improves signal quality during high-volatility sessions.
- Parameter: `STABILIZATION_WAIT_SECONDS`
- Test window: matched session comparison over 2 weeks
- Success metric: lower stop-out rate at similar trade count
- Status: PENDING
