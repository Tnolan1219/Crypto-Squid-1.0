# Vultr Runbook (Copy/Paste)

Replace placeholders first:
- `<VPS_IP>`
- `<SSH_KEY_PATH>`
- `<YOUR_DOMAIN>`
- `<GITHUB_REPO_URL>`
- `<CONTROL_TOKEN>`

## 1) SSH to VPS
```bash
ssh -i <SSH_KEY_PATH> root@<VPS_IP>
```

## 2) Bootstrap server
```bash
apt update && apt install -y git
git clone <GITHUB_REPO_URL> /opt/cryptosquid
bash /opt/cryptosquid/ops/vultr/bootstrap_vultr.sh <GITHUB_REPO_URL>
```

## 3) Fill env
```bash
nano /opt/cryptosquid/.env
```

Set at minimum:
```env
ENV=production
TRADING_ENABLED=true
LOG_ONLY=false
PAPER_MODE=true
ENABLE_LIVE_TRADING=false

COINBASE_API_KEY_NAME=<your_key_name>
COINBASE_PRIVATE_KEY=<your_private_key>
SUPABASE_URL=<optional_or_blank>
SUPABASE_KEY=<optional_or_blank>

CONTROL_API_TOKEN=<CONTROL_TOKEN>
DASHBOARD_HOST=127.0.0.1
DASHBOARD_PORT=8787

RISK_PER_TRADE_PCT=0.50
MAX_TRADES_PER_DAY=3
MAX_CONSECUTIVE_LOSSES=2
DAILY_LOSS_LIMIT_PCT=1.0
```

## 4) Restart services
```bash
systemctl restart cryptosquid-engine cryptosquid-dashboard
systemctl status cryptosquid-engine --no-pager
systemctl status cryptosquid-dashboard --no-pager
```

## 5) Nginx domain
```bash
cp /opt/cryptosquid/ops/vultr/nginx/cryptosquid.conf /etc/nginx/sites-available/cryptosquid
sed -i 's/bot-api.yourdomain.com/bot-api.<YOUR_DOMAIN>/g' /etc/nginx/sites-available/cryptosquid
ln -sf /etc/nginx/sites-available/cryptosquid /etc/nginx/sites-enabled/cryptosquid
nginx -t && systemctl reload nginx
```

## 6) TLS
```bash
certbot --nginx -d bot-api.<YOUR_DOMAIN>
```

## 7) Validate API
```bash
curl https://bot-api.<YOUR_DOMAIN>/health
curl https://bot-api.<YOUR_DOMAIN>/snapshot
curl -H "Authorization: Bearer <CONTROL_TOKEN>" https://bot-api.<YOUR_DOMAIN>/control/status
curl -H "Authorization: Bearer <CONTROL_TOKEN>" -X POST https://bot-api.<YOUR_DOMAIN>/control/stop
curl -H "Authorization: Bearer <CONTROL_TOKEN>" -X POST https://bot-api.<YOUR_DOMAIN>/control/start
```

## 8) Deploy Vercel proxy app
From local machine:
```bash
cd ops/vercel-dashboard
npm i -g vercel
vercel --prod
```

In Vercel project settings -> Environment Variables:
- `TRADER_API_BASE_URL=https://bot-api.<YOUR_DOMAIN>`
- `TRADER_API_TOKEN=<CONTROL_TOKEN>`

Redeploy after adding vars.

## 9) Enable automatic VPS sync from GitHub main
```bash
chmod +x /opt/cryptosquid/ops/vultr/sync_from_github.sh
cp /opt/cryptosquid/ops/vultr/systemd/cryptosquid-sync.service /etc/systemd/system/
cp /opt/cryptosquid/ops/vultr/systemd/cryptosquid-sync.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now cryptosquid-sync.timer
systemctl start cryptosquid-sync.service
systemctl list-timers --all | grep cryptosquid-sync
```
