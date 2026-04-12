"""
main.py — CONSILIUM AI v3.0
Запуск: uvicorn main:app --reload --port 8000
"""

import os
import sys
from loguru import logger

os.makedirs("logs", exist_ok=True)
logger.remove()
logger.add(sys.stdout, level="INFO", colorize=True,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
logger.add("logs/consilium_{time:YYYY-MM-DD}.log",
    rotation="10 MB", retention="30 days", level="DEBUG", encoding="utf-8")

logger.info("🚀 CONSILIUM AI v3.0 — запуск сервера")

# Путь к основному проекту с бизнес-логикой
OLD_PROJECT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '..', 'Consilium AI')
OLD_PROJECT = os.path.normpath(OLD_PROJECT)

if not os.path.exists(OLD_PROJECT):
    # Fallback: абсолютный путь
    OLD_PROJECT = r"C:\Users\HP\OneDrive\Рабочий стол\Consilium AI"

if OLD_PROJECT not in sys.path:
    sys.path.insert(0, OLD_PROJECT)

# Меняем рабочую директорию чтобы SQLite нашёл consilium.db
os.chdir(OLD_PROJECT)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_database
from app.api import auth, chat, council
from app.api import ws_council

init_database()

app = FastAPI(title="CONSILIUM AI v3.0", version="3.0.0")

# Статика — фронтенд из v30
V30_DIR = os.path.dirname(os.path.abspath(__file__))
V30_FRONTEND = os.path.join(V30_DIR, 'frontend')

app.mount("/static", StaticFiles(directory=V30_FRONTEND), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(council.router)
app.include_router(ws_council.router)

@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(V30_FRONTEND, 'index.html'))

logger.info(f"✅ Сервер готов | http://localhost:8000 | Frontend: {V30_FRONTEND}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
