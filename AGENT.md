# Seven Split Trading Bot - Project Documentation

## 1. Project Overview
The **Seven Split Trading Bot** is an automated cryptocurrency trading system designed to execute a grid-based "split" trading strategy. It interacts with the Upbit exchange (both real and mock) to automatically buy on price drops and sell on rebounds, aiming to accumulate profit through volatility.

## 2. Architecture
The project follows a microservices-like architecture with three main components:

### 2.1. Frontend (`/frontend`)
*   **Tech Stack:** React, Vite, Axios.
*   **Port:** 5173 (Development).
*   **Role:** User Interface for monitoring and control.
*   **Key Components:**
    *   **Dashboard:** Real-time view of portfolio, asset status, and active splits.
    *   **Config:** Form to adjust trading parameters (investment amount, buy/sell rates).
    *   **SplitCard/Grid Status:** Visual representation of individual trading positions.
    *   **WebSocket:** Receives real-time updates from the backend.

### 2.2. Backend (`/backend`)
*   **Tech Stack:** Python, FastAPI, SQLite, PyUpbit.
*   **Port:** 8000.
*   **Role:** Core trading logic and API server.
*   **Key Features:**
    *   **Strategy Engine:** Executes the `SevenSplitStrategy`.
    *   **Database:** Stores trade history, active splits, and configuration in `sevensplit.db`.
    *   **API:** REST endpoints for frontend interaction (`/status`, `/config`, `/start`, `/stop`).
    *   **WebSocket:** Pushes real-time state to the frontend.

### 2.3. Mock Exchange (`/mock-exchange`)
*   **Tech Stack:** Python, FastAPI.
*   **Port:** 5001.
*   **Role:** Simulates the Upbit API for safe testing and development.
*   **Key Features:**
    *   **Price Simulation:** Can fetch real prices from Upbit or be manually overridden.
    *   **Order Matching:** Simulates limit and market order execution in memory.
    *   **Control Panel:** Web UI (at `http://localhost:5001`) to manually set prices and control the market.
    *   **Recursion Protection:** Smartly handles live price fetching to avoid self-referential loops.

## 3. Trading Strategy: Seven Split (Hybrid Grid)
The bot implements a strategy that divides capital into multiple "splits" to average down costs and sell for profit.

### 3.1. Core Logic
1.  **Initial Entry:** Starts by creating a buy order (Split #1) at the current market price.
2.  **Buying (Averaging Down):**
    *   If the price drops by `buy_rate` (e.g., 0.5%) from the last buy price, a new buy order is placed.
    *   This creates a "grid" of buy orders as the price falls.
3.  **Selling (Taking Profit):**
    *   When a buy order is filled, a corresponding sell limit order is immediately placed.
    *   Target Sell Price = `Buy Price * (1 + sell_rate)`.
4.  **Rebuy Strategy (Looping):**
    *   When all positions are sold (cleared), the bot decides how to re-enter based on `rebuy_strategy`:
        *   `reset_on_clear`: Resets and buys immediately at the current price (Trend Following).
        *   `last_sell_price`: Waits for a drop from the last sell price (Balanced).
        *   `last_buy_price`: Only buys if price drops below the previous lowest buy (Conservative).

## 4. Key Features

### 4.1. Dashboard
*   **Portfolio Overview:** Total valuation, KRW balance, held coin volume, and unrealized P/L.
*   **Real-time Status:** WebSocket-driven updates for price and order status.
*   **Grid Status:** Table showing all active splits, their entry prices, and current P/L.
*   **Trade History:** Log of recent buy/sell executions with net profit calculations.

### 4.2. Modes
*   **MOCK Mode:**
    *   Uses the local Mock Exchange server.
    *   Safe for testing strategy logic without real money.
    *   Allows manual price manipulation to test "what-if" scenarios.
*   **REAL Mode:**
    *   Connects directly to Upbit API.
    *   Requires valid Access/Secret keys.
    *   Executes real trades.

## 5. Configuration Parameters
Users can adjust these settings via the Dashboard:

| Parameter | Description | Default |
| :--- | :--- | :--- |
| `investment_per_split` | Amount of KRW to invest in each split. | 100,000 |
| `min_price` | Minimum price safety floor (won't buy below this). | 50,000,000 |
| `buy_rate` | Price drop percentage to trigger a new buy. | 0.5% (0.005) |
| `sell_rate` | Profit percentage to trigger a sell. | 0.5% (0.005) |
| `tick_interval` | How often (in seconds) the bot checks prices. | 1.0s |
| `rebuy_strategy` | Behavior when all positions are cleared (see Strategy section). | `reset_on_clear` |

## 6. Development & Usage

### 6.1. Running the Project
The entire stack can be started with a single script:
```bash
./run-dev.sh
```
This script:
1.  Starts the Mock Exchange (Port 5001).
2.  Starts the Backend (Port 8000).
3.  Starts the Frontend (Port 5173).

### 6.2. Directory Structure
```
/
├── backend/            # Python FastAPI Backend
│   ├── main.py         # API Entry point
│   ├── strategy.py     # Trading Logic
│   └── database.py     # SQLite Interface
├── frontend/           # React Frontend
│   └── src/components/ # UI Components
├── mock-exchange/      # Mock Upbit Server
│   └── main.py         # Mock Logic
└── run-dev.sh          # Unified startup script
```

## 7. Current Status
*   **Implemented:**
    *   Full Seven Split strategy logic.
    *   Mock Exchange with live price fetching and manual override.
    *   Real-time Dashboard with WebSocket updates.
    *   Seamless switching between Mock and Real modes.
    *   Database persistence for bot state (survives restarts).
*   **Pending/Future Goals:**
    *   Advanced charting in Dashboard.
    *   Multi-ticker support (currently optimized for BTC, ETH, SOL).
    *   Backtesting engine.
