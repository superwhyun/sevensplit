#!/bin/bash

# Run Trading Bot Backend Server
# Serves on http://localhost:8000

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/backend"

# Check if virtual environment exists and activate it
if [ -d "$SCRIPT_DIR/venv" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
fi

# Try to find Python with uvicorn
UVICORN_CMD=""

# Try conda python's uvicorn first
if [ -x "/opt/miniconda3/bin/uvicorn" ]; then
    UVICORN_CMD="/opt/miniconda3/bin/uvicorn"
elif command -v uvicorn &> /dev/null; then
    UVICORN_CMD="uvicorn"
fi

if [ -z "$UVICORN_CMD" ]; then
    echo "Error: uvicorn not found. Please run: pip install -r requirements.txt"
    exit 1
fi

# Allow disabling reload to keep WebSocket connections stable by default
UVICORN_OPTS="--host 0.0.0.0 --port 8000"
if [ "${RELOAD:-0}" = "1" ]; then
    UVICORN_OPTS="--reload $UVICORN_OPTS"
fi

exec $UVICORN_CMD main:app $UVICORN_OPTS
