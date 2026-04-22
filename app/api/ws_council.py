"""
app/api/ws_council.py — WebSocket эндпоинт для стриминга делиберации.

Протокол:
  Клиент → Сервер (первое сообщение, JSON):
    {"token": "eyJ...", "message": "текст запроса", "chat_id": "chat_..."}

  Сервер → Клиент:
    {"type": "council_ready",  "selected": [...]}
    {"type": "phase_start",    "phase": "scout", "text": "..."}
    {"type": "phase_done",     "phase": "scout", "tokens": 198, "provider": "...", "preview": "..."}
    {"type": "final",          "response": "...", "credits_left": N}
    {"type": "error",          "message": "..."}
"""

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.sql import select, update
from loguru import logger

from app.database import engine, users
from app.dependencies import verify_jwt_token
from app.api.council import run_council_deliberation

router = APIRouter()


@router.websocket("/ws/council")
async def ws_council(websocket: WebSocket):
    await websocket.accept()
    logger.info("🔌 WS: новое подключение")

    try:
        # 1. Читаем первое сообщение
        raw = await websocket.receive_text()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            await websocket.send_json({"type": "error", "message": "Invalid JSON"})
            await websocket.close(code=1008)
            return

        token   = data.get("token", "")
        message = data.get("message", "").strip()
        chat_id = data.get("chat_id", "")

        # Пинг при подключении — не обрабатываем как запрос
        if message == "__ping__":
            await websocket.send_json({"type": "pong"})
            # Ждём следующее сообщение
            raw2 = await websocket.receive_text()
            try:
                data = json.loads(raw2)
                token   = data.get("token", token)
                message = data.get("message", "").strip()
                chat_id = data.get("chat_id", chat_id)
            except json.JSONDecodeError:
                await websocket.close(code=1008)
                return

        if not message:
            await websocket.send_json({"type": "error", "message": "Empty message"})
            await websocket.close(code=1008)
            return

        # 2. Верификация JWT
        payload = verify_jwt_token(token)
        if payload is None:
            await websocket.send_json({"type": "error", "message": "Token invalid or expired."})
            await websocket.close(code=4001)
            return

        try:
            user_id = int(payload.get("sub"))
        except (TypeError, ValueError):
            await websocket.send_json({"type": "error", "message": "Malformed token"})
            await websocket.close(code=4001)
            return

        # 3. Получаем пользователя
        with engine.connect() as conn:
            user = conn.execute(select(users).where(users.c.id == user_id)).fetchone()

        if not user:
            await websocket.send_json({"type": "error", "message": "User not found"})
            await websocket.close(code=4001)
            return

        user_credits = user.credits
        logger.info(f"🔌 WS: user={user_id} credits={user_credits} msg={message[:50]}...")

        # 4. Callback для стриминга фаз клиенту
        async def on_phase(msg: dict) -> None:
            await websocket.send_json(msg)

        # 5. Запускаем делиберацию
        result = await run_council_deliberation(
            query=message,
            user_credits=user_credits,
            history_count=0,
            on_phase=on_phase,
        )

        # 6. Списываем кредиты
        credits_needed = result.get("credits_needed", 1)
        new_credits = max(0, user_credits - credits_needed)

        with engine.connect() as conn:
            conn.execute(update(users).where(users.c.id == user_id).values(credits=new_credits))
            conn.commit()

        logger.info(f"🔌 WS: done | credits {user_credits}→{new_credits}")

        # 7. Финальный результат
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
