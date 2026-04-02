# Market Regime Definitions - Hyperliquid MVP

### R1 - Washout and rebound friendly
- Sharp downside bursts, elevated short-term volume, fast mean reversion.
- Action: normal operation.

### R2 - Trend continuation pressure
- Persistent downside trend with weak bounces.
- Action: allow only strongest signals; monitor stop frequency.

### R3 - Low-volatility chop
- Small candles, weak volume spikes, noisy z-score flips.
- Action: expect low activity and more rejects.

### R4 - Event shock
- Macro/news shock with unstable spreads and large gaps.
- Action: keep bot in log-only or pause via `TRADING_ENABLED=false`.

### R5 - Recovery grind
- Slow drift higher after flush with limited volatility.
- Action: time-stop behavior becomes more important than TP hits.
