# CRYPTO SQUID v2 — Strategy Specification

> Version: coinbase-mvp-v2  
> Exchange: Coinbase Advanced Trade (spot perpetuals)  
> Universe: BTC-USD, ETH-USD  
> Mode: Long-only. Event-driven. Rule-based. No ML in live path.

---

## Core Thesis

Behavioral panic sell-offs create short-horizon mean-reversion opportunities in liquid crypto markets.
The edge is **conditional and narrow**: panic must be abnormal, occur in adequate liquidity,
and show visible selling exhaustion before entry.

Competing with market makers and systematic traders means the subset of tradeable events
is small. High selectivity and clean execution beat high frequency.

---

## Data Architecture

| Source | Use |
|---|---|
| Coinbase WebSocket — `market_trades` | Tick stream → 1-second OHLCV bars, volume imbalance |
| Coinbase WebSocket — `level2` | Best bid/ask → spread calculation |
| Coinbase REST (authenticated) | Order placement, order status, account balance |

**1-second bars** are built internally from the tick stream.

Rolling windows maintained per symbol:
- 15s, 60s, 180s (signal windows)
- 1800s / 30 min (baseline for z-score and volume normalization)

REST polling is NOT used for signal generation. WebSocket only.

---

## Signal Pipeline (5 stages)

### Stage 1 — Regime Filter (daily)

All conditions must be true before evaluating any setup:

| Check | Value |
|---|---|
| Max trades per day | 6 |
| Max consecutive losses | 2 |
| Max signals evaluated per symbol per day | 4 |
| Daily loss limit | 1.0% of equity |
| Max rejected fills in a row | 3 |

Per-tick regime checks:

| Check | BTC-USD | ETH-USD |
|---|---|---|
| Max spread | ≤ 4 bps | ≤ 6 bps |
| 60s dollar volume | ≥ 35th pct of 30-min dist | same |
| Product status | online | online |

---

### Stage 2 — Panic Trigger

All four conditions required simultaneously:

| Metric | BTC threshold | ETH threshold |
|---|---|---|
| 180-second return | ≤ −0.90% | ≤ −1.20% |
| Price z-score (vs 30-min 1s returns) | ≤ −2.25 | ≤ −2.25 |
| 180-second volume ratio (vs 30-min median) | ≥ 2.0× | ≥ 2.0× |
| Seller-initiated volume share (180s) | ≥ 60% | ≥ 60% |

When triggered, the **panic low** and trigger metadata are recorded.
The event is logged to `data/events/events.csv` immediately (state = "candidate").

---

### Stage 3 — Disorder Filter (runs until stabilization phase)

Reject the setup if either condition is true:

| Condition | Threshold | Reason |
|---|---|---|
| Spread > 2× rolling median | reject | still chaotic / illiquid |
| New price low > 15 bps below panic low | reject | continuing liquidation, not reversal |

If rejected: logged (state = "rejected_disorder") and reset to IDLE.

---

### Stage 4 — Stabilization Confirmation

Minimum wait: **20 seconds** after panic low.

Then require ALL of:

| Condition | Threshold |
|---|---|
| No new price low | 20 consecutive seconds |
| Seller-initiated volume share (last 10s) | < 55% |

Stabilization timeout: **90 seconds** — if not confirmed by then, abort.
Aborted event logged (state = "rejected_stab").

---

### Stage 5 — Entry Signal

When stabilization confirmed:

- Entry limit price = signal price − 3 bps (maker-biased)
- Order lifetime = **15 seconds** (cancel if unfilled)
- Do not chase

Stop price = tighter of:
- Fixed stop: entry × (1 − sl_pct / 100)
- Structure stop: panic_low × (1 − 8 bps)

---

## Position Management

### Sizing

```
risk_budget = equity × 1.00%
stop_distance = entry - stop
size = risk_budget / stop_distance
```

Caps:
- BTC: max 20% of equity gross exposure
- ETH: max 15% of equity gross exposure

### Staged Exits

| Step | BTC target | ETH target | Action |
|---|---|---|---|
| TP1 | +0.55% | +0.70% | Exit 50% of position |
| After TP1 | — | — | Move stop to breakeven + 2 bps |
| TP2 | +0.95% | +1.15% | Exit remaining 50% |

### Time Controls

| Rule | Threshold |
|---|---|
| Fast-reduce trigger | 5 minutes elapsed, PnL between −0.10% and +0.20% → reduce 50% |
| Hard time stop | 15 minutes — flatten everything |

### Stop Cases

| Trigger | Action |
|---|---|
| Price ≤ stop (before TP1) | Full exit, log SL |
| Price ≤ breakeven stop (after TP1) | Exit remainder, log SL_BREAKEVEN |
| Time stop | Exit all remaining, log TIME_STOP |

---

## Risk Controls (Layer 1 — Immutable)

These cannot be changed without explicit user approval:

- Long-only
- No market orders — limit only
- One position per symbol at a time
- Max 6 trades/day
- Max 2 consecutive losses
- Max 1% daily drawdown
- `TRADING_ENABLED=false` halts all new entries immediately

---

## Tunable Parameters (Layer 2 — via hypotheses.md → approval → params_v2.py)

See: `strategy/v2-params.md`

Process:
1. Propose in `strategy/hypotheses.md` with evidence from event study data
2. Wait for user approval
3. Update `src/params_v2.py` — one parameter at a time
4. Note change in `changelog.md`

**Never** optimize to recent winners. **Never** change multiple parameters simultaneously.

---

## What This Is NOT

- Not a trend-following system
- Not a "buy the dip" system (most dips are filtered out)
- Not validated for live trading yet
- Not a high-frequency system (signal fires at most 2× per day per asset)

---

## Source Files

| File | Role |
|---|---|
| `src/params_v2.py` | All parameters as Python dataclasses |
| `src/signal_v2.py` | Signal state machine (Stages 1–5) |
| `src/bar_builder.py` | 1-second bars + rolling stats |
| `src/coinbase_ws.py` | WebSocket tick feed |
| `src/paper_engine_v2.py` | Staged exit paper simulator |
| `src/event_collector.py` | Event study CSV logger |
| `src/bot_v2.py` | Main loop |
| `strategy/v2-params.md` | Parameter reference table (human-readable) |
| `docs/ANTI_OVERFITTING_PROTOCOL.md` | Research + validation protocol |
