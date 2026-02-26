#!/usr/bin/env bash
# Levanta la app en local: backend + frontend.
# Pre-requisito: PostgreSQL corriendo en localhost:5432.
#   Con Homebrew: brew services start postgresql@15 && createdb invoice_automation

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# ── 1. PostgreSQL ───────────────────────────────────────────────────────────
_port_open() { python3 -c "
import socket; s=socket.socket(); s.settimeout(1)
try: s.connect(('127.0.0.1',$1)); s.close(); exit(0)
except: exit(1)
" 2>/dev/null; }

if ! _port_open 5432; then
  echo "❌  PostgreSQL no responde en localhost:5432."
  echo ""
  echo "  Con Homebrew:"
  echo "    brew services start postgresql@15"
  echo "    export PATH=\"/opt/homebrew/opt/postgresql@15/bin:\$PATH\""
  echo "    createdb invoice_automation"
  exit 1
fi
echo "✅  PostgreSQL OK"

# ── 2. Puerto del backend (5000 puede estar en uso por AirPlay en Mac) ─────
BACKEND_PORT=5000
if _port_open 5000; then
  echo "⚠️   Puerto 5000 ocupado (¿AirPlay Receiver?). Usando 5001."
  echo "    Para liberar: Ajustes > General > AirDrop y Handoff > desactivar Receptor AirPlay."
  BACKEND_PORT=5001
fi
export PORT=$BACKEND_PORT

# ── 3. .env del frontend apunta al puerto correcto ────────────────────────
FRONTEND_ENV="$ROOT/frontend/.env"
echo "REACT_APP_API_URL=http://localhost:$BACKEND_PORT" > "$FRONTEND_ENV"

# ── 4. Backend: venv, dependencias y migraciones ──────────────────────────
if [ ! -d "$ROOT/backend/venv" ]; then
  echo "Creando venv e instalando dependencias del backend..."
  cd "$ROOT/backend" && python3 -m venv venv && ./venv/bin/pip install -q -r requirements.txt
  cd "$ROOT"
fi

cd "$ROOT/backend"
export FLASK_APP=app.app
echo "Aplicando migraciones..."
./venv/bin/flask db upgrade
echo "✅  Migraciones OK. Iniciando backend en http://localhost:$BACKEND_PORT"
PORT=$BACKEND_PORT ./venv/bin/python -m app.app &
BACKEND_PID=$!
cd "$ROOT"

# ── 5. Frontend ────────────────────────────────────────────────────────────
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "Instalando dependencias del frontend..."
  cd "$ROOT/frontend" && npm install && cd "$ROOT"
fi
echo "Iniciando frontend en http://localhost:3000"
cd "$ROOT/frontend" && npm start &
FRONTEND_PID=$!
cd "$ROOT"

echo ""
echo "════════════════════════════════════════"
echo "  App local:  http://localhost:3000"
echo "  Backend:    http://localhost:$BACKEND_PORT"
echo "  Ctrl+C para parar ambos procesos."
echo "════════════════════════════════════════"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT INT TERM
wait
