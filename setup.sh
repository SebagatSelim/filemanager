#!/usr/bin/env bash
# One-time setup for macOS / Linux: Python packages, .env, database, demo data, Node packages.
# Start MySQL first (macOS: `brew services start mysql`, or XAMPP / MAMP), then run:  ./setup.sh
set -euo pipefail
cd "$(dirname "$0")"

trap 'echo; echo "Setup stopped because of an error (see the messages above)."; \
      echo "- Is MySQL running?  - Are Python 3.11+ and Node.js 20+ installed?"' ERR

PYTHON="${PYTHON:-python3}"
if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    echo "FileAI needs Python 3.11 or newer ($("$PYTHON" --version 2>&1 || echo "$PYTHON not found"))."
    echo "macOS: brew install python@3.12   then run:  PYTHON=python3.12 ./setup.sh"
    exit 1
fi

echo
echo "=== 1/5  Backend: Python virtual environment ==="
[ -d backend/.venv ] || "$PYTHON" -m venv backend/.venv
backend/.venv/bin/python -m pip install --upgrade pip >/dev/null
backend/.venv/bin/python -m pip install -q -r backend/requirements.txt

echo
echo "=== 2/5  Backend: settings file ==="
if [ ! -f backend/.env ]; then
    cp backend/.env.example backend/.env
    echo "Created backend/.env  (edit DATABASE_URL if your MySQL user has a password)"
else
    echo "backend/.env already exists - keeping it"
fi

echo
echo "=== 3/5  Database tables ==="
(cd backend && .venv/bin/python -m flask --app run.py init-db)

echo
echo "=== 4/5  Demo account and sample documents ==="
(cd backend && .venv/bin/python -m flask --app run.py seed-demo)

echo
echo "=== 5/5  Frontend: Node packages ==="
(cd frontend && npm install)

echo
echo "Setup complete. Run ./start-dev.sh to launch the app."
echo "Demo login: demo@fileai.test / Demo@12345"
