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
from datetime import datetime, timedelta, timezone

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

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

# Initialize Exchange Service
from services.exchange_service import ExchangeService
exchange_service = ExchangeService(exchange)

# --- Strategy Management ---
# Initialize Strategy Service
from services.strategy_service import StrategyService
strategy_service = StrategyService(db, exchange_service)

# Load strategies on startup
strategy_service.load_strategies()

# load_strategies moved to StrategyService

# --- WebSocket connection registry ---
ws_connections = set()

# --- Global Caches ---
shared_prices: Dict[str, float] = {}
accounts_cache = {'data': [], 'timestamp': 0}
supplementary_price_cache = {'data': {}, 'timestamp': 0}

# Background thread for strategy tick
def run_strategies():
    # Track last tick time for each strategy
    strategies = strategy_service.strategies
    last_tick_time = {s_id: 0.0 for s_id in strategies.keys()}
    
    while True:
        try:
            loop_start_time = time.time()
            
            # Refresh strategy list keys
            strategies = strategy_service.strategies
            current_strategy_ids = list(strategies.keys())
            
            # 1. Collect all tickers (Running + Stopped) + Major Coins for Portfolio
            tickers_to_fetch = {"KRW-BTC", "KRW-ETH", "KRW-SOL"}
            for s_id in current_strategy_ids:
                if s_id in strategies:
                    tickers_to_fetch.add(strategies[s_id].ticker)
            
            # 2. Fetch Data (Prices + Orders) - ALWAYS run once per loop
            prices = {}
            all_open_orders = []
            
            # Fetch Prices
            if tickers_to_fetch:
                ticker_list = list(tickers_to_fetch)
                if hasattr(exchange, "get_current_prices"):
                    try:
                        prices = exchange.get_current_prices(ticker_list)
                    except Exception as e:
                        logging.error(f"Failed to fetch prices: {e}")
                else:
                    for ticker in ticker_list:
                        try:
                            price = exchange.get_current_price(ticker)
                            if price:
                                prices[ticker] = price
                        except Exception as e:
                            logging.error(f"Failed to fetch price for {ticker}: {e}")

            # Update Shared Cache
            global shared_prices
            shared_prices.update(prices)

            # Fetch Orders
            try:
                if hasattr(exchange, "get_orders"):
                    all_open_orders = exchange.get_orders(state='wait')
            except Exception as e:
                logging.error(f"Failed to fetch open orders: {e}")
                all_open_orders = None

            # 3. Tick Strategies
            current_time = time.time()
            for s_id in current_strategy_ids:
                if s_id not in strategies: continue
                strategy = strategies[s_id]
                
                if s_id not in last_tick_time:
                    last_tick_time[s_id] = 0.0
                
                # Tick regardless of running state (RSI updates even if stopped)
                # strategy.tick handles is_running check internally for order management
                tick_interval = strategy.config.tick_interval
                if current_time - last_tick_time[s_id] >= tick_interval:
                    price = prices.get(strategy.ticker)
                    if price:
                        strategy.tick(current_price=price, open_orders=all_open_orders)
                        last_tick_time[s_id] = current_time

        except Exception as e:
            logging.error(f"Error in strategy loop: {e}")
            time.sleep(1.0)
        
        # Enforce fixed 1-second loop duration
        elapsed = time.time() - loop_start_time
        sleep_time = max(0.1, 1.0 - elapsed)
        time.sleep(sleep_time)

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
        for s in strategy_service.get_all_strategies()
    ]

@app.post("/strategies")
def create_strategy(req: CreateStrategyRequest):
    """Create a new strategy"""
    try:
        s_id = strategy_service.create_strategy(
            name=req.name,
            ticker=req.ticker,
            budget=req.budget,
            config=req.config.model_dump()
        )
        return {"status": "success", "strategy_id": s_id, "message": "Strategy created"}
    except Exception as e:
        logging.error(f"Failed to create strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/strategies/{strategy_id}")
def delete_strategy(strategy_id: int):
    """Delete a strategy"""
    try:
        strategy_service.delete_strategy(strategy_id)
        return {"status": "success", "message": "Strategy deleted"}
    except Exception as e:
        logging.error(f"Failed to delete strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/strategies/{strategy_id}/events")
