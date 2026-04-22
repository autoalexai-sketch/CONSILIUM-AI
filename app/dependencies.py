"""
app/dependencies.py — Вспомогательные функции:
  • Хэширование и проверка паролей
  • JWT: создание и верификация токенов
  • Зависимость get_current_user (FastAPI Depends)
  • Логирование классификации
  • Отправка welcome-письма
"""

import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

import aiosmtplib
from email.message import EmailMessage
from fastapi import HTTPException, Header
from jose import JWTError, jwt
from sqlalchemy.sql import select
from loguru import logger

from app.config import settings
from app.database import engine, users
from core.cognitive_classifier import TaskProfile


# ── Пароли ────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    import bcrypt
    sha_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(sha_hash.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    import bcrypt
    sha_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return bcrypt.checkpw(sha_hash.encode("utf-8"), hashed.encode("utf-8"))


# ── JWT ───────────────────────────────────────────────────────────────────

def create_access_token(user_id: int, email: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    payload = {
        "sub":   str(user_id),
        "email": email,
        "iat":   now,
        "exp":   expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_jwt_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as e:
        logger.debug(f"JWT verify failed: {e}")
        return None


# ── Логирование классификации ─────────────────────────────────────────────

async def save_classification_log(query: str, profile: TaskProfile) -> None:
    try:
        conn = sqlite3.connect(settings.DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO classification_logs
            (query_preview, detected_language, dimensions, emotional_load,
             urgency, ambiguity_score, required_depth, confidence_score, processing_time_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                query[:100],
                profile.suggested_language,
                ",".join([d.name for d in profile.dimensions]),
                profile.emotional_load,
                profile.urgency,
                profile.ambiguity_score,
                profile.required_depth,
                profile.confidence_score,
                profile.processing_time_ms,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"Classification log skipped: {e}")


# ── Welcome-письмо ────────────────────────────────────────────────────────

async def send_welcome_email(user_email: str, lang: str = "pl") -> None:
    if not settings.SMTP_USER or not settings.SMTP_PASS:
        logger.debug("SMTP не настроен — отправка письма пропущена")
        return

    subjects = {
        "pl": "Witamy w Consilium AI!",
        "en": "Welcome to Consilium AI!",
        "ru": "Добро пожаловать в Consilium AI!",
        "ua": "Вітаємо в Consilium AI!",
    }
    contents = {
        "en": "Welcome to Consilium AI!\n\nYour account is active. You received 10 free credits.\n\nConsilium AI Team",
        "pl": "Witamy w Consilium AI!\n\nTwoje konto jest aktywne. Otrzymałeś 10 darmowych kredytów.\n\nZespół Consilium AI",
        "ru": "Добро пожаловать в Consilium AI!\n\nАккаунт активирован. Вы получили 10 кредитов.\n\nКоманда Consilium AI",
        "ua": "Вітаємо в Consilium AI!\n\nАкаунт активовано. Ви отримали 10 кредитів.\n\nКоманда Consilium AI",
    }

    message = EmailMessage()
    message["From"] = settings.SMTP_USER
    message["To"] = user_email
    message["Subject"] = subjects.get(lang, subjects["en"])
    message.set_content(contents.get(lang, contents["en"]))

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_SERVER,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASS,
            start_tls=True,
        )
        logger.info(f"📧 Welcome email отправлен: {user_email}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки email на {user_email}: {e}")


# ── Аутентификация (FastAPI Depends) ──────────────────────────────────────

async def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = authorization.split(" ")[1]
    payload = verify_jwt_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token invalid or expired. Please log in again.")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Malformed token: missing sub")

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Malformed token: invalid sub")

    with engine.connect() as conn:
        user = conn.execute(select(users).where(users.c.id == user_id)).fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="User not found.")
        return user
