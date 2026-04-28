"""
app/api/experience.py — API для просмотра Experience Layer.
Эндпоинты: GET /api/experience/sessions, POST /api/experience/feedback
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
    current_user=Depends(get_current_user),
):
    """Возвращает последние N сессий текущего пользователя."""
    sessions = experience_service.get_user_sessions(
        user_id=current_user.id,
        limit=min(limit, 100),
    )
    return {"sessions": sessions, "count": len(sessions)}


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
