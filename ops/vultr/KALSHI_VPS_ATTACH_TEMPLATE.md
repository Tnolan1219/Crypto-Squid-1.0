# Kalshi Strategy: Same VPS Attach Template (Separate Repo + Separate Vercel)

Use this exact template to attach your Kalshi bot to the SAME VPS with isolated paths/services/domain/dashboard.

## 1) Naming convention (replace once and keep consistent)

- Repo: `<KALSHI_REPO_URL>`
- VPS app dir: `/opt/kalshi-bot`
- Linux user: `kalshibot`
- Services:
  - `kalshi-engine.service`
  - `kalshi-dashboard.service`
  - `kalshi-sync.service`
  - `kalshi-sync.timer`
- Nginx host: `kalshi-api.<your-domain>`
- Vercel project: `kalshi-<name>`

## 2) Minimal folder requirements in Kalshi repo

- `scripts/run_all.py` (single runtime entrypoint)
- dashboard API server with:
  - `GET /health`
  - `GET /snapshot`
  - `GET|POST /control/start`
  - `GET|POST /control/stop`
  - `GET /control/status`
- `.env.example` with:
  - `TRADING_ENABLED`, `PAPER_MODE`, `ENABLE_LIVE_TRADING`
  - `CONTROL_API_TOKEN`
  - strategy credentials
- `ops/vultr/systemd/*.service`
- `ops/vultr/nginx/*.conf`
- `ops/vultr/sync_from_github.sh`

## 3) VPS bootstrap for Kalshi app (one-time)

```bash
apt update && apt install -y python3 python3-venv python3-pip git nginx certbot python3-certbot-nginx ufw fail2ban unattended-upgrades unzip rsync curl
useradd -m -s /bin/bash kalshibot || true
mkdir -p /opt/kalshi-bot
chown -R kalshibot:kalshibot /opt/kalshi-bot
```

## 4) Initial deploy to `/opt/kalshi-bot`

Choose one:

- Git clone (if auth is ready)
- SFTP upload (same method we used for Crypto Squid when repo auth blocked)

Then:
```bash
cd /opt/kalshi-bot
sudo -u kalshibot python3 -m venv .venv
sudo -u kalshibot .venv/bin/pip install --upgrade pip
sudo -u kalshibot .venv/bin/pip install -r requirements.txt
cp .env.example .env
chown kalshibot:kalshibot .env
chmod 600 .env
```

## 5) Systemd attach

```bash
cp /opt/kalshi-bot/ops/vultr/systemd/kalshi-engine.service /etc/systemd/system/
cp /opt/kalshi-bot/ops/vultr/systemd/kalshi-dashboard.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now kalshi-engine kalshi-dashboard
```

## 6) Nginx + TLS attach

```bash
cp /opt/kalshi-bot/ops/vultr/nginx/kalshi.conf /etc/nginx/sites-available/kalshi
ln -sf /etc/nginx/sites-available/kalshi /etc/nginx/sites-enabled/kalshi
nginx -t && systemctl reload nginx
certbot --nginx -d kalshi-api.<your-domain>
```

## 7) Auto-sync attach (main -> VPS every minute)

```bash
chmod +x /opt/kalshi-bot/ops/vultr/sync_from_github.sh
cp /opt/kalshi-bot/ops/vultr/systemd/kalshi-sync.service /etc/systemd/system/
cp /opt/kalshi-bot/ops/vultr/systemd/kalshi-sync.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now kalshi-sync.timer
systemctl start kalshi-sync.service
systemctl list-timers --all | grep kalshi-sync
```

## 8) Vercel attach (separate project)

Create a separate Vercel project and set:

- `TRADER_API_BASE_URL=https://kalshi-api.<your-domain>`
- `TRADER_API_TOKEN=<KALSHI_CONTROL_API_TOKEN>`

Deploy dashboard from Kalshi repo root (or its dashboard folder).

## 9) Isolation rules (critical)

- Never reuse Crypto Squid service names for Kalshi.
- Never share `.env` between bots.
- Separate API domains and Vercel projects.
- Separate data paths:
  - `/opt/kalshi-bot/data/...`
  - `/opt/kalshi-bot/reports/...`
  - `/opt/kalshi-bot/journal/...`

## 10) Exact attach checklist (copy/paste for other folders)

1. Create isolated app dir + user.
2. Deploy code and install venv deps.
3. Fill `.env` with paper defaults + token.
4. Register engine/dashboard systemd units.
5. Set Nginx reverse proxy + TLS domain.
6. Add sync script + sync timer.
7. Deploy separate Vercel proxy/dashboard project.
8. Verify `/health`, `/snapshot`, control stop/start/status.
9. Verify services auto-restart and sync timer active.
