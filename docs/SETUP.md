# Setup Notes

## Required env vars
- REAL mode:
  - `UPBIT_ACCESS_KEY`
  - `UPBIT_SECRET_KEY`

## Optional env vars
- `UPBIT_OPEN_API_SERVER_URL` (default: `https://api.upbit.com`)
- `DB_PATH` (default: `backend/sevensplit.db`)
- `CANDLE_DB_PATH` (default: `backend/market_data.db`)
- `PRICE_DB_PATH` (default: `backend/price_data.db`)
- `TRADING_MODE` (`REAL` or `DEV`)
- `DEV_INITIAL_KRW` (default: `10000000`)

## Mode guide
- `TRADING_MODE=REAL`: real orders are sent to Upbit (private API keys required).
- `TRADING_MODE=DEV`: no real orders, dev fills only; strategy logic/tick flow is the same.

Recommended for local dev:
- Keep `DB_PATH` separate (dev strategy state).
- Share `CANDLE_DB_PATH` and `PRICE_DB_PATH` with real for the same market data cache.

## Scripts
- `./scripts/run-real.sh`
- `npm run dev`
- `npm run build:docker`
