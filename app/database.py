"""
app/database.py -- SQLAlchemy engine, metadata, table definitions.

Supports both SQLite (local dev) and PostgreSQL (production on AWS RDS).
DATABASE_URL in .env controls which is used:
  SQLite:     sqlite:///./consilium.db
  PostgreSQL: postgresql://user:pass@host:5432/consilium
"""

from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String,
    MetaData, Table, inspect, Text, DateTime, Float, Boolean,
)
from sqlalchemy.pool import NullPool, QueuePool
from loguru import logger

from app.config import settings

# ── Engine — auto-detect SQLite vs PostgreSQL ─────────────────────────────────
_db_url = settings.DATABASE_URL

if _db_url.startswith("sqlite"):
    # SQLite: local dev only
    engine = create_engine(
        _db_url,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    logger.info("DB: SQLite (local dev mode)")
else:
    # PostgreSQL: production (AWS RDS or Supabase)
    engine = create_engine(
        _db_url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,      # auto-reconnect on stale connections
        pool_recycle=300,        # recycle connections every 5 min
        echo=False,
    )
    logger.info("DB: PostgreSQL (production mode)")

metadata = MetaData()

# ── Tables ────────────────────────────────────────────────────────────────────

users = Table(
    "users",
    metadata,
    Column("id",            Integer,      primary_key=True),
    Column("email",         String(255),  unique=True, nullable=False),
    Column("password_hash", String(255),  nullable=False),
    Column("credits",       Integer,      default=10),
    Column("auth_token",    String(255),  nullable=True),
    Column("created_at",    DateTime,     default=datetime.utcnow),
)

chat_history = Table(
    "chat_history",
    metadata,
    Column("id",         Integer,      primary_key=True),
    Column("user_id",    Integer,      nullable=False),
    Column("chat_id",    String(100),  nullable=False),
    Column("title",      String(255)),
    Column("messages",   Text),
    Column("updated_at", DateTime,     default=datetime.utcnow),
)

# -- Experience Layer ---------------------------------------------------------
experience_sessions = Table(
    "experience_sessions",
    metadata,
    Column("id",                Integer,      primary_key=True),
    Column("user_id",           Integer,      nullable=False),
    Column("chat_id",           String(100),  nullable=False),
    Column("query_text",        Text,         nullable=False),
    Column("query_hash",        String(64),   nullable=False),
    Column("task_type",         String(100),  nullable=True),
    Column("protocol_used",     String(100),  nullable=True),
    Column("selected_directors",Text,         nullable=True),
    Column("started_at",        DateTime,     default=datetime.utcnow),
    Column("finished_at",       DateTime,     nullable=True),
    Column("latency_ms",        Integer,      nullable=True),
    Column("cost_usd",          Float,        nullable=True),
    Column("status",            String(20),   default="running"),
    Column("outcome_label",     String(50),   nullable=True),
    Column("coherence_score",   Float,        nullable=True),
    Column("user_rating",       Integer,      nullable=True),
    Column("helpfulness_score", Float,        nullable=True),
    Column("feedback_text",     Text,         nullable=True),
    Column("followup_required", Boolean,      default=False),
)

experience_signals = Table(
    "experience_signals",
    metadata,
    Column("id",           Integer,      primary_key=True),
    Column("session_id",   Integer,      nullable=False),
    Column("signal_type",  String(100),  nullable=False),
    Column("value_num",    Float,        nullable=True),
    Column("value_text",   Text,         nullable=True),
    Column("source",       String(100),  nullable=True),
    Column("weight",       Float,        default=1.0),
    Column("created_at",   DateTime,     default=datetime.utcnow),
)

# -- Decision Journal ---------------------------------------------------------
decision_journal = Table(
    "decision_journal",
    metadata,
    Column("id",             Integer,      primary_key=True),
    Column("user_id",        Integer,      nullable=False),
    Column("session_id",     Integer,      nullable=True),
    Column("title",          String(255),  nullable=False),
    Column("query_text",     Text,         nullable=False),
    Column("verdict",        Text,         nullable=False),
    Column("council_used",   String(500),  nullable=True),
    Column("outcome_label",  String(50),   nullable=True),
    Column("tags",           String(500),  nullable=True),
    Column("is_pinned",      Boolean,      default=False),
    Column("approval_state", String(20),   default="draft"),
    Column("created_at",     DateTime,     default=datetime.utcnow),
    Column("updated_at",     DateTime,     default=datetime.utcnow),
)

# -- User Principles ----------------------------------------------------------
user_principles = Table(
    "user_principles",
    metadata,
    Column("id",         Integer,      primary_key=True),
    Column("user_id",    Integer,      nullable=False),
    Column("title",      String(255),  nullable=False),
    Column("body",       Text,         nullable=False),
    Column("source",     String(255),  nullable=True),
    Column("category",   String(100),  nullable=True),
    Column("is_active",  Boolean,      default=True),
    Column("created_at", DateTime,     default=datetime.utcnow),
)


def init_database() -> None:
    """Create all tables if they don't exist. Safe to run on every startup."""
    try:
        inspector = inspect(engine)

        # Handle SQLite legacy migration (auth_token column)
        if _db_url.startswith("sqlite") and inspector.has_table("users"):
            columns = [col["name"] for col in inspector.get_columns("users")]
            if "auth_token" not in columns:
                logger.warning("DB schema outdated -- running migration...")
                metadata.drop_all(engine, tables=[users])

        # Create all missing tables
        metadata.create_all(engine)
        logger.info("Database initialized")

    except Exception as e:
        logger.error(f"Database init failed: {e}")
        raise
