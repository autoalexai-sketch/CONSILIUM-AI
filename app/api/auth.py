"""
app/api/auth.py — Аутентификация: /register, /login, /verify, /me, /credits
"""

import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from sqlalchemy.sql import select
from loguru import logger

from app.database import engine, users
from app.dependencies import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    send_welcome_email,
)
from app.middleware.rate_limiter import rate_limiter

router = APIRouter()


class AuthRequest(BaseModel):
    email: str
    password: str


@router.post("/register")
async def register(data: AuthRequest, request: Request):
    await rate_limiter.check(request)

    with engine.connect() as conn:
        existing = conn.execute(
            select(users).where(users.c.email == data.email)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="User already exists")

        ins = users.insert().values(
            email=data.email,
            password_hash=hash_password(data.password),
            credits=10,
            created_at=datetime.utcnow(),
        )
        result = conn.execute(ins)
        conn.commit()
        user_id = result.inserted_primary_key[0]

    jwt_token = create_access_token(user_id=user_id, email=data.email)
    asyncio.create_task(send_welcome_email(data.email))
    logger.info(f"👤 Новый пользователь: {data.email} (ID: {user_id})")

    return {"status": "success", "message": "Account created",
            "user_id": user_id, "token": jwt_token, "credits": 10}


@router.post("/login")
async def login(data: AuthRequest, request: Request):
    await rate_limiter.check(request)

    with engine.connect() as conn:
        user = conn.execute(
            select(users).where(users.c.email == data.email)
        ).fetchone()

        if not user or not verify_password(data.password, user.password_hash):
            logger.warning(f"⚠️ Неудачный вход: {data.email}")
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user_id = user.id
        user_credits = user.credits

    jwt_token = create_access_token(user_id=user_id, email=data.email)
    logger.info(f"🔑 Вход выполнен: {data.email} (ID: {user_id})")

    return {"status": "success", "user_id": user_id,
            "token": jwt_token, "credits": user_credits}


@router.get("/verify")
async def verify_token_endpoint(current_user=Depends(get_current_user)):
    return {"status": "valid", "user_id": current_user.id,
            "email": current_user.email, "credits": current_user.credits}


@router.get("/me")
async def get_me(current_user=Depends(get_current_user)):
    """Alias /me → same as /verify. Used by frontend after login."""
    return {
        "status": "valid",
        "user_id": current_user.id,
        "email": current_user.email,
        "credits": current_user.credits,
    }


@router.get("/credits")
async def get_credits(current_user=Depends(get_current_user)):
    return {"credits": current_user.credits}
