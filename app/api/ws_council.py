"""
app/api/ws_council.py - WebSocket endpoint for streaming deliberation.

Protocol:
  Client -> Server (JSON):
    {"token": "eyJ...", "message": "query text", "chat_id": "chat_..."}

  Server -> Client:
    {"type": "council_ready",  "selected": [...]}
    {"type": "phase_start",    "phase": "scout", "text": "..."}
    {"type": "phase_done",     "phase": "scout", "tokens": 198, "provider": "..."}
    {"type": "final",          "response": "...", "credits_left": N}
    {"type": "error",          "message": "..."}

  Connection stays open - multiple questions per session supported.
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


def _calc_fallback_coherence(result: dict) -> int:
    """Estimate coherence from director success rate when Synthesizer didn't run."""
    delib = result.get("deliberation") or {}
    if not delib:
        return 0
    total = len(delib)
    ok = sum(1 for v in delib.values() if v.get("success"))
    if total == 0:
        return 0
    return int((ok / total) * 85)  # max 85 -- real synthesizer can go higher


@router.websocket("/ws/council")
async def ws_council(websocket: WebSocket):
    await websocket.accept()
    logger.info("WS: new connection")

    user_id: int | None = None
    chat_id: str = ""
    session_history: list = []  # last N user queries for follow-up context

    try:
        while True:
            # --- Read next message ---
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            token   = data.get("token", "")
            message = data.get("message", "").strip()
            chat_id = data.get("chat_id", chat_id)

            # Keepalive ping
            if message == "__ping__":
                await websocket.send_json({"type": "pong"})
                continue

            if not message:
                await websocket.send_json({"type": "error", "message": "Empty message"})
                continue

            # --- Enrich short follow-up queries with conversation context ---
            # e.g. "предложи варианты моделей" after discussing laptops
            enriched_message = message
            if len(message.split()) <= 6 and session_history:
                # Short message — prepend last user query as context
                last_q = session_history[-1] if session_history else ""
                enriched_message = f"{message} (context: {last_q[:200]})"
            session_history.append(message)

            # --- Verify JWT ---
            payload = verify_jwt_token(token)
            if payload is None:
                await websocket.send_json({"type": "error", "message": "Token invalid or expired."})
                continue

            try:
                user_id = int(payload.get("sub"))
            except (TypeError, ValueError):
                await websocket.send_json({"type": "error", "message": "Malformed token"})
                continue

            # --- Load user ---
            with engine.connect() as conn:
                user = conn.execute(
                    select(users).where(users.c.id == user_id)
                ).fetchone()

            if not user:
                await websocket.send_json({"type": "error", "message": "User not found"})
                continue

            user_credits = user.credits
            logger.info(f"WS: user={user_id} credits={user_credits} msg={message[:50]}...")

            if user_credits <= 0:
                await websocket.send_json({"type": "error", "message": "Not enough credits"})
                continue

            # --- Start experience session ---
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
                logger.warning(f"ExperienceService.create_session failed: {_e}")

            # --- Phase streaming callback ---
            async def on_phase(msg: dict) -> None:
                await websocket.send_json(msg)

            # --- Run deliberation ---
            result = await run_council_deliberation(
            query=enriched_message,
            user_credits=user_credits,
            history_count=len(session_history),
            on_phase=on_phase,
            user_id=user_id,
            )

            # --- Deduct credits ---
            credits_needed = result.get("credits_needed", 1)
            new_credits = max(0, user_credits - credits_needed)

            with engine.connect() as conn:
                conn.execute(
                    update(users).where(users.c.id == user_id).values(credits=new_credits)
                )
                conn.commit()

            logger.info(f"WS: done | credits {user_credits}->{new_credits}")

            # --- Finalize experience session ---
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
                    logger.debug(f"Experience logged: session={exp_session_id} latency={latency_ms}ms")
                except Exception as _e:
                    logger.warning(f"ExperienceService.finalize failed: {_e}")

            # --- Send final result ---
            await websocket.send_json({
                "type":            "final",
                "response":        result.get("final_decision", ""),
                "council_used":    result.get("council", {}).get("selected", []),
                "cost_usd":        result.get("total_cost_usd", 0.0),
                "deliberation":    result.get("deliberation", {}),
                "credits_left":    new_credits,
                "chat_id":         chat_id,
                "coherence_score": (
                    (result.get("synthesis_report") or {}).get("coherence_score")
                    or result.get("coherence_score")
                    or _calc_fallback_coherence(result)
                ),
                "synthesis_report": result.get("synthesis_report"),
                "journal_id":      result.get("journal_id"),
            })

    except WebSocketDisconnect:
        logger.info("WS: client disconnected")
    except Exception as e:
        logger.error(f"WS: error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": f"Server error: {str(e)[:100]}"})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass