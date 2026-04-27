"""
main.py — Точка входа CONSILIUM AI v3.0
Запуск: uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from loguru import logger
import os

from app.config import settings
from app.database import init_database
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.council import router as council_router
from app.api.ws_council import router as ws_router

# ── Приложение ────────────────────────────────────────────────────────────
app = FastAPI(
    title="Consilium AI v3.0",
    description="Multi-agent Intellectual Work Environment",
    version="3.0.0",
)

# ── CORS ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Роутеры ───────────────────────────────────────────────────────────────
# Auth монтируем дважды:
#   /register  /login  /verify       ← используется при регистрации
#   /api/auth/register  /api/auth/login  /api/auth/verify  ← используется при логине
app.include_router(auth_router,    prefix="",          tags=["auth"])
app.include_router(auth_router,    prefix="/api/auth", tags=["auth-compat"])
app.include_router(chat_router,    prefix="",          tags=["chat"])
app.include_router(council_router, prefix="",          tags=["council"])
app.include_router(ws_router,      prefix="",          tags=["websocket"])

# ── Статические файлы (frontend) ──────────────────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")

if os.path.exists(FRONTEND_DIR):
    for subdir in ("img", "css", "js"):
        subpath = os.path.join(FRONTEND_DIR, subdir)
        if os.path.exists(subpath):
            app.mount(f"/{subdir}", StaticFiles(directory=subpath), name=subdir)

    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    async def serve_frontend():
        index = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index):
            return FileResponse(index)
        return {"status": "ok", "message": "Consilium AI v3.0"}

# ── Health & Version ──────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "consilium-ai",
        "version": "3.0.0",
        "env": os.getenv("APP_ENV", "dev"),
    }

@app.head("/health")
async def health_head():
    """Render использует HEAD для healthcheck на cold-start."""
    return Response(status_code=200)

@app.get("/version")
async def version():
    return {"version": "3.0.0", "service": "consilium-ai"}

# ── Startup ───────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Starting Consilium AI v3.0...")
    init_database()
    logger.info(f"✅ Database initialized: {settings.DATABASE_URL}")
    logger.info(f"✅ CORS origins: {settings.CORS_ORIGINS}")
    logger.info(f"✅ Frontend: {FRONTEND_DIR}")
    logger.info("🎯 Consilium AI v3.0 is ready!")
    logger.info("   UI:      http://localhost:8000/")
    logger.info("   Docs:    http://localhost:8000/docs")
    logger.info("   Health:  http://localhost:8000/health")
    logger.info("   WS:      ws://localhost:8000/ws/council")
