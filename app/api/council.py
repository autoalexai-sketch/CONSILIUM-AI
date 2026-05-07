"""
app/api/council.py â€” ĐˇĐľĐ˛ĐµŃ‚ Đ´Đ¸Ń€ĐµĐşŃ‚ĐľŃ€ĐľĐ˛.

run_council_deliberation() ĐżŃ€Đ¸Đ˝Đ¸ĐĽĐ°ĐµŃ‚ ĐľĐżŃ†Đ¸ĐľĐ˝Đ°Đ»ŃŚĐ˝Ń‹Đą on_phase callback.
ĐšĐľĐłĐ´Đ° Đ·Đ°Đ´Đ°Đ˝ â€” ŃŃ‚Ń€Đ¸ĐĽĐ¸Ń‚ ĐľĐ±Đ˝ĐľĐ˛Đ»ĐµĐ˝Đ¸ŃŹ ĐżĐľ WebSocket Đ˛ Ń€ĐµĐ°Đ»ŃŚĐ˝ĐľĐĽ Đ˛Ń€ĐµĐĽĐµĐ˝Đ¸.
"""

from typing import Optional, Callable, Any

from fastapi import APIRouter, HTTPException, Request
from loguru import logger

from core.ai_fallback import fallback_manager
from core.cognitive_classifier import CognitiveDimension, TaskProfile
from core.council_selector import CouncilSelector
from core.prompts import PromptBuilder, PromptUtils
from core.synthesizer_integration import SynthesizerPhase
from app.dependencies import save_classification_log
from app.middleware.rate_limiter import rate_limiter
from app.services import classifier, openrouter

router = APIRouter()


def _build_free_prompt(role: str, query: str, lang: str, context: str = "") -> str:
    """ĐšĐľŃ€ĐľŃ‚ĐşĐ¸Đą ĐżŃ€ĐľĐĽĐżŃ‚ Đ´Đ»ŃŹ Ollama / free plan."""
    lang_map = {"ru": "Ń€ŃŃŃĐşĐľĐĽ", "uk": "ŃĐşŃ€Đ°Đ¸Đ˝ŃĐşĐľĐĽ", "ua": "ŃĐşŃ€Đ°Đ¸Đ˝ŃĐşĐľĐĽ",
                "pl": "ĐżĐľĐ»ŃŚŃĐşĐľĐĽ", "en": "Đ°Đ˝ĐłĐ»Đ¸ĐąŃĐşĐľĐĽ"}
    lang_instr = f"ĐžŃ‚Đ˛ĐµŃ‡Đ°Đą Đ˝Đ° {lang_map.get(lang, 'Ń€ŃŃŃĐşĐľĐĽ')} ŃŹĐ·Ń‹ĐşĐµ. Đ‘ŃĐ´ŃŚ Đ»Đ°ĐşĐľĐ˝Đ¸Ń‡ĐµĐ˝."
    ctx = f"\n\nĐšĐľĐ˝Ń‚ĐµĐşŃŃ‚:\n{context[:400]}" if context else ""
    templates = {
        "scout":     f"{lang_instr} ĐźĐµŃ€ĐµŃ‡Đ¸ŃĐ»Đ¸ 3-5 ĐşĐ»ŃŽŃ‡ĐµĐ˛Ń‹Ń… Ń„Đ°ĐşŃ‚Đ° ĐżĐľ Ń‚ĐµĐĽĐµ: {query}",
        "analyst":   f"{lang_instr} ĐšŃ€Đ°Ń‚ĐşĐľ ĐżŃ€ĐľĐ°Đ˝Đ°Đ»Đ¸Đ·Đ¸Ń€ŃĐą (2-3 Đ˛Ń‹Đ˛ĐľĐ´Đ°): {query}{ctx}",
        "architect": f"{lang_instr} ĐźŃ€ĐµĐ´Đ»ĐľĐ¶Đ¸ 2-3 ĐşĐľĐ˝ĐşŃ€ĐµŃ‚Đ˝Ń‹Ń… ŃĐ°ĐłĐ° Đ´Đ»ŃŹ Ń€ĐµŃĐµĐ˝Đ¸ŃŹ: {query}{ctx}",
        "devil":     f"{lang_instr} ĐťĐ°Đ·ĐľĐ˛Đ¸ 2-3 ĐłĐ»Đ°Đ˛Đ˝Ń‹Ń… Ń€Đ¸ŃĐşĐ° Đ¸Đ»Đ¸ ŃĐ»Đ°Đ±Ń‹Ń… ĐĽĐµŃŃ‚Đ°: {query}{ctx}",
        "chairman":  f"{lang_instr} Đ”Đ°Đą Ń‡Ń‘Ń‚ĐşĐ¸Đą Ń€Đ°Đ·Đ˛Ń‘Ń€Đ˝ŃŃ‚Ń‹Đą ĐľŃ‚Đ˛ĐµŃ‚: {query}{ctx}",
        "operator":  f"{lang_instr} ĐˇĐľŃŃ‚Đ°Đ˛ŃŚ ĐżĐľŃĐ°ĐłĐľĐ˛Ń‹Đą ĐżĐ»Đ°Đ˝ Đ´ĐµĐąŃŃ‚Đ˛Đ¸Đą: {query}{ctx}",
    }
    return templates.get(role, f"{lang_instr} {query}")


