"""Singleton factories for database managers."""

import os

from .managers import DatabaseManager, PriceDatabaseManager

_db_manager = None
_candle_db_manager = None
_price_db_manager = None


def get_db() -> DatabaseManager:
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def get_candle_db() -> DatabaseManager:
    global _candle_db_manager
    if _candle_db_manager is None:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        market_db_path = os.getenv("CANDLE_DB_PATH")
        if not market_db_path:
            market_db_path = os.path.join(backend_dir, "database", "market_data.db")
        market_db_dir = os.path.dirname(os.path.abspath(market_db_path))
        os.makedirs(market_db_dir, exist_ok=True)
        _candle_db_manager = DatabaseManager(db_path=market_db_path)
    return _candle_db_manager


def get_price_db() -> PriceDatabaseManager:
    global _price_db_manager
    if _price_db_manager is None:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        price_db_path = os.getenv("PRICE_DB_PATH")
        if not price_db_path:
            price_db_path = os.path.join(backend_dir, "database", "price_data.db")
        price_db_dir = os.path.dirname(os.path.abspath(price_db_path))
        os.makedirs(price_db_dir, exist_ok=True)
        _price_db_manager = PriceDatabaseManager(db_path=price_db_path)
    return _price_db_manager
