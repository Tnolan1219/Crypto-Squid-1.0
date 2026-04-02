# Anti-Overfitting Research Protocol

> Source: López de Prado (2018), Bailey & López de Prado (2014), BIS MktC13 (2016)
> Applied to: CRYPTO SQUID v2

---

## Why This Exists

Backtest overfitting is the dominant failure mode in systematic strategy research.
An analyst can run hundreds of parameter combinations until the backtest looks good —
but the result is a strategy that fit historical noise, not a real edge.

This protocol enforces the professional standard: **hypothesis first, test second, evaluate robustly**.

---

## Core Rule

> **One parameter. One change. One reason. Document before testing.**

Changing multiple parameters simultaneously makes it impossible to attribute what improved.
It also inflates the false discovery rate exponentially.

---

## The 5-Phase Research Process

### Phase 1 — Event Study (FIRST — before touching any thresholds)

**Goal**: understand the raw data before fitting anything.

1. Run `bot_v2.py` with `TRADING_ENABLED=false` to collect events without paper-trading
2. Or run normally — event logging is always on regardless of trade mode
3. Collect data for all candidate events in `data/events/events.csv`
4. Minimum: **300 candidate events** before any parameter optimization

For each event, the collector logs:
- Trigger features: drop%, z-score, volume ratio, spread, imbalance
- Signal state: candidate, rejected_regime, rejected_disorder, rejected_stab, fired
- Outcome columns: filled in post-hoc from bar data (via `/propose-experiments`)

From Phase 1 output, answer:
- What fraction of candidates pass each filter?
- What is the raw return distribution after trigger (10s, 30s, 60s, 180s)?
- Does the thesis hold? (reversal after panic, not continuation)
- Which filter is weakest / strongest?

**Do not change any parameters during Phase 1.**

---

### Phase 2 — Parameter Family (narrow scope)

Only these parameter families are eligible for optimization:

| Family | Parameters |
|---|---|
| Trigger thresholds | `drop_threshold_pct`, `zscore_threshold`, `volume_ratio_threshold`, `trade_imbalance_sell_threshold` |
| Stabilization | `stab_min_wait_seconds`, `stab_no_new_low_seconds`, `stab_seller_share_max` |
| Exit levels | `tp1_pct`, `tp2_pct`, `sl_pct`, `sl_structure_bps` |
| Time controls | `time_stop_minutes`, `fast_reduce_minutes` |

**Off-limits for optimization:**
- Risk budget (Layer 1)
- Daily limits (Layer 1)
- Entry mechanism (limit-only, 15s lifetime — these are cost controls, not signal)
- Adding new filters without a written hypothesis

---

### Phase 3 — Chronological Validation

**Never use random cross-validation on time series.** Use chronological splits only.

Minimum standard:
```
Events sorted by timestamp →
  Train:      first 60% of events
  Validate:   next 20%
  Test:       final 20% (held out until last)
```

Better standard (use once 300+ events are available):
- Walk-forward: 3-month rolling training window, 1-month test window
- Report performance on each out-of-sample fold separately

**Test window is sacred**: only evaluate it once, after all parameter decisions are frozen from the validation set.

---

### Phase 4 — Robust Evaluation Metrics

Do not optimize raw PnL alone. Rank versions by ALL of:

| Metric | Why |
|---|---|
| Net expectancy after fees | Core viability |
| Median trade PnL | Resistance to outlier dependency |
| Out-of-sample Sharpe | Risk-adjusted return |
| Deflated Sharpe Ratio (DSR) | Corrects for number of trials / selection bias |
| Max drawdown | Survivability |
| Fraction of profitable days | Stability |
| PnL by month | Concentration check (no single month > 35% of total) |

Fee assumptions (Coinbase Advanced):
- Maker fill: ~0.00% (post-only limit)
- Worst case: 0.05% per side if taker = 0.10% round-trip
- Always compute net-of-fees expectancy before claiming an edge

---

### Phase 5 — Fragility Check

Reject ANY strategy version that:

1. Only works in one calendar month
2. Depends on a single outlier trade for profitability
3. Flips unprofitable when fees increase by 1 tick (0.01%)
4. Degrades sharply if spread assumption worsens by 1 bps
5. Requires taker execution most of the time
6. Out-of-sample performance is materially worse than in-sample

If a version fails Phase 5, it does NOT graduate to live — regardless of how good the backtest looks.

---

## Go-Live Criteria (Pass/Fail Checklist)

A version may graduate to live ONLY when ALL are true:

- [ ] ≥ 300 candidate events logged
- [ ] ≥ 80 paper trades closed
- [ ] Positive net expectancy (after fees) in both validate AND test sets
- [ ] No single calendar month contributes > 35% of total net PnL
- [ ] Median trade PnL positive after 0.10% round-trip fee haircut
- [ ] Out-of-sample max drawdown < 3× average monthly return
- [ ] Deflated Sharpe Ratio > 0
- [ ] Live paper results broadly match event-study expectations
- [ ] WebSocket connectivity stable for ≥ 5 consecutive days
- [ ] Risk controls (stop, time stop, daily limits) verified in paper trades
- [ ] User explicit sign-off: "approved for live"

---

## Claude's Role in This Process

| Action | Claude may do |
|---|---|
| Collect event data | Yes — always running |
| Analyze event CSV on request | Yes |
| Propose experiments (≤ 3 at a time) | Yes — via `/propose-experiments` |
| Write proposals to `strategy/hypotheses.md` | Yes |
| Change params without approval | NO |
| Change multiple params at once | NO |
| Optimize to recent winners | NO |
| Declare an edge from in-sample data alone | NO |

---

## Self-Improvement Loop

After every weekly review (`/weekly-review`):

1. Claude analyzes `data/events/events.csv` for patterns
2. Proposes ≤ 3 parameter changes with supporting data from the event study
3. Writes proposals to `strategy/hypotheses.md`
4. User reviews and approves/rejects each proposal
5. Approved changes: update `src/params_v2.py` + `strategy/v2-params.md`
6. Log change in `changelog.md` with date, parameter, old value, new value, rationale
7. Run session-close → sync to mem0

**One change at a time. One week minimum between changes.**

---

## Phase Gates Summary

```
Collect 300+ events
  ↓
Phase 1 event study (read-only analysis)
  ↓
Propose ≤ 3 parameter changes (hypotheses.md)
  ↓ user approves
Update params_v2.py (one at a time)
  ↓
Collect 80+ paper trades
  ↓
Phase 3/4 chronological validation + robust metrics
  ↓ pass Phase 5 fragility check
  ↓
Go-live checklist all green
  ↓ user explicit sign-off
Live trading (small size, full monitoring)
```
