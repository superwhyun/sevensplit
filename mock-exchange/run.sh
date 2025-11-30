#!/bin/bash
cd "$(dirname "$0")"
if [ -d "../venv" ]; then
    source "../venv/bin/activate"
fi
if [ -f .env ]; then
  export $(cat .env | xargs)
fi
export HOST=0.0.0.0
uvicorn main:app --host 0.0.0.0 --port ${PORT:-5001} --reload --no-access-log
