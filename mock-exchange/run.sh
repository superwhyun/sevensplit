#!/bin/bash
cd "$(dirname "$0")"
if [ -d "../venv" ]; then
    source "../venv/bin/activate"
fi
if [ -f .env ]; then
  export $(cat .env | xargs)
fi
export HOST=0.0.0.0
python main.py
