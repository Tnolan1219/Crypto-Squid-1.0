#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/cryptosquid"
APP_USER="cryptosquid"
SYNC_STATE_DIR="${APP_DIR}/data/control"
SYNC_STAMP="${SYNC_STATE_DIR}/last_sync.json"
ZIP_URL="${ZIP_URL:-https://codeload.github.com/Tnolan1219/Crypto-Squid-1.0/zip/refs/heads/main}"
TMP_ROOT="/tmp/cryptosquid-sync"
ZIP_PATH="${TMP_ROOT}/main.zip"
EXTRACT_DIR="${TMP_ROOT}/extract"
SRC_DIR="${EXTRACT_DIR}/Crypto-Squid-1.0-main"

mkdir -p "${TMP_ROOT}" "${EXTRACT_DIR}" "${SYNC_STATE_DIR}"

if ! command -v curl >/dev/null 2>&1; then
  apt-get update -qq && apt-get install -y -qq curl
fi
if ! command -v unzip >/dev/null 2>&1; then
  apt-get update -qq && apt-get install -y -qq unzip
fi
if ! command -v rsync >/dev/null 2>&1; then
  apt-get update -qq && apt-get install -y -qq rsync
fi

curl -fsSL "${ZIP_URL}" -o "${ZIP_PATH}"
rm -rf "${EXTRACT_DIR}" && mkdir -p "${EXTRACT_DIR}"
unzip -q "${ZIP_PATH}" -d "${EXTRACT_DIR}"

if [[ ! -d "${SRC_DIR}" ]]; then
  echo "Sync source directory not found: ${SRC_DIR}"
  exit 1
fi

rsync -a --delete \
  --exclude ".env" \
  --exclude ".venv" \
  --exclude "data/" \
  --exclude "logs/" \
  --exclude "journal/raw-trades/" \
  --exclude "reports/daily/" \
  --exclude "reports/weekly/" \
  --exclude ".vercel/" \
  --exclude "node_modules/" \
  "${SRC_DIR}/" "${APP_DIR}/"

chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

if [[ ! -x "${APP_DIR}/.venv/bin/python" ]]; then
  sudo -u "${APP_USER}" python3 -m venv "${APP_DIR}/.venv"
fi

sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/pip" install --upgrade pip -q
sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt" -q

systemctl restart cryptosquid-engine cryptosquid-dashboard

python3 - <<'PY'
import json, time
from pathlib import Path
path = Path('/opt/cryptosquid/data/control/last_sync.json')
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps({
    'synced_at_unix': int(time.time()),
    'source': 'github-main-zip',
}, separators=(',', ':')))
PY

rm -rf "${TMP_ROOT}"
echo "sync complete"
