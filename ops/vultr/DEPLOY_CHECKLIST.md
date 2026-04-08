# Vultr Deploy Checklist (Production-Safe)

## 1) Prereqs
- [ ] Vultr Ubuntu 22.04/24.04 VPS created
- [ ] DNS A record created (example: `bot-api.yourdomain.com`)
- [ ] GitHub repo access ready (deploy key or PAT)
- [ ] Vercel project created for remote dashboard/proxy

## 2) VPS hardening
- [ ] Create non-root sudo user
- [ ] SSH keys only (`PasswordAuthentication no`)
- [ ] UFW fail-closed:
  - [ ] `ufw default deny incoming`
  - [ ] `ufw default allow outgoing`
  - [ ] allow `22/tcp`, `80/tcp`, `443/tcp`
- [ ] `fail2ban` installed and enabled
- [ ] unattended security updates enabled

## 3) Runtime install
- [ ] Install packages: `python3`, `python3-venv`, `python3-pip`, `git`, `nginx`, `certbot`, `python3-certbot-nginx`
- [ ] Clone repo to `/opt/cryptosquid`
- [ ] Create venv and install requirements
- [ ] Create `/opt/cryptosquid/.env` from `.env.example`
- [ ] Set `CONTROL_API_TOKEN` in `.env` (required)

## 4) Safe defaults
- [ ] `TRADING_ENABLED=true` (global gate can still be stopped remotely)
- [ ] `RISK_PER_TRADE_PCT=0.50`
- [ ] `MAX_TRADES_PER_DAY=3`
- [ ] `MAX_CONSECUTIVE_LOSSES=2`
- [ ] `DAILY_LOSS_LIMIT_PCT=1.0`
- [ ] `ENABLE_LIVE_TRADING=false` until explicit go-live signoff

## 5) systemd services
- [ ] Copy `ops/vultr/systemd/cryptosquid-engine.service` to `/etc/systemd/system/`
- [ ] Copy `ops/vultr/systemd/cryptosquid-dashboard.service` to `/etc/systemd/system/`
- [ ] `sudo systemctl daemon-reload`
- [ ] `sudo systemctl enable --now cryptosquid-engine`
- [ ] `sudo systemctl enable --now cryptosquid-dashboard`
- [ ] `systemctl status` both services show active

## 6) Nginx + TLS
- [ ] Copy `ops/vultr/nginx/cryptosquid.conf` to `/etc/nginx/sites-available/cryptosquid`
- [ ] Enable site and reload nginx
- [ ] Issue cert: `sudo certbot --nginx -d bot-api.yourdomain.com`
- [ ] Verify HTTPS works

## 7) Validate remote API
- [ ] `GET https://bot-api.yourdomain.com/health`
- [ ] `GET https://bot-api.yourdomain.com/snapshot`
- [ ] `GET https://bot-api.yourdomain.com/control/status` with Bearer token
- [ ] `GET https://bot-api.yourdomain.com/control/stop` disables trading
- [ ] `GET https://bot-api.yourdomain.com/control/start` re-enables trading

## 8) Vercel wiring
- [ ] Add Vercel env vars:
  - [ ] `TRADER_API_BASE_URL=https://bot-api.yourdomain.com`
  - [ ] `TRADER_API_TOKEN=<CONTROL_API_TOKEN>`
- [ ] Deploy dashboard/proxy app
- [ ] Confirm controls work from Vercel UI

## 9) Operational risk controls
- [ ] Verify kill switch behavior (`/control/stop` + `TRADING_ENABLED=false`)
- [ ] Verify service restart survives reboot
- [ ] Verify log rotation is configured
- [ ] Verify backup/restore plan for `data/`
