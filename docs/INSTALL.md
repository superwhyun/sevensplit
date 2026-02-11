# Install

## Prerequisites
- Python 3.11+
- Node.js 22+
- npm

## Setup
```bash
python -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
```

## Environment
Create `backend/.env.real`:
```bash
UPBIT_ACCESS_KEY=your_access_key
UPBIT_SECRET_KEY=your_secret_key
UPBIT_OPEN_API_SERVER_URL=https://api.upbit.com
```

## Run
```bash
npm run dev
```

`npm run dev` uses `TRADING_MODE=DEV` by default (no real orders).
Use `./scripts/run-real.sh` for real trading mode.
