import os
import pyupbit
import asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel
from exchange import UpbitExchange
from strategy import SevenSplitStrategy, StrategyConfig
import threading
import time
import glob
import logging
from typing import Dict, Any

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
server_url = os.getenv("UPBIT_OPEN_API_SERVER_URL", "https://api.upbit.com")
env_mode = os.getenv("MODE", "").upper()
current_mode = env_mode if env_mode else ("REAL" if env_access_key and env_secret_key else "MOCK")

# MODE in .env takes highest priority
if env_mode == "MOCK":
    # In mock mode, always talk to the server at UPBIT_OPEN_API_SERVER_URL (e.g., 5001 mock)
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
        exchange = UpbitExchange("mock_access_key", "mock_secret_key", server_url=server_url)
        current_mode = "MOCK"
        print(f"Using Upbit Exchange with default mock creds (URL: {server_url})")

TICKERS = ["KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-XRP"]
strategies = {ticker: SevenSplitStrategy(exchange, ticker) for ticker in TICKERS}

# --- WebSocket connection registry ---
ws_connections = set()

# Background thread for strategy tick
def run_strategies():
    # Track last tick time for each ticker
    last_tick_time = {ticker: 0.0 for ticker in strategies.keys()}
    
    while True:
        try:
            current_time = time.time()
            
            # Determine which tickers need to be ticked based on their tick_interval
            tickers_to_tick = []
            for ticker, strategy in strategies.items():
                if strategy.is_running:
                    tick_interval = strategy.config.tick_interval
                    if current_time - last_tick_time[ticker] >= tick_interval:
                        tickers_to_tick.append(ticker)
            
            if tickers_to_tick:
                # Batch fetch prices for tickers that need ticking
                prices = {}
                
                # Use exchange's get_current_prices method if available
                if hasattr(exchange, "get_current_prices"):
                    prices = exchange.get_current_prices(tickers_to_tick)
                else:
                    # Fallback to individual price fetches
                    for ticker in tickers_to_tick:
                        try:
                            price = exchange.get_current_price(ticker)
                            if price:
                                prices[ticker] = price
                        except Exception as e:
                            logging.error(f"Failed to fetch price for {ticker}: {e}")

                # Tick strategies
                for ticker in tickers_to_tick:
                    price = prices.get(ticker)
                    if price:
                        strategies[ticker].tick(current_price=price)
                        last_tick_time[ticker] = current_time
                        
        except Exception as e:
            logging.error(f"Error in strategy loop: {e}")
        
        # Sleep for a short interval to avoid busy waiting
        time.sleep(0.1)

thread = threading.Thread(target=run_strategies, daemon=True)
thread.start()

@app.get("/")
def read_root():
    return {"message": "Seven Split Bot API is running"}

@app.get("/status")
def get_status(ticker: str = "KRW-BTC"):
    if ticker not in strategies:
        raise HTTPException(status_code=404, detail="Ticker not found")

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

    state = strategies[ticker].get_state(current_price=current_price)
    # Mode flag
    state["mode"] = current_mode
    
    # Add Wallet Info
    state["balance_krw"] = exchange.get_balance("KRW")
    state["balance_coin"] = exchange.get_balance(ticker)
    
    # Calculate Total Asset Value (KRW + Coin Value)
    # Note: This is a rough estimate using current price.
    current_price = state["current_price"]
    if current_price:
        state["total_asset_value"] = state["balance_krw"] + (state["balance_coin"] * current_price)
    else:
        state["total_asset_value"] = state["balance_krw"]

    return state


def get_full_snapshot() -> Dict[str, Any]:
    """Aggregate all tickers' status plus portfolio for websocket push."""
    snapshot = {"tickers": {}}
    
    # Batch fetch prices for all tickers ONCE
    try:
        if hasattr(exchange, "get_current_prices"):
            prices = exchange.get_current_prices(TICKERS)
        else:
            prices = {}
    except Exception as e:
        logging.error(f"Failed to batch fetch prices: {e}")
        prices = {}
    
    for ticker in TICKERS:
        try:
            # Get strategy state with pre-fetched price
            state = strategies[ticker].get_state(current_price=prices.get(ticker))
            
            # Add mode flag
            state["mode"] = current_mode
            
            # Add Wallet Info
            state["balance_krw"] = exchange.get_balance("KRW")
            state["balance_coin"] = exchange.get_balance(ticker)
            
            # Calculate Total Asset Value
            current_price = state["current_price"]
            if current_price:
                state["total_asset_value"] = state["balance_krw"] + (state["balance_coin"] * current_price)
            else:
                state["total_asset_value"] = state["balance_krw"]
            
            snapshot["tickers"][ticker] = state
        except Exception as e:
            logging.error(f"Snapshot error for {ticker}: {e}")
    
    # Get portfolio with pre-fetched prices
    snapshot["portfolio"] = get_portfolio(prices)
    
    return snapshot

