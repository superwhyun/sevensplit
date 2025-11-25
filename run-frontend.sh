#!/bin/bash

# Run Trading Bot Monitoring UI
# Serves on http://localhost:5173

cd "$(dirname "$0")/frontend"
exec npm run dev
