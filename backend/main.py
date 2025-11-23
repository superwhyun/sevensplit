import os
import pyupbit
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel
from exchange import UpbitExchange, MockExchange
from strategy import SevenSplitStrategy, StrategyConfig
import threading
import time
import glob
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

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
access_key = os.getenv("UPBIT_ACCESS_KEY")
secret_key = os.getenv("UPBIT_SECRET_KEY")

if access_key and secret_key:
    exchange = UpbitExchange(access_key, secret_key)
    print("Using Real Upbit Exchange")
else:
    exchange = MockExchange()
    print("Using Mock Exchange")

TICKERS = ["KRW-BTC", "KRW-ETH", "KRW-SOL"]
strategies = {ticker: SevenSplitStrategy(exchange, ticker) for ticker in TICKERS}

# Background thread for strategy tick
def run_strategies():
    while True:
        try:
            # Batch fetch prices for all tickers
            tickers = list(strategies.keys())
            if tickers:
                # For mock exchange, check if any ticker is held
                # If held, use the held price instead of fetching live
                prices = {}

                if isinstance(exchange, MockExchange):
                    for ticker in tickers:
                        if exchange.is_price_held(ticker):
                            # Use held price
                            prices[ticker] = exchange.get_current_price(ticker)
                        else:
                            # Fetch live price
                            try:
                                live_price = pyupbit.get_current_price(ticker)
                                if live_price:
                                    prices[ticker] = live_price
                                    # Update exchange cache
                                    exchange.price[ticker] = live_price
                            except Exception as e:
                                logging.error(f"Failed to fetch price for {ticker}: {e}")
                else:
                    # Real exchange: fetch all prices at once
                    fetched_prices = pyupbit.get_current_price(tickers)

                    # Normalize to dict if single float returned
                    if isinstance(fetched_prices, (int, float)):
                        prices = {tickers[0]: fetched_prices}
                    elif fetched_prices is None:
                        prices = {}
                    else:
                        prices = fetched_prices

                for ticker, strategy in strategies.items():
                    if strategy.is_running:
                        price = prices.get(ticker)
                        if price:
                            strategy.tick(current_price=price)
        except Exception as e:
            print(f"Error in strategy loop: {e}")
        time.sleep(1) # Tick every 1 second

thread = threading.Thread(target=run_strategies, daemon=True)
thread.start()

@app.get("/")
def read_root():
    return {"message": "Seven Split Bot API is running"}

@app.get("/status")
def get_status(ticker: str = "KRW-BTC"):
    if ticker not in strategies:
        raise HTTPException(status_code=404, detail="Ticker not found")
    
    state = strategies[ticker].get_state()
    state["mode"] = "REAL" if isinstance(exchange, UpbitExchange) else "MOCK"
    
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

class CommandRequest(BaseModel):
    ticker: str = "KRW-BTC"

@app.post("/start")
def start_bot(cmd: CommandRequest):
    if cmd.ticker not in strategies:
        raise HTTPException(status_code=404, detail="Ticker not found")
    strategies[cmd.ticker].start()
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
def reset_mock():
    global exchange, strategies

    # Helper to reset mock state for testing
    if isinstance(exchange, MockExchange):
        # Stop all strategies first
        for ticker in TICKERS:
            try:
                if strategies[ticker].is_running:
                    strategies[ticker].stop()
            except Exception as e:
                print(f"Error stopping strategy for {ticker}: {e}")

        # Delete all state files in backend directory
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        state_files = glob.glob(os.path.join(backend_dir, "state_*.json"))
        deleted_files = []
        for file in state_files:
            try:
                os.remove(file)
                deleted_files.append(file)
                print(f"Deleted {file}")
            except Exception as e:
                print(f"Failed to delete {file}: {e}")

        # Completely reinitialize exchange
        exchange = MockExchange()

        # Recreate all strategies
        strategies = {}
        for ticker in TICKERS:
            strategies[ticker] = SevenSplitStrategy(exchange, ticker)
            print(f"Recreated strategy for {ticker}")

        return {"status": "mock reset", "deleted_files": deleted_files}
    return {"status": "not a mock exchange"}

class PriceOverrideRequest(BaseModel):
    ticker: str
    price: float

