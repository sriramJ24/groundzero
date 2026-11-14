#!/usr/bin/env bash
# One command to run FIELDOS locally: builds the dashboard and serves it with the API on port 8000.
# Requirements: Python 3.10+ and Node 20+.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d backend/.venv ]; then
  echo "==> Creating Python environment"
  python3 -m venv backend/.venv
fi
backend/.venv/bin/pip install -q -r backend/requirements.txt

if [ ! -d frontend/dist ] || [ "${REBUILD:-0}" = "1" ]; then
  echo "==> Building dashboard"
  (cd frontend && npm install --no-audit --no-fund && npm run build)
fi

IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || echo "<LAPTOP_LAN_IP>")
echo
echo "  Dashboard:        http://localhost:8000"
echo "  Camera endpoint:  POST http://${IP}:8000/api/captures   (same Wi-Fi as the ESP32)"
echo
exec backend/.venv/bin/uvicorn app:app --app-dir backend --host 0.0.0.0 --port 8000
