#!/bin/bash

# Run Mock Exchange Server (API + UI)
# Serves on http://localhost:5001

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/backend"

# Check if virtual environment exists and activate it
if [ -d "$SCRIPT_DIR/venv" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
fi

# Try to find Python with FastAPI
PYTHON_CMD=""

# Try conda python first
if [ -x "/opt/miniconda3/bin/python3" ]; then
    if /opt/miniconda3/bin/python3 -c "import fastapi" 2>/dev/null; then
        PYTHON_CMD="/opt/miniconda3/bin/python3"
    fi
fi

# Fall back to system python3
if [ -z "$PYTHON_CMD" ]; then
    PYTHON_CMD="python3"
fi

# Allow overriding host/port; default to 127.0.0.1:5001 to avoid sandbox bind errors
HOST=${HOST:-127.0.0.1}
PORT=${PORT:-5001}
HOST="$HOST" PORT="$PORT" exec $PYTHON_CMD mock_api_server.py