async def _emit(on_phase: Optional[Callable], msg: dict) -> None:
    """Đ‘ĐµĐ·ĐľĐżĐ°ŃĐ˝Ń‹Đą Đ˛Ń‹Đ·ĐľĐ˛ on_phase callback."""
    if on_phase is None:
        return
    try:
        await on_phase(msg)
    except Exception as e:
        logger.debug(f"WS emit skipped: {e}")


def _is_simple_query(query: str) -> bool:
    """True â€” ĐżŃ€ĐľŃŃ‚ĐľĐą Ń„Đ°ĐşŃ‚Đ¸Ń‡ĐµŃĐşĐ¸Đą Đ˛ĐľĐżŃ€ĐľŃ, Đ˝Đµ Ń‚Ń€ĐµĐ±ŃĐµŃ‚ ĐżĐľĐ»Đ˝ĐľĐłĐľ ŃĐľĐ˛ĐµŃ‚Đ°."""
    q = query.strip().lower()
    words = q.split()
    # ĐˇĐ»Đ¸ŃĐşĐľĐĽ ĐşĐľŃ€ĐľŃ‚ĐşĐ¸Đą
    if len(words) <= 5:
        return True
    # ĐźĐ°Ń‚Ń‚ĐµŃ€Đ˝Ń‹ ĐżŃ€ĐľŃŃ‚Ń‹Ń… Đ˛ĐľĐżŃ€ĐľŃĐľĐ˛
    simple = [
        'ĐżĐľĐłĐľĐ´Đ°', 'Ń‚ĐµĐĽĐżĐµŃ€Đ°Ń‚ŃŃ€Đ°', 'ĐşŃŃ€Ń Đ˛Đ°Đ»ŃŽŃ‚', 'ŃĐşĐľĐ»ŃŚĐşĐľ ŃŃ‚ĐľĐ¸Ń‚',
        'ĐşĐ°ĐşĐ°ŃŹ ĐżĐľĐłĐľĐ´Đ°', 'ĐşĐ°ĐşĐľĐą ŃĐµĐłĐľĐ´Đ˝ŃŹ', 'ĐşĐ°ĐşĐľĐµ ŃĐµĐłĐľĐ´Đ˝ŃŹ', 'Ń‡Ń‚Đľ Ń‚Đ°ĐşĐľĐµ',
        'ĐşŃ‚Đľ Ń‚Đ°ĐşĐľĐą', 'ĐşĐľĐłĐ´Đ° ĐľŃ‚ĐşŃ€Ń‹Đ»ŃŃŹ', 'ĐşĐľĐłĐ´Đ° ĐľŃ‚ĐşŃ€Ń‹Đ˛Đ°ĐµŃ‚ŃŃŹ',
        'weather', 'temperature', 'what is', 'who is', 'when did',
        'ĐżŃ€Đ¸Đ˛ĐµŃ‚', 'Đ·Đ´Ń€Đ°ŃŃ‚Đ˛ŃĐą', 'hello', 'hi ', 'ŃĐżĐ°ŃĐ¸Đ±Đľ', 'thank',
        'ŃŃ‚ĐľĐ»Đ¸Ń†Đ°', 'Đ˝Đ°ŃĐµĐ»ĐµĐ˝Đ¸Đµ', 'ĐżĐ»ĐľŃ‰Đ°Đ´ŃŚ', 'Đ´Đ»Đ¸Đ˝Đ°', 'Đ˛Ń‹ŃĐľŃ‚Đ°',
    ]
    return any(p in q for p in simple)


