"""
app/api/knowledge.py — Decision Journal + User Principles
P0 — персональная база решений и принципов пользователя
"""

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.sql import select, update, desc
from sqlalchemy import func
from loguru import logger

from app.dependencies import get_current_user
from app.database import engine, decision_journal, user_principles

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class JournalEntry(BaseModel):
    title: str
    query_text: str
    verdict: str
    council_used: Optional[str] = None
    outcome_label: Optional[str] = "unverified"
    tags: Optional[str] = None
    session_id: Optional[int] = None


@router.get("/journal")
async def get_journal(limit: int = 20, current_user=Depends(get_current_user)):
    with engine.connect() as conn:
        rows = conn.execute(
            select(decision_journal)
            .where(decision_journal.c.user_id == current_user.id)
            .order_by(desc(decision_journal.c.created_at))
            .limit(min(limit, 100))
        ).fetchall()
    return {"entries": [dict(r._mapping) for r in rows], "count": len(rows)}


@router.get("/journal/count")
async def get_journal_count(current_user=Depends(get_current_user)):
    with engine.connect() as conn:
        result = conn.execute(
            select(func.count()).select_from(decision_journal)
            .where(decision_journal.c.user_id == current_user.id)
        ).scalar()
    return {"count": result or 0}


@router.post("/journal")
async def add_journal_entry(entry: JournalEntry, current_user=Depends(get_current_user)):
    with engine.begin() as conn:
        result = conn.execute(
            decision_journal.insert().values(
                user_id=current_user.id,
                session_id=entry.session_id,
                title=entry.title[:255],
                query_text=entry.query_text[:2000],
                verdict=entry.verdict,
                council_used=entry.council_used,
                outcome_label=entry.outcome_label,
                tags=entry.tags,
                is_pinned=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
    logger.info(f"📋 Journal entry added: user={current_user.id}")
    return {"status": "ok", "id": result.inserted_primary_key[0]}


@router.patch("/journal/{entry_id}/pin")
async def toggle_pin(entry_id: int, current_user=Depends(get_current_user)):
    with engine.begin() as conn:
        row = conn.execute(
            select(decision_journal).where(
                (decision_journal.c.id == entry_id) &
                (decision_journal.c.user_id == current_user.id)
            )
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Entry not found")
        new_pin = not row.is_pinned
        conn.execute(
            update(decision_journal)
            .where(decision_journal.c.id == entry_id)
            .values(is_pinned=new_pin, updated_at=datetime.utcnow())
        )
    return {"status": "ok", "is_pinned": new_pin}


@router.delete("/journal/{entry_id}")
async def delete_journal_entry(entry_id: int, current_user=Depends(get_current_user)):
    with engine.begin() as conn:
        conn.execute(
            decision_journal.delete().where(
                (decision_journal.c.id == entry_id) &
                (decision_journal.c.user_id == current_user.id)
            )
        )
    return {"status": "ok"}


class PrincipleEntry(BaseModel):
    title: str
    body: str
    source: Optional[str] = "user"
    category: Optional[str] = "general"


@router.get("/principles")
async def get_principles(current_user=Depends(get_current_user)):
    with engine.connect() as conn:
        rows = conn.execute(
            select(user_principles)
            .where(
                (user_principles.c.user_id == current_user.id) &
                (user_principles.c.is_active == True)
            )
            .order_by(desc(user_principles.c.created_at))
        ).fetchall()
    return {"principles": [dict(r._mapping) for r in rows], "count": len(rows)}


@router.get("/principles/count")
async def get_principles_count(current_user=Depends(get_current_user)):
    with engine.connect() as conn:
        result = conn.execute(
            select(func.count()).select_from(user_principles)
            .where(
                (user_principles.c.user_id == current_user.id) &
                (user_principles.c.is_active == True)
            )
        ).scalar()
    return {"count": result or 0}


@router.post("/principles")
async def add_principle(entry: PrincipleEntry, current_user=Depends(get_current_user)):
    with engine.begin() as conn:
        result = conn.execute(
            user_principles.insert().values(
                user_id=current_user.id,
                title=entry.title[:255],
                body=entry.body,
                source=entry.source,
                category=entry.category,
                is_active=True,
                created_at=datetime.utcnow(),
            )
        )
    logger.info(f"⭐ Principle added: user={current_user.id}")
    return {"status": "ok", "id": result.inserted_primary_key[0]}


@router.delete("/principles/{principle_id}")
async def delete_principle(principle_id: int, current_user=Depends(get_current_user)):
    with engine.begin() as conn:
        conn.execute(
            update(user_principles)
            .where(
                (user_principles.c.id == principle_id) &
                (user_principles.c.user_id == current_user.id)
            )
            .values(is_active=False)
        )
    return {"status": "ok"}


class ApprovalUpdate(BaseModel):
    state: str  # draft | verified | approved


@router.patch("/journal/{entry_id}/approve")
async def set_approval_state(
    entry_id: int,
    payload: ApprovalUpdate,
    current_user=Depends(get_current_user),
):
    """Изменить статус решения: draft → verified → approved."""
    valid_states = {"draft", "verified", "approved"}
    if payload.state not in valid_states:
        raise HTTPException(status_code=400, detail=f"State must be one of: {valid_states}")
    with engine.begin() as conn:
        row = conn.execute(
            select(decision_journal).where(
                (decision_journal.c.id == entry_id) &
                (decision_journal.c.user_id == current_user.id)
            )
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Entry not found")
        conn.execute(
            update(decision_journal)
            .where(decision_journal.c.id == entry_id)
            .values(approval_state=payload.state, updated_at=datetime.utcnow())
        )
    logger.info(f"📋 Journal entry {entry_id} → {payload.state} (user={current_user.id})")
    return {"status": "ok", "id": entry_id, "approval_state": payload.state}