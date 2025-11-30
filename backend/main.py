import os
import pyupbit
import asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from pydantic import BaseModel
from exchange import UpbitExchange
from strategy import SevenSplitStrategy, StrategyConfig
import threading
import time
import glob
import logging
import io
import csv
from typing import Dict, Any, List, Optional
from simulation import run_simulation, SimulationConfig

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment from backend/.env explicitly to ensure correct config even when run from repo root
BACKEND_DIR = os.path.dirname(__file__)
env_filename = os.getenv("ENV_FILE", ".env")
load_dotenv(os.path.join(BACKEND_DIR, env_filename))

app = FastAPI(title="Seven Split Bitcoin Bot")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Exchange and Strategy
from database import get_db

# Initialize DB handle (still used elsewhere)
db = get_db()

# Check for .env file
env_access_key = os.getenv("UPBIT_ACCESS_KEY")
env_secret_key = os.getenv("UPBIT_SECRET_KEY")
server_url_env = os.getenv("UPBIT_OPEN_API_SERVER_URL")
server_url = server_url_env if server_url_env else "https://api.upbit.com"
env_mode = os.getenv("MODE", "").upper()
current_mode = env_mode if env_mode else ("REAL" if env_access_key and env_secret_key else "MOCK")

# MODE in .env takes highest priority
if env_mode == "MOCK":
    # In mock mode, always talk to the server at UPBIT_OPEN_API_SERVER_URL (e.g., 5001 mock)
    # If URL not explicitly set, default to localhost mock server
    if not server_url_env:
        server_url = "http://localhost:5001"
        
    access_key = env_access_key or "mock_access_key"
    secret_key = env_secret_key or "mock_secret_key"
    exchange = UpbitExchange(access_key, secret_key, server_url=server_url)
    current_mode = "MOCK"
    print(f"Using Mock Exchange via API (forced by MODE=mock) URL: {server_url}")
elif env_mode == "REAL":
    # Force REAL; require keys from env
    access_key = env_access_key
    secret_key = env_secret_key
    exchange = UpbitExchange(access_key, secret_key, server_url=server_url)
    current_mode = "REAL"
    print(f"Using Upbit Exchange (forced by MODE=real) URL: {server_url}")
else:
    # Priority: .env settings first (always use the URL from .env), otherwise UpbitExchange with mock creds
    if env_access_key and env_secret_key:
        exchange = UpbitExchange(env_access_key, env_secret_key, server_url=server_url)
        current_mode = "REAL"
        print(f"Using Upbit Exchange from .env (URL: {server_url})")
    else:
        # If URL not explicitly set, default to localhost mock server for fallback mock mode
        if not server_url_env:
            server_url = "http://localhost:5001"
            
        exchange = UpbitExchange("mock_access_key", "mock_secret_key", server_url=server_url)
        current_mode = "MOCK"
        print(f"Using Upbit Exchange with default mock creds (URL: {server_url})")

# --- Strategy Management ---
strategies: Dict[int, SevenSplitStrategy] = {}

def load_strategies():
    """Load strategies from DB, or create defaults if none exist."""
    global strategies
    strategies = {}
    db_strategies = db.get_all_strategies()
    
    if not db_strategies:
        logging.info("No strategies found in DB. Please create one.")
    else:
        logging.info(f"Loading {len(db_strategies)} strategies from DB.")
        for s in db_strategies:
            strategies[s.id] = SevenSplitStrategy(exchange, s.id, s.ticker, s.budget)

load_strategies()

# --- WebSocket connection registry ---
ws_connections = set()

