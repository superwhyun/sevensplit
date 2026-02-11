# Architecture

SevenSplit is a two-part system:

1. Backend (`backend/`)
- FastAPI API + strategy engine
- Upbit integration
- SQLite persistence

2. Frontend (`frontend/`)
- React + Vite dashboard
- Calls backend REST/WebSocket endpoints

## Runtime flow
- `backend/main.py` starts API and strategy loop.
- `backend/core/engine.py` fetches prices/candles/orders and ticks each strategy.
- Strategy logic lives under `backend/strategy.py` and `backend/strategies/`.

## Data stores
- Trading DB: `DB_PATH` (default: `backend/sevensplit.db`)
- Candle DB: `CANDLE_DB_PATH` (default: `backend/market_data.db`)

## Deployment
- Local dev: `npm run dev`
- Docker build: `npm run build:docker`
