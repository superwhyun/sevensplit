#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting SevenSplit in MOCK MODE...${NC}"
echo ""
echo -e "${PURPLE}Architecture:${NC}"
echo -e "  1. ${BLUE}Mock Exchange Server${NC} (Port ${PORT:-5001}) - API + Control Panel UI"
echo -e "  2. ${BLUE}Trading Bot Backend${NC} (Port 8000) - Strategy Execution"
echo -e "  3. ${BLUE}Bot Monitoring UI${NC} (Port 5173) - Dashboard"
echo ""

# Set Environment for Mock Mode
export ENV_FILE=".env.mock"

# Source the mock config to make variables available to shell
if [ -f "./backend/.env.mock" ]; then
    set -a # automatically export all variables
    source ./backend/.env.mock
    set +a
else
    echo -e "${RED}Error: backend/.env.mock not found${NC}"
    exit 1
fi

# Kill existing processes on ports 5001, 8000, 5173
echo -e "${YELLOW}Checking for processes on ports 5001, 8000, 5173...${NC}"
PIDS=$(lsof -ti:5001,8000,5173 2>/dev/null)
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

# Start Mock Exchange Server in background
echo -e "${BLUE}[Exchange]${NC} Starting Mock Exchange Server on ${HOST:-127.0.0.1}:${PORT:-5001}..."
(
    ./mock-exchange/run.sh
) &
EXCHANGE_PID=$!

# Wait a bit for exchange to start
sleep 2

# Start Trading Bot Backend in background
echo -e "${BLUE}[Bot]${NC} Starting Trading Bot Backend..."
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
echo -e "${GREEN}✓ All servers are running in MOCK MODE!${NC}"
echo ""
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  🏦 Mock Exchange:${NC}     http://localhost:5001"
echo -e "     ${YELLOW}→ Control prices, view exchange accounts${NC}"
echo ""
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
