# Oracle Free Deploy Checklist

## Preflight
- [ ] Oracle account created
- [ ] Always Free VM provisioned (Ubuntu)
- [ ] SSH key configured
- [ ] Security list allows SSH (22)
- [ ] Optional: security list allows dashboard port (8787)

## VM Setup
- [ ] `sudo apt update && sudo apt install -y python3 python3-venv git`
- [ ] `sudo mkdir -p /opt/cryptosquid`
- [ ] Repo cloned to `/opt/cryptosquid`
- [ ] Venv created and dependencies installed

## App Config
- [ ] `.env` created in `/opt/cryptosquid/.env`
- [ ] Paper mode flags set:
  - [ ] `LOG_ONLY=false`
  - [ ] `PAPER_MODE=true`
  - [ ] `ENABLE_LIVE_TRADING=false`

## Services
- [ ] Copy service files from `ops/oracle-free/systemd/` to `/etc/systemd/system/`
- [ ] `sudo systemctl daemon-reload`
- [ ] `sudo systemctl enable --now cryptosquid-bot`
- [ ] `sudo systemctl enable --now cryptosquid-dashboard`
- [ ] `sudo systemctl status cryptosquid-bot`
- [ ] `sudo systemctl status cryptosquid-dashboard`

## Validation
- [ ] Dashboard loads at `http://<vm-ip>:8787`
- [ ] `runtime_state.json` is updating
- [ ] Bot logs show normal ticks and no repeated exceptions
