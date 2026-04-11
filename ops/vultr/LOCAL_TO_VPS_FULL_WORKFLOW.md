# Local -> VPS -> Vercel: Full Workflow, Retro, Gotchas, and Repeatable Process

This is the complete record of what we did to get Crypto Squid running from local code to a live VPS-backed dashboard, plus the repeatable workflow for future bots.

## 1) Final Architecture (what is live now)

- Local repo (`main`) is source of truth.
- VPS (`45.76.2.84`) runs bot + dashboard services.
- VPS auto-syncs from GitHub `main` every minute using a systemd timer.
- Vercel site proxies control/read endpoints to VPS.
- Dashboard can start/stop strategy, show bot status, prices, KPIs, charts, orders, fills.

## 2) What we implemented (chronological)

1. Added secure runtime control plane:
   - `src/dashboard.py` endpoints: `/health`, `/snapshot`, `/control/status|start|stop`
   - Bearer-token auth via `CONTROL_API_TOKEN`
2. Added runtime kill gate file:
   - `data/control/runtime_control.json` read by `core/engine.py`
   - Manual stop/start without restart
3. Added daily-loss failsafe latch in engine:
   - If daily loss breach occurs, engine latches to stop mode
4. Standardized risk defaults in `.env.example`:
   - 0.50% risk, 3 trades/day, 2 consecutive losses, 1.0% daily loss
5. Added Vultr deploy assets:
   - `ops/vultr/bootstrap_vultr.sh`
   - `ops/vultr/systemd/*.service`
   - `ops/vultr/nginx/cryptosquid.conf`
   - `ops/vultr/DEPLOY_CHECKLIST.md`, `ops/vultr/RUNBOOK.md`
6. Added Vercel proxy dashboard implementation:
   - root `index.html` and `api/*.js`
7. Fixed Vercel build failures and routing issues.
8. Deployed VPS runtime and validated remote control API.
9. Added `cryptosquid-sync` auto-update timer/service (GitHub zip -> rsync -> restart services).
10. Implemented guarded Coinbase live execution path while keeping paper default:
    - `strategies/coinbase_live_client.py`
    - `strategies/coinbase_v2_strategy.py` live-mode reconciliation logic
11. Upgraded dashboard to full KPI/charts/trade views.
12. Added Coinbase reporting feed for account/order/fill visibility:
    - `src/coinbase_reporting.py`
    - `/snapshot` now includes `coinbase` reporting payload

## 3) Issues we hit and exact fixes

### A) Vercel deployment failed repeatedly
- Symptom: deploys failed or did not serve API routes.
- Root cause: project framework preset was incorrect (Python preset conflicted with this setup).
- Fix:
  - switched Vercel project framework to `Other` via Vercel API/CLI
  - simplified `vercel.json`
  - removed overly restrictive `.vercelignore`
  - redeployed and re-aliased

### B) Stale control status in dashboard
- Symptom: `/control/status` looked stale after stop/start.
- Root cause: response caching at edge/browser.
- Fix:
  - added `Cache-Control: no-store` in `api/health.js`, `api/snapshot.js`, `api/control.js`
  - added cache-busting query in frontend fetch

### C) VPS sync using git pull not possible
- Symptom: `/opt/cryptosquid` had no `.git`; pull failed.
- Root cause: initial deployment used file upload/bootstrap path.
- Fix:
  - implemented `sync_from_github.sh` (codeload zip + rsync + pip + service restart)
  - added `cryptosquid-sync.service` + `.timer`

### D) Dependency compatibility on Ubuntu 22.04
- Symptom: runtime dependency mismatch risk.
- Fix:
  - pinned `numpy==2.2.6` for Python 3.10 compatibility on VPS

### E) Git add/indexing issue with runtime temp files
- Symptom: staging failed due transient `runtime_state.tmp`.
- Fix:
  - removed temp artifact from staging path
  - ensured runtime data files are excluded/ignored where needed

### F) CRLF concerns for Linux scripts
- Symptom: shell scripts can fail if CRLF line endings are committed.
- Fix:
  - added `.gitattributes` LF policy

