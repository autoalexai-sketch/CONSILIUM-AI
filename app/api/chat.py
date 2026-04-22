"""
app/api/chat.py — Чат и история разговоров.
Эндпоинты: /chat, /buy_credits, /sync_chats, /get_chats, /delete_chat/{chat_id}
"""

import uuid
import re
import json
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.sql import select, update
from sqlalchemy.sql import delete as sql_delete
from loguru import logger

from app.config import settings
from app.database import engine, users, chat_history
from app.dependencies import get_current_user
from app.middleware.rate_limiter import rate_limiter
from core.ai_fallback import fallback_manager

router = APIRouter()


CASUAL_PATTERNS = [
    r'^(привет|hello|hi|hey|cześć|witaj|hej|привіт|ello|howdy|greetings|salut|hola|ciao)',
    r'^(yo|sup|wassup|поздравляю)',
    r'^(как дела|how are you|jak się masz|як справи|как ты|how do you do)',
    r'^(что нового|what\'s new|что происходит|what\'s up)',
    r'^(спасибо|thanks|thank you|dziękuję|дякую|merci)',
    r'^(пока|bye|goodbye|do widzenia|до побачення|farewell|see you)',
    r'^(что ты умеешь|what can you do|co potrafisz)',
    r'^(кто ты|who are you|kim jesteś|хто ти)',
    r'^(да|no|yes|nope|yep|ага|неа)',
    r'^(ладно|ok|okay|sure|конечно)',
    r'^(помощь|help|помогите|помоги)',
    r'^(ммм|хм|эм|умм|erm)',
    r'^(ну|well|так|so|итак)',
    r'^(окей|cool|nice|awesome|great|классно|супер)',
    r'^(привіт|як справи|як ти|що нового)',
    r'^(дякую|дяку)',
    r'^(до побачення|бувай)',
    r'^(cześć|hej|elo|witam|pozdrawiam)',
    r'^(jak się masz|jak leci|co nowego)',
    r'^(dziękuję|dzięki)',
    r'^(do widzenia|do zobaczenia|pa|pa pa)',
]


@router.post("/chat")
async def chat(request: Request, current_user=Depends(get_current_user)):
    await rate_limiter.check(request)

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    message = data.get("message", "").strip()
    chat_id = data.get("chat_id", "") or str(uuid.uuid4())

    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    logger.info(f"💬 CHAT | user={current_user.id} | msg={message[:60]}...")

    is_casual = (
        any(re.search(pattern, message, re.I) for pattern in CASUAL_PATTERNS)
        or len(message) < 20
    )

    logger.debug(f"   Type: {'⚡ CASUAL' if is_casual else '🧠 COUNCIL'} | credits={current_user.credits}")

    if is_casual:
        logger.info("   → Fast-Track activated (no credits needed)")
        system_prompt = (
            "You are a friendly, helpful AI assistant. "
            "Respond naturally and conversationally. "
            "Keep responses short (1-2 sentences). Be warm and engaging."
        )

        # 1. Groq (fastest for demo)
        if settings.GROQ_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}",
                                 "Content-Type": "application/json"},
                        json={"model": "llama3-8b-8192",
                              "messages": [{"role": "system", "content": system_prompt},
                                           {"role": "user", "content": message}],
                              "max_tokens": 300},
                    )
                    if response.status_code == 200:
                        content = response.json()["choices"][0]["message"]["content"]
                        logger.info("   ✅ Fast-Track: Groq")
                        return {"response": content, "credits_left": current_user.credits,
                                "mode": "fast", "provider": "groq", "chat_id": chat_id}
            except Exception as e:
                logger.warning(f"   ⚠️ Groq failed: {str(e)[:50]}")

        # 2. Ollama (local fallback)
        try:
            ollama_res = await fallback_manager.call_ollama_direct(
                prompt=message, model="llama3:8b", fast_mode=True)
            if ollama_res and ollama_res.get("success"):
                logger.info("   ✅ Fast-Track: Ollama")
                return {"response": ollama_res["content"], "credits_left": current_user.credits,
                        "mode": "fast", "provider": "ollama", "chat_id": chat_id}
        except Exception as e:
            logger.warning(f"   ⚠️ Ollama failed: {str(e)[:50]}")

        # 3. OpenRouter
        if settings.OPENROUTER_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                                 "Content-Type": "application/json",
                                 "HTTP-Referer": "http://localhost:8000",
                                 "X-Title": "Consilium AI"},
                        json={"model": "anthropic/claude-3-5-haiku",
                              "messages": [{"role": "system", "content": system_prompt},
                                           {"role": "user", "content": message}],
                              "max_tokens": 500},
                    )
                    if response.status_code == 200:
                        content = response.json()["choices"][0]["message"]["content"]
                        logger.info("   ✅ Fast-Track: OpenRouter")
                        return {"response": content, "credits_left": current_user.credits,
                                "mode": "fast", "provider": "openrouter", "chat_id": chat_id}
            except Exception as e:
                logger.warning(f"   ⚠️ OpenRouter failed: {str(e)[:50]}")

        # 4. Gemini
        try:
            if fallback_manager.gemini_available:
                gemini_response = fallback_manager.client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=f"{system_prompt}\n\nUser: {message}\n\nAssistant:",
                )
                if gemini_response.text:
                    logger.info("   ✅ Fast-Track: Gemini")
                    return {"response": gemini_response.text, "credits_left": current_user.credits,
                            "mode": "fast", "provider": "gemini", "chat_id": chat_id}
        except Exception as e:
            logger.warning(f"   ⚠️ Gemini failed: {str(e)[:50]}")

        logger.error("   💥 All fast-track providers failed")
        return {"response": "Извини, я временно недоступен. Попробуй ещё раз. 🤖",
                "credits_left": current_user.credits, "mode": "fast",
                "provider": "error", "chat_id": chat_id}

    # === ПОЛНЫЙ СОВЕТ =====================================================
    logger.info("   🧠 Launching full Council deliberation...")
    user_credits = current_user.credits
    is_free = user_credits <= 0

    if is_free:
        logger.warning("   ⚠️ Credits: 0 — FREE LOCAL MODE")

    from app.api.council import run_council_deliberation

    try:
        result = await run_council_deliberation(
            query=message, user_credits=user_credits, history_count=0)

        credits_needed = result.get("credits_needed", 1)
        with engine.connect() as conn:
            new_credits = max(0, current_user.credits - credits_needed)
            conn.execute(update(users).where(users.c.id == current_user.id)
                         .values(credits=new_credits))
            conn.commit()

        logger.info(f"   ✅ Council complete | credits: {current_user.credits}→{new_credits}")

        return {"response": result.get("final_decision", "No decision reached"),
                "credits_left": new_credits,
                "council_used": result.get("council", {}).get("selected", []),
                "cost_usd": result.get("total_cost_usd", 0.0),
                "chat_id": chat_id, "mode": "council", "provider": "council"}

    except Exception as e:
        logger.error(f"   ❌ Council deliberation failed: {str(e)[:200]}")
        raise HTTPException(status_code=500, detail=f"Deliberation error: {str(e)}")


