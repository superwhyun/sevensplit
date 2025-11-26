#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${RED}Starting SevenSplit in REAL TRADING MODE...${NC}"
echo -e "${RED}WARNING: Real money will be used for trading.${NC}"
echo ""
echo -e "${PURPLE}Architecture:${NC}"
echo -e "  1. ${BLUE}Trading Bot Backend${NC} (Port 8000) - Strategy Execution"
echo -e "  2. ${BLUE}Bot Monitoring UI${NC} (Port 5173) - Dashboard"
echo ""

# Set Environment for Real Mode
export ENV_FILE=".env.real"

# Source the real config
if [ -f "./backend/.env.real" ]; then
    echo -e "${YELLOW}Loading configuration from backend/.env.real...${NC}"
    set -a
    source ./backend/.env.real
    set +a
else
    echo -e "${RED}Error: backend/.env.real not found${NC}"
    exit 1
fi

# Check for API Keys
if [ -z "$UPBIT_ACCESS_KEY" ] || [ -z "$UPBIT_SECRET_KEY" ]; then
    echo -e "${RED}ERROR: UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY are missing.${NC}"
    echo -e "Please open ${BLUE}backend/.env.real${NC} and enter your actual Upbit API keys."
    exit 1
fi

# Kill existing processes on ports 8000, 5173 (NOT 5001, as we don't use mock server)
echo -e "${YELLOW}Checking for processes on ports 8000, 5173...${NC}"
PIDS=$(lsof -ti:8000,5173 2>/dev/null)
if [ -n "$PIDS" ]; then
    echo -e "${YELLOW}Killing existing processes: $PIDS${NC}"
    echo "$PIDS" | xargs kill -9 2>/dev/null
    sleep 1
    echo -e "${GREEN}✓ Ports cleared${NC}"
else
    echo -e "${GREEN}✓ All ports are free${NC}"
fi
echo ""

# Trap CTRL+C and kill all background processes
cleanup() {
  echo ""
  echo -e "${YELLOW}Stopping all servers...${NC}"
  kill $(jobs -p) 2>/dev/null
  wait
  echo -e "${GREEN}All servers stopped${NC}"
}
trap cleanup SIGINT SIGTERM EXIT

# Start Trading Bot Backend in background
echo -e "${BLUE}[Bot]${NC} Starting Trading Bot Backend (REAL MODE)..."
(
    ./backend/run.sh
) &
BOT_PID=$!

# Wait a bit for backend to start
sleep 2

# Start Frontend in background
echo -e "${BLUE}[Frontend]${NC} Starting Bot Monitoring UI..."
(
    ./frontend/run.sh
) &
FRONTEND_PID=$!

# Wait for servers to fully start
sleep 2

# Display access information
echo ""
echo -e "${RED}✓ All servers are running in REAL TRADING MODE!${NC}"
echo ""
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  🤖 Trading Bot API:${NC}   http://localhost:8000"
echo -e "     ${YELLOW}→ Backend API for bot operations${NC}"
echo ""
echo -e "${BLUE}  📊 Bot Dashboard:${NC}     http://localhost:5173"
echo -e "     ${YELLOW}→ Monitor bot status, trades, portfolio${NC}"
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}Press CTRL+C to stop all servers${NC}"
echo ""

# Wait for all background jobs
wait
