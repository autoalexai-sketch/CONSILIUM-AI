"""
core/context_gateway.py -- Context Gateway for CONSILIUM AI v3.0

Fetches:
  1. User principles (user_principles table)
  2. Similar past decisions (decision_journal table)
  3. Detects financial/risky queries for automatic Critic activation

Context injected into Scout and Chairman prompts.
"""

import re
from typing import Optional
from loguru import logger


class ContextGateway:
    MAX_PRINCIPLES   = 5
    MAX_PAST_DECISIONS = 3
    PREVIEW_LEN      = 300

    # ── Financial / risk detection ─────────────────────────────────────────
    _FINANCIAL_KW = [
        'деньги', 'бюджет', 'инвестиц', 'кредит', 'ипотек', 'сбереж',
        'зарплат', 'расход', 'доход', 'прибыль', 'убыток', 'купить',
        'квартир', 'машин', 'стоимость', 'цена', 'финанс', 'эконом',
        'налог', 'бизнес',
        # Polish
        'pieniądz', 'budżet', 'kredyt', 'hipoteka', 'oszczędnoś', 'zakup',
        'mieszkan', 'koszt', 'cena', 'dochód', 'wydatek', 'firma',
        # English
        'money', 'budget', 'invest', 'credit', 'mortgage', 'saving',
        'salary', 'expense', 'income', 'profit', 'loss', 'buy', 'apartment',
        'cost', 'price', 'finance', 'economy', 'tax', 'business',
    ]

    _RISK_KW = [
        'риск', 'опасн', 'провал', 'последств', 'что если', 'worst case',
        'гаранти', 'надёжн', 'юридическ', 'закон', 'штраф', 'проблем',
        'risk', 'danger', 'fail', 'consequence', 'guarantee', 'legal',
        'penalty', 'problem', 'ryzyko', 'niebezpiecz', 'problem',
    ]

    def is_financial_or_risky(self, query: str) -> bool:
        """Detect if query is financial or high-risk — triggers Critic director."""
        q = query.lower()
        score = 0

        for kw in self._FINANCIAL_KW:
            if re.search(r'\b' + re.escape(kw), q):
                score += 2

        for kw in self._RISK_KW:
            if re.search(r'\b' + re.escape(kw), q):
                score += 1

        # Large monetary amounts (3+ digit numbers with currency)
        if re.search(r'\b\d{3,}\s*(тыс|млн|zł|usd|eur|руб|pln|uah)', q):
            score += 2

        return score >= 3

    # ── Main context fetch ─────────────────────────────────────────────────
    def get_context(self, query: str, user_id: int) -> dict:
        """
        Returns dict with context_block string.
        user_id=0 returns empty context.
        """
        is_high_stakes = self.is_financial_or_risky(query)

        if not user_id:
            return {
                "principles": [], "past_decisions": [],
                "context_block": "",
                "is_high_stakes": is_high_stakes,
            }

        try:
            from app.database import engine, user_principles, decision_journal
            from sqlalchemy.sql import select, desc

            principles     = []
            past_decisions = []

            with engine.connect() as conn:
                # 1. User principles
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

                # 2. Similar past decisions — simple word-overlap scoring
                query_words = set(query.lower().split())
                candidates = conn.execute(
                    select(decision_journal)
                    .where(
                        (decision_journal.c.user_id == user_id) &
                        (decision_journal.c.approval_state.in_(
                            ["approved", "verified", "auto"]
                        ))
                    )
                    .order_by(desc(decision_journal.c.created_at))
                    .limit(20)
                ).fetchall()

                scored = []
                for row in candidates:
                    row_words = set((row.query_text or "").lower().split())
                    overlap   = len(query_words & row_words)
                    if overlap > 0:
                        scored.append((overlap, row))
                scored.sort(key=lambda x: x[0], reverse=True)

                past_decisions = [
                    {
                        "title":          row.title,
                        "query":          (row.query_text or "")[:150],
                        "verdict_preview": (row.verdict or "")[:self.PREVIEW_LEN],
                        "approval_state": row.approval_state,
                    }
                    for _, row in scored[:self.MAX_PAST_DECISIONS]
                ]

            context_block = self._build_context_block(principles, past_decisions)
            logger.debug(
                f"ContextGateway: user={user_id} "
                f"principles={len(principles)} decisions={len(past_decisions)} "
                f"high_stakes={is_high_stakes}"
            )
            return {
                "principles":     principles,
                "past_decisions": past_decisions,
                "context_block":  context_block,
                "is_high_stakes": is_high_stakes,
            }

        except Exception as e:
            logger.warning(f"ContextGateway failed (non-critical): {e}")
            return {
                "principles": [], "past_decisions": [],
                "context_block": "", "is_high_stakes": is_high_stakes,
            }

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


# Global singleton
context_gateway = ContextGateway()
