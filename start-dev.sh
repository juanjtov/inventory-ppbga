#!/bin/bash
# Premier Padel BGA — Start both development servers
# Usage: ./start-dev.sh

set -e

cleanup() {
  echo ""
  echo "Deteniendo servidores..."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
  echo "Servidores detenidos."
}

trap cleanup EXIT INT TERM

# Start backend
echo "Iniciando backend (FastAPI) en puerto 8000..."
cd backend
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Start frontend
echo "Iniciando frontend (Vite) en puerto 5173..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "========================================="
echo "  Premier Padel BGA — Servidores activos"
echo "========================================="
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo "  API docs: http://localhost:8000/docs"
echo "========================================="
echo "  Ctrl+C para detener ambos servidores"
echo "========================================="
echo ""

wait
