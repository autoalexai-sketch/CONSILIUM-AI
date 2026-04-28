"""
ExperienceService — MVP слой опыта для CONSILIUM AI v3.0.

Замкнутый цикл:
  create_session() → [делиберация] → finalize_session() + add_signal()

Таблицы: experience_sessions, experience_signals (см. app/database.py)
"""

import hashlib
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from loguru import logger

from app.database import engine


class ExperienceService:
    """Пишет и читает опыт сессий. Синхронный (движок SQLAlchemy Core)."""

    # ── Создание сессии ───────────────────────────────────────────────────
    def create_session(
        self,
        user_id: int,
        chat_id: str,
        query_text: str,
        task_type: Optional[str] = None,
        protocol_used: Optional[str] = None,
        selected_directors: Optional[list] = None,
    ) -> int:
        """
        Создаёт запись experience_sessions со статусом 'running'.
        Возвращает id новой сессии.
        """
        query_hash = hashlib.sha256(
            query_text.strip().lower().encode("utf-8")
        ).hexdigest()

        stmt = text("""
            INSERT INTO experience_sessions
              (user_id, chat_id, query_text, query_hash,
               task_type, protocol_used, selected_directors,
               started_at, status)
            VALUES
              (:user_id, :chat_id, :query_text, :query_hash,
               :task_type, :protocol_used, :selected_directors,
               :started_at, 'running')
        """)
        with engine.begin() as conn:
            result = conn.execute(stmt, {
                "user_id":            user_id,
                "chat_id":            chat_id,
                "query_text":         query_text[:2000],
                "query_hash":         query_hash,
                "task_type":          task_type,
                "protocol_used":      protocol_used,
                "selected_directors": str(selected_directors or []),
                "started_at":         datetime.utcnow(),
            })
            # SQLite: lastrowid
            session_id = result.lastrowid

        logger.debug(f"📝 ExperienceSession created: id={session_id}")
        return session_id

    # ── Финализация сессии ────────────────────────────────────────────────
    def finalize_session(
        self,
        session_id: int,
        status: str = "success",
        outcome_label: str = "unverified",
        coherence_score: Optional[float] = None,
        latency_ms: Optional[int] = None,
        cost_usd: Optional[float] = None,
    ) -> None:
        """Обновляет сессию — ставит статус, coherence и latency."""
        stmt = text("""
            UPDATE experience_sessions
            SET status          = :status,
                outcome_label   = :outcome_label,
                coherence_score = :coherence_score,
                latency_ms      = :latency_ms,
                cost_usd        = :cost_usd,
                finished_at     = :finished_at
            WHERE id = :session_id
        """)
        with engine.begin() as conn:
            conn.execute(stmt, {
                "session_id":      session_id,
                "status":          status,
                "outcome_label":   outcome_label,
                "coherence_score": coherence_score,
                "latency_ms":      latency_ms,
                "cost_usd":        cost_usd,
                "finished_at":     datetime.utcnow(),
            })
        logger.debug(f"📝 ExperienceSession finalized: id={session_id} status={status}")

    # ── Сигнал качества ───────────────────────────────────────────────────
    def add_signal(
        self,
        session_id: int,
        signal_type: str,
        value_num: Optional[float] = None,
        value_text: Optional[str] = None,
        source: str = "system",
        weight: float = 1.0,
    ) -> None:
        """Записывает reward/quality сигнал для сессии."""
        stmt = text("""
            INSERT INTO experience_signals
              (session_id, signal_type, value_num, value_text,
               source, weight, created_at)
            VALUES
              (:session_id, :signal_type, :value_num, :value_text,
               :source, :weight, :created_at)
        """)
        with engine.begin() as conn:
            conn.execute(stmt, {
                "session_id":  session_id,
                "signal_type": signal_type,
                "value_num":   value_num,
                "value_text":  value_text,
                "source":      source,
                "weight":      weight,
                "created_at":  datetime.utcnow(),
            })

    # ── Чтение сессий пользователя ────────────────────────────────────────
    def get_user_sessions(self, user_id: int, limit: int = 20) -> list:
        """Возвращает последние N сессий пользователя."""
        stmt = text("""
            SELECT id, chat_id, query_text, task_type, protocol_used,
                   status, outcome_label, coherence_score,
                   latency_ms, cost_usd, started_at, finished_at
            FROM experience_sessions
            WHERE user_id = :user_id
            ORDER BY started_at DESC
            LIMIT :limit
        """)
        with engine.connect() as conn:
            rows = conn.execute(stmt, {"user_id": user_id, "limit": limit}).fetchall()
        return [dict(r._mapping) for r in rows]


# Глобальный экземпляр
experience_service = ExperienceService()