def get_strategy_events(strategy_id: int, page: int = 1, limit: int = 10):
    """Get system events for a strategy"""
    try:
        return db.get_events(strategy_id, page=page, limit=limit)
    except Exception as e:
        logging.error(f"Failed to fetch events: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch events")

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
    strategy = strategy_service.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    ticker = strategy.ticker

    # Batch fetch price for the requested ticker to avoid individual API call
    # Batch fetch price for the requested ticker to avoid individual API call
    # Use shared_prices if available
    global shared_prices
    current_price = shared_prices.get(ticker)
    
    if not current_price:
        try:
            if hasattr(exchange, "get_current_prices"):
                prices = exchange.get_current_prices([ticker])
                current_price = prices.get(ticker)
                # Update cache
                shared_prices.update(prices)
            else:
                current_price = None
        except Exception as e:
            logging.error(f"Failed to fetch price for {ticker}: {e}")
            current_price = None

    state = strategy.get_state(current_price=current_price)
    # Mode flag
    state["mode"] = current_mode
    
    # Fetch accounts (use cache if available)
    global accounts_cache
    current_time = time.time()
    accounts_raw = []
    
    try:
        # Check cache validity (10s)
        if current_time - accounts_cache['timestamp'] < 10 and accounts_cache['data']:
             accounts_raw = accounts_cache['data']
        else:
             accounts_raw = exchange._request('GET', '/v1/accounts') if hasattr(exchange, '_request') else []
             accounts_cache['data'] = accounts_raw
             accounts_cache['timestamp'] = current_time
             
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
    all_tickers = list(set(s.ticker for s in strategy_service.get_all_strategies()))
    
    # Use shared prices from the strategy loop
    # This eliminates redundant API calls for UI updates
    # Use shared prices from the strategy loop
    global shared_prices
        
    # If we have shared prices, use them. 
    prices = shared_prices.copy()
    
    # Check for missing tickers (e.g. stopped strategies)
    missing_tickers = [t for t in all_tickers if t not in prices]
    
    if missing_tickers:
        # Fetch missing tickers with 1s Caching
        global supplementary_price_cache
        current_time = time.time()
            
        try:
            # Check if we need to refresh cache (older than 1s)
            if current_time - supplementary_price_cache['timestamp'] > 1.0:
                if hasattr(exchange, "get_current_prices"):
                    # Batch fetch missing tickers
                    supp_prices = exchange.get_current_prices(missing_tickers)
                    supplementary_price_cache['data'] = supp_prices
                    supplementary_price_cache['timestamp'] = current_time
            
            # Merge cached supplementary prices
            prices.update(supplementary_price_cache['data'])
            
        except Exception as e:
            logging.error(f"Failed to fetch supplementary prices: {e}")

    # Fetch Accounts (Raw) with 10s Caching
    global accounts_cache
    current_time = time.time()
    
    try:
        if current_time - accounts_cache['timestamp'] > 10:
            # Cache expired or empty, fetch new data
            accounts_raw = exchange._request('GET', '/v1/accounts') if hasattr(exchange, '_request') else []
            accounts_cache['data'] = accounts_raw
            accounts_cache['timestamp'] = current_time
        else:
            # Use cached data
            accounts_raw = accounts_cache['data']
    except Exception as e:
        logging.error(f"Failed to fetch accounts: {e}")
        # On error, try to use cached data if available, else empty
        accounts_raw = accounts_cache.get('data', [])

    # Create Balance Map
    balance_map = {acc['currency']: float(acc['balance']) for acc in accounts_raw}

    for s_id, strategy in strategy_service.strategies.items():
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
def get_candles(market: str, count: int = 200, interval: str = "minutes/5", to: Optional[str] = None):
    try:
        candles = exchange.get_candles(market, count, interval, to=to)
        return candles
    except Exception as e:
        logging.error(f"Failed to fetch candles: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch candles")

class CommandRequest(BaseModel):
    strategy_id: int

