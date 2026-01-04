import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Core and Engine
from core.config import BACKEND_DIR
from core.engine import start_engine
from api.router import router
from api.ws import websocket_endpoint

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI(title="Seven Split Bitcoin Bot")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(router)

# WebSocket Endpoint
app.websocket("/ws")(websocket_endpoint)

# Start Background Strategy Engine
start_engine()

# --- Static File Serving (Frontend) ---
FRONTEND_DIST = os.path.join(os.path.dirname(BACKEND_DIR), "frontend", "dist")

if os.path.exists(FRONTEND_DIST):
    # Mount assets directory
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/")
    async def serve_spa_root():
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        file_path = os.path.join(FRONTEND_DIST, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
else:
    @app.get("/")
    def read_root():
        return {"message": "Seven Split Bot API is running (Frontend build not found)"}
