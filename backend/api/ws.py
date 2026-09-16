import asyncio
import logging
import json
import time
from typing import Any, Dict, Optional, Tuple

from fastapi import WebSocket, WebSocketDisconnect
from core.config import ws_connections
from api.router import get_full_snapshot

# One snapshot per second is shared by every connected client, and it is built in a worker
# thread so the DB queries and strategy locks never block the asyncio event loop.
SNAPSHOT_TTL_SEC = 0.9
PUSH_INTERVAL_SEC = 1.0

_snapshot_cache: Dict[str, Any] = {"ts": 0.0, "data": None, "json": None}
_snapshot_lock: Optional[asyncio.Lock] = None


def _get_snapshot_lock() -> asyncio.Lock:
    global _snapshot_lock
    if _snapshot_lock is None:
        _snapshot_lock = asyncio.Lock()
    return _snapshot_lock


async def get_shared_snapshot() -> Tuple[dict, str]:
    """Return (snapshot, canonical_json), refreshing at most once per SNAPSHOT_TTL_SEC."""
    async with _get_snapshot_lock():
        now = time.monotonic()
        if _snapshot_cache["data"] is None or (now - _snapshot_cache["ts"]) >= SNAPSHOT_TTL_SEC:
            data = await asyncio.to_thread(get_full_snapshot)
            _snapshot_cache["data"] = data
            _snapshot_cache["json"] = json.dumps(data, sort_keys=True)
            _snapshot_cache["ts"] = now
        return _snapshot_cache["data"], _snapshot_cache["json"]


async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ws_connections.add(websocket)

    # Track last sent data to detect changes
    last_snapshot_json = None

    try:
        # Send initial snapshot immediately
        initial_snapshot, initial_json = await get_shared_snapshot()
        await websocket.send_json(initial_snapshot)
        last_snapshot_json = initial_json

        while True:
            await asyncio.sleep(PUSH_INTERVAL_SEC)

            current_snapshot, current_json = await get_shared_snapshot()

            # Only send if data has changed
            if current_json != last_snapshot_json:
                await websocket.send_json(current_snapshot)
                last_snapshot_json = current_json

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
    finally:
        ws_connections.discard(websocket)
