#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting SevenSplit Development Servers...${NC}"
echo ""

# Trap CTRL+C and kill all background processes
trap 'kill $(jobs -p) 2>/dev/null' EXIT

# Start backend in background
echo -e "${BLUE}[Backend]${NC} Starting FastAPI server with auto-reload..."
(
    cd backend
    source ../venv/bin/activate
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
) &

# Wait a bit for backend to start
sleep 2

# Start frontend in background
echo -e "${BLUE}[Frontend]${NC} Starting Vite dev server with HMR..."
(
    cd frontend
    npm run dev
) &

# Wait for both processes
echo ""
echo -e "${GREEN}✓ Both servers are running!${NC}"
echo -e "  ${BLUE}Backend:${NC}  http://localhost:8000"
echo -e "  ${BLUE}Frontend:${NC} http://localhost:5173"
echo ""
echo "Press CTRL+C to stop all servers"
echo ""

# Wait for all background jobs
wait