# Background thread for strategy tick
def run_strategies():
    # Track last tick time for each strategy
    last_tick_time = {s_id: 0.0 for s_id in strategies.keys()}
    
    while True:
        try:
            current_time = time.time()
            
            # Refresh strategy list keys in case of additions/deletions
            current_strategy_ids = list(strategies.keys())
            
            # Determine which strategies need to be ticked
            strategies_to_tick = []
            tickers_to_fetch = set()
            
            for s_id in current_strategy_ids:
                if s_id not in strategies: continue # Handle deletion race condition
                strategy = strategies[s_id]
                
                if s_id not in last_tick_time:
                    last_tick_time[s_id] = 0.0
                
                if strategy.is_running:
                    tick_interval = strategy.config.tick_interval
                    if current_time - last_tick_time[s_id] >= tick_interval:
                        strategies_to_tick.append(strategy)
                        tickers_to_fetch.add(strategy.ticker)
            
            if strategies_to_tick:
                # Batch fetch prices for all unique tickers needed
                prices = {}
                ticker_list = list(tickers_to_fetch)
                
                if ticker_list:
                    # Use exchange's get_current_prices method if available
                    if hasattr(exchange, "get_current_prices"):
                        prices = exchange.get_current_prices(ticker_list)
                    else:
                        # Fallback to individual price fetches
                        for ticker in ticker_list:
                            try:
                                price = exchange.get_current_price(ticker)
                                if price:
                                    prices[ticker] = price
                            except Exception as e:
                                logging.error(f"Failed to fetch price for {ticker}: {e}")

                # Tick strategies
                for strategy in strategies_to_tick:
                    price = prices.get(strategy.ticker)
                    if price:
                        strategy.tick(current_price=price)
                        last_tick_time[strategy.strategy_id] = current_time
                        
        except Exception as e:
            logging.error(f"Error in strategy loop: {e}")
            # Sleep longer on error to prevent rapid-fire logging/retries
            time.sleep(2.0)
        
        # Sleep for a short interval to avoid busy waiting
        time.sleep(0.1)

thread = threading.Thread(target=run_strategies, daemon=True)
thread.start()

# --- API Endpoints ---

class CreateStrategyRequest(BaseModel):
    name: str
    ticker: str
    budget: float = 1000000.0
    config: StrategyConfig

@app.get("/strategies")
def get_strategies():
    """List all strategies"""
    return [
        {
            "id": s.strategy_id,
            "name": db.get_strategy(s.strategy_id).name,
            "ticker": s.ticker,
            "budget": s.budget,
            "is_running": s.is_running
        }
        for s in strategies.values()
    ]

@app.post("/strategies")
def create_strategy(req: CreateStrategyRequest):
    """Create a new strategy"""
    try:
        s = db.create_strategy(
            name=req.name,
            ticker=req.ticker,
            budget=req.budget,
            config=req.config.dict()
        )
        strategies[s.id] = SevenSplitStrategy(exchange, s.id, s.ticker, s.budget)
        return {"status": "success", "strategy_id": s.id, "message": "Strategy created"}
    except Exception as e:
        logging.error(f"Failed to create strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/strategies/{strategy_id}")
def delete_strategy(strategy_id: int):
    """Delete a strategy"""
    if strategy_id not in strategies:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    try:
        # Stop if running
        if strategies[strategy_id].is_running:
            strategies[strategy_id].stop()
            
        # Remove from memory
        del strategies[strategy_id]
        
        # Remove from DB
        db.delete_strategy(strategy_id)
        
        return {"status": "success", "message": "Strategy deleted"}
    except Exception as e:
        logging.error(f"Failed to delete strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/strategies/{strategy_id}/export")
