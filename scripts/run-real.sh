#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

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
export TRADING_MODE="REAL"

# Source the real config
if [ -f "./backend/.env.real" ]; then
    echo -e "${YELLOW}Loading configuration from backend/.env.real...${NC}"
    set -a
    source ./backend/.env.real
    set +a
elif [ -f "./backend/.env.dev" ]; then
    echo -e "${YELLOW}Loading configuration from backend/.env.dev...${NC}"
    set -a
    source ./backend/.env.dev
    set +a
else
    echo -e "${RED}Error: Configuration file not found (backend/.env.real or backend/.env.dev)${NC}"
    exit 1
fi

# Check for API Keys
if [ -z "$UPBIT_ACCESS_KEY" ] || [ -z "$UPBIT_SECRET_KEY" ]; then
    echo -e "${RED}ERROR: UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY are missing.${NC}"
    echo -e "Please open ${BLUE}backend/.env.real${NC} and enter your actual Upbit API keys."
    exit 1
fi

# Kill existing processes on port 8000
echo -e "${YELLOW}Checking for processes on port 8000...${NC}"
PIDS=$(lsof -ti:8000 2>/dev/null)
if [ -n "$PIDS" ]; then
    echo -e "${YELLOW}Killing existing processes: $PIDS${NC}"
    echo "$PIDS" | xargs kill -9 2>/dev/null
    sleep 1
    echo -e "${GREEN}✓ Ports cleared${NC}"
else
    echo -e "${GREEN}✓ Port 8000 is free${NC}"
fi
echo ""

# Build Frontend
echo -e "${BLUE}[Frontend]${NC} Building static assets..."
cd frontend
npm run build
if [ $? -ne 0 ]; then
    echo -e "${RED}Frontend build failed!${NC}"
    exit 1
fi
cd ..
echo -e "${GREEN}✓ Frontend built successfully${NC}"
echo ""

# Trap CTRL+C and kill all background processes
cleanup() {
  echo ""
  echo -e "${YELLOW}Stopping server...${NC}"
  kill $(jobs -p) 2>/dev/null
  wait
  echo -e "${GREEN}Server stopped${NC}"
}
trap cleanup SIGINT SIGTERM EXIT

# Start Trading Bot Backend (which serves Frontend)
echo -e "${BLUE}[System]${NC} Starting SevenSplit (Backend + UI)..."
(
    ./backend/run.sh
) &
BOT_PID=$!

# Wait for server to start
sleep 2

# Display access information
echo ""
echo -e "${RED}✓ SevenSplit is running in REAL TRADING MODE!${NC}"
echo ""
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  🚀 Access URL:${NC}     http://localhost:8000"
echo -e "     ${YELLOW}→ Dashboard & API are both on this port${NC}"
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}Press CTRL+C to stop${NC}"
echo ""

# Wait for background jobs
wait