async def _call_director(role: str, prompt: str, director_spec, is_free: bool) -> dict:
    """Đ•Đ´Đ¸Đ˝Ń‹Đą Đ˛Ń‹Đ·ĐľĐ˛ Đ´Đ¸Ń€ĐµĐşŃ‚ĐľŃ€Đ° Ń fallback."""
    return await fallback_manager.call_with_backup(
        openrouter.call_director,
        director_spec,
        [{"role": "user", "content": prompt}]
    )


async def run_council_deliberation(
    query: str,
    user_credits: int = 15,
    history_count: int = 0,
    on_phase: Optional[Callable[[dict], Any]] = None,
    user_id: int = 0,
) -> dict:
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    logger.info(f"{'='*60}")
    logger.info(f"đź“ť Đ—ĐĐźĐ ĐžĐˇ: {query[:70]}...")

    # â”€â”€ FAST-TRACK: ĐżŃ€ĐľŃŃ‚Ń‹Đµ Đ˛ĐľĐżŃ€ĐľŃŃ‹ â€” ĐľĐ´Đ¸Đ˝ Đ´Đ¸Ń€ĐµĐşŃ‚ĐľŃ€ Đ±ĐµĐ· ŃĐľĐ˛ĐµŃ‚Đ° â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if _is_simple_query(query):
        logger.info("âšˇ Fast-track: ĐżŃ€ĐľŃŃ‚ĐľĐą Đ˛ĐľĐżŃ€ĐľŃ, ĐżŃ€ĐľĐżŃŃĐşĐ°ĐµĐĽ ŃĐľĐ˛ĐµŃ‚")
        await _emit(on_phase, {"type": "phase_start", "phase": "chairman",
                               "text": "Đ‘Ń‹ŃŃ‚Ń€Ń‹Đą ĐľŃ‚Đ˛ĐµŃ‚..."})
        lang_map = {"ru": "Ń€ŃŃŃĐşĐľĐĽ", "uk": "ŃĐşŃ€Đ°Đ¸Đ˝ŃĐşĐľĐĽ",
                   "ua": "ŃĐşŃ€Đ°Đ¸Đ˝ŃĐşĐľĐĽ", "pl": "ĐżĐľĐ»ŃŚŃĐşĐľĐĽ", "en": "English"}
        # ĐžĐżŃ€ĐµĐ´ĐµĐ»ŃŹĐµĐĽ ŃŹĐ·Ń‹Đş Đ±Ń‹ŃŃ‚Ń€Đľ
        detected_lang = "ru"
        if any(w in query.lower() for w in ["the ", "what ", "how ", "when ", "where "]):
            detected_lang = "en"
        elif any(w in query.lower() for w in ["jak ", "czy ", "co ", "gdzie ", "kiĹ‚ka"]):
            detected_lang = "pl"
        elif any(ord(c) in range(0x400, 0x450) for c in query[:20]):
            detected_lang = "ru"
        lang_name = lang_map.get(detected_lang, "Ń€ŃŃŃĐşĐľĐĽ")
        prompt = f"ĐžŃ‚Đ˛ĐµŃ‡Đ°Đą Đ˝Đ° {lang_name} ŃŹĐ·Ń‹ĐşĐµ. Đ‘ŃĐ´ŃŚ Ń‚ĐľŃ‡Đ˝Ń‹ĐĽ Đ¸ ĐżĐľĐ»ĐµĐ·Đ˝Ń‹ĐĽ.\n\n{query}"
        res = await fallback_manager._call_groq(prompt)
        answer = res.get("content", "") if res.get("success") else "[ĐťĐµ ŃĐ´Đ°Đ»ĐľŃŃŚ ĐżĐľĐ»ŃŃ‡Đ¸Ń‚ŃŚ ĐľŃ‚Đ˛ĐµŃ‚]"
        await _emit(on_phase, {
            "type": "phase_done", "phase": "chairman",
            "tokens": res.get("tokens", 0), "provider": res.get("provider", "groq"),
            "preview": answer[:300]
        })
        return {
            "success": True, "query": query,
            "profile": {"language": detected_lang, "dimensions": ["FACTUAL"],
                        "urgency": 0.3, "depth": 2},
            "council": {"selected": ["chairman"], "directors": {}},
            "deliberation": {"chairman": {"model": "groq", "success": True,
                             "preview": answer[:300], "tokens": res.get("tokens", 0),
                             "cost_usd": 0.0}},
            "final_decision": answer,
            "total_cost_usd": 0.0,
            "credits_needed": 1,
            "errors": None,
            "synthesis_report": None,
        }

    # â”€â”€ 1. ĐšĐ›ĐĐˇĐˇĐĐ¤ĐĐšĐĐ¦ĐĐŻ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    await _emit(on_phase, {
        "type": "phase_start", "phase": "classifier",
        "text": "Discovery: Đ°Đ˝Đ°Đ»Đ¸Đ· ĐşĐľĐłĐ˝Đ¸Ń‚Đ¸Đ˛Đ˝ĐľĐą ŃĐ»ĐľĐ¶Đ˝ĐľŃŃ‚Đ¸ Đ·Đ°ĐżŃ€ĐľŃĐ°..."
    })
    profile = await classifier.analyze(query)
    await save_classification_log(query, profile)

    # â”€â”€ 2. Đ’Đ«Đ‘ĐžĐ  ĐˇĐžĐ’Đ•Đ˘Đ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    is_free = user_credits <= 0
    selector = CouncilSelector(max_budget_usd=0.15, is_free_plan=is_free)
    selected_ids = selector.select_council(
        profile=profile,
        user_credits=user_credits,
        user_history_count=history_count,
        explicit_keywords=query.lower().split(),
    )

    if "chairman" not in selected_ids:
        selected_ids.append("chairman")

    if is_free:
        selected_ids = [d for d in selected_ids if d in ["scout", "analyst", "chairman"]]
    else:
        if profile.required_depth >= 6 or CognitiveDimension.COMPLEX in profile.dimensions:
            if "devil" not in selected_ids and len(selected_ids) < 6:
                selected_ids.append("devil")

    # ĐˇŃ‚Ń€ĐľĐ¸ĐĽ dict Đ´Đ¸Ń€ĐµĐşŃ‚ĐľŃ€ĐľĐ˛ Đ¸Đ· CouncilSelector
    directors = {}
    for did in selected_ids:
        spec = selector.get_director(did)
        if spec:
            directors[did] = spec

    await _emit(on_phase, {"type": "council_ready", "selected": selected_ids})
    logger.info(f"đź‘Ą ĐˇĐľĐ˛ĐµŃ‚: {selected_ids}")

    results = {}
    total_cost = 0.0
    errors = []

    # â”€â”€ 3. SCOUT â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if "scout" in directors:
        await _emit(on_phase, {"type": "phase_start", "phase": "scout",
                               "text": "Evidence: ŃĐşĐ°Đ˝Đ¸Ń€ĐľĐ˛Đ°Đ˝Đ¸Đµ Đ¸ŃŃ‚ĐľŃ‡Đ˝Đ¸ĐşĐľĐ˛..."})
        prompt = (_build_free_prompt("scout", query, profile.suggested_language) if is_free
                  else PromptUtils.add_language_context(
                      PromptBuilder.build_scout_prompt(query, profile), profile.suggested_language))
        res = await _call_director("scout", prompt, directors["scout"], is_free)
        results["scout"] = res
        if not res.get("error"):
            total_cost += res.get("cost_usd", 0.0)
            await _emit(on_phase, {"type": "phase_done", "phase": "scout",
                                   "tokens": res.get("tokens", 0), "provider": res.get("provider", "?"),
                                   "preview": str(res.get("content", ""))[:200]})
        else:
            errors.append(f"Scout: {res.get('error', '')}")
            await _emit(on_phase, {"type": "phase_error", "phase": "scout", "error": res.get("error")})

    facts = (results.get("scout", {}).get("content", "")
             if not results.get("scout", {}).get("error") else "")

    # â”€â”€ 4. ANALYST â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if "analyst" in directors:
        await _emit(on_phase, {"type": "phase_start", "phase": "analyst",
                               "text": "Analysis: Đ˛Ń‹ŃŹĐ˛Đ»ĐµĐ˝Đ¸Đµ ĐżĐ°Ń‚Ń‚ĐµŃ€Đ˝ĐľĐ˛ Đ¸ ŃŃ‚Ń€ŃĐşŃ‚ŃŃ€Ń‹..."})
        prompt = (_build_free_prompt("analyst", query, profile.suggested_language, facts) if is_free
                  else PromptUtils.add_language_context(
                      PromptBuilder.build_analyst_prompt(query, profile, [facts]), profile.suggested_language))
        res = await _call_director("analyst", prompt, directors["analyst"], is_free)
        results["analyst"] = res
        if not res.get("error"):
            total_cost += res.get("cost_usd", 0.0)
            await _emit(on_phase, {"type": "phase_done", "phase": "analyst",
                                   "tokens": res.get("tokens", 0), "provider": res.get("provider", "?"),
                                   "preview": str(res.get("content", ""))[:200]})
        else:
            errors.append(f"Analyst: {res.get('error', '')}")
            await _emit(on_phase, {"type": "phase_error", "phase": "analyst", "error": res.get("error")})

    analysis = (results.get("analyst", {}).get("content", "")
                if not results.get("analyst", {}).get("error") else "")

    # â”€â”€ 5. ARCHITECT â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if "architect" in directors:
        await _emit(on_phase, {"type": "phase_start", "phase": "architect",
                               "text": "Architecture: ĐżŃ€ĐľĐµĐşŃ‚Đ¸Ń€ĐľĐ˛Đ°Đ˝Đ¸Đµ Ń€ĐµŃĐµĐ˝Đ¸ŃŹ..."})
        prompt = (_build_free_prompt("architect", query, profile.suggested_language, analysis) if is_free
                  else PromptUtils.add_language_context(
                      PromptBuilder.build_architect_prompt(query, profile, analysis), profile.suggested_language))
        res = await _call_director("architect", prompt, directors["architect"], is_free)
        results["architect"] = res
        if not res.get("error"):
            total_cost += res.get("cost_usd", 0.0)
            await _emit(on_phase, {"type": "phase_done", "phase": "architect",
                                   "tokens": res.get("tokens", 0), "provider": res.get("provider", "?"),
                                   "preview": str(res.get("content", ""))[:200]})
        else:
            errors.append(f"Architect: {res.get('error', '')}")
            await _emit(on_phase, {"type": "phase_error", "phase": "architect", "error": res.get("error")})

    solutions = (results.get("architect", {}).get("content", "")
                 if not results.get("architect", {}).get("error") else "")

    # â”€â”€ 6. DEVIL'S ADVOCATE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    criticism = ""
    if "devil" in directors and not is_free:
        await _emit(on_phase, {"type": "phase_start", "phase": "devil",
                               "text": "Red Teaming: ĐżĐľĐ¸ŃĐş Ń€Đ¸ŃĐşĐľĐ˛ Đ¸ ŃĐ»Đ°Đ±Ń‹Ń… ĐĽĐµŃŃ‚..."})
        prompt = PromptUtils.add_language_context(
            PromptBuilder.build_devil_advocate_prompt(query, profile, facts, analysis, solutions),
            profile.suggested_language)
        res = await _call_director("devil", prompt, directors["devil"], is_free)
        results["devil"] = res
        if not res.get("error"):
            total_cost += res.get("cost_usd", 0.0)
            criticism = res.get("content", "")
            await _emit(on_phase, {"type": "phase_done", "phase": "devil",
                                   "tokens": res.get("tokens", 0), "provider": res.get("provider", "?"),
                                   "preview": str(res.get("content", ""))[:200]})
        else:
            errors.append(f"Devil: {res.get('error', '')}")
            await _emit(on_phase, {"type": "phase_error", "phase": "devil", "error": res.get("error")})

    # â”€â”€ 7. SYNTHESIZER â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    syn_result = None
    if not is_free and len(results) >= 2:
        await _emit(on_phase, {"type": "phase_start", "phase": "synthesizer",
                               "text": "Quality Gate: ĐżŃ€ĐľĐ˛ĐµŃ€ĐşĐ° ŃĐľĐłĐ»Đ°ŃĐľĐ˛Đ°Đ˝Đ˝ĐľŃŃ‚Đ¸..."})
        syn_result = await SynthesizerPhase.execute(
            query=query,
            phase_results={k: {"content": v.get("content", ""), "success": not v.get("error")}
                           for k, v in results.items()},
            task_profile=profile,
            language=profile.suggested_language,
        )
        results["synthesizer"] = syn_result
        if syn_result.get("success"):
            total_cost += syn_result.get("cost_usd", 0.0)
            await _emit(on_phase, {"type": "phase_done", "phase": "synthesizer",
                                   "tokens": syn_result.get("tokens", 0),
                                   "provider": syn_result.get("provider", "synthesizer"),
                                   "preview": "ĐĐ˝Đ°Đ»Đ¸Đ· ĐżŃ€ĐľŃ‚Đ¸Đ˛ĐľŃ€ĐµŃ‡Đ¸Đą Đ·Đ°Đ˛ĐµŃ€ŃŃ‘Đ˝"})

    # â”€â”€ 8. CHAIRMAN â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    chairman_result = None
    if "chairman" in directors:
        await _emit(on_phase, {"type": "phase_start", "phase": "chairman",
                               "text": "Verdict: ŃĐ¸Đ˝Ń‚ĐµĐ· Ń„Đ¸Đ˝Đ°Đ»ŃŚĐ˝ĐľĐłĐľ Ń€ĐµŃĐµĐ˝Đ¸ŃŹ..."})
        prompt = (_build_free_prompt("chairman", query, profile.suggested_language,
                                     f"{analysis}\n{solutions}") if is_free
                  else PromptUtils.add_language_context(
                      PromptBuilder.build_chairman_prompt(
                          query, profile, facts, analysis, solutions, criticism),
                      profile.suggested_language))
        chairman_result = await _call_director("chairman", prompt, directors["chairman"], is_free)
        results["chairman"] = chairman_result
        if not chairman_result.get("error"):
            total_cost += chairman_result.get("cost_usd", 0.0)
            await _emit(on_phase, {"type": "phase_done", "phase": "chairman",
                                   "tokens": chairman_result.get("tokens", 0),
                                   "provider": chairman_result.get("provider", "?"),
                                   "preview": str(chairman_result.get("content", ""))[:200]})
        else:
            errors.append(f"Chairman: {chairman_result.get('error', '')}")
            await _emit(on_phase, {"type": "phase_error", "phase": "chairman",
                                   "error": chairman_result.get("error")})

    # â”€â”€ 9. Đ¤ĐĐťĐĐ›Đ¬ĐťĐ«Đ™ ĐžĐ˘Đ’Đ•Đ˘ + VETO â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    final_response = None

    if chairman_result and not chairman_result.get("error") and chairman_result.get("content"):
        final_response = chairman_result["content"]

        if syn_result and syn_result.get("analysis"):
            coherence = syn_result["analysis"].get("coherence_score", 100)
            if coherence < 50:
                logger.warning(f"âš ď¸Ź VETO Đ°ĐşŃ‚Đ¸Đ˛Đ¸Ń€ĐľĐ˛Đ°Đ˝ (coherence={coherence}%)")
                final_response = (
                    f"âš ď¸Ź [Đ’ĐťĐĐśĐĐťĐĐ•: ĐšĐľĐ˝Ń‚Ń€ĐľĐ»ŃŚ ĐşĐ°Ń‡ĐµŃŃ‚Đ˛Đ° Đ˛Ń‹ŃŹĐ˛Đ¸Đ» Ń€Đ¸ŃĐşĐ¸]\n\n"
                    f"{final_response}\n\n"
                    f"**ĐĐťĐĐ›ĐĐ— ĐšĐžĐťĐ˘Đ ĐžĐ›Đ•Đ Đ:** "
                    f"{syn_result['analysis'].get('meta_recommendation', 'ĐžĐ±Đ˝Đ°Ń€ŃĐ¶ĐµĐ˝Ń‹ ĐżŃ€ĐľŃ‚Đ¸Đ˛ĐľŃ€ĐµŃ‡Đ¸ŃŹ.')}"
                )

    if not final_response:
        for phase_key in ["analyst", "architect", "scout", "devil"]:
            if phase_key in results:
                content = results[phase_key].get("content", "")
                if content and not content.startswith("[ĐžŃĐ¸Đ±ĐşĐ°"):
                    logger.warning(f"âš ď¸Ź Fallback: Đ¸ŃĐżĐľĐ»ŃŚĐ·ŃĐµŃ‚ŃŃŹ {phase_key}")
                    final_response = f"âš ď¸Ź ĐźŃ€ĐµĐ´ŃĐµĐ´Đ°Ń‚ĐµĐ»ŃŚ Đ˝ĐµĐ´ĐľŃŃ‚ŃĐżĐµĐ˝ â€” ĐľŃ‚Đ˛ĐµŃ‚ ĐľŃ‚ {phase_key.capitalize()}:\n\n{content}"
                    break

    if not final_response:
        provider_errors = errors or ["Đ’ŃĐµ AI-ĐżŃ€ĐľĐ˛Đ°ĐąĐ´ĐµŃ€Ń‹ Đ˛Ń€ĐµĐĽĐµĐ˝Đ˝Đľ Đ˝ĐµĐ´ĐľŃŃ‚ŃĐżĐ˝Ń‹"]
        logger.error(f"âťŚ Đ’ŃĐµ ĐżŃ€ĐľĐ˛Đ°ĐąĐ´ĐµŃ€Ń‹ Đ˝ĐµĐ´ĐľŃŃ‚ŃĐżĐ˝Ń‹: {provider_errors}")
        final_response = (
            f"ĐˇĐ¸ŃŃ‚ĐµĐĽĐ° Đ˛Ń€ĐµĐĽĐµĐ˝Đ˝Đľ Đ˝Đµ ĐĽĐľĐ¶ĐµŃ‚ Đ´Đ°Ń‚ŃŚ ĐľŃ‚Đ˛ĐµŃ‚.\n\n"
            f"{''.join(f'â€˘ {e}' + chr(10) for e in provider_errors)}\n"
            f"ĐźŃ€ĐľĐ˛ĐµŃ€ŃŚŃ‚Đµ API ĐşĐ»ŃŽŃ‡Đ¸ Đ˛ .env Đ¸Đ»Đ¸ Đ·Đ°ĐżŃŃŃ‚Đ¸Ń‚Đµ Ollama."
        )

    # â”€â”€ 10. Đ¤ĐžĐ ĐśĐĐ ĐžĐ’ĐĐťĐĐ• ĐžĐ˘Đ’Đ•Đ˘Đ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    deliberation = {}
    for phase, res in results.items():
        if res and isinstance(res, dict):
            deliberation[phase] = {
                "model":   res.get("provider", "unknown"),
                "success": not bool(res.get("error")),
                "preview": str(res.get("content", ""))[:300] + "..." if res.get("content") else "ĐťĐµŃ‚ Đ´Đ°Đ˝Đ˝Ń‹Ń…",
                "tokens":  res.get("tokens", 0),
                "cost_usd": round(res.get("cost_usd", 0), 4),
            }

    logger.info(f"đźŹ Đ”ĐµĐ»Đ¸Đ±ĐµŃ€Đ°Ń†Đ¸ŃŹ Đ·Đ°Đ˛ĐµŃ€ŃĐµĐ˝Đ° | cost=${total_cost:.4f} | errors={len(errors)}")

    return {
        "success": len(errors) == 0 or (chairman_result and not chairman_result.get("error")),
        "query": query,
        "profile": {
            "language":   profile.suggested_language,
            "dimensions": [d.name for d in profile.dimensions],
            "urgency":    profile.urgency,
            "depth":      profile.required_depth,
        },
        "council": {
            "selected": selected_ids,
            "directors": {k: {"model": getattr(v, "model", str(v)),
                              "description": getattr(v, "description", "ĐŁŃ‡Đ°ŃŃ‚Đ˝Đ¸Đş ŃĐľĐ˛ĐµŃ‚Đ°")}
                          for k, v in directors.items()},
        },
        "deliberation":     deliberation,
        "final_decision":   final_response,
        "total_cost_usd":   round(total_cost, 4),
        "credits_needed":   max(1, int(total_cost * 100)),
        "errors":           errors if errors else None,
        "synthesis_report": results.get("synthesizer", {}).get("analysis"),
    }


