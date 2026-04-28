"""
app/database.py — Подключение к базе данных, определение таблиц.
"""

from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String,
    MetaData, Table, inspect, Text, DateTime, Float, Boolean,
)
from loguru import logger

from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
)
metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("email", String(255), unique=True, nullable=False),
    Column("password_hash", String(255), nullable=False),
    Column("credits", Integer, default=10),
    Column("auth_token", String(255), nullable=True),
    Column("created_at", DateTime, default=datetime.utcnow),
)

chat_history = Table(
    "chat_history",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, nullable=False),
    Column("chat_id", String(100), nullable=False),
    Column("title", String(255)),
    Column("messages", Text),
    Column("updated_at", DateTime, default=datetime.utcnow),
)

# ── Experience Layer ──────────────────────────────────────────────────────────
experience_sessions = Table(
    "experience_sessions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, nullable=False),
    Column("chat_id", String(100), nullable=False),
    Column("query_text", Text, nullable=False),
    Column("query_hash", String(64), nullable=False),
    Column("task_type", String(100), nullable=True),
    Column("protocol_used", String(100), nullable=True),
    Column("selected_directors", Text, nullable=True),
    Column("started_at", DateTime, default=datetime.utcnow),
    Column("finished_at", DateTime, nullable=True),
    Column("latency_ms", Integer, nullable=True),
    Column("cost_usd", Float, nullable=True),
    Column("status", String(20), default="running"),
    Column("outcome_label", String(50), nullable=True),
    Column("coherence_score", Float, nullable=True),
    Column("user_rating", Integer, nullable=True),
    Column("helpfulness_score", Float, nullable=True),
    Column("feedback_text", Text, nullable=True),
    Column("followup_required", Boolean, default=False),
)

experience_signals = Table(
    "experience_signals",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("session_id", Integer, nullable=False),
    Column("signal_type", String(100), nullable=False),
    Column("value_num", Float, nullable=True),
    Column("value_text", Text, nullable=True),
    Column("source", String(100), nullable=True),
    Column("weight", Float, default=1.0),
    Column("created_at", DateTime, default=datetime.utcnow),
)


def init_database() -> None:
    """Создаёт таблицы при первом запуске или обновляет структуру."""
    inspector = inspect(engine)

    if inspector.has_table("users"):
        columns = [col["name"] for col in inspector.get_columns("users")]
        if "auth_token" not in columns:
            logger.warning("Структура БД устарела — выполняется миграция...")
            metadata.drop_all(engine, tables=[users])
            metadata.create_all(engine)
            logger.info("✅ База данных обновлена!")
    else:
        metadata.create_all(engine)

    if not inspector.has_table("chat_history"):
        chat_history.create(engine)

    # Experience Layer — создаём если ещё нет
    if not inspector.has_table("experience_sessions"):
        experience_sessions.create(engine)
        logger.info("✅ experience_sessions table created")

    if not inspector.has_table("experience_signals"):
        experience_signals.create(engine)
        logger.info("✅ experience_signals table created")

    logger.info("✅ Database initialized")
