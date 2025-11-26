#!/bin/bash
cd "$(dirname "$0")"
if [ -d "../venv" ]; then
    source "../venv/bin/activate"
fi
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --no-access-log