@app.get("/accounts")
def get_accounts():
    """Expose detailed exchange account info for dashboard or debugging."""
    try:
        return exchange.get_accounts()
    except Exception as e:
        logging.error(f"Failed to fetch accounts: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch accounts")

class CommandRequest(BaseModel):
    ticker: str = "KRW-BTC"

@app.post("/start")
def start_bot(cmd: CommandRequest):
    if cmd.ticker not in strategies:
        raise HTTPException(status_code=404, detail="Ticker not found")
    
    # Fetch current price before starting to avoid individual API call
    try:
        if hasattr(exchange, "get_current_prices"):
            prices = exchange.get_current_prices([cmd.ticker])
            current_price = prices.get(cmd.ticker)
        else:
            current_price = None
    except Exception as e:
        logging.error(f"Failed to fetch price for {cmd.ticker}: {e}")
        current_price = None
    
    strategies[cmd.ticker].start(current_price=current_price)
    return {"status": "started", "ticker": cmd.ticker}

@app.post("/stop")
def stop_bot(cmd: CommandRequest):
    if cmd.ticker not in strategies:
        raise HTTPException(status_code=404, detail="Ticker not found")
    strategies[cmd.ticker].stop()
    return {"status": "stopped", "ticker": cmd.ticker}

class ConfigRequest(BaseModel):
    ticker: str = "KRW-BTC"
    config: StrategyConfig

@app.post("/config")
def update_config(req: ConfigRequest):
    if req.ticker not in strategies:
        raise HTTPException(status_code=404, detail="Ticker not found")
    strategies[req.ticker].update_config(req.config)
    return {"status": "config updated", "ticker": req.ticker, "config": req.config}

@app.post("/reset")
def reset_strategy(cmd: CommandRequest):
    """Reset a specific ticker's strategy"""
    ticker = cmd.ticker

    if ticker not in strategies:
        raise HTTPException(status_code=404, detail="Ticker not found")

    try:
        # Stop the strategy if running
        if strategies[ticker].is_running:
            strategies[ticker].stop()

        # Cancel all pending orders for this ticker
        strategy = strategies[ticker]
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
        db.delete_all_splits(ticker)
        db.delete_all_trades(ticker)

        # Recreate the strategy for this ticker only
        strategies[ticker] = SevenSplitStrategy(exchange, ticker)
        logging.info(f"Reset strategy for {ticker}")

        return {"status": "success", "ticker": ticker, "message": f"Strategy reset for {ticker}"}
    except Exception as e:
        logging.error(f"Failed to reset strategy for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset: {str(e)}")

@app.post("/reset-all")
def reset_all_mock():
    """Reset all strategies and exchange (MOCK mode only)"""
    global exchange, strategies, current_mode

    # Only allow reset in MOCK mode
    if current_mode != "MOCK":
        return {"status": "not a mock exchange"}

    # Stop all strategies first
    for ticker in TICKERS:
        try:
            if strategies[ticker].is_running:
                strategies[ticker].stop()
        except Exception as e:
            print(f"Error stopping strategy for {ticker}: {e}")

    # Reset database
    from database import get_db
    db_local = get_db()
    db_local.reset_all_data()
    print("Database reset complete")

    # Reinitialize exchange pointing to mock server
    access_key = env_access_key or "mock_access_key"
    secret_key = env_secret_key or "mock_secret_key"
    exchange = UpbitExchange(access_key, secret_key, server_url=server_url)

    # Recreate all strategies
    strategies = {}
    for ticker in TICKERS:
        strategies[ticker] = SevenSplitStrategy(exchange, ticker)
        print(f"Recreated strategy for {ticker}")

    return {"status": "mock reset", "message": "All strategies and database reset"}

@app.get("/portfolio")
def get_portfolio(prices: dict = {}):
    """Get overall portfolio status across all tickers"""
    portfolio = {
        "mode": current_mode,
        "coins": {},
        "accounts": []
    }

    # Get accounts - if prices are provided, use them to avoid redundant API calls
    if hasattr(exchange, "get_accounts"):
        if prices:
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
            trades = db.get_trades(ticker)
            coin_profit = sum(t.net_profit for t in trades)
            data["realized_profit"] = coin_profit
        except Exception:
            data["realized_profit"] = 0.0

    return portfolio


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


