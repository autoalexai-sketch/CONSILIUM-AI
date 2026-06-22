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
    def get_user_sessions(self, user_id: int, limit: int = 20, offset: int = 0) -> list:
        """Возвращает последние N сессий пользователя, начиная с offset
        (для пагинации -- используется Session History view)."""
        stmt = text("""
            SELECT id, chat_id, query_text, task_type, protocol_used,
                   status, outcome_label, coherence_score,
                   latency_ms, cost_usd, started_at, finished_at
            FROM experience_sessions
            WHERE user_id = :user_id
            ORDER BY started_at DESC
            LIMIT :limit OFFSET :offset
        """)
        with engine.connect() as conn:
            rows = conn.execute(
                stmt, {"user_id": user_id, "limit": limit, "offset": offset}
            ).fetchall()
        return [dict(r._mapping) for r in rows]

    # ── Точный total count (для history-cnt в sidebar, не зависит от limit) ─
    def get_session_count(self, user_id: int) -> int:
        """Возвращает ОБЩЕЕ число сессий пользователя в БД, независимо от
        limit/offset -- нужно для history-cnt badge в sidebar."""
        stmt = text("""
            SELECT COUNT(*) AS cnt
            FROM experience_sessions
            WHERE user_id = :user_id
        """)
        with engine.connect() as conn:
            row = conn.execute(stmt, {"user_id": user_id}).fetchone()
        return int(row.cnt) if row else 0

    # ── Одна сессия + связанный Decision Journal verdict (если есть) ────────
    def get_session_detail(self, session_id: int, user_id: int) -> Optional[dict]:
        """
        Возвращает сессию по id (только если она принадлежит user_id) вместе
        с verdict из decision_journal, если Chairman успешно завершил
        делиберацию и council.py сохранил decision_journal.session_id =
        session_id (см. app/api/council.py, шаг 10 AUTOSAVE).

        experience_sessions сам по себе не хранит текст ответа -- это
        намеренно: ответ живёт в decision_journal (которым управляет
        Knowledge Vault), а experience_sessions хранит только метрики
        качества для closed-loop learning. Этот метод джойнит оба источника
        на чтении, не дублируя данные на запись.
        """
        sess_stmt = text("""
            SELECT id, user_id, chat_id, query_text, task_type, protocol_used,
                   selected_directors, status, outcome_label, coherence_score,
                   latency_ms, cost_usd, user_rating, helpfulness_score,
                   feedback_text, started_at, finished_at
            FROM experience_sessions
            WHERE id = :session_id AND user_id = :user_id
        """)
        with engine.connect() as conn:
            row = conn.execute(sess_stmt, {"session_id": session_id, "user_id": user_id}).fetchone()
            if not row:
                return None
            session = dict(row._mapping)

            journal_stmt = text("""
                SELECT id, title, verdict, council_used, outcome_label,
                       approval_state, is_pinned, created_at
                FROM decision_journal
                WHERE session_id = :session_id AND user_id = :user_id
                ORDER BY created_at DESC
                LIMIT 1
            """)
            jrow = conn.execute(journal_stmt, {"session_id": session_id, "user_id": user_id}).fetchone()
            session["journal"] = dict(jrow._mapping) if jrow else None

        return session

    # ── Удаление сессии (не трогает связанный decision_journal) ─────────────
    def delete_session(self, session_id: int, user_id: int) -> bool:
        """Удаляет сессию (и её сигналы) пользователя. Decision Journal
        запись НЕ удаляется -- это отдельный артефакт, который пользователь
        может хранить/закреплять независимо от Session History."""
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT id FROM experience_sessions WHERE id = :sid AND user_id = :uid"),
                {"sid": session_id, "uid": user_id},
            ).fetchone()
            if not row:
                return False
            conn.execute(
                text("DELETE FROM experience_signals WHERE session_id = :sid"),
                {"sid": session_id},
            )
            conn.execute(
                text("DELETE FROM experience_sessions WHERE id = :sid AND user_id = :uid"),
                {"sid": session_id, "uid": user_id},
            )
        return True


# Глобальный экземпляр
experience_service = ExperienceService()