@app.post("/start")
def start_bot(cmd: CommandRequest):
    try:
        strategy_service.start_strategy(cmd.strategy_id)
        return {"status": "started", "strategy_id": cmd.strategy_id}
    except ValueError:
        raise HTTPException(status_code=404, detail="Strategy not found")
    except Exception as e:
        logging.error(f"Failed to start strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stop")
def stop_bot(cmd: CommandRequest):
    try:
        strategy_service.stop_strategy(cmd.strategy_id)
        return {"status": "stopped", "strategy_id": cmd.strategy_id}
    except ValueError:
        raise HTTPException(status_code=404, detail="Strategy not found")

class ConfigRequest(BaseModel):
    strategy_id: int
    config: StrategyConfig
    budget: Optional[float] = None

@app.post("/config")
def update_config(req: ConfigRequest):
    try:
        strategy_service.update_config(req.strategy_id, req.config, req.budget)
        strategy = strategy_service.get_strategy(req.strategy_id)
        return {"status": "config updated", "strategy_id": req.strategy_id, "config": req.config, "budget": strategy.budget}
    except ValueError:
        raise HTTPException(status_code=404, detail="Strategy not found")

class UpdateNameRequest(BaseModel):
    name: str

@app.patch("/strategies/{strategy_id}")
def update_strategy_name(strategy_id: int, req: UpdateNameRequest):
    strategy = strategy_service.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    # Update in memory
    strategy.name = req.name
    
    # Update in DB
    db.update_strategy_name(strategy_id, req.name)
    
    return {"status": "success", "strategy_id": strategy_id, "name": req.name}


@app.post("/simulate")
def simulate_strategy(sim_config: SimulationConfig):
    """Run a simulation based on provided config and candles"""
    try:
        result = run_simulation(sim_config)
        return result
    except Exception as e:
        import traceback
        logging.error(f"Simulation failed: {e}")
        raise HTTPException(status_code=500, detail=f"{str(e)}\n{traceback.format_exc()}")

class SimulationRequest(BaseModel):
    start_time: str # ISO format

