"""
app/database.py — Подключение к базе данных, определение таблиц.
"""

from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String,
    MetaData, Table, inspect, Text, DateTime,
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

    logger.info("✅ Database initialized")