def export_trades(strategy_id: int):
    """Export trades to CSV"""
    trades = db.get_trades(strategy_id)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "ID", "Ticker", "Split ID", "Buy Price", "Sell Price", 
        "Volume", "Buy Amount", "Sell Amount", "Gross Profit", 
        "Total Fee", "Net Profit", "Profit Rate (%)", "Timestamp"
    ])
    
    for t in trades:
        writer.writerow([
            t.id, t.ticker, t.split_id, t.buy_price, t.sell_price,
            t.coin_volume, t.buy_amount, t.sell_amount, t.gross_profit,
            t.total_fee, t.net_profit, t.profit_rate, t.timestamp
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=trades_strategy_{strategy_id}.csv"}
    )

@app.get("/status")
def get_status(strategy_id: int):
    if strategy_id not in strategies:
        raise HTTPException(status_code=404, detail="Strategy not found")

    strategy = strategies[strategy_id]
    ticker = strategy.ticker

    # Batch fetch price for the requested ticker to avoid individual API call
    try:
        if hasattr(exchange, "get_current_prices"):
            prices = exchange.get_current_prices([ticker])
            current_price = prices.get(ticker)
        else:
            current_price = None
    except Exception as e:
        logging.error(f"Failed to fetch price for {ticker}: {e}")
        current_price = None

    state = strategy.get_state(current_price=current_price)
    # Mode flag
    state["mode"] = current_mode
    
    # Fetch accounts once to get both balances
    try:
        accounts_raw = exchange._request('GET', '/v1/accounts') if hasattr(exchange, '_request') else []
        balance_map = {acc['currency']: float(acc['balance']) for acc in accounts_raw}
    except Exception as e:
        logging.error(f"Failed to fetch accounts for status: {e}")
        balance_map = {}

    # Add Wallet Info
    state["balance_krw"] = balance_map.get("KRW", 0.0)
    currency = ticker.split("-")[1] if "-" in ticker else ticker
    state["balance_coin"] = balance_map.get(currency, 0.0)
    
    # Calculate Total Asset Value (KRW + Coin Value)
    # Note: This is a rough estimate using current price.
    current_price = state["current_price"]
    if current_price:
        state["total_asset_value"] = state["balance_krw"] + (state["balance_coin"] * current_price)
    else:
        state["total_asset_value"] = state["balance_krw"]

    return state


def get_full_snapshot() -> Dict[str, Any]:
    """Aggregate all strategies' status plus portfolio for websocket push."""
    snapshot = {"strategies": {}}
    
    # Collect all tickers needed
    all_tickers = list(set(s.ticker for s in strategies.values()))
    
    # Batch fetch prices for all tickers ONCE
    # Batch fetch prices for all tickers ONCE
    # Note: This might hit rate limits if called too frequently.
    # But since we removed rate limiting in exchange.py, we rely on Upbit's quota.
    try:
        if hasattr(exchange, "get_current_prices") and all_tickers:
            prices = exchange.get_current_prices(all_tickers)
        else:
            prices = {}
    except Exception as e:
        # logging.error(f"Failed to batch fetch prices: {e}") # Reduce noise
        prices = {}
    
    # Fetch Accounts (Raw) ONCE
    try:
        accounts_raw = exchange._request('GET', '/v1/accounts') if hasattr(exchange, '_request') else []
    except Exception as e:
        logging.error(f"Failed to fetch accounts: {e}")
        accounts_raw = []

    # Create Balance Map
    balance_map = {acc['currency']: float(acc['balance']) for acc in accounts_raw}

    for s_id, strategy in strategies.items():
        try:
            ticker = strategy.ticker
            # Get strategy state with pre-fetched price
            state = strategy.get_state(current_price=prices.get(ticker))
            
            # Add mode flag
            state["mode"] = current_mode
            
            # Add Wallet Info using cached balance map
            state["balance_krw"] = balance_map.get("KRW", 0.0)
            currency = ticker.split("-")[1] if "-" in ticker else ticker
            state["balance_coin"] = balance_map.get(currency, 0.0)
            
            # Calculate Total Asset Value
            current_price = state["current_price"]
            if current_price:
                state["total_asset_value"] = state["balance_krw"] + (state["balance_coin"] * current_price)
            else:
                state["total_asset_value"] = state["balance_krw"]
            
            snapshot["strategies"][s_id] = state
        except Exception as e:
            logging.error(f"Snapshot error for strategy {s_id}: {e}")
    
    # Get portfolio with pre-fetched prices and accounts
    snapshot["portfolio"] = _calculate_portfolio(prices, accounts_raw)
    
    return snapshot

@app.get("/accounts")
def get_accounts():
    """Expose detailed exchange account info for dashboard or debugging."""
    try:
        return exchange.get_accounts()
    except Exception as e:
        logging.error(f"Failed to fetch accounts: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch accounts")

@app.get("/candles")
def get_candles(market: str, count: int = 200):
    """Proxy endpoint for fetching candles"""
    try:
        if hasattr(exchange, "get_candles"):
            return exchange.get_candles(market, count)
        else:
            # Fallback for MockExchange if it doesn't implement get_candles
            # But we should implement it there too if needed.
            # For now, just return empty list or error
            return []
    except Exception as e:
        logging.error(f"Failed to fetch candles: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch candles")

class CommandRequest(BaseModel):
    strategy_id: int

@app.post("/start")
def start_bot(cmd: CommandRequest):
    if cmd.strategy_id not in strategies:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    strategy = strategies[cmd.strategy_id]
    
    # Fetch current price before starting to avoid individual API call
    try:
        if hasattr(exchange, "get_current_prices"):
            prices = exchange.get_current_prices([strategy.ticker])
            current_price = prices.get(strategy.ticker)
        else:
            current_price = None
    except Exception as e:
        logging.error(f"Failed to fetch price for {strategy.ticker}: {e}")
        current_price = None
    
    strategy.start(current_price=current_price)
    return {"status": "started", "strategy_id": cmd.strategy_id}

@app.post("/stop")
def stop_bot(cmd: CommandRequest):
    if cmd.strategy_id not in strategies:
        raise HTTPException(status_code=404, detail="Strategy not found")
    strategies[cmd.strategy_id].stop()
    return {"status": "stopped", "strategy_id": cmd.strategy_id}

class ConfigRequest(BaseModel):
    strategy_id: int
    config: StrategyConfig
    budget: Optional[float] = None

@app.post("/config")
def update_config(req: ConfigRequest):
    if req.strategy_id not in strategies:
        raise HTTPException(status_code=404, detail="Strategy not found")
    if req.budget is not None:
        strategies[req.strategy_id].budget = req.budget
    strategies[req.strategy_id].update_config(req.config)
    return {"status": "config updated", "strategy_id": req.strategy_id, "config": req.config, "budget": strategies[req.strategy_id].budget}

@app.post("/simulate")
def simulate_strategy(sim_config: SimulationConfig):
    """Run a simulation based on provided config and candles"""
    try:
        result = run_simulation(sim_config)
        return result
    except Exception as e:
        logging.error(f"Simulation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reset")
def reset_strategy(cmd: CommandRequest):
    """Reset a specific strategy"""
    s_id = cmd.strategy_id

    if s_id not in strategies:
        raise HTTPException(status_code=404, detail="Strategy not found")

    try:
        # Stop the strategy if running
        if strategies[s_id].is_running:
            strategies[s_id].stop()

        # Cancel all pending orders for this strategy
        strategy = strategies[s_id]
        for split in strategy.splits:
            if split.buy_order_uuid:
                try:
                    exchange.cancel_order(split.buy_order_uuid)
                except Exception as e:
                    logging.error(f"Failed to cancel buy order {split.buy_order_uuid}: {e}")
            if split.sell_order_uuid:
                try:
                    exchange.cancel_order(split.sell_order_uuid)
                except Exception as e:
                    logging.error(f"Failed to cancel sell order {split.sell_order_uuid}: {e}")

        # Clear splits and trades from database
        db.delete_all_splits(s_id)
        db.delete_all_trades(s_id)
        
        # Reset strategy state in DB (next_split_id, last_buy_price, etc.)
        db.update_strategy_state(
            s_id,
            next_split_id=1,
            last_buy_price=None,
            last_sell_price=None
        )

        # Recreate the strategy instance
        s_rec = db.get_strategy(s_id)
        strategies[s_id] = SevenSplitStrategy(exchange, s_id, s_rec.ticker, s_rec.budget)
        logging.info(f"Reset strategy {s_id}")

        return {"status": "success", "strategy_id": s_id, "message": f"Strategy reset for {s_id}"}
    except Exception as e:
        logging.error(f"Failed to reset strategy {s_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset: {str(e)}")

import requests

@app.post("/reset-all")
def reset_all_mock():
    """Reset all strategies and exchange (MOCK mode only)"""
    global exchange, strategies, current_mode

    # Only allow reset in MOCK mode
    if current_mode != "MOCK":
        return {"status": "not a mock exchange"}

    # Stop all strategies first
    for s_id, strategy in strategies.items():
        try:
            if strategy.is_running:
                strategy.stop()
        except Exception as e:
            print(f"Error stopping strategy {s_id}: {e}")

    # Reset database (Trading data only, preserve strategies)
    from database import get_db
    db_local = get_db()
    db_local.reset_trading_data()
    print("Database trading data reset complete")

    # Call Mock Server Reset Endpoint
    try:
        # server_url is global, e.g. http://localhost:5001
        resp = requests.post(f"{server_url}/mock/reset", timeout=5)
        if resp.status_code == 200:
            print("Mock server reset successful")
        else:
            print(f"Mock server reset failed: {resp.text}")
    except Exception as e:
        print(f"Failed to call mock server reset: {e}")

    # Reinitialize exchange pointing to mock server
    access_key = env_access_key or "mock_access_key"
    secret_key = env_secret_key or "mock_secret_key"
    exchange = UpbitExchange(access_key, secret_key, server_url=server_url)

    # Reload strategies (will load existing strategies from DB)
    load_strategies()

    return {"status": "mock reset", "message": "All strategies and database reset"}

def _calculate_portfolio(prices: dict = {}, accounts_raw: list = None):
    """Internal logic to calculate portfolio status"""
    portfolio = {
        "mode": current_mode,
        "coins": {},
        "accounts": []
    }

    # Get accounts - if prices are provided, use them to avoid redundant API calls
    if hasattr(exchange, "get_accounts"):
        if accounts_raw is not None:
             # Use provided raw accounts
             accounts = []
             for account in accounts_raw:
                currency = account.get('currency')
                balance = float(account.get('balance', 0))
                locked = float(account.get('locked', 0))
                ticker = f"KRW-{currency}" if currency and currency != 'KRW' else None
                current_price = 1.0 if currency == 'KRW' else prices.get(ticker, 0.0)
                total_balance = balance + locked
                value = total_balance * current_price if current_price else 0.0
                
                accounts.append({
                    **account,
                    "ticker": ticker,
                    "current_price": current_price,
                    "balance_value": value,
                    "total_balance": total_balance
                })
        elif prices:
            # Temporarily inject prices into accounts manually to avoid extra API call
            accounts_raw = exchange._request('GET', '/v1/accounts') if hasattr(exchange, '_request') else []
            accounts = []
            for account in accounts_raw:
                currency = account.get('currency')
                balance = float(account.get('balance', 0))
                locked = float(account.get('locked', 0))
                ticker = f"KRW-{currency}" if currency and currency != 'KRW' else None
                current_price = 1.0 if currency == 'KRW' else prices.get(ticker, 0.0)
                total_balance = balance + locked
                value = total_balance * current_price if current_price else 0.0
                
                accounts.append({
                    **account,
                    "ticker": ticker,
                    "current_price": current_price,
                    "balance_value": value,
                    "total_balance": total_balance
                })
        else:
            accounts = exchange.get_accounts()
    else:
        accounts = []
    # Normalize numeric fields in accounts to avoid stringy zeros
    normalized_accounts = []
    for acc in accounts:
        if not isinstance(acc, dict):
            continue
        normalized_accounts.append({
            **acc,
            "balance": float(acc.get("balance", 0.0) or 0.0),
            "locked": float(acc.get("locked", 0.0) or 0.0),
            "avg_buy_price": float(acc.get("avg_buy_price", 0.0) or 0.0),
            "current_price": float(acc.get("current_price", 0.0) or 0.0),
            "balance_value": float(acc.get("balance_value", 0.0) or 0.0),
            "total_balance": float(acc.get("total_balance", 0.0) or 0.0),
        })

    accounts = normalized_accounts
    portfolio["accounts"] = accounts

    # Seed KRW balance
    balance_krw = 0.0
    for acc in accounts:
        if acc.get("currency") == "KRW":
            balance_krw = float(acc.get("total_balance", acc.get("balance", 0.0)))
            break
    portfolio["balance_krw"] = balance_krw

    total_value = 0.0
    initial_balance = 10000000  # Initial mock balance, adjust as needed

    for acc in accounts:
        currency = acc.get("currency")
        ticker = acc.get("ticker")
        if currency == "KRW":
            total_value += balance_krw
            continue

        if not ticker:
            ticker = f"KRW-{currency}"
        coin = currency
        current_price = float(acc.get("current_price", 0.0) or 0.0)
        balance_val = float(acc.get("balance_value", 0.0) or 0.0)
        available = float(acc.get("balance", 0.0) or 0.0)
        locked = float(acc.get("locked", 0.0) or 0.0)
        total_balance = float(acc.get("total_balance", available + locked))

        portfolio["coins"][coin] = {
            "ticker": ticker,
            "balance": total_balance,
            "available": available,
            "locked": locked,
            "current_price": current_price,
            "value": balance_val,
            "avg_buy_price": float(acc.get("avg_buy_price", 0.0) or 0.0)
        }
        total_value += balance_val

    portfolio["total_value"] = total_value
    
    # Calculate Total Realized Profit from DB
    try:
        all_trades = db.get_all_trades()
        total_realized_profit = sum(t.net_profit for t in all_trades)
    except Exception as e:
        logging.error(f"Failed to calculate realized profit: {e}")
        total_realized_profit = 0.0

    portfolio["total_realized_profit"] = total_realized_profit
    
    # Add realized profit per coin
    for coin, data in portfolio["coins"].items():
        ticker = data["ticker"]
        try:
            # This is tricky now because trades are by strategy_id, not just ticker.
            # But we can still query by ticker if we wanted, but the DB method get_trades uses strategy_id now.
            # We need a method to get trades by ticker or just sum up all strategies for this ticker.
            # For now, let's just sum up all trades for this coin across all strategies.
            # Wait, db.get_all_trades() returns all trades. We can filter in memory.
            coin_trades = [t for t in all_trades if t.ticker == ticker]
            coin_profit = sum(t.net_profit for t in coin_trades)
            data["realized_profit"] = coin_profit
        except Exception:
            data["realized_profit"] = 0.0

    return portfolio


@app.get("/portfolio")
def get_portfolio():
    return _calculate_portfolio()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ws_connections.add(websocket)
    try:
        # Send initial snapshot immediately
        await websocket.send_json(get_full_snapshot())

        while True:
            # Simple heartbeat / polling loop
            await websocket.send_json(get_full_snapshot())
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
    finally:
        ws_connections.discard(websocket)


from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# ... (existing code) ...

# Serve frontend static files if they exist (Production/Docker mode)
# This assumes the frontend is built to ../frontend/dist
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

if os.path.exists(FRONTEND_DIST):
    # Mount assets directory
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    # Serve index.html at root
    @app.get("/")
    async def serve_spa_root():
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

    # Catch-all route for SPA (React Router)
    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        # Check if file exists in dist (e.g. favicon.ico, robots.txt)
        file_path = os.path.join(FRONTEND_DIST, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
            
        # Otherwise return index.html for client-side routing
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

else:
    @app.get("/")
    def read_root():
        return {"message": "Seven Split Bot API is running (Frontend build not found)"}
