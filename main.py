"""
main.py â€” Đ˘ĐľŃ‡ĐşĐ° Đ˛Ń…ĐľĐ´Đ° CONSILIUM AI v3.0
Đ—Đ°ĐżŃŃĐş: uvicorn main:app --reload --port 8000
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
from app.api.experience import router as experience_router
from app.api.knowledge import router as knowledge_router
from app.middleware.security import add_security_headers
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False

# â”€â”€ ĐźŃ€Đ¸Đ»ĐľĐ¶ĐµĐ˝Đ¸Đµ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
app = FastAPI(
    title="Consilium AI v3.0",
    description="Multi-agent Intellectual Work Environment",
    version="3.0.0",
)

# â”€â”€ CORS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# â”€â”€ Đ ĐľŃŃ‚ĐµŃ€Ń‹ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Auth ĐĽĐľĐ˝Ń‚Đ¸Ń€ŃĐµĐĽ Đ´Đ˛Đ°Đ¶Đ´Ń‹:
#   /register  /login  /verify       â† Đ¸ŃĐżĐľĐ»ŃŚĐ·ŃĐµŃ‚ŃŃŹ ĐżŃ€Đ¸ Ń€ĐµĐłĐ¸ŃŃ‚Ń€Đ°Ń†Đ¸Đ¸
#   /api/auth/register  /api/auth/login  /api/auth/verify  â† Đ¸ŃĐżĐľĐ»ŃŚĐ·ŃĐµŃ‚ŃŃŹ ĐżŃ€Đ¸ Đ»ĐľĐłĐ¸Đ˝Đµ
app.include_router(auth_router,       prefix="",          tags=["auth"])
app.include_router(auth_router,       prefix="/api/auth",  tags=["auth-compat"])
app.include_router(chat_router,       prefix="",           tags=["chat"])
app.include_router(council_router,    prefix="",           tags=["council"])
app.include_router(ws_router,         prefix="",           tags=["websocket"])
app.include_router(experience_router, tags=["experience"])
app.include_router(knowledge_router, tags=["knowledge"])

# â”€â”€ Security headers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
add_security_headers(app)

# â”€â”€ ĐˇŃ‚Đ°Ń‚Đ¸Ń‡ĐµŃĐşĐ¸Đµ Ń„Đ°ĐąĐ»Ń‹ (frontend) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

# â”€â”€ Health & Version â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
    """Render Đ¸ŃĐżĐľĐ»ŃŚĐ·ŃĐµŃ‚ HEAD Đ´Đ»ŃŹ healthcheck Đ˝Đ° cold-start."""
    return Response(status_code=200)

@app.get("/version")
async def version():
    return {"version": "3.0.0", "service": "consilium-ai"}

# â”€â”€ Startup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.on_event("startup")
async def startup_event():
    logger.info("đźš€ Starting Consilium AI v3.0...")
    init_database()
    logger.info(f"âś… Database initialized: {settings.DATABASE_URL}")
    logger.info(f"âś… CORS origins: {settings.CORS_ORIGINS}")
    logger.info(f"âś… Frontend: {FRONTEND_DIR}")
    logger.info("đźŽŻ Consilium AI v3.0 is ready!")
    logger.info("   UI:      http://localhost:8000/")
    logger.info("   Docs:    http://localhost:8000/docs")
    logger.info("   Health:  http://localhost:8000/health")
    logger.info("   WS:      ws://localhost:8000/ws/council")

