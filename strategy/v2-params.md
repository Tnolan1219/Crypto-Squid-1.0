# v2 Tunable Parameters

> Layer 2: propose changes via `strategy/hypotheses.md` → user approval → update `src/params_v2.py`
> One parameter at a time. Document rationale. Never optimize to recent winners.

---

## Signal Thresholds

| Parameter | BTC-USD | ETH-USD | Notes |
|---|---:|---:|---|
| `drop_threshold_pct` | 0.90 | 1.20 | 180-second return must be ≤ negative of this |
| `zscore_threshold` | −2.25 | −2.25 | Z-score of 1-sec return vs 30-min distribution |
| `volume_ratio_threshold` | 2.0× | 2.0× | 180s dollar volume vs 30-min median |
| `trade_imbalance_sell_threshold` | 60% | 60% | Fraction of 180s volume that is seller-initiated |

---

## Regime Filter

| Parameter | BTC-USD | ETH-USD | Notes |
|---|---:|---:|---|
| `max_spread_bps` | 4.0 | 6.0 | Reject entry if spread exceeds this |
| `disorder_spread_multiple` | 2.0× | 2.0× | Reject if spread > 2× rolling median |
| `disorder_new_low_bps` | 15 | 15 | Reject if new low > 15 bps below panic low |
| `volume_percentile_35_threshold` | 35th pct | 35th pct | Min liquidity: 60s vol ≥ 35th pct of 30-min dist |

---

## Stabilization

| Parameter | Value | Notes |
|---|---:|---|
| `stab_min_wait_seconds` | 20s | Minimum wait after panic trigger |
| `stab_no_new_low_seconds` | 20s | Panic low must hold for this long |
| `stab_seller_share_max` | 55% | Seller vol share in last 10s must be below this |
| `stab_timeout_seconds` | 90s | Abort if not stabilized by this time |

---

## Entry

| Parameter | Value | Notes |
|---|---:|---|
| `entry_offset_bps` | 3 bps | Limit = signal price − 3 bps |
| `entry_order_lifetime_seconds` | 15s | Cancel unfilled limit after 15 seconds |

---

## Exit — BTC-USD

| Parameter | Value | Notes |
|---|---:|---|
| `tp1_pct` | 0.55% | First target — exit 50% of position |
| `tp2_pct` | 0.95% | Second target — exit remaining 50% |
| `sl_pct` | 0.45% | Fixed stop % below entry |
| `sl_structure_bps` | 8 bps | Structure stop: 8 bps below panic low |
| `time_stop_minutes` | 15 min | Hard time stop |
| `fast_reduce_minutes` | 5 min | Partial reduce if PnL in −0.10% to +0.20% range |

---

## Exit — ETH-USD

| Parameter | Value | Notes |
|---|---:|---|
| `tp1_pct` | 0.70% | First target — exit 50% |
| `tp2_pct` | 1.15% | Second target — exit remaining 50% |
| `sl_pct` | 0.55% | Fixed stop % below entry |
| `sl_structure_bps` | 8 bps | Structure stop: 8 bps below panic low |
| `time_stop_minutes` | 15 min | Hard time stop |
| `fast_reduce_minutes` | 5 min | Partial reduce if PnL is marginal |

---

## Risk (Layer 1 — Immutable)

| Parameter | Value | Notes |
|---|---:|---|
| `risk_per_trade_pct` | 0.35% | Risk budget per trade (was 0.50% in v1 — deliberately conservative for unproven strategy) |
| `max_trades_per_day` | 2 | Daily fill cap |
| `max_signals_evaluated_per_asset` | 4 | Daily signal eval cap per symbol |
| `max_consecutive_losses` | 2 | Stop for the day after 2 losses in a row |
| `daily_loss_limit_pct` | 1.0% | Realized drawdown cap for the day |
| `max_gross_exposure_btc_pct` | 20% | Max position size as % of equity |
| `max_gross_exposure_eth_pct` | 15% | Max position size as % of equity |

---

## Process

1. Any proposed change must be written in `strategy/hypotheses.md` with:
   - Current value and proposed value
   - Evidence from `data/events/events.csv` supporting the change
   - Expected impact on signal frequency and expectancy
2. Claude proposes ≤ 3 changes per weekly review
3. User approves or rejects each proposal
4. Approved changes → update `src/params_v2.py` and this file
5. Log in `changelog.md`: date, parameter, old → new, rationale
6. One change at a time, one week minimum between changes
