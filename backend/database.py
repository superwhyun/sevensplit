"""Backward-compatible database exports.

This module remains as a compatibility layer for existing imports.
Implementation details now live under `backend/db/`.
"""

from db import (  # noqa: F401
    Base,
    CandleDays,
    CandleMinutes5,
    CandleMinutes60,
    DatabaseManager,
    Split,
    Strategy,
    SystemConfig,
    SystemEvent,
    Trade,
    get_candle_db,
    get_db,
)

__all__ = [
    "Base",
    "Strategy",
    "Split",
    "Trade",
    "SystemConfig",
    "SystemEvent",
    "CandleMinutes5",
    "CandleMinutes60",
    "CandleDays",
    "DatabaseManager",
    "get_db",
    "get_candle_db",
]
