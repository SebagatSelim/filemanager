#!/usr/bin/env bash
# Starts the Flask API and the React app (macOS / Linux), then opens the browser. Ctrl+C stops both.
# Make sure MySQL is running and ./setup.sh has been run once.
set -euo pipefail
cd "$(dirname "$0")"

# macOS uses port 5000 for AirPlay Receiver, so there the API runs on 5001. Override with API_PORT=...
if [ -z "${API_PORT:-}" ]; then
    if [ "$(uname)" = "Darwin" ]; then API_PORT=5001; else API_PORT=5000; fi
fi

(cd backend && exec .venv/bin/python -m flask --app run.py run --port "$API_PORT") &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT INT TERM

(sleep 6; open "http://localhost:5173" 2>/dev/null || xdg-open "http://localhost:5173" 2>/dev/null || true) &

cd frontend
VITE_API_PROXY_TARGET="http://127.0.0.1:$API_PORT" npm run dev
