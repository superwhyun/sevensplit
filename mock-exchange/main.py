import logging
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import requests
import uuid
from datetime import datetime, timezone
import threading
import time
import uvicorn
import os
from database import get_db

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize prices and start background threads
    initialize_default_prices()
    
    price_updater_thread = threading.Thread(target=price_updater, daemon=True)
    price_updater_thread.start()
    
    matcher_thread = threading.Thread(target=order_matcher, daemon=True)
    matcher_thread.start()
    
    yield
    # Shutdown: Threads are daemon, so they will exit when the process ends

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def log_server_side(request: Request, call_next):
    """Log requests with server host/port instead of client addr."""
    # server_host, server_port = request.scope.get("server", ("?", "?"))
    # path = request.url.path
    # method = request.method
    response = await call_next(request)
    # logging.info(f"[{server_host}:{server_port}] {method} {path} -> {response.status_code}")
    return response

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get the exchange-ui directory path
EXCHANGE_UI_DIR = os.path.join(os.path.dirname(__file__), "ui")

class MockExchangeLogic:
    def __init__(self, initial_balance=10000000):
        self.db = get_db()
        self.balance = {"KRW": initial_balance}
        self.orders = {}  # uuid -> order info (in-memory cache)
        self.price_overrides = {}  # ticker -> price
        self.price_held = {}       # ticker -> bool
        self.avg_buy_prices = {}   # currency -> avg buy price
        self.lock = threading.RLock()
        # Base URL for fetching live prices directly
        live_base = os.getenv("UPBIT_LIVE_API_BASE")
        if not live_base:
            live_base = os.getenv("UPBIT_OPEN_API_SERVER_URL")
        # If it points to this mock server (localhost/5001), disable to avoid recursion
        if live_base and ("127.0.0.1" in live_base or "localhost" in live_base or ":5001" in live_base):
            live_base = None
        self.live_api_base = live_base.rstrip("/") if live_base else None
        # Simple per-ticker cache to avoid 429 (Too Many Requests)
        self.live_price_cache_sec = float(os.getenv("LIVE_PRICE_CACHE_SECONDS", "1.5"))
        self.last_live_fetch = {}  # ticker -> timestamp
        
        # Cache for valid markets
        self.valid_markets = set()
        self.last_markets_update = 0

        self._refresh_balances()
        self._load_orders()

    def _get_valid_markets(self):
        """Fetch and cache valid KRW markets to avoid 404s on delisted coins"""
        current_time = time.time()
        # Update cache every hour (3600 seconds)
        if not self.valid_markets or (current_time - self.last_markets_update > 3600):
            if not self.live_api_base:
                return set()
                
            try:
                url = f"{self.live_api_base}/v1/market/all"
                resp = requests.get(url, params={'isDetails': 'false'}, timeout=3)
                resp.raise_for_status()
                data = resp.json()
                
                if isinstance(data, list):
                    new_markets = {m['market'] for m in data if m['market'].startswith('KRW-')}
                    if new_markets:
                        self.valid_markets = new_markets
                        self.last_markets_update = current_time
                        logging.info(f"Mock server: Refreshed valid markets: {len(self.valid_markets)} KRW pairs found")
            except Exception as e:
                logging.warning(f"Mock server: Failed to fetch valid markets: {e}")
                
        return self.valid_markets

    def get_tick_size(self, price):
        """Return the tick size for a given price in KRW market based on user provided table."""
        if price >= 1000000:
            return 1000
        elif price >= 500000:
            return 500
        elif price >= 100000:
            return 100
        elif price >= 50000:
            return 50
        elif price >= 10000:
            return 10
        elif price >= 5000:
            return 5
        elif price >= 1000:
            return 1
        elif price >= 100:
            return 1
        else:
            return 0.1 # Default for < 100

    def normalize_price(self, price):
        """Normalize price to the nearest tick size (floor)."""
        tick_size = self.get_tick_size(price)
        
        # Use Decimal for precise arithmetic
        from decimal import Decimal
        
        # Convert to string first to avoid float precision issues
        try:
            d_price = Decimal(str(price))
            d_tick = Decimal(str(tick_size))
            
            # Floor division to get number of ticks
            normalized = (d_price // d_tick) * d_tick
            
            if tick_size >= 1:
                return int(normalized)
            else:
                return float(normalized)
        except:
            return price

    def _load_orders(self):
        """Load pending orders from DB into memory"""
        try:
            db_orders = self.db.get_mock_orders(state='wait')
            for order in db_orders:
                self.orders[order.uuid] = {
                    "uuid": order.uuid,
                    "side": order.side,
                    "ord_type": order.ord_type,
                    "price": order.price,
                    "state": order.state,
                    "market": order.market,
                    "created_at": order.created_at.isoformat() if order.created_at else datetime.now(timezone.utc).isoformat(),
                    "volume": order.volume,
                    "remaining_volume": order.remaining_volume,
                    "reserved_fee": order.reserved_fee,
                    "remaining_fee": order.remaining_fee,
                    "paid_fee": order.paid_fee,
                    "locked": order.locked,
                    "executed_volume": order.executed_volume,
                    "trades_count": order.trades_count
                }
            if db_orders:
                logging.info(f"Mock server: Loaded {len(db_orders)} pending orders from DB")
        except Exception as e:
            logging.error(f"Mock server: Failed to load orders from DB: {e}")

    def _refresh_balances(self):
        try:
            # Acquire lock to ensure consistency between DB read and memory update
            # and to prevent race conditions with reset
            with self.lock:
                accounts = self.db.get_mock_accounts()
                
                # Track found currencies to identify removals
                found_currencies = set()
                
                for acc in accounts:
                    self.balance[acc.currency] = acc.balance
                    self.avg_buy_prices[acc.currency] = acc.avg_buy_price
                    found_currencies.add(acc.currency)
                
                # Remove currencies that are in memory but not in DB (e.g. after reset)
                for currency in list(self.balance.keys()):
                    if currency not in found_currencies:
                        del self.balance[currency]
                        if currency in self.avg_buy_prices:
                            del self.avg_buy_prices[currency]
                            
        except Exception as e:
            logging.error(f"Mock server: failed to refresh balances: {e}")

    def _persist_balance(self, currency: str):
        try:
            self.db.set_mock_balance(currency, self.balance.get(currency, 0.0), self.avg_buy_prices.get(currency, 0.0))
        except Exception as e:
            logging.error(f"Mock server: failed to persist balance for {currency}: {e}")

    def get_accounts(self):
        self._refresh_balances()
        accounts = []
        with self.lock:
            # Get valid markets to filter out delisted/invalid coins
            valid_markets = self._get_valid_markets()

            # Batch fetch prices for all non-KRW currencies
            tickers_to_fetch = []
            for currency in self.balance.keys():
                if currency != "KRW":
                    ticker = f"KRW-{currency}"
                    # Only fetch price if it's a valid market (or if we failed to fetch valid markets, try anyway)
                    if not valid_markets or ticker in valid_markets:
                        tickers_to_fetch.append(ticker)
            
            # Fetch all prices in one call
            prices = self.get_prices_for_markets(tickers_to_fetch) if tickers_to_fetch else {}
            
            for currency, balance in self.balance.items():
                # Calculate locked amount from open orders
                locked = 0.0
                if currency == "KRW":
                    for order in self.orders.values():
                        if order["state"] == "wait" and order["side"] == "bid":
                            locked += float(order["locked"])
                else:
                    for order in self.orders.values():
                        if order["state"] == "wait" and order["side"] == "ask":
                            if order["market"].endswith(f"-{currency}"):
                                locked += float(order["locked"])

                total_balance = balance + locked
                ticker = f"KRW-{currency}" if currency != "KRW" else None
                if currency == "KRW":
                    current_price = 1.0
                else:
                    current_price = prices.get(ticker, 0.0) if ticker else 0.0
                balance_value = total_balance * current_price if current_price else 0.0

                
                accounts.append({
                    "currency": currency,
                    "balance": float(balance),
                    "locked": float(locked),
                    "avg_buy_price": float(self.avg_buy_prices.get(currency, 0.0) or 0.0),
                    "avg_buy_price_modified": False,
                    "unit_currency": "KRW",
                    "ticker": ticker,
                    "current_price": float(current_price or 0.0),
                    "balance_value": float(balance_value or 0.0),
                    "total_balance": float(total_balance or 0.0)
                })
        return accounts

    def get_order(self, uuid):
        self._refresh_balances()
        with self.lock:
            return self.orders.get(uuid)

    def _fetch_live_price(self, ticker: str) -> float | None:
        """Fetch live price with a direct HTTP call (avoid pyupbit returning 0/None)."""
        if not self.live_api_base:
            return None
        url = f"{self.live_api_base}/v1/ticker"
        try:
            resp = requests.get(url, params={"markets": ticker}, timeout=3)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and data and data[0].get("trade_price"):
                return float(data[0]["trade_price"])
            logging.error(f"Live price parse error for {ticker}: {data}")
        except Exception as e:
            logging.error(f"Live price HTTP error for {ticker}: {e}")
        return None

    def _fetch_live_prices(self, tickers: list[str]) -> dict[str, float]:
        """Batch fetch live prices for multiple markets."""
        if not self.live_api_base:
            return {}
        prices: dict[str, float] = {}
        if not tickers:
            return prices

        url = f"{self.live_api_base}/v1/ticker"
        markets_param = ",".join(tickers)
        try:
            # Log who is calling this with full stack trace
            # import traceback
            # stack = traceback.extract_stack()
            # # Get last 5 callers
            # stack_trace = " <- ".join([f"{s.filename.split('/')[-1]}:{s.lineno}({s.name})" for s in stack[-5:-1]])
            # logging.info(f"🌐 Upbit API Request: GET {url}?markets={markets_param} [Stack: {stack_trace}]")
            
            resp = requests.get(url, params={"markets": markets_param}, timeout=3)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                for item in data:
                    market = item.get("market")
                    price = item.get("trade_price")
                    if market and price:
                        prices[market] = float(price)
                # logging.info(f"✅ Upbit API Response: {len(prices)} prices fetched")
            if not prices:
                logging.error(f"Live price batch parse error for {tickers}: {data}")
        except Exception as e:
            logging.error(f"❌ Upbit API Error for {tickers}: {e}")
        return prices

    def get_prices_for_markets(self, markets: list[str], force_fetch: bool = False) -> dict[str, float]:
        """Return prices for multiple markets. Uses cached prices unless force_fetch=True."""
        result: dict[str, float] = {}
        
        if not force_fetch:
            # Use cached prices
            for market in markets:
                cached_price = self.price_overrides.get(market, 0.0)
                result[market] = cached_price
            return result
        
        # Force fetch from Upbit
        fetch_targets: list[str] = []
        for market in markets:
            # Held tickers: always use override/cached
            if self.price_held.get(market, False):
                result[market] = self.price_overrides.get(market, 0.0)
                continue
            fetch_targets.append(market)

        # Batch fetch all targets in one API call
        if fetch_targets:
            live_prices = self._fetch_live_prices(fetch_targets)
            if live_prices:
                for market, price in live_prices.items():
                    self.price_overrides[market] = price
                    result[market] = price
            else:
                logging.error(f"Failed to fetch live prices from Upbit API")
                # Fallback to last known prices
                for market in fetch_targets:
                    fallback = self.price_overrides.get(market, 0.0)
                    if fallback:
                        logging.warning(f"Using last known price for {market}")
                    else:
                        logging.error(f"No price available for {market}. Returning 0.")
                    result[market] = fallback

        return result

    def get_orders(self, state='wait'):
        self._refresh_balances()
        with self.lock:
            # Get from memory
            orders = [o for o in self.orders.values() if o['state'] == state]
            
            # Also check DB for orders not in memory
            try:
                db_orders = self.db.get_mock_orders(state=state)
                mem_uuids = {o['uuid'] for o in orders}
                
                for db_order in db_orders:
                    if db_order.uuid not in mem_uuids:
                        # Load from DB
                        order = {
                            "uuid": db_order.uuid,
                            "side": db_order.side,
                            "ord_type": db_order.ord_type,
                            "price": db_order.price,
                            "state": db_order.state,
                            "market": db_order.market,
                            "created_at": db_order.created_at.isoformat() if db_order.created_at else datetime.now(timezone.utc).isoformat(),
                            "volume": db_order.volume,
                            "remaining_volume": db_order.remaining_volume,
                            "reserved_fee": db_order.reserved_fee,
                            "remaining_fee": db_order.remaining_fee,
                            "paid_fee": db_order.paid_fee,
                            "locked": db_order.locked,
                            "executed_volume": db_order.executed_volume,
                            "trades_count": db_order.trades_count
                        }
                        orders.append(order)
                        # Cache in memory for next time
                        self.orders[db_order.uuid] = order
            except Exception as e:
                logging.error(f"Mock server: Failed to load orders from DB: {e}")
            
            return orders

    def place_order(self, market, side, volume, price, ord_type):
        self._refresh_balances()
        with self.lock:
            currency = market.split("-")[1]
            
            # Validation and Balance Check
            if side == "bid":
                cost = float(price) * float(volume) if price and volume else float(price) # Market buy uses price as total
                if ord_type == 'price': # Market buy
                     cost = float(price)
                
                fee = cost * 0.0005
                total_needed = cost + fee
                if self.balance.get("KRW", 0) < total_needed:
                    return {"error": {"message": "Insufficient funds"}}
                self.balance["KRW"] -= total_needed
                self._persist_balance("KRW")
                locked = total_needed
            else:
                # Add epsilon for float precision issues
                if self.balance.get(currency, 0) < float(volume) - 1e-9:
                    return {"error": {"message": "Insufficient funds"}}
                self.balance[currency] -= float(volume)
                self._persist_balance(currency)
                locked = float(volume)

            order_id = str(uuid.uuid4())
            order_data = {
                "uuid": order_id,
                "side": side,
                "ord_type": ord_type,
                "price": str(price) if price else None,
                "state": "wait",
                "market": market,
                "volume": str(volume) if volume else None,
                "remaining_volume": str(volume) if volume else None,
                "reserved_fee": str(locked - (float(price)*float(volume))) if side == "bid" and ord_type=='limit' else "0",
                "remaining_fee": "0",
                "paid_fee": "0",
                "locked": str(locked),
                "executed_volume": "0",
                "trades_count": 0
            }
            
            # Save to DB
            try:
                self.db.add_mock_order(order_data)
            except Exception as e:
                logging.error(f"Mock server: Failed to save order to DB: {e}")
            
            # Cache in memory
            order = {**order_data, "created_at": datetime.now(timezone.utc).isoformat()}
            self.orders[order_id] = order
            
            # Check for immediate execution
            self.check_orders()
            
            return order

    def cancel_order(self, uuid):
        self._refresh_balances()
        with self.lock:
            if uuid not in self.orders:
                # Try loading from DB
                db_order = self.db.get_mock_order(uuid)
                if not db_order:
                    return None
                # Load into memory
                self.orders[uuid] = {
                    "uuid": db_order.uuid,
                    "side": db_order.side,
                    "ord_type": db_order.ord_type,
                    "price": db_order.price,
                    "state": db_order.state,
                    "market": db_order.market,
                    "created_at": db_order.created_at.isoformat() if db_order.created_at else datetime.now(timezone.utc).isoformat(),
                    "volume": db_order.volume,
                    "remaining_volume": db_order.remaining_volume,
                    "reserved_fee": db_order.reserved_fee,
                    "remaining_fee": db_order.remaining_fee,
                    "paid_fee": db_order.paid_fee,
                    "locked": db_order.locked,
                    "executed_volume": db_order.executed_volume,
                    "trades_count": db_order.trades_count
                }
            
            order = self.orders[uuid]
            if order["state"] != "wait":
                return None
            
            # Refund
            currency = order["market"].split("-")[1]
            if order["side"] == "bid":
                self.balance["KRW"] = self.balance.get("KRW", 0) + float(order["locked"])
                self._persist_balance("KRW")
            else:
                self.balance[currency] = self.balance.get(currency, 0) + float(order["locked"])
                self._persist_balance(currency)
            
            order["state"] = "cancel"
            
            # Update DB
            try:
                self.db.update_mock_order(uuid, state="cancel")
            except Exception as e:
                logging.error(f"Mock server: Failed to update order in DB: {e}")
            
            return order

    def get_current_price(self, ticker):
        # 1) If held, always use manual override/cached value
        if self.price_held.get(ticker, False):
            return self.price_overrides.get(ticker, 0.0)

        # 2) Live mode: delegate to batched cache-aware lookup
        prices = self.get_prices_for_markets([ticker])
        return prices.get(ticker, 0.0)

    def set_price(self, ticker, price):
        with self.lock:
            # Normalize price before setting
            normalized_price = self.normalize_price(float(price))
            self.price_overrides[ticker] = normalized_price
            logging.info(f"Mock price set for {ticker}: {normalized_price} (raw: {price})")

    def hold_price(self, ticker, hold):
        with self.lock:
            self.price_held[ticker] = hold
            if hold and ticker not in self.price_overrides:
                # Freeze at the last known price (from live or override)
                live_price = self._fetch_live_price(ticker)
                fallback = self.price_overrides.get(ticker, 0.0)
                self.price_overrides[ticker] = live_price if live_price else fallback
                logging.info(f"Mock price held for {ticker}: {self.price_overrides[ticker]}")

    def check_orders(self):
        self._refresh_balances()
        with self.lock:
            # Use cached prices from price_overrides instead of fetching
            # Prices are updated by get_prices_for_markets calls from API requests
            for order in list(self.orders.values()):
                if order["state"] == "wait":
                    # Use cached price if available
                    current_price = self.price_overrides.get(order["market"], 0.0)
                    if not current_price:
                        continue
                        
                    is_match = False
                    if order["ord_type"] == "limit":
                        if order["side"] == "bid" and current_price <= float(order["price"]):
                            is_match = True
                        elif order["side"] == "ask" and current_price >= float(order["price"]):
                            is_match = True
                    elif order["ord_type"] == "price": 
                        is_match = True 
                    elif order["ord_type"] == "market": 
                        is_match = True

                    if is_match:
                        vol = float(order["volume"]) if order["volume"] else 0
                        price = float(order["price"]) if order["price"] else current_price
                        
                        if order["ord_type"] == "price": # Market Buy
                             # price is total amount in KRW
                             amount = float(order["price"])
                             vol = amount / current_price
                             price = current_price
                        
                        total = vol * price
                        fee = total * 0.0005
                        
                        currency = order["market"].split("-")[1]
                        
                        if order["side"] == "bid":
                            prev_balance = self.balance.get(currency, 0)
                            prev_avg = self.avg_buy_prices.get(currency, 0.0)
                            new_total = prev_balance + vol

                            if new_total > 0:
                                new_avg = ((prev_avg * prev_balance) + (price * vol)) / new_total
                                self.avg_buy_prices[currency] = new_avg

                            self.balance[currency] = new_total
                            self._persist_balance(currency)
                        else:
                            self.balance["KRW"] = self.balance.get("KRW", 0) + (total - fee)
                            if self.balance.get(currency, 0) <= 0:
                                self.avg_buy_prices[currency] = 0.0
                            self._persist_balance("KRW")
                            self._persist_balance(currency)

                        # Create trade info
                        trade = {
                            "market": order["market"],
                            "uuid": str(uuid.uuid4()),
                            "price": str(price),
                            "volume": str(vol),
                            "funds": str(total),
                            "side": order["side"],
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }
                        
                        order["state"] = "done"
                        order["trades_count"] = 1
                        order["executed_volume"] = str(vol)
                        order["remaining_volume"] = "0"
                        order["trades"] = [trade] # Add trades list
                        
                        # Update DB
                        try:
                            self.db.update_mock_order(order["uuid"], 
                                state="done",
                                trades_count=1,
                                executed_volume=str(vol),
                                remaining_volume="0"
                            )
                        except Exception as e:
                            logging.error(f"Mock server: Failed to update order in DB: {e}")

mock_logic = MockExchangeLogic()

# Initialize default prices on startup
def initialize_default_prices():
    """Fetch initial prices from Upbit API on startup"""
    if not mock_logic.live_api_base:
        logging.warning("No live API configured - prices will return 0 until manually set via /mock/price")
        return
    
    try:
        tickers = ["KRW-BTC", "KRW-ETH", "KRW-SOL"]
        prices = mock_logic._fetch_live_prices(tickers)
        if prices:
            for ticker, price in prices.items():
                mock_logic.price_overrides[ticker] = price
            logging.info(f"Initialized prices from Upbit API: {prices}")
        else:
            logging.error("Failed to fetch initial prices from Upbit API")
    except Exception as e:
        logging.error(f"Error initializing prices from Upbit API: {e}")



# Price updater thread - periodically fetch prices from Upbit
def price_updater():
    """Periodically update prices from Upbit API"""
    default_tickers = ["KRW-BTC", "KRW-ETH", "KRW-SOL"]
    while True:
        try:
            # Collect tickers from pending orders
            pending_tickers = set()
            with mock_logic.lock:
                for order in mock_logic.orders.values():
                    if order["state"] == "wait":
                        pending_tickers.add(order["market"])
            
            # Combine with default tickers
            tickers_to_fetch = list(set(default_tickers) | pending_tickers)
            
            # Force fetch prices for all tickers in one API call
            if tickers_to_fetch:
                mock_logic.get_prices_for_markets(tickers_to_fetch, force_fetch=True)
                # Check orders immediately after price update
                mock_logic.check_orders()
            # Prices are automatically cached in price_overrides
        except Exception as e:
            logging.error(f"Price updater error: {e}")
        time.sleep(3)  # Update every 3 seconds to avoid 429

def order_matcher():
    while True:
        try:
            mock_logic.check_orders()
        except Exception as e:
            logging.error(f"Order matcher error: {e}")
        time.sleep(1)

# Start background threads


# --- Upbit API Endpoints ---

@app.get("/v1/candles/days")
def candles_days(market: str, count: int = 200, to: Optional[str] = None):
    """Proxy /v1/candles/days from real Upbit API"""
    if not mock_logic.live_api_base:
        return []
    
    try:
        url = f"{mock_logic.live_api_base}/v1/candles/days"
        params = {'market': market, 'count': count}
        if to: params['to'] = to
            
        logging.info(f"🌐 [UPBIT API PROXY] Days for {market} (to={to})")
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code == 200:
            return resp.json()
        else:
            logging.error(f"Upbit API Error {resp.status_code}: {resp.text}")
            raise HTTPException(status_code=resp.status_code, detail="Upbit API Error")
    except Exception as e:
        logging.error(f"Failed to proxy daily candles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/candles/minutes/{unit}")
def candles_minutes(unit: int, market: str, to: Optional[str] = None, count: int = 200):
    """Proxy /v1/candles/minutes/{unit} from real Upbit API"""
    if not mock_logic.live_api_base:
        return []
    
    try:
        url = f"{mock_logic.live_api_base}/v1/candles/minutes/{unit}"
        params = {'market': market, 'count': count}
        if to: params['to'] = to
            
        logging.info(f"🌐 [UPBIT API PROXY] Minutes/{unit} for {market} (to={to})")
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code == 200:
            return resp.json()
        else:
            logging.error(f"Upbit API Error {resp.status_code}: {resp.text}")
            raise HTTPException(status_code=resp.status_code, detail="Upbit API Error")
    except Exception as e:
        logging.error(f"Failed to proxy minute candles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Upbit API Endpoints ---

@app.get("/v1/accounts")
def accounts(request: Request):
    # Mock server accepts any request without authentication
    return mock_logic.get_accounts()

class OrderRequest(BaseModel):
    market: str
    side: str
    volume: Optional[str] = None
    price: Optional[str] = None
    ord_type: str

@app.post("/v1/orders")
def place_order(order: OrderRequest, request: Request):
    # Mock server accepts any request without authentication
    result = mock_logic.place_order(order.market, order.side, order.volume, order.price, order.ord_type)
    if "error" in result:
        return JSONResponse(content=result["error"], status_code=400)
    return result

@app.get("/v1/orders")
def get_orders(state: str = "wait"):
    return mock_logic.get_orders(state)

@app.get("/v1/order")
def get_order(uuid: str, request: Request):
    # Mock server accepts any request without authentication
    order = mock_logic.get_order(uuid)
    if order:
        return order
    return JSONResponse(content={"error": {"message": "Order not found"}}, status_code=404)

@app.delete("/v1/order")
def cancel_order(uuid: str, request: Request):
    # Mock server accepts any request without authentication
    result = mock_logic.cancel_order(uuid)
    if result:
        return result
    return JSONResponse(content={"error": {"message": "Order not found"}}, status_code=404)

@app.get("/v1/market/all")
def market_all(isDetails: bool = False):
    """Proxy /v1/market/all from real Upbit API or return defaults"""
    if mock_logic.live_api_base:
        try:
            url = f"{mock_logic.live_api_base}/v1/market/all"
            resp = requests.get(url, params={'isDetails': str(isDetails).lower()}, timeout=3)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logging.error(f"Failed to proxy /v1/market/all: {e}")
    
    # Fallback defaults if live API fails
    return [
        {"market": "KRW-BTC", "korean_name": "비트코인", "english_name": "Bitcoin"},
        {"market": "KRW-ETH", "korean_name": "이더리움", "english_name": "Ethereum"},
        {"market": "KRW-SOL", "korean_name": "솔라나", "english_name": "Solana"},
        {"market": "KRW-XRP", "korean_name": "리플", "english_name": "Ripple"}
    ]

@app.get("/v1/ticker")
def ticker(markets: str):
    if not markets:
        return []
    
    market_list = markets.split(",")
    prices = mock_logic.get_prices_for_markets(market_list)
    now = datetime.now(timezone.utc)
    timestamp_ms = int(time.time() * 1000)

    result = []
    for market in market_list:
        price = prices.get(market, 0.0)
        result.append({
            "market": market,
            "trade_date": now.strftime("%Y%m%d"),
            "trade_time": now.strftime("%H%M%S"),
            "trade_date_kst": now.strftime("%Y%m%d"),
            "trade_time_kst": now.strftime("%H%M%S"),
            "trade_timestamp": timestamp_ms,
            "opening_price": price,
            "high_price": price,
            "low_price": price,
            "trade_price": price,
            "prev_closing_price": price,
            "change": "EVEN",
            "change_price": 0,
            "change_rate": 0,
            "signed_change_price": 0,
            "signed_change_rate": 0,
            "trade_volume": 0,
            "acc_trade_price": 0,
            "acc_trade_price_24h": 0,
            "acc_trade_volume": 0,
            "acc_trade_volume_24h": 0,
            "highest_52_week_price": price,
            "highest_52_week_date": "2023-01-01",
            "lowest_52_week_price": price,
            "lowest_52_week_date": "2023-01-01",
            "timestamp": timestamp_ms
        })
    return result


# --- Mock Control Endpoints ---

class MockHoldRequest(BaseModel):
    ticker: str
    hold: bool = True

@app.post("/mock/hold")
def mock_hold(req: MockHoldRequest):
    mock_logic.hold_price(req.ticker, req.hold)
    return {"status": "ok", "ticker": req.ticker, "held": req.hold}

@app.get("/mock/hold")
def get_mock_hold(ticker: str):
    is_held = mock_logic.price_held.get(ticker, False)
    return {"ticker": ticker, "held": is_held}

class MockPriceRequest(BaseModel):
    ticker: str
    price: float

@app.post("/mock/price")
def mock_price(req: MockPriceRequest):
    mock_logic.set_price(req.ticker, req.price)
    return {"status": "ok", "ticker": req.ticker, "price": req.price}

@app.get("/mock/price")
def get_mock_price(ticker: str):
    """Return the current mock price for a ticker (respects hold/override)."""
    return {"ticker": ticker, "price": mock_logic.get_current_price(ticker)}

@app.post("/mock/reset")
def mock_reset():
    """Reset mock exchange state (balances, orders, prices)"""
    with mock_logic.lock:
        # 1. Clear all orders first
        mock_logic.orders = {}
        
        # Use the DB manager's reset method to clear DB tables
        try:
            mock_logic.db.reset_trading_data()
        except Exception as e:
            logging.error(f"Failed to reset DB data: {e}")

        # 2. Reset Balances
        mock_logic.balance = {"KRW": 10000000.0}
        mock_logic.avg_buy_prices = {}
        
        # 3. Reset Prices
        mock_logic.price_overrides = {}
        mock_logic.price_held = {}

        logging.info("Mock exchange reset to initial state")

    # Re-initialize default prices
    initialize_default_prices()
    
    return {
        "status": "ok",
        "message": "All balances and orders reset to initial state",
        "accounts": mock_logic.get_accounts()
    }

class MockBalanceRequest(BaseModel):
    currency: str
    balance: float
    avg_buy_price: float | None = None

@app.post("/mock/balance")
def mock_balance(req: MockBalanceRequest):
    with mock_logic.lock:
        mock_logic.balance[req.currency] = req.balance
        if req.avg_buy_price is not None:
            mock_logic.avg_buy_prices[req.currency] = req.avg_buy_price
        mock_logic._persist_balance(req.currency)
    # Return refreshed accounts for immediate UI update
    return {
        "status": "ok",
        "currency": req.currency,
        "balance": req.balance,
        "accounts": mock_logic.get_accounts()
    }

# --- Serve Exchange UI ---

@app.get("/")
def serve_ui():
    """Serve the exchange control panel UI"""
    index_path = os.path.join(EXCHANGE_UI_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Exchange UI not found. Please check exchange-ui directory."}

if __name__ == "__main__":
    # Reload can be enabled via env RELOAD=1 when desired
    enable_reload = os.getenv("RELOAD", "0") == "1"
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5001"))
    uvicorn.run("main:app", host=host, port=port, reload=enable_reload, access_log=False)