### G) Engine running indicator false-negatives
- Symptom: dashboard occasionally showed not running despite active loop.
- Fix:
  - added `updated_at` in strategy runtime payload
  - fallback mtime-based heartbeat detection in `src/dashboard.py`

## 4) Current operating commands

### Local deploy flow
```bash
git add .
git commit -m "<message>"
git push origin main
```

VPS auto-sync pulls and applies in about 60 seconds.

## 4.1) Persistent deployment method (do not ask again)

- Primary deploy path: `git push origin main` from local source-of-truth repo.
- VPS applies updates via `cryptosquid-sync.timer` every minute.
- Agent default behavior:
  1. implement changes locally
  2. run local validation checks
  3. commit and push to `main`
  4. verify VPS health/snapshot endpoints
- Direct SSH is only required for timer/service break-glass operations.
- SSH material/location must be maintained in operator environment, never in repo.

### VPS health checks
```bash
systemctl is-active cryptosquid-engine
systemctl is-active cryptosquid-dashboard
systemctl is-active cryptosquid-sync.timer
cat /opt/cryptosquid/data/control/last_sync.json
```

### Remote control API (through Vercel)
```bash
GET /api/health
GET /api/snapshot
POST /api/control?action=stop
POST /api/control?action=start
GET /api/control?action=status
```

## 5) Data flows now available in `/snapshot`

- `state`: bot runtime status, mode, symbols, positions, stats, trade list
- `control`: remote gate status (`trading_enabled`, reason, timestamp)
- `coinbase`: live reporting payload
  - prices (`BTC-USD`, `ETH-USD`)
  - balances and estimated equity
  - open orders + count
  - recent fills
- `engine_running`: heartbeat flag

## 6) Markdown workflows (journal, lessons, Obsidian)

### Daily workflow
1. Let bot run in paper mode.
2. Pull snapshot and verify KPIs.
3. Generate/update daily report under `reports/daily/`.
4. If notable event occurred, add a note under `journal/`.

### Weekly workflow
1. Run weekly review report in `reports/weekly/<YYYY-WNN>.md`.
2. Record strategy lessons in:
   - local: `memory/reflections/` or `memory/lessons/`
   - project: `strategy/hypotheses.md` (max 3 experiment ideas)
3. Mirror key lessons to Obsidian:
   - `08_Trading/CryptoSquid/...` structure (see `docs/TRADE_MEMORY.md`)

### Obsidian consistency
- Set `OBSIDIAN_VAULT_PATH` in `.env`.
- Keep this structure stable:
  - `08_Trading/CryptoSquid/trades/...`
  - `08_Trading/CryptoSquid/reports/daily/...`
  - `08_Trading/CryptoSquid/reports/weekly/...`
  - `08_Trading/CryptoSquid/self-improvement/lessons.md`

## 7) Gotchas checklist before every push

- Do not commit `.env` or secrets.
- Keep `ENABLE_LIVE_TRADING=false` unless intentional go-live.
- Verify `PAPER_MODE=true` on VPS after sync if staying paper.
- Verify `cryptosquid-sync.timer` is still active.
- Confirm Vercel env vars still exist (`TRADER_API_BASE_URL`, `TRADER_API_TOKEN`).
- If dashboard control seems stale, verify cache headers and re-check alias target.

## 8) Repeatable update-and-verify loop

1. Change code locally.
2. `git push origin main`.
3. Wait 60-90 seconds.
4. Check VPS sync stamp changed.
5. Verify:
   - `/api/health`
   - `/api/snapshot`
   - stop/start cycle
6. Log outcomes in `journal/` and `reports/`.

## 9) Live-mode guardrails (current state)

- Live execution code path exists and is guarded.
- Runtime remains paper unless BOTH are true:
  - strategy mode set to `live`
  - `.env` has `ENABLE_LIVE_TRADING=true`
- Keep current default for safety:
  - `PAPER_MODE=true`
  - `ENABLE_LIVE_TRADING=false`
