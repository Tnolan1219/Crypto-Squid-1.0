# Tunable Parameters — CRYPTO SQUID v2

> Layer 2: propose via `strategy/hypotheses.md` → user approval → update `src/params_v2.py`
> Full parameter table with rationale: `strategy/v2-params.md`

## Quick reference

| Parameter | BTC-USD | ETH-USD | Change process |
|---|---:|---:|---|
| drop_threshold_pct | 0.90% | 1.20% | hypothesis → approval |
| zscore_threshold | −2.25 | −2.25 | hypothesis → approval |
| volume_ratio_threshold | 2.0× | 2.0× | hypothesis → approval |
| trade_imbalance_sell | 60% | 60% | hypothesis → approval |
| max_spread_bps | 4 bps | 6 bps | hypothesis → approval |
| stab_min_wait_seconds | 20s | 20s | hypothesis → approval |
| tp1_pct | 0.55% | 0.70% | hypothesis → approval |
| tp2_pct | 0.95% | 1.15% | hypothesis → approval |
| sl_pct | 0.45% | 0.55% | hypothesis → approval |
| time_stop_minutes | 15 min | 15 min | hypothesis → approval |

## Process rule

1. Write proposed change in `strategy/hypotheses.md` with supporting data from `data/events/events.csv`
2. Claude proposes ≤ 3 changes per weekly review
3. User approves or rejects
4. Approved → update `src/params_v2.py` + this file + `changelog.md`
5. One change at a time. Minimum one week between parameter changes.

See full specification: `strategy/v2-params.md`
See research protocol: `docs/ANTI_OVERFITTING_PROTOCOL.md`
