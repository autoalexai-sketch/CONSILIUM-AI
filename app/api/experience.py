"""
app/api/experience.py — API для просмотра Experience Layer (Session History).
Эндпоинты:
  GET    /api/experience/sessions            — список сессий (с пагинацией)
  GET    /api/experience/sessions/count       — точный total count
  GET    /api/experience/sessions/{id}        — детали одной сессии + verdict
  DELETE /api/experience/sessions/{id}        — удалить сессию
  POST   /api/experience/feedback             — оценка пользователя (closed-loop)
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from loguru import logger

from app.dependencies import get_current_user
from core.experience.experience_service import experience_service

router = APIRouter(prefix="/api/experience", tags=["experience"])


# ── GET /api/experience/sessions ──────────────────────────────────────────
@router.get("/sessions")
async def get_sessions(
    limit: int = 20,
    offset: int = 0,
    current_user=Depends(get_current_user),
):
    """
    Возвращает страницу сессий текущего пользователя (newest first).
    `count` здесь -- ОБЩЕЕ число сессий в БД (не длина текущей страницы),
    так sidebar badge и пагинация на фронтенде показывают верное число
    даже когда limit < total.
    """
    limit = min(max(limit, 1), 100)
    sessions = experience_service.get_user_sessions(
        user_id=current_user.id,
        limit=limit,
        offset=max(offset, 0),
    )
    total = experience_service.get_session_count(user_id=current_user.id)
    return {"sessions": sessions, "count": total, "returned": len(sessions)}


# ── GET /api/experience/sessions/count ────────────────────────────────────
@router.get("/sessions/count")
async def get_sessions_count(current_user=Depends(get_current_user)):
    """Точный total count -- используется для history-cnt badge в sidebar,
    тот же контракт что у /api/knowledge/journal/count и .../principles/count."""
    total = experience_service.get_session_count(user_id=current_user.id)
    return {"count": total}


# ── GET /api/experience/sessions/{id} ─────────────────────────────────────
@router.get("/sessions/{session_id}")
async def get_session_detail(session_id: int, current_user=Depends(get_current_user)):
    """
    Детали одной сессии, включая сохранённый Chairman verdict (если есть).
    Используется когда пользователь кликает по элементу Session History --
    открывает прошлый ответ вместо повторной отправки запроса.

    `journal` будет null если: запрос был fast-track (casual/simple, минуя
    Council) -- такие сессии не пишут decision_journal по дизайну.
    """
    session = experience_service.get_session_detail(
        session_id=session_id, user_id=current_user.id
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# ── DELETE /api/experience/sessions/{id} ──────────────────────────────────
@router.delete("/sessions/{session_id}")
async def delete_session(session_id: int, current_user=Depends(get_current_user)):
    """Удаляет сессию из истории. Связанная запись в decision_journal
    (если есть) НЕ удаляется -- это отдельная сущность пользователя."""
    deleted = experience_service.delete_session(
        session_id=session_id, user_id=current_user.id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "ok", "id": session_id}


# ── POST /api/experience/feedback ─────────────────────────────────────────
class FeedbackPayload(BaseModel):
    session_id: int
    rating: int = Field(..., ge=1, le=5, description="Оценка 1–5")
    helpful: bool = True
    comment: Optional[str] = None


@router.post("/feedback")
async def post_feedback(
    payload: FeedbackPayload,
    current_user=Depends(get_current_user),
):
    """
    Принимает оценку пользователя и записывает как сигнал.
    Это основа closed-loop learning.
    """
    try:
        experience_service.add_signal(
            session_id=payload.session_id,
            signal_type="user_feedback",
            value_num=float(payload.rating),
            value_text=payload.comment,
            source="user",
            weight=1.5,  # Пользовательский сигнал важнее синтетического
        )
        # Обновляем user_rating прямо в сессии
        from sqlalchemy import text
        from app.database import engine
        with engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE experience_sessions
                    SET user_rating       = :rating,
                        helpfulness_score = :score,
                        feedback_text     = :comment,
                        outcome_label     = :label
                    WHERE id = :sid
                """),
                {
                    "sid":     payload.session_id,
                    "rating":  payload.rating,
                    "score":   payload.rating / 5.0,
                    "comment": payload.comment,
                    "label":   "success" if payload.helpful else "partial_success",
                },
            )
        logger.info(
            f"⭐ Feedback: session={payload.session_id} "
            f"rating={payload.rating} helpful={payload.helpful}"
        )
        return {"status": "ok", "session_id": payload.session_id}

    except Exception as e:
        logger.error(f"❌ Feedback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
