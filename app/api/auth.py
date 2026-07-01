"""
app/api/auth.py -- Authentication: /register, /login, /verify, /me, /credits

hCaptcha bot protection on /register:
  - Frontend sends captcha_token from hCaptcha widget
  - Backend verifies via https://hcaptcha.com/siteverify
  - If HCAPTCHA_SECRET is not configured, verification is skipped (dev mode)
  - captcha_token field is optional so existing clients don't break during rollout
"""

import asyncio
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException, Depends, Request, Header
from typing import Optional
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
from app.config import settings

router = APIRouter()


async def _verify_hcaptcha(token: str) -> bool:
    """Verify hCaptcha response token with hCaptcha API.
    Returns True if valid, False otherwise.
    Raises nothing -- caller decides how to handle failure.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                "https://hcaptcha.com/siteverify",
                data={
                    "secret": settings.HCAPTCHA_SECRET,
                    "response": token,
                },
            )
            result = resp.json()
            return bool(result.get("success"))
    except Exception as e:
        logger.warning(f"hCaptcha verification request failed: {e}")
        return False


class AuthRequest(BaseModel):
    email: str
    password: str
    captcha_token: Optional[str] = None  # required in prod when HCAPTCHA_SECRET is set


@router.post("/register")
async def register(data: AuthRequest, request: Request):
    await rate_limiter.check(request)

    # --- hCaptcha verification ---
    if settings.HCAPTCHA_SECRET:
        if not data.captcha_token:
            raise HTTPException(status_code=400, detail="Captcha required")
        ok = await _verify_hcaptcha(data.captcha_token)
        if not ok:
            logger.warning(f"hCaptcha failed for registration: {data.email}")
            raise HTTPException(status_code=400, detail="Captcha verification failed")

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
    logger.info(f"👤 New user: {data.email} (ID: {user_id})")

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
            logger.warning(f"⚠️ Failed login: {data.email}")
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user_id = user.id
        user_credits = user.credits

    jwt_token = create_access_token(user_id=user_id, email=data.email)
    logger.info(f"🔑 Login: {data.email} (ID: {user_id})")

    return {"status": "success", "user_id": user_id,
            "token": jwt_token, "credits": user_credits}


@router.get("/verify")
async def verify_token_endpoint(current_user=Depends(get_current_user)):
    return {"status": "valid", "user_id": current_user.id,
            "email": current_user.email, "credits": current_user.credits}


@router.get("/me")
async def get_me(authorization: Optional[str] = Header(None)):
    """Returns user info if token valid, or 401 without raising exception noise."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    from app.dependencies import verify_jwt_token
    token = authorization.split(" ")[1]
    payload = verify_jwt_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token invalid or expired")
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Malformed token")
    try:
        user_id = int(user_id_str)
        with engine.connect() as conn:
            row = conn.execute(
                select(users).where(users.c.id == user_id)
            ).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="User not found")
        return {
            "status": "valid",
            "user_id": row.id,
            "email": row.email,
            "credits": row.credits,
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Auth error")


@router.get("/credits")
async def get_credits(current_user=Depends(get_current_user)):
    return {"credits": current_user.credits}


@router.get("/captcha-config")
async def captcha_config():
    """Returns hCaptcha site key for the frontend to render the widget.
    Returns enabled: false if HCAPTCHA_SECRET is not configured (dev mode).
    """
    return {
        "enabled": bool(settings.HCAPTCHA_SECRET),
        "site_key": settings.HCAPTCHA_SITE_KEY,
    }
