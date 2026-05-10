"""
core/context_gateway.py — Context Gateway для CONSILIUM AI v3.0

Перед каждой делиберацией подтягивает релевантный контекст:
  1. Принципы пользователя (user_principles)
  2. Похожие прошлые решения (decision_journal)

Контекст инжектируется в промпты Scout и Chairman.
"""

from typing import Optional
from loguru import logger


class ContextGateway:
    MAX_PRINCIPLES = 5
    MAX_PAST_DECISIONS = 3
    PREVIEW_LEN = 300

    def get_context(self, query: str, user_id: int) -> dict:
        """
        Возвращает dict с принципами, похожими решениями и готовым context_block.
        Если user_id=0 или нет данных — возвращает пустой контекст без ошибки.
        """
        if not user_id:
            return {"principles": [], "past_decisions": [], "context_block": ""}

        try:
            from app.database import engine, user_principles, decision_journal
            from sqlalchemy.sql import select, desc

            principles = []
            past_decisions = []

            with engine.connect() as conn:
                # 1. Принципы пользователя
                rows = conn.execute(
                    select(user_principles)
                    .where(
                        (user_principles.c.user_id == user_id) &
                        (user_principles.c.is_active == True)
                    )
                    .order_by(desc(user_principles.c.created_at))
                    .limit(self.MAX_PRINCIPLES)
                ).fetchall()
                principles = [
                    {"title": r.title, "body": r.body, "category": r.category}
                    for r in rows
                ]

                # 2. Похожие прошлые решения — простой скоринг по пересечению слов
                query_words = set(query.lower().split())
                candidates = conn.execute(
                    select(decision_journal)
                    .where(
                        (decision_journal.c.user_id == user_id) &
                        (decision_journal.c.approval_state.in_(["approved", "verified", "auto"]))
                    )
                    .order_by(desc(decision_journal.c.created_at))
                    .limit(20)
                ).fetchall()

                scored = []
                for row in candidates:
                    row_words = set((row.query_text or "").lower().split())
                    score = len(query_words & row_words)
                    if score > 0:
                        scored.append((score, row))
                scored.sort(key=lambda x: x[0], reverse=True)

                past_decisions = [
                    {
                        "title": row.title,
                        "query": (row.query_text or "")[:150],
                        "verdict_preview": (row.verdict or "")[:self.PREVIEW_LEN],
                        "approval_state": row.approval_state,
                    }
                    for _, row in scored[:self.MAX_PAST_DECISIONS]
                ]

            context_block = self._build_context_block(principles, past_decisions)
            logger.debug(
                f"ContextGateway: user={user_id} "
                f"principles={len(principles)} decisions={len(past_decisions)}"
            )
            return {
                "principles": principles,
                "past_decisions": past_decisions,
                "context_block": context_block,
            }

        except Exception as e:
            logger.warning(f"ContextGateway failed (non-critical): {e}")
            return {"principles": [], "past_decisions": [], "context_block": ""}

    def _build_context_block(self, principles: list, past_decisions: list) -> str:
        parts = []

        if principles:
            p_lines = "\n".join(
                f"  - [{p['category']}] {p['title']}: {p['body'][:120]}"
                for p in principles
            )
            parts.append(f"## User Principles\n{p_lines}")

        if past_decisions:
            d_lines = "\n".join(
                f"  - [{d['approval_state']}] {d['title']}\n"
                f"    Past query: {d['query'][:100]}\n"
                f"    Decision: {d['verdict_preview'][:200]}"
                for d in past_decisions
            )
            parts.append(f"## Relevant Past Decisions\n{d_lines}")

        if not parts:
            return ""

        return (
            "\n\n---\n### PERSONAL CONTEXT (from Decision Journal)\n"
            + "\n\n".join(parts)
            + "\n---\n"
        )


# Глобальный синглтон
context_gateway = ContextGateway()