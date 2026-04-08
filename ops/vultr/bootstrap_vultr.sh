#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   sudo bash ops/vultr/bootstrap_vultr.sh <github_repo_url>
# Example:
#   sudo bash ops/vultr/bootstrap_vultr.sh https://github.com/Tnolan1219/Crypto-Squid-1.0.git

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

REPO_URL="${1:-}"
if [[ -z "$REPO_URL" ]]; then
  echo "Missing repo URL argument."
  exit 1
fi

APP_USER="cryptosquid"
APP_DIR="/opt/cryptosquid"

apt update
apt install -y python3 python3-venv python3-pip git nginx certbot python3-certbot-nginx ufw fail2ban unattended-upgrades

if ! id -u "$APP_USER" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "$APP_USER"
fi

mkdir -p "$APP_DIR"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

sudo -u "$APP_USER" bash -lc "if [[ ! -d '$APP_DIR/.git' ]]; then git clone '$REPO_URL' '$APP_DIR'; fi"
sudo -u "$APP_USER" bash -lc "cd '$APP_DIR' && python3 -m venv .venv && .venv/bin/pip install --upgrade pip && .venv/bin/pip install -r requirements.txt"

if [[ ! -f "$APP_DIR/.env" ]]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  chown "$APP_USER":"$APP_USER" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
fi

cp "$APP_DIR/ops/vultr/systemd/cryptosquid-engine.service" /etc/systemd/system/cryptosquid-engine.service
cp "$APP_DIR/ops/vultr/systemd/cryptosquid-dashboard.service" /etc/systemd/system/cryptosquid-dashboard.service

systemctl daemon-reload
systemctl enable cryptosquid-engine
systemctl enable cryptosquid-dashboard

ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

systemctl enable --now fail2ban
systemctl enable --now unattended-upgrades || true

cp "$APP_DIR/ops/vultr/logrotate/cryptosquid" /etc/logrotate.d/cryptosquid

echo
echo "Bootstrap complete. Services are registered but NOT yet started."
echo ""
echo "REQUIRED before starting services:"
echo "  1) Edit $APP_DIR/.env:"
echo "       nano $APP_DIR/.env"
echo "     Set: COINBASE_API_KEY_NAME, COINBASE_PRIVATE_KEY, CONTROL_API_TOKEN"
echo ""
echo "  2) Validate env:"
echo "       sudo -u $APP_USER $APP_DIR/.venv/bin/python $APP_DIR/scripts/test_env.py"
echo ""
echo "  3) Start services:"
echo "       systemctl start cryptosquid-engine cryptosquid-dashboard"
echo "       systemctl status cryptosquid-engine cryptosquid-dashboard --no-pager"
echo ""
echo "  4) Configure Nginx:"
echo "       cp $APP_DIR/ops/vultr/nginx/cryptosquid.conf /etc/nginx/sites-available/cryptosquid"
echo "       ln -sf /etc/nginx/sites-available/cryptosquid /etc/nginx/sites-enabled/cryptosquid"
echo "       nginx -t && systemctl reload nginx"
echo ""
echo "  5) Issue TLS cert: certbot --nginx -d bot-api.<YOUR_DOMAIN>"
