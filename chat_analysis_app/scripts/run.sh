#!/usr/bin/env bash
# HTTP :8000 redirects → HTTPS :8443 (mic needs HTTPS off-localhost).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CERT="$ROOT/certs/cert.pem"
KEY="$ROOT/certs/key.pem"
HOST_IP="${HOST_IP:-$(hostname -I 2>/dev/null | awk '{print $1}')}"
LOG="${LOG:-/tmp/northline.log}"
REDIR_LOG="${REDIR_LOG:-/tmp/northline-redirect.log}"
PID_FILE="${PID_FILE:-/tmp/northline.pid}"
REDIR_PID_FILE="${REDIR_PID_FILE:-/tmp/northline-redirect.pid}"

if [[ ! -f "$CERT" || ! -f "$KEY" ]]; then
  mkdir -p "$ROOT/certs"
  openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "$KEY" -out "$CERT" -days 825 \
    -subj "/CN=${HOST_IP:-localhost}" \
    -addext "subjectAltName=IP:${HOST_IP:-127.0.0.1},IP:127.0.0.1,DNS:localhost"
  echo "Created self-signed cert for ${HOST_IP:-localhost}"
fi

# Stop previous instances
if [[ -f "$PID_FILE" ]]; then
  kill "$(cat "$PID_FILE")" 2>/dev/null || true
  rm -f "$PID_FILE"
fi
if [[ -f "$REDIR_PID_FILE" ]]; then
  kill "$(cat "$REDIR_PID_FILE")" 2>/dev/null || true
  rm -f "$REDIR_PID_FILE"
fi
pkill -f 'uvicorn app.main:app' 2>/dev/null || true
pkill -f 'scripts/http_redirect.py' 2>/dev/null || true
sleep 1

export HF_HUB_OFFLINE=1
export HF_HOME="$ROOT/models/hf"
export LTP_PATH="$ROOT/models/languagetool"
export NORTHLINE_DEVICE="${NORTHLINE_DEVICE:-auto}"
# Help pip-installed NVIDIA cu11 libs resolve on Linux
for d in "$ROOT"/.venv/lib/python*/site-packages/nvidia/*/lib; do
  [[ -d "$d" ]] && export LD_LIBRARY_PATH="$d${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
done


nohup "$ROOT/.venv/bin/python" "$ROOT/scripts/http_redirect.py" >"$REDIR_LOG" 2>&1 &
echo $! >"$REDIR_PID_FILE"

nohup "$ROOT/.venv/bin/uvicorn" app.main:app \
  --host 0.0.0.0 --port 8443 --workers 1 \
  --ssl-certfile "$CERT" --ssl-keyfile "$KEY" \
  >"$LOG" 2>&1 &
echo $! >"$PID_FILE"

echo "Northline HTTPS: https://${HOST_IP:-127.0.0.1}:8443"
echo "HTTP redirect:  http://${HOST_IP:-127.0.0.1}:8000 → HTTPS"
echo "PIDs: app=$(cat "$PID_FILE") redirect=$(cat "$REDIR_PID_FILE")"
