import os
import logging
from dotenv import load_dotenv
from exchange import UpbitExchange
from database import get_db
from services.exchange_service import ExchangeService
from services.strategy_service import StrategyService
from typing import Dict, Set

# --- Environment Setup ---
BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
env_filename = os.getenv("ENV_FILE", ".env")
load_dotenv(os.path.join(BACKEND_DIR, env_filename))

# --- Global Components ---
db = get_db()

# --- Upbit Exchange Initialization ---
env_access_key = os.getenv("UPBIT_ACCESS_KEY")
env_secret_key = os.getenv("UPBIT_SECRET_KEY")
server_url_env = os.getenv("UPBIT_OPEN_API_SERVER_URL")
server_url = server_url_env if server_url_env else "https://api.upbit.com"
env_mode = os.getenv("MODE", "").upper()

if env_mode == "MOCK":
    if not server_url_env:
        server_url = "http://localhost:5001"
    access_key = env_access_key or "mock_access_key"
    secret_key = env_secret_key or "mock_secret_key"
    exchange = UpbitExchange(access_key, secret_key, server_url=server_url)
    current_mode = "MOCK"
    print(f"Using Mock Exchange via API (forced by MODE=mock) URL: {server_url}")
elif env_mode == "REAL":
    access_key = env_access_key
    secret_key = env_secret_key
    exchange = UpbitExchange(access_key, secret_key, server_url=server_url)
    current_mode = "REAL"
    print(f"Using Upbit Exchange (forced by MODE=real) URL: {server_url}")
else:
    if env_access_key and env_secret_key:
        exchange = UpbitExchange(env_access_key, env_secret_key, server_url=server_url)
        current_mode = "REAL"
        print(f"Using Upbit Exchange from .env (URL: {server_url})")
    else:
        if not server_url_env:
            server_url = "http://localhost:5001"
        exchange = UpbitExchange("mock_access_key", "mock_secret_key", server_url=server_url)
        current_mode = "MOCK"
        print(f"Using Upbit Exchange with default mock creds (URL: {server_url})")

# --- Real Upbit Exchange for Candle Data (Always Pointing to REAL API) ---
# This is used to fetch reliable candle data for caching, even when in MOCK mode.
real_exchange = UpbitExchange(
    env_access_key or "dummy", 
    env_secret_key or "dummy", 
    server_url="https://api.upbit.com"
)

# --- Services ---
exchange_service = ExchangeService(exchange)
strategy_service = StrategyService(db, exchange_service)
strategy_service.load_strategies()

# --- Global States & Caches ---
ws_connections: Set = set()
shared_prices: Dict[str, float] = {}
accounts_cache = {'data': [], 'timestamp': 0.0}
supplementary_price_cache = {'data': {}, 'timestamp': 0.0}
candle_cache = {'data': {}, 'timestamp': {}}  # {ticker: {interval: candles}}