@router.post("/council/deliberate")
async def council_deliberate(request: Request):
    await rate_limiter.check(request)
    data = await request.json()
    return await run_council_deliberation(
        query=data.get("query", ""),
        user_credits=data.get("credits", 15),
        history_count=data.get("history_count", 0),
    )


@router.get("/debug/classify")
async def debug_classify(q: str = ""):
    if not q:
        return {"error": "Đ”ĐľĐ±Đ°Đ˛ŃŚŃ‚Đµ ?q=Đ˛Đ°Ń Đ·Đ°ĐżŃ€ĐľŃ"}
    profile = await classifier.analyze(q, {})
    await save_classification_log(q, profile)
    return {
        "query": q,
        "detected_language": profile.suggested_language,
        "task_type": [d.name for d in profile.dimensions],
        "emotional_load": round(profile.emotional_load, 2),
        "urgency": round(profile.urgency, 2),
        "processing_ms": round(profile.processing_time_ms, 2),
    }


@router.post("/debug/select-council")
async def debug_select_council(request: Request):
    data = await request.json()
    query = data.get("query", "")
    user_credits = data.get("credits", 15)
    profile = await classifier.analyze(query)
    is_free = user_credits <= 0
    selector = CouncilSelector(max_budget_usd=0.15, is_free_plan=is_free)
    selected = selector.select_council(
        profile=profile, user_credits=user_credits,
        user_history_count=0, explicit_keywords=query.lower().split())

    # Autosave verdict to Decision Journal
    if final_response and user_id and not final_response.startswith("System"):
        try:
            import json as _json
            from datetime import datetime as _dt
            from app.database import decision_journal as _dj
            with engine.begin() as _conn:
                _conn.execute(_dj.insert().values(
                    user_id=user_id, session_id=None,
                    title=query[:80], query_text=query[:2000],
                    verdict=final_response[:5000],
                    council_used=_json.dumps(selected_ids),
                    outcome_label="auto", is_pinned=False,
                    created_at=_dt.utcnow(), updated_at=_dt.utcnow(),
                ))
            logger.debug(f"Journal autosaved: user={user_id}")
        except Exception as _e:
            logger.debug(f"Journal autosave skipped: {_e}")
    return {
        "query": query,
        "task_profile": {"dimensions": [d.name for d in profile.dimensions],
                         "urgency": profile.urgency, "depth": profile.required_depth},
        "selected_council": selected,
        "council_details": selector.get_council_details(selected),
        "estimated_cost_usd": round(selector._estimate_cost(selected), 4),
    }

