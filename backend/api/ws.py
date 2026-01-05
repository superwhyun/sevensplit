import asyncio
import logging
import json
from fastapi import WebSocket, WebSocketDisconnect
from core.config import ws_connections
from api.router import get_full_snapshot

async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ws_connections.add(websocket)

    # Track last sent data to detect changes
    last_snapshot = None

    try:
        # Send initial snapshot immediately
        initial_snapshot = get_full_snapshot()
        await websocket.send_json(initial_snapshot)
        last_snapshot = json.dumps(initial_snapshot, sort_keys=True)

        while True:
            # Check for changes every second
            await asyncio.sleep(1)

            current_snapshot = get_full_snapshot()
            current_json = json.dumps(current_snapshot, sort_keys=True)

            # Only send if data has changed
            if current_json != last_snapshot:
                await websocket.send_json(current_snapshot)
                last_snapshot = current_json

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
    finally:
        ws_connections.discard(websocket)
