# SevenSplit Setup Guide

## Prerequisites

- Python 3.8 or higher
- Node.js 18 or higher
- npm

## Installation

### 1. Clone the repository
```bash
git clone <repository-url>
cd SevenSplit
```

### 2. Install Python dependencies

**IMPORTANT**: If you have multiple Python installations (Homebrew, conda, system Python), make sure to install dependencies in the correct environment.

**Option A: Using conda (recommended if you have conda)**
```bash
# Make sure conda is active
conda activate base  # or your preferred environment
pip install -r requirements.txt
```

**Option B: Using pip**
```bash
pip install -r requirements.txt

# Or explicitly use pip3
pip3 install -r requirements.txt
```

**Option C: Using virtual environment (recommended for isolation)**
```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

**Verify installation:**
```bash
python3 -c "import fastapi, uvicorn, pyupbit; print('✓ All dependencies installed!')"
```

### 3. Install Frontend dependencies
```bash
cd frontend
npm install
cd ..
```

## Configuration

### For Mock Mode (Default)
No configuration needed! The system will use a virtual exchange with 10,000,000 KRW initial balance.

### For Real Trading Mode
1. Create a `.env` file in the `backend` directory:
```bash
cd backend
cp .env.example .env  # If example exists, or create new file
```

2. Add your Upbit API keys to `.env`:
```
UPBIT_ACCESS_KEY=your_access_key_here
UPBIT_SECRET_KEY=your_secret_key_here
UPBIT_OPEN_API_SERVER_URL=http://localhost:5001  # For mock mode
```

## Running the Application

### Quick Start - All Services
```bash
./run-dev.sh
```

This will start all three services:
- 🏦 **Mock Exchange**: http://localhost:5001
- 🤖 **Trading Bot API**: http://localhost:8000
- 📊 **Bot Dashboard**: http://localhost:5173

### Individual Services

**Start Mock Exchange only:**
```bash
./run-exchange.sh
```

**Start Trading Bot Backend only:**
```bash
./run-trading-bot.sh
```

**Start Frontend Dashboard only:**
```bash
./run-frontend.sh
```

## Troubleshooting

### Python Module Not Found

If you see `ModuleNotFoundError: No module named 'fastapi'`, install dependencies:

```bash
# Check which Python you're using
which python3
python3 --version

# Install dependencies
pip install -r requirements.txt

# Or use pip3 explicitly
pip3 install -r requirements.txt
```

### Port Already in Use

If you get "address already in use" error:

```bash
# Kill all processes on required ports
lsof -ti:5001,8000,5173 | xargs kill -9
```

### Frontend Dependencies Issue

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Python Version Issues

Make sure you're using Python 3.8+:
```bash
python3 --version
```

If you have multiple Python versions, you may need to use a specific one:
```bash
# Example: use python3.11 explicitly
python3.11 -m pip install -r requirements.txt
```

## Verification

After installation, verify all dependencies are installed:

```bash
# Check Python packages
python3 -c "import fastapi, uvicorn, pyupbit; print('✓ All Python packages OK')"

# Check Node packages
cd frontend && npm list --depth=0
```

## First Run

1. Start all services: `./run-dev.sh`
2. Open the Bot Dashboard: http://localhost:5173
3. Open the Exchange UI: http://localhost:5001
4. Start the bot from the dashboard
5. Control prices from the Exchange UI (Hold price and adjust)
6. Watch the bot execute trades automatically

## Development

### Hot Reload

All services support hot reload:
- **Backend**: Uvicorn auto-reloads on file changes
- **Frontend**: Vite HMR (Hot Module Replacement)
- **Exchange**: Uvicorn auto-reloads on file changes

### Logs

Logs are displayed in the terminal where you started the services.

### State Files

Bot state is saved in `backend/state_*.json` files. You can delete these to reset the bot state.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system architecture.