@app.post("/strategies/{strategy_id}/simulate")
def simulate_strategy_from_time(strategy_id: int, req: SimulationRequest):
    """Run simulation for a specific strategy starting from a given time"""
    logging.info(f"Received simulation request for strategy {strategy_id} from {req.start_time}")
    
    # Always load simulation params from DB to ensure fresh config/budget
    # In-memory strategy object might have stale budget or un-synced state
    s_rec = db.get_strategy(strategy_id)
    if not s_rec:
        logging.error(f"Strategy {strategy_id} not found in DB")
        raise HTTPException(status_code=404, detail="Strategy not found")
        
    # Create StrategyConfig by copying fields from SQLAlchemy model
    # Note: s_rec is an SQLAlchemy model instance, not a dict
    config_dict = {
        'investment_per_split': s_rec.investment_per_split,
        'min_price': s_rec.min_price,
        'max_price': s_rec.max_price,
        'buy_rate': s_rec.buy_rate,
        'sell_rate': s_rec.sell_rate,
        'fee_rate': s_rec.fee_rate,
        'tick_interval': s_rec.tick_interval,
        'rebuy_strategy': s_rec.rebuy_strategy,
        'max_trades_per_day': s_rec.max_trades_per_day,
        
        # RSI Config
        'strategy_mode': s_rec.strategy_mode,
        'rsi_period': s_rec.rsi_period,
        'rsi_timeframe': s_rec.rsi_timeframe,

        # RSI Buying
        'rsi_buy_max': s_rec.rsi_buy_max,
        'rsi_buy_first_threshold': s_rec.rsi_buy_first_threshold,
        'rsi_buy_first_amount': s_rec.rsi_buy_first_amount,
        'rsi_buy_next_threshold': s_rec.rsi_buy_next_threshold,
        'rsi_buy_next_amount': s_rec.rsi_buy_next_amount,

        # RSI Selling
        'rsi_sell_min': s_rec.rsi_sell_min,
        'rsi_sell_first_threshold': s_rec.rsi_sell_first_threshold,
        'rsi_sell_first_amount': s_rec.rsi_sell_first_amount,
        'rsi_sell_next_threshold': s_rec.rsi_sell_next_threshold,
        'rsi_sell_next_amount': s_rec.rsi_sell_next_amount,

        # Risk
        'stop_loss': s_rec.stop_loss,
        'max_holdings': s_rec.max_holdings,

        # Trailing Buy
        'use_trailing_buy': s_rec.use_trailing_buy,
        'trailing_buy_rebound_percent': s_rec.trailing_buy_rebound_percent,
        'trailing_buy_batch': getattr(s_rec, 'trailing_buy_batch', True)
    }
    
    config = StrategyConfig(**config_dict)

    ticker = s_rec.ticker
    budget = s_rec.budget
    
    # DEBUG: Log what we loaded
    logging.info(f"SIM START: Loaded Strategy {strategy_id} ({ticker}) from DB. Budget={budget}")

    # Fetch candles
    # Determine interval based on strategy mode
    interval = "days" if config.strategy_mode == "RSI" else "minutes/5"
    
    # Fetch candles with pagination to cover start_time
    # Upbit API returns latest first. We need to fetch backwards until we cover start_time.
    # We will fetch up to 2000 candles (10 pages) to avoid abuse.
    
    start_dt = None
    try:
        start_dt = datetime.fromisoformat(req.start_time.replace('Z', '+00:00'))
    except:
        pass

    candles = []
    to_cursor = None
    max_pages = 20
    pages_fetched = 0
    fetch_logs = []
    
    try:
        logging.info(f"Fetching candles for {ticker} (Mode: {config.strategy_mode}, Interval: {interval}) starting search from {start_dt}")
        
        while pages_fetched < max_pages:
            logging.info(f"Fetching page {pages_fetched+1} (to={to_cursor})")
            batch = exchange.get_candles(ticker, count=200, interval=interval, to=to_cursor)
            
            if not batch:
                break
                
            # Prepend because batch is sorted desc by API usually? 
            # Upbit returns [latest, ..., oldest] ? No, Upbit returns [latest, ..., oldest] usually?
            # Actually Upbit /candles/minutes/5 returns:
            # [ {timestamp: t_latest}, {timestamp: t_prev}, ... ]
            # So batch[0] is latest, batch[-1] is oldest.
            
            # We want chronological order in our final list: [oldest, ..., latest]
            # So we should prepend batch reversed?
            # Let's check existing code: candles.sort(key=lambda x: x['candle_date_time_kst'])
            # So order doesn't matter for the list construction as long as we sort later.
            
            # Log batch info
            if batch:
                latest_in_batch = batch[0]['candle_date_time_kst']
                oldest_in_batch_log = batch[-1]['candle_date_time_kst']
                msg = f"FETCH: Page {pages_fetched}, Count={len(batch)}, Range=[{latest_in_batch} ... {oldest_in_batch_log}]"
                fetch_logs.append(msg)
                logging.info(msg)
            
            candles.extend(batch)
            
            # Check oldest in this batch
            # Upbit returns sorted by time DESC (latest first)
            # So the last item is the oldest in this batch.
            oldest_in_batch = batch[-1]
            oldest_dt_str = oldest_in_batch['candle_date_time_utc'] or oldest_in_batch['candle_date_time_kst']
            # Convert to aware UTC
            # Convert to aware UTC
            if oldest_dt_str.endswith('Z'):
                 oldest_dt = datetime.fromisoformat(oldest_dt_str.replace('Z', '+00:00'))
            else:
                 # Assume ISO
                 oldest_dt = datetime.fromisoformat(oldest_dt_str)
                 # Force UTC if naive
                 if oldest_dt.tzinfo is None:
                     oldest_dt = oldest_dt.replace(tzinfo=timezone.utc)
                 
                 # Double check if we can get better precision from explicit UTC field
                 if 'candle_date_time_utc' in oldest_in_batch:
                      dt_utc = datetime.fromisoformat(oldest_in_batch['candle_date_time_utc'].replace('Z', '+00:00'))
                      if dt_utc.tzinfo is None:
                          dt_utc = dt_utc.replace(tzinfo=timezone.utc)
                      oldest_dt = dt_utc
            
            # Prepare 'to' for next batch (oldest timestamp formatted string)
            # Upbit 'to' expects ISO string.
            to_cursor = oldest_in_batch['candle_date_time_utc'] # Use UTC for 'to' if available
            
            pages_fetched += 1
            
            # Check coverage
            if start_dt and oldest_dt <= start_dt:
                # We reached the start time.
                # BUT we need history ("warmup data") for indicators like RSI to be accurate.
                # Let's verify how many candles we have BEFORE start_dt.
                # List 'candles' is currently growing with older pages appended.
                # The 'batch' we just added contains candles around 'oldest_dt'.
                
                # Count candles strictly older than start_dt
                # This is approximate because we haven't sorted 'candles' yet, but 'batch' is older than previous batches.
                # So basically everything in 'batch' (or subsequent batches) is older than start_dt effectively?
                # No, the first batch crossing start_dt has some older, some newer.
                # Subsequent batches are ALL older.
                
                # Check total rough count of older candles
                # Since 'candles' collects pages (Reverse Order of Time if pages are prepended? No, extended.)
                # We need to be careful about list structure.
                # Current logic: candles.extend(batch).
                # Batch 0: [Latest ... T_start+100]
                # Batch 1: [T_start+99 ... T_start-100] -> oldest_dt < start_dt is TRUE here.
                # At this point, we have ~100 candles older than start_dt.
                # We want 200.
                
                # So:
                older_count = sum(1 for c in candles if (c.get('candle_date_time_utc') or c.get('candle_date_time_kst')) < req.start_time) # comparing strings ok? ISO format yes.
                
                # String comparison is risky if timezones differ (Z vs +00:00).
                # But let's rely on simple page count after crossing.
                # If we just crossed, let's fetch 1 more page (200 candles) to be safe?
                pass 
                
            # If we already covered start_dt deep enough?
            # Let's use a simpler heuristic:
            # If oldest_dt is significantly older than start_dt (e.g. 1 day/200 candles worth), break.
            buffer_time = timedelta(days=1) if interval == "minutes/5" else timedelta(days=20)
            if start_dt and oldest_dt < (start_dt - buffer_time):
                 logging.info(f"Buffered enough history ({oldest_dt} < {start_dt} - buffer). Stopping.")
                 break

            if len(batch) < 200:
                # No more data available
                break
                
        if not candles:
             logging.error("No candles returned from exchange")
             raise HTTPException(status_code=500, detail="Failed to fetch candles")
             
        logging.info(f"Fetched total {len(candles)} candles")
        
    except Exception as e:
        import traceback
        logging.error(f"Error fetching candles: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error fetching candles: {str(e)}")
    
    # Sort candles by time
    candles.sort(key=lambda x: x['candle_date_time_kst'])
    
    # Find start index
    start_index = -1
    try:
        # start_time is UTC ISO string from frontend (e.g. 2023-10-27T00:00:00.000Z)
        start_dt = datetime.fromisoformat(req.start_time.replace('Z', '+00:00'))
        logging.info(f"Parsed start time (UTC): {start_dt}")
        
        # KST Timezone
        kst_tz = timezone(timedelta(hours=9))
        
        for i, candle in enumerate(candles):
            # candle_date_time_kst is ISO string (e.g. 2023-10-27T09:00:00) - Naive KST
            c_dt_naive = datetime.fromisoformat(candle['candle_date_time_kst'])
            # Make it aware (KST)
            c_dt = c_dt_naive.replace(tzinfo=kst_tz)
            
            # Compare
            # start_dt is UTC. c_dt is KST. Both aware. Comparison works.
            # LOGGING
            if i < 5 or i % 100 == 0:
                 logging.info(f"SIM SEARCH: idx={i}, candle_kst={candle['candle_date_time_kst']}, c_dt_utc={c_dt.astimezone(timezone.utc)}, start_dt={start_dt}")

            if interval == "days":
                # Compare dates (local date in KST vs local date of start_time in KST?)
                # start_dt is UTC. Convert to KST to compare "days" correctly.
                start_dt_kst = start_dt.astimezone(kst_tz)
                if c_dt.date() >= start_dt_kst.date():
                    start_index = i
                    logging.warning(f"SIM START FOUND (days): idx={i}, candle_kst={candle['candle_date_time_kst']}, c_dt_utc={c_dt.astimezone(timezone.utc)} >= start_dt_kst={start_dt_kst}")
                    break
            else:
                # Compare full datetime
                if c_dt >= start_dt:
                    start_index = i
                    break
        logging.info(f"Found start index: {start_index}")
    except Exception as e:
        logging.error(f"Error finding start index: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing time: {str(e)}")
            
    if start_index == -1:
        start_index = 0

    sim_config = SimulationConfig(
        strategy_config=config,
        candles=candles,
        start_index=start_index,
        ticker=ticker,
        budget=budget
    )

    try:
        result = run_simulation(sim_config)
        if 'debug_logs' in result:
             result['debug_logs'].extend(fetch_logs)
        return result
    except Exception as e:
        import traceback
        logging.error(f"Simulation failed: {e}")
        raise HTTPException(status_code=500, detail=f"{str(e)}\n{traceback.format_exc()}")

