#!/bin/bash
cd backend
source ../venv/bin/activate

# Load .env if exists
if [ -f .env ]; then
  export $(cat .env | grep -v '#' | awk '/=/ {print $1}')
fi

# Function to kill background jobs on exit
cleanup() {
  echo "Stopping backend servers..."
  kill $(jobs -p) 2>/dev/null
  wait
}
trap cleanup SIGINT SIGTERM EXIT

echo "Starting Mock Server on port 5001..."
uvicorn mock_api_server:app --reload --host 0.0.0.0 --port 5001 &
# Wait a bit for mock server to initialize
sleep 1

echo "Starting Main Bot Server on port 8000..."
uvicorn main:app --reload --host 0.0.0.0 --port 8000
