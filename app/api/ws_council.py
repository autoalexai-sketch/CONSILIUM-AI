"""
app/api/ws_council.py â€” WebSocket ŃŤĐ˝Đ´ĐżĐľĐ¸Đ˝Ń‚ Đ´Đ»ŃŹ ŃŃ‚Ń€Đ¸ĐĽĐ¸Đ˝ĐłĐ° Đ´ĐµĐ»Đ¸Đ±ĐµŃ€Đ°Ń†Đ¸Đ¸.

ĐźŃ€ĐľŃ‚ĐľĐşĐľĐ»:
  ĐšĐ»Đ¸ĐµĐ˝Ń‚ â†’ ĐˇĐµŃ€Đ˛ĐµŃ€ (ĐżĐµŃ€Đ˛ĐľĐµ ŃĐľĐľĐ±Ń‰ĐµĐ˝Đ¸Đµ, JSON):
    {"token": "eyJ...", "message": "Ń‚ĐµĐşŃŃ‚ Đ·Đ°ĐżŃ€ĐľŃĐ°", "chat_id": "chat_..."}

  ĐˇĐµŃ€Đ˛ĐµŃ€ â†’ ĐšĐ»Đ¸ĐµĐ˝Ń‚:
    {"type": "council_ready",  "selected": [...]}
    {"type": "phase_start",    "phase": "scout", "text": "..."}
    {"type": "phase_done",     "phase": "scout", "tokens": 198, "provider": "...", "preview": "..."}
    {"type": "final",          "response": "...", "credits_left": N}
    {"type": "error",          "message": "..."}
"""

import json
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, BackgroundTasks
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
    logger.info("đź”Ś WS: Đ˝ĐľĐ˛ĐľĐµ ĐżĐľĐ´ĐşĐ»ŃŽŃ‡ĐµĐ˝Đ¸Đµ")

    try:
        # 1. Đ§Đ¸Ń‚Đ°ĐµĐĽ ĐżĐµŃ€Đ˛ĐľĐµ ŃĐľĐľĐ±Ń‰ĐµĐ˝Đ¸Đµ
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

        # ĐźĐ¸Đ˝Đł ĐżŃ€Đ¸ ĐżĐľĐ´ĐşĐ»ŃŽŃ‡ĐµĐ˝Đ¸Đ¸ â€” Đ˝Đµ ĐľĐ±Ń€Đ°Đ±Đ°Ń‚Ń‹Đ˛Đ°ĐµĐĽ ĐşĐ°Đş Đ·Đ°ĐżŃ€ĐľŃ
        if message == "__ping__":
            await websocket.send_json({"type": "pong"})
            # Đ–Đ´Ń‘ĐĽ ŃĐ»ĐµĐ´ŃŃŽŃ‰ĐµĐµ ŃĐľĐľĐ±Ń‰ĐµĐ˝Đ¸Đµ
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

        # 2. Đ’ĐµŃ€Đ¸Ń„Đ¸ĐşĐ°Ń†Đ¸ŃŹ JWT
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

        # 3. ĐźĐľĐ»ŃŃ‡Đ°ĐµĐĽ ĐżĐľĐ»ŃŚĐ·ĐľĐ˛Đ°Ń‚ĐµĐ»ŃŹ
        with engine.connect() as conn:
            user = conn.execute(select(users).where(users.c.id == user_id)).fetchone()

        if not user:
            await websocket.send_json({"type": "error", "message": "User not found"})
            await websocket.close(code=4001)
            return

        user_credits = user.credits
        logger.info(f"đź”Ś WS: user={user_id} credits={user_credits} msg={message[:50]}...")

        # â”€â”€ Experience: Đ˝Đ°Ń‡Đ¸Đ˝Đ°ĐµĐĽ ŃĐµŃŃĐ¸ŃŽ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
            logger.warning(f"âš ď¸Ź ExperienceService.create_session failed: {_e}")

        # 4. Callback Đ´Đ»ŃŹ ŃŃ‚Ń€Đ¸ĐĽĐ¸Đ˝ĐłĐ° Ń„Đ°Đ· ĐşĐ»Đ¸ĐµĐ˝Ń‚Ń
        async def on_phase(msg: dict) -> None:
            await websocket.send_json(msg)

        # 5. Đ—Đ°ĐżŃŃĐşĐ°ĐµĐĽ Đ´ĐµĐ»Đ¸Đ±ĐµŃ€Đ°Ń†Đ¸ŃŽ
        result = await run_council_deliberation(
            query=message,
            user_credits=user_credits,
            history_count=0,
            on_phase=on_phase,
        )

        # 6. ĐˇĐżĐ¸ŃŃ‹Đ˛Đ°ĐµĐĽ ĐşŃ€ĐµĐ´Đ¸Ń‚Ń‹
        credits_needed = result.get("credits_needed", 1)
        new_credits = max(0, user_credits - credits_needed)

        with engine.connect() as conn:
            conn.execute(update(users).where(users.c.id == user_id).values(credits=new_credits))
            conn.commit()

        logger.info(f"đź”Ś WS: done | credits {user_credits}â†’{new_credits}")

        # â”€â”€ Experience: Ń„Đ¸Đ˝Đ°Đ»Đ¸Đ·Đ¸Ń€ŃĐµĐĽ ŃĐµŃŃĐ¸ŃŽ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
                # ĐˇĐ¸ĐłĐ˝Đ°Đ» ĐşĐ°Ń‡ĐµŃŃ‚Đ˛Đ° ĐľŃ‚ Synthesizer
                if coherence is not None:
                    experience_service.add_signal(
                        session_id=exp_session_id,
                        signal_type="coherence_score",
                        value_num=float(coherence),
                        source="synthesizer",
                        weight=1.0,
                    )
                logger.debug(f"đź“ť Experience logged: session={exp_session_id} latency={latency_ms}ms")
            except Exception as _e:
                logger.warning(f"âš ď¸Ź ExperienceService.finalize failed: {_e}")

        # 7. Đ¤Đ¸Đ˝Đ°Đ»ŃŚĐ˝Ń‹Đą Ń€ĐµĐ·ŃĐ»ŃŚŃ‚Đ°Ń‚
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
        logger.info("đź”Ś WS: ĐşĐ»Đ¸ĐµĐ˝Ń‚ ĐľŃ‚ĐşĐ»ŃŽŃ‡Đ¸Đ»ŃŃŹ")
    except Exception as e:
        logger.error(f"đź”Ś WS: ĐľŃĐ¸Đ±ĐşĐ°: {e}")
        try:
            await websocket.send_json({"type": "error", "message": f"Server error: {str(e)[:100]}"})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

