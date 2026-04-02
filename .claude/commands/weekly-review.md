---
description: Generate weekly performance analysis, classification summary, and pattern detection
argument-hint: "<YYYY-WNN e.g. 2026-W14>"
---

You are performing the weekly self-improvement review for Crypto Squid.

**Week:** $ARGUMENTS

## Data to gather

1. Read all trade journal entries in `journal/raw-trades/` from the specified week
2. Query SQLite at `data/trades/trades.db` for that week's records
3. Read `strategy/core-rules.md` — check rule compliance
4. Read `strategy/tunable-params.md` — note current parameter values
5. Read `strategy/hypotheses.md` — check status of active hypotheses
6. Read prior weekly report if it exists in `reports/weekly/`

## Analysis to perform

### Performance Metrics
- Total trades / wins / losses / missed
- Win rate, average R, total PnL
- Rule compliance rate

### Pattern Detection
Answer these questions:
- Were losses clustered by: time of day? specific price levels? low-intensity signals?
- Were wins clustered by: specific signal characteristics? regimes?
- Any setup types that consistently underperformed?
- Was execution quality (slippage, fill rates) acceptable?

### Trade Classification Summary
Count across: valid-winner / valid-loser / invalid-winner / invalid-loser
Flag any invalid trades for root cause review.

### Edge Assessment
Is the strategy performing as expected?
- If win rate < 50% over 15+ trades → flag for review
- If average R < 1.0 → flag exit management issue
- If >30% invalid trades → flag discipline issue

## Constraints (anti-overfitting rules)
- Minimum 30 trades before proposing parameter changes
- Maximum 3 parameter experiments proposed per week
- Only one parameter change at a time
- Do not propose changes based on fewer than 10 data points

## Output

Write report to `reports/weekly/YYYY-WNN.md` with:
1. Summary stats table
2. Pattern findings (max 5 observations)
3. Edge assessment verdict (STABLE / INVESTIGATE / PAUSE)
4. Proposed experiments (0–3 max, each with hypothesis ref to hypotheses.md)
5. Next week focus

Then tell the user the key findings in 3–5 sentences.
