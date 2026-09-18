import os
import logging
import threading
from dotenv import load_dotenv
from exchange import PaperExchange, UpbitExchange
from database import get_candle_db, get_db
from services.exchange_service import ExchangeService
from services.settings_service import MODE_REAL, SettingsService
from services.simulation_service import SimulationService
from services.strategy_service import StrategyService
from typing import Dict, Set

# --- Environment Setup ---
BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
env_filename = os.getenv("ENV_FILE", ".env.dev")
load_dotenv(os.path.join(BACKEND_DIR, env_filename))

server_url_env = os.getenv("UPBIT_OPEN_API_SERVER_URL")
server_url = server_url_env if server_url_env else "https://api.upbit.com"

# --- Global Components ---
db = get_db()

# The strategy engine ticks under this lock; settings changes that swap the exchange
# or reload strategies take it too, so a tick never straddles a mode switch.
engine_lock = threading.RLock()

# --- Global States & Caches ---
ws_connections: Set = set()
shared_prices: Dict[str, float] = {}
accounts_cache = {'data': [], 'timestamp': 0.0}
supplementary_price_cache = {'data': {}, 'timestamp': 0.0}
candle_cache = {'data': {}, 'timestamp': {}}  # {ticker: {interval: candles}}


def build_exchange(mode: str, access_key, secret_key, paper_initial_krw: float):
    """Concrete exchange for an execution mode. Used at boot and on every mode switch."""
    if mode == MODE_REAL:
        if not access_key or not secret_key:
            raise RuntimeError("Missing UPBIT_ACCESS_KEY/UPBIT_SECRET_KEY for REAL mode.")
        logging.info(f"Using Upbit Exchange (URL: {server_url})")
        return UpbitExchange(access_key, secret_key, server_url=server_url)

    public_client = UpbitExchange("paper", "paper", server_url=server_url)
    logging.info(
        f"Using Paper Exchange (public market data URL: {server_url}, initial_krw={paper_initial_krw:,.0f})"
    )
    return PaperExchange(public_client=public_client, initial_krw=paper_initial_krw)


def validate_upbit_keys(access_key: str, secret_key: str) -> dict:
    return UpbitExchange(access_key, secret_key, server_url=server_url).verify_credentials()


# --- Real Upbit Exchange for Candle Data (Always Pointing to REAL API) ---
# Public endpoints only; credentials are not required for candles.
real_exchange = UpbitExchange("dummy", "dummy", server_url="https://api.upbit.com")

# --- Services ---
exchange_service = ExchangeService(None)
strategy_service = StrategyService(db, exchange_service)
settings_service = SettingsService(
    db=db,
    exchange_service=exchange_service,
    strategy_service=strategy_service,
    exchange_factory=build_exchange,
    key_validator=validate_upbit_keys,
    env=dict(os.environ),
    engine_lock=engine_lock,
    accounts_cache=accounts_cache,
)
settings_service.bootstrap()
simulation_service = SimulationService(db=db, candle_db=get_candle_db(), public_exchange=real_exchange)
