import os
import logging
from dotenv import load_dotenv
from exchange import PaperExchange, UpbitExchange
from database import get_candle_db, get_db
from services.exchange_service import ExchangeService
from services.simulation_service import SimulationService
from services.strategy_service import StrategyService
from typing import Dict, Set

# --- Environment Setup ---
BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
env_filename = os.getenv("ENV_FILE", ".env.dev")
load_dotenv(os.path.join(BACKEND_DIR, env_filename))
trading_mode = os.getenv("TRADING_MODE", "DEV").upper()

# --- Global Components ---
db = get_db()

# --- Exchange Initialization ---
env_access_key = os.getenv("UPBIT_ACCESS_KEY")
env_secret_key = os.getenv("UPBIT_SECRET_KEY")
server_url_env = os.getenv("UPBIT_OPEN_API_SERVER_URL")
server_url = server_url_env if server_url_env else "https://api.upbit.com"

if trading_mode == "REAL":
    if not env_access_key or not env_secret_key:
        raise RuntimeError("Missing UPBIT_ACCESS_KEY/UPBIT_SECRET_KEY for REAL mode.")
    exchange = UpbitExchange(env_access_key, env_secret_key, server_url=server_url)
    current_mode = "REAL"
    print(f"Using Upbit Exchange (URL: {server_url})")
elif trading_mode in ("DEV", "PAPER"):
    public_client = UpbitExchange("paper", "paper", server_url=server_url)
    initial_krw = float(os.getenv("DEV_INITIAL_KRW") or os.getenv("PAPER_INITIAL_KRW", "10000000"))
    exchange = PaperExchange(public_client=public_client, initial_krw=initial_krw)
    current_mode = "DEV"
    print(f"Using Dev Exchange (public market data URL: {server_url}, initial_krw={initial_krw})")
else:
    raise RuntimeError(f"Invalid TRADING_MODE: {trading_mode}. Use REAL or DEV.")

# --- Real Upbit Exchange for Candle Data (Always Pointing to REAL API) ---
# This is used to fetch reliable candle data for caching.
real_exchange = UpbitExchange(
    env_access_key or "dummy", 
    env_secret_key or "dummy", 
    server_url="https://api.upbit.com"
)

# --- Services ---
exchange_service = ExchangeService(exchange)
strategy_service = StrategyService(db, exchange_service)
strategy_service.load_strategies()
simulation_service = SimulationService(db=db, candle_db=get_candle_db(), public_exchange=real_exchange)

# --- Global States & Caches ---
ws_connections: Set = set()
shared_prices: Dict[str, float] = {}
accounts_cache = {'data': [], 'timestamp': 0.0}
supplementary_price_cache = {'data': {}, 'timestamp': 0.0}
candle_cache = {'data': {}, 'timestamp': {}}  # {ticker: {interval: candles}}