@app.post("/override-price")
def override_price(req: PriceOverrideRequest):
    if not isinstance(exchange, MockExchange):
        raise HTTPException(status_code=400, detail="Only available in mock mode")

    print(f"Setting price for {req.ticker} to {req.price}")
    exchange.set_mock_price(req.ticker, req.price)

    # Verify the price was set
    current = exchange.get_current_price(req.ticker)
    print(f"Current price for {req.ticker} is now: {current}")

    return {"status": "price overridden", "ticker": req.ticker, "price": req.price, "current_price": current}

class PriceHoldRequest(BaseModel):
    ticker: str
    hold: bool

@app.post("/toggle-price-hold")
def toggle_price_hold(req: PriceHoldRequest):
    if not isinstance(exchange, MockExchange):
        raise HTTPException(status_code=400, detail="Only available in mock mode")

    print(f"Toggling price hold for {req.ticker} to {req.hold}")
    exchange.hold_price(req.ticker, req.hold)
    is_held = exchange.is_price_held(req.ticker)
    print(f"Price hold for {req.ticker} is now: {is_held}")

    return {"status": "price hold toggled", "ticker": req.ticker, "hold": req.hold, "is_held": is_held}

@app.get("/price-hold-status")
def get_price_hold_status(ticker: str = "KRW-BTC"):
    if not isinstance(exchange, MockExchange):
        return {"is_held": False}

    is_held = exchange.is_price_held(ticker)
    return {"ticker": ticker, "is_held": is_held}

@app.get("/portfolio")
def get_portfolio():
    """Get overall portfolio status across all tickers"""
    portfolio = {
        "mode": "REAL" if isinstance(exchange, UpbitExchange) else "MOCK",
        "balance_krw": exchange.get_balance("KRW"),
        "coins": {}
    }

    total_value = portfolio["balance_krw"]
    initial_balance = 10000000  # Initial mock balance, adjust as needed

    for ticker in TICKERS:
        coin = ticker.split("-")[1]
        balance_coin = exchange.get_balance(ticker)
        current_price = exchange.get_current_price(ticker)
        coin_value = balance_coin * current_price if current_price else 0

        portfolio["coins"][coin] = {
            "ticker": ticker,
            "balance": balance_coin,
            "current_price": current_price,
            "value": coin_value
        }
        total_value += coin_value

    portfolio["total_value"] = total_value
    portfolio["total_profit_amount"] = total_value - initial_balance
    portfolio["total_profit_rate"] = ((total_value - initial_balance) / initial_balance * 100) if initial_balance > 0 else 0

    return portfolio

class SetApiKeysRequest(BaseModel):
    access_key: str
    secret_key: str

@app.post("/set-api-keys")
def set_api_keys(req: SetApiKeysRequest):
    """Switch to Real mode with provided API keys"""
    global exchange, strategies

    try:
        # Stop all running strategies
        for ticker in TICKERS:
            if ticker in strategies and strategies[ticker].is_running:
                strategies[ticker].stop()

        # Create new UpbitExchange with provided keys
        exchange = UpbitExchange(req.access_key, req.secret_key)

        # Recreate strategies with new exchange
        strategies = {}
        for ticker in TICKERS:
            strategies[ticker] = SevenSplitStrategy(exchange, ticker)
            logging.info(f"Switched to REAL mode for {ticker}")

        return {"status": "success", "mode": "REAL", "message": "Switched to Real mode"}
    except Exception as e:
        logging.error(f"Failed to switch to Real mode: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to switch to Real mode: {str(e)}")

@app.post("/switch-to-mock")
def switch_to_mock():
    """Switch back to Mock mode"""
    global exchange, strategies

    try:
        # Stop all running strategies
        for ticker in TICKERS:
            if ticker in strategies and strategies[ticker].is_running:
                strategies[ticker].stop()

        # Create new MockExchange
        exchange = MockExchange()

        # Recreate strategies with new exchange
        strategies = {}
        for ticker in TICKERS:
            strategies[ticker] = SevenSplitStrategy(exchange, ticker)
            logging.info(f"Switched to MOCK mode for {ticker}")

        return {"status": "success", "mode": "MOCK", "message": "Switched to Mock mode"}
    except Exception as e:
        logging.error(f"Failed to switch to Mock mode: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to switch to Mock mode: {str(e)}")
