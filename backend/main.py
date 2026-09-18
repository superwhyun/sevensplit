import os
import logging
import secrets
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Configure logging. INFO keeps buy/sell execution and order reconciliation visible in
# container logs; per-tick chatter is emitted at DEBUG. Override with LOG_LEVEL=DEBUG|WARNING.
_log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
logging.basicConfig(level=_log_level, format='%(asctime)s - %(levelname)s - %(message)s')

# Core and Engine
from core.config import BACKEND_DIR
from core.engine import start_engine
from api.router import router
from api.ws import websocket_endpoint

app = FastAPI(title="Seven Split Bitcoin Bot")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Optional dashboard password ---
# When DASHBOARD_PASSWORD is set, every state-changing request and the settings endpoints
# must carry the password in the X-Dashboard-Password header. Read-only dashboard data stays
# open so the WebSocket feed keeps working. Leave the variable unset for localhost-only use.
DASHBOARD_PASSWORD = (os.getenv("DASHBOARD_PASSWORD") or "").strip()
AUTH_HEADER = "x-dashboard-password"
PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
PROTECTED_GET_PREFIXES = ("/settings",)
AUTH_EXEMPT_PATHS = {"/auth/status", "/auth/check"}


def _is_protected(request: Request) -> bool:
    path = request.url.path
    if path in AUTH_EXEMPT_PATHS:
        return False
    if request.method in PROTECTED_METHODS:
        return True
    return request.method == "GET" and path.startswith(PROTECTED_GET_PREFIXES)


def _password_matches(candidate: str) -> bool:
    return secrets.compare_digest((candidate or "").encode("utf-8"), DASHBOARD_PASSWORD.encode("utf-8"))


@app.middleware("http")
async def dashboard_password_guard(request: Request, call_next):
    if DASHBOARD_PASSWORD and _is_protected(request) and request.method != "OPTIONS":
        if not _password_matches(request.headers.get(AUTH_HEADER, "")):
            return JSONResponse(status_code=401, content={"detail": "대시보드 비밀번호가 필요합니다."})
    return await call_next(request)


@app.get("/auth/status")
def auth_status():
    return {"password_required": bool(DASHBOARD_PASSWORD)}


@app.post("/auth/check")
async def auth_check(request: Request):
    if not DASHBOARD_PASSWORD:
        return {"ok": True}
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    candidate = (body or {}).get("password") or request.headers.get(AUTH_HEADER, "")
    if _password_matches(candidate):
        return {"ok": True}
    return JSONResponse(status_code=401, content={"ok": False, "detail": "비밀번호가 올바르지 않습니다."})


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
