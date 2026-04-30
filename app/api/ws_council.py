"""
app/api/ws_council.py — WebSocket эндпоинт для стриминга делиберации.

Протокол:
  Клиент → Сервер (JSON):
    {"token": "eyJ...", "message": "текст запроса", "chat_id": "chat_..."}

  Сервер → Клиент:
    {"type": "council_ready",  "selected": [...]}
    {"type": "phase_start",    "phase": "scout", "text": "..."}
    {"type": "phase_done",     "phase": "scout", "tokens": 198, "provider": "...", "preview": "..."}
    {"type": "final",          "response": "...", "credits_left": N}
    {"type": "error",          "message": "..."}

  Соединение остаётся открытым — можно отправлять несколько вопросов подряд.
"""

import json
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.sql import select, update
from loguru import logger

from app.database import engine, users
from app.dependencies import verify_jwt_token
from app.api.council import run_council_deliberation
from core.experience.experience_service import experience_service

router = APIRouter()


@router.websocket("/ws/council")
async def ws_council(websocket: WebSocket):
    await websocket.accept()
    logger.info("🔌 WS: новое подключение")

    # ── Переменные сессии (устанавливаются один раз при первом сообщении) ──
    user_id: int | None = None
    chat_id: str = ""

    try:
        while True:
            # ── Читаем следующее сообщение ────────────────────────────────
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            token   = data.get("token", "")
            message = data.get("message", "").strip()
            chat_id = data.get("chat_id", chat_id)

            # Пинг — отвечаем и ждём следующее сообщение
            if message == "__ping__":
                await websocket.send_json({"type": "pong"})
                continue

            if not message:
                await websocket.send_json({"type": "error", "message": "Empty message"})
                continue

            # ── Верификация JWT ───────────────────────────────────────────
            payload = verify_jwt_token(token)
            if payload is None:
                await websocket.send_json({"type": "error", "message": "Token invalid or expired."})
                continue

            try:
                user_id = int(payload.get("sub"))
            except (TypeError, ValueError):
                await websocket.send_json({"type": "error", "message": "Malformed token"})
                continue

            # ── Получаем пользователя ─────────────────────────────────────
            with engine.connect() as conn:
                user = conn.execute(
                    select(users).where(users.c.id == user_id)
                ).fetchone()

            if not user:
                await websocket.send_json({"type": "error", "message": "User not found"})
                continue

            user_credits = user.credits
            logger.info(f"🔌 WS: user={user_id} credits={user_credits} msg={message[:50]}...")

            # Проверяем кредиты
            if user_credits <= 0:
                await websocket.send_json({"type": "error", "message": "Недостаточно кредитов"})
                continue

            # ── Experience: начинаем сессию ───────────────────────────────
            exp_session_id: int | None = None
            t_start = time.monotonic()
            try:
                exp_session_id = experience_service.create_session(
                    user_id=user_id,
                    chat_id=chat_id or "ws",
                    query_text=message,
                    protocol_used="council",
                )
            except Exception as _e:
                logger.warning(f"⚠️ ExperienceService.create_session failed: {_e}")

            # ── Callback для стриминга фаз клиенту ────────────────────────
            async def on_phase(msg: dict) -> None:
                await websocket.send_json(msg)

            # ── Запускаем делиберацию ─────────────────────────────────────
            result = await run_council_deliberation(
                query=message,
                user_credits=user_credits,
                history_count=0,
                on_phase=on_phase,
            )

            # ── Списываем кредиты ─────────────────────────────────────────
            credits_needed = result.get("credits_needed", 1)
            new_credits = max(0, user_credits - credits_needed)

            with engine.connect() as conn:
                conn.execute(
                    update(users).where(users.c.id == user_id).values(credits=new_credits)
                )
                conn.commit()

            logger.info(f"🔌 WS: done | credits {user_credits}→{new_credits}")

            # ── Experience: финализируем сессию ───────────────────────────
            if exp_session_id is not None:
                try:
                    latency_ms = int((time.monotonic() - t_start) * 1000)
                    coherence  = result.get("coherence_score")
                    cost       = result.get("total_cost_usd", 0.0)
                    experience_service.finalize_session(
                        session_id=exp_session_id,
                        status="success",
                        outcome_label="unverified",
                        coherence_score=coherence,
                        latency_ms=latency_ms,
                        cost_usd=cost,
                    )
                    if coherence is not None:
                        experience_service.add_signal(
                            session_id=exp_session_id,
                            signal_type="coherence_score",
                            value_num=float(coherence),
                            source="synthesizer",
                            weight=1.0,
                        )
                    logger.debug(f"📝 Experience logged: session={exp_session_id} latency={latency_ms}ms")
                except Exception as _e:
                    logger.warning(f"⚠️ ExperienceService.finalize failed: {_e}")

            # ── Финальный результат ───────────────────────────────────────
            await websocket.send_json({
                "type":         "final",
                "response":     result.get("final_decision", ""),
                "council_used": result.get("council", {}).get("selected", []),
                "cost_usd":     result.get("total_cost_usd", 0.0),
                "deliberation": result.get("deliberation", {}),
                "credits_left": new_credits,
                "chat_id":      chat_id,
            })

    except WebSocketDisconnect:
        logger.info("🔌 WS: клиент отключился")
    except Exception as e:
        logger.error(f"🔌 WS: ошибка: {e}")
        try:
            await websocket.send_json({"type": "error", "message": f"Server error: {str(e)[:100]}"})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
