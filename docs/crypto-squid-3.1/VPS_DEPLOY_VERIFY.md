# Crypto-Squid 3.1 VPS Deploy + Verify

## Paper-First Runtime Settings

Required in VPS `.env` / `/etc/...env`:

- `ENABLED_STRATEGIES=coinbase_v3`
- `TRADING_ENABLED=false`
- `PAPER_MODE=true`
- `ENABLE_LIVE_TRADING=false`
- `LIVE_TRADING_CONFIRM=NO`

## Launch

Run engine:

`python scripts/run_all.py`

Run dashboard:

`python src/dashboard.py`

## Verify Checklist

1. Process health
   - Engine process running continuously
   - Dashboard process running
2. WebSocket health
   - Logs show `ws.connected` and `ws.subscribed`
   - No reconnect storm
3. Universe health
   - Runtime state contains `symbol_universe.active`
   - Expected symbols present when tradable
4. Strategy health
   - Runtime state `version` is `v3.1`
   - `strategy_name` is `Crypto-Squid 3.1`
5. Safety health
   - `mode.trading_enabled` false in paper
   - `live.health_error` empty or expected guard state
6. Trade loop health
   - Event count increases over time
   - Entries/exits appear in `trades` with reasons

## Dashboard Endpoints

- Local: `http://127.0.0.1:8787/`
- VPS direct: `http://<VPS_IP>:8787/` (if firewall + bind allow)
- Health API: `http://<VPS_IP>:8787/health`
- Snapshot API: `http://<VPS_IP>:8787/snapshot`

## Live Promotion (later)

Enable only when paper metrics and controls are stable:

- `TRADING_ENABLED=true`
- `ENABLE_LIVE_TRADING=true`
- `LIVE_TRADING_CONFIRM=YES`
