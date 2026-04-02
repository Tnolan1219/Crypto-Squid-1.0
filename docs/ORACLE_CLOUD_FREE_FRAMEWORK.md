# Oracle Cloud Free Framework (Paper Runtime)

This framework deploys the bot and dashboard as always-on services on an Oracle Cloud Free Tier VM, without changing strategy code.

## Scope
- Keep current repo logic unchanged.
- Run paper trading continuously when your local machine is off.
- Add operational safety and restart behavior.

## Target Architecture
- Oracle Cloud Always Free VM (Ubuntu)
- Python virtual environment on VM
- Two systemd services:
  - `cryptosquid-bot.service` -> `python src/bot.py`
  - `cryptosquid-dashboard.service` -> `python src/dashboard.py`
- Optional reverse proxy for dashboard (Nginx + basic auth)

## Phase 1: Provision
1. Create VM in Oracle Cloud Free Tier
2. Open ports:
   - SSH: `22`
   - Dashboard (optional direct): `8787`
3. SSH into VM and create app directory (example):
   - `/opt/cryptosquid`

## Phase 2: Runtime Setup
1. Install OS packages
   - `python3`, `python3-venv`, `git`
2. Clone repo into `/opt/cryptosquid`
3. Create venv and install dependencies
4. Create `.env` on VM from your current local values

## Phase 3: Services
1. Copy service templates from `ops/oracle-free/systemd/`
2. Place into `/etc/systemd/system/`
3. Run:
   - `sudo systemctl daemon-reload`
   - `sudo systemctl enable --now cryptosquid-bot`
   - `sudo systemctl enable --now cryptosquid-dashboard`
4. Verify:
   - `sudo systemctl status cryptosquid-bot`
   - `sudo systemctl status cryptosquid-dashboard`

## Phase 4: Safety
- Keep `.env` in paper mode:
  - `LOG_ONLY=false`
  - `PAPER_MODE=true`
  - `ENABLE_LIVE_TRADING=false`
- Keep `TRADING_ENABLED=true` only while supervised
- Restrict dashboard exposure to trusted IPs or add auth

## Phase 5: Operations
- Logs:
  - `journalctl -u cryptosquid-bot -f`
  - `journalctl -u cryptosquid-dashboard -f`
- Restart:
  - `sudo systemctl restart cryptosquid-bot`
  - `sudo systemctl restart cryptosquid-dashboard`
- Stop:
  - `sudo systemctl stop cryptosquid-bot`
  - `sudo systemctl stop cryptosquid-dashboard`

## Success Criteria
- Services auto-start after reboot
- Dashboard reachable at VM IP on `:8787`
- `data/trades/runtime_state.json` updates every loop
- No strategy code changes required
