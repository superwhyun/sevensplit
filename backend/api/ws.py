import asyncio
import logging
from fastapi import WebSocket, WebSocketDisconnect
from core.config import ws_connections
from api.router import get_full_snapshot

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