@app.post("/reset")
def reset_strategy(cmd: CommandRequest):
    """Reset a specific strategy"""
    s_id = cmd.strategy_id

    try:
        strategy_service.reset_strategy(s_id)
        return {"status": "success", "strategy_id": s_id, "message": f"Strategy reset for {s_id}"}
    except ValueError:
        raise HTTPException(status_code=404, detail="Strategy not found")
    except Exception as e:
        logging.error(f"Failed to reset strategy {s_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset: {str(e)}")

class DebugRSIRequest(BaseModel):
    strategy_id: int
    rsi: float
    prev_rsi: Optional[float] = None
    rsi_short: Optional[float] = None

@app.post("/debug/rsi")
def set_debug_rsi(req: DebugRSIRequest):
    """[MOCK ONLY] Force set RSI values for testing."""
    if current_mode != "MOCK":
        raise HTTPException(status_code=403, detail="Debug endpoints only available in MOCK mode")
        
    strategy = strategy_service.get_strategy(req.strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
        
    # Inject values directly into logic module
    strategy.rsi_logic.current_rsi = req.rsi
    if req.prev_rsi is not None:
        strategy.rsi_logic.prev_rsi = req.prev_rsi
    if req.rsi_short is not None:
        strategy.rsi_logic.current_rsi_short = req.rsi_short
        
    # Prevent overwrite by next tick's calculation for a short duration
    # Set last update time to future so it doesn't recalc immediately
    strategy.rsi_logic.last_rsi_update = time.time() + 60 
    
    return {"status": "success", "message": f"RSI set to {req.rsi} (Prev: {req.prev_rsi}) for strategy {req.strategy_id}"}

import requests

@app.post("/reset-all")
def reset_all_mock():
    """Reset all strategies and exchange (MOCK mode only)"""
    global exchange, current_mode

    # Only allow reset in MOCK mode
    if current_mode != "MOCK":
        return {"status": "not a mock exchange"}

    # Stop all strategies first
    for s_id, strategy in strategy_service.strategies.items():
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
    
    # Reinitialize Exchange Service
    global exchange_service
    exchange_service = ExchangeService(exchange)

    # Reload strategies (will load existing strategies from DB)
    strategy_service.load_strategies()

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
    global shared_prices
    global accounts_cache
    
    # Use cached accounts if available and valid
    current_time = time.time()
    accounts_raw = None
    
    try:
        if current_time - accounts_cache['timestamp'] < 10 and accounts_cache['data']:
            accounts_raw = accounts_cache['data']
        # If not valid, _calculate_portfolio will fetch (and we should probably update cache there? 
        # But _calculate_portfolio is pure logic mostly.
        # Let's fetch here if needed to keep consistency
        else:
             accounts_raw = exchange._request('GET', '/v1/accounts') if hasattr(exchange, '_request') else []
             accounts_cache['data'] = accounts_raw
             accounts_cache['timestamp'] = current_time
    except Exception:
        pass

    return _calculate_portfolio(prices=shared_prices, accounts_raw=accounts_raw)


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