@router.post("/buy_credits")
async def buy_credits(amount: int, price: float, current_user=Depends(get_current_user)):
    credited_amount = {5: 100, 20: 500, 35: 1000}.get(int(price), amount)
    with engine.connect() as conn:
        conn.execute(update(users).where(users.c.id == current_user.id)
                     .values(credits=users.c.credits + credited_amount))
        conn.commit()
        user = conn.execute(select(users).where(users.c.id == current_user.id)).fetchone()
    logger.info(f"💰 Кредиты: +{credited_amount} | user={current_user.id}")
    return {"status": "success", "credits_added": credited_amount, "credits_total": user.credits}


@router.post("/sync_chats")
async def sync_chats(chats: dict, current_user=Depends(get_current_user)):
    with engine.connect() as conn:
        for chat_id_key, chat_data in chats.items():
            existing = conn.execute(
                select(chat_history).where(
                    (chat_history.c.user_id == current_user.id) &
                    (chat_history.c.chat_id == chat_id_key)
                )
            ).fetchone()
            messages_json = json.dumps(chat_data.get("messages", []))
            if existing:
                conn.execute(update(chat_history).where(chat_history.c.id == existing.id)
                             .values(title=chat_data.get("title", "New Chat"),
                                     messages=messages_json, updated_at=datetime.utcnow()))
            else:
                conn.execute(chat_history.insert().values(
                    user_id=current_user.id, chat_id=chat_id_key,
                    title=chat_data.get("title", "New Chat"),
                    messages=messages_json, updated_at=datetime.utcnow()))
        conn.commit()
    return {"status": "success", "synced": len(chats)}


@router.get("/get_chats")
async def get_chats(current_user=Depends(get_current_user)):
    with engine.connect() as conn:
        result = conn.execute(
            select(chat_history).where(chat_history.c.user_id == current_user.id)
        ).fetchall()
        chats = {}
        for row in result:
            chats[row.chat_id] = {
                "id": row.chat_id, "title": row.title,
                "messages": json.loads(row.messages) if row.messages else [],
                "updatedAt": row.updated_at.isoformat() if row.updated_at else datetime.utcnow().isoformat(),
            }
        return chats


@router.delete("/delete_chat/{chat_id}")
async def delete_chat(chat_id: str, current_user=Depends(get_current_user)):
    with engine.connect() as conn:
        conn.execute(sql_delete(chat_history).where(
            (chat_history.c.user_id == current_user.id) &
            (chat_history.c.chat_id == chat_id)
        ))
        conn.commit()
    return {"status": "success"}
