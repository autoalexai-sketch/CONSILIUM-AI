"""
app/api/council.py — Совет директоров.

run_council_deliberation() принимает опциональный on_phase callback.
Когда задан — стримит обновления по WebSocket в реальном времени.
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
    """Короткий промпт для Ollama / free plan."""
    lang_map = {"ru": "русском", "uk": "украинском", "ua": "украинском",
                "pl": "польском", "en": "английском"}
    lang_instr = f"Отвечай на {lang_map.get(lang, 'русском')} языке. Будь лаконичен."
    ctx = f"\n\nКонтекст:\n{context[:400]}" if context else ""
    templates = {
        "scout":     f"{lang_instr} Перечисли 3-5 ключевых факта по теме: {query}",
        "analyst":   f"{lang_instr} Кратко проанализируй (2-3 вывода): {query}{ctx}",
        "architect": f"{lang_instr} Предложи 2-3 конкретных шага для решения: {query}{ctx}",
        "devil":     f"{lang_instr} Назови 2-3 главных риска или слабых места: {query}{ctx}",
        "chairman":  f"{lang_instr} Дай чёткий развёрнутый ответ: {query}{ctx}",
        "operator":  f"{lang_instr} Составь пошаговый план действий: {query}{ctx}",
    }
    return templates.get(role, f"{lang_instr} {query}")


async def _emit(on_phase: Optional[Callable], msg: dict) -> None:
    """Безопасный вызов on_phase callback."""
    if on_phase is None:
        return
    try:
        await on_phase(msg)
    except Exception as e:
        logger.debug(f"WS emit skipped: {e}")


def _is_simple_query(query: str) -> bool:
    """True — простой фактический вопрос, не требует полного совета."""
    q = query.strip().lower()
    words = q.split()
    # Слишком короткий
    if len(words) <= 5:
        return True
    # Паттерны простых вопросов
    simple = [
        'погода', 'температура', 'курс валют', 'сколько стоит',
        'какая погода', 'какой сегодня', 'какое сегодня', 'что такое',
        'кто такой', 'когда открылся', 'когда открывается',
        'weather', 'temperature', 'what is', 'who is', 'when did',
        'привет', 'здраствуй', 'hello', 'hi ', 'спасибо', 'thank',
        'столица', 'население', 'площадь', 'длина', 'высота',
    ]
    return any(p in q for p in simple)


async def _call_director(role: str, prompt: str, director_spec, is_free: bool) -> dict:
    """Единый вызов директора с fallback."""
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
) -> dict:
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    logger.info(f"{'='*60}")
    logger.info(f"📝 ЗАПРОС: {query[:70]}...")

    # ── FAST-TRACK: простые вопросы — один директор без совета ─────────────────
    if _is_simple_query(query):
        logger.info("⚡ Fast-track: простой вопрос, пропускаем совет")
        await _emit(on_phase, {"type": "phase_start", "phase": "chairman",
                               "text": "Быстрый ответ..."})
        lang_map = {"ru": "русском", "uk": "украинском",
                   "ua": "украинском", "pl": "польском", "en": "English"}
        # Определяем язык быстро
        detected_lang = "ru"
        if any(w in query.lower() for w in ["the ", "what ", "how ", "when ", "where "]):
            detected_lang = "en"
        elif any(w in query.lower() for w in ["jak ", "czy ", "co ", "gdzie ", "kiłka"]):
            detected_lang = "pl"
        elif any(ord(c) in range(0x400, 0x450) for c in query[:20]):
            detected_lang = "ru"
        lang_name = lang_map.get(detected_lang, "русском")
        prompt = f"Отвечай на {lang_name} языке. Будь точным и полезным.\n\n{query}"
        res = await fallback_manager._call_groq(prompt)
        answer = res.get("content", "") if res.get("success") else "[Не удалось получить ответ]"
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

    # ── 1. КЛАССИФИКАЦИЯ ─────────────────────────────────────────────────
    await _emit(on_phase, {
        "type": "phase_start", "phase": "classifier",
        "text": "Discovery: анализ когнитивной сложности запроса..."
    })
    profile = await classifier.analyze(query)
    await save_classification_log(query, profile)
    _dim = next(iter(profile.dimensions), None)
    _dim_name = _dim.value if _dim else "UNKNOWN"
    await _emit(on_phase, {
        "type": "phase_done", "phase": "classifier",
        "tokens": 0, "provider": "local",
        "preview": f"{_dim_name} | depth={profile.required_depth}"
    })

    # ── 2. ВЫБОР СОВЕТА ──────────────────────────────────────────────────
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

    # Строим dict директоров из CouncilSelector
    directors = {}
    for did in selected_ids:
        spec = selector.get_director(did)
        if spec:
            directors[did] = spec

    await _emit(on_phase, {"type": "council_ready", "selected": selected_ids})
    logger.info(f"👥 Совет: {selected_ids}")

    results = {}
    total_cost = 0.0
    errors = []

    # ── 3. SCOUT ─────────────────────────────────────────────────────────
    if "scout" in directors:
        await _emit(on_phase, {"type": "phase_start", "phase": "scout",
                               "text": "Evidence: сканирование источников..."})
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

    # ── 4. ANALYST ───────────────────────────────────────────────────────
    if "analyst" in directors:
        await _emit(on_phase, {"type": "phase_start", "phase": "analyst",
                               "text": "Analysis: выявление паттернов и структуры..."})
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

    # ── 5. ARCHITECT ─────────────────────────────────────────────────────
    if "architect" in directors:
        await _emit(on_phase, {"type": "phase_start", "phase": "architect",
                               "text": "Architecture: проектирование решения..."})
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

    # ── 6. DEVIL'S ADVOCATE ──────────────────────────────────────────────
    criticism = ""
    if "devil" in directors and not is_free:
        await _emit(on_phase, {"type": "phase_start", "phase": "devil",
                               "text": "Red Teaming: поиск рисков и слабых мест..."})
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

    # ── 7. SYNTHESIZER ───────────────────────────────────────────────────
    syn_result = None
    if not is_free and len(results) >= 2:
        await _emit(on_phase, {"type": "phase_start", "phase": "synthesizer",
                               "text": "Quality Gate: проверка согласованности..."})
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
                                   "preview": "Анализ противоречий завершён"})

    # ── 8. CHAIRMAN ──────────────────────────────────────────────────────
    chairman_result = None
    if "chairman" in directors:
        await _emit(on_phase, {"type": "phase_start", "phase": "chairman",
                               "text": "Verdict: синтез финального решения..."})
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

    # ── 9. ФИНАЛЬНЫЙ ОТВЕТ + VETO ────────────────────────────────────────
    final_response = None

    if chairman_result and not chairman_result.get("error") and chairman_result.get("content"):
        final_response = chairman_result["content"]

        if syn_result and syn_result.get("analysis"):
            coherence = syn_result["analysis"].get("coherence_score", 100)
            if coherence < 50:
                logger.warning(f"⚠️ VETO активирован (coherence={coherence}%)")
                final_response = (
                    f"⚠️ [ВНИМАНИЕ: Контроль качества выявил риски]\n\n"
                    f"{final_response}\n\n"
                    f"**АНАЛИЗ КОНТРОЛЕРА:** "
                    f"{syn_result['analysis'].get('meta_recommendation', 'Обнаружены противоречия.')}"
                )

    if not final_response:
        for phase_key in ["analyst", "architect", "scout", "devil"]:
            if phase_key in results:
                content = results[phase_key].get("content", "")
                if content and not content.startswith("[Ошибка"):
                    logger.warning(f"⚠️ Fallback: используется {phase_key}")
                    final_response = f"⚠️ Председатель недоступен — ответ от {phase_key.capitalize()}:\n\n{content}"
                    break

    if not final_response:
        provider_errors = errors or ["Все AI-провайдеры временно недоступны"]
        logger.error(f"❌ Все провайдеры недоступны: {provider_errors}")
        final_response = (
            f"Система временно не может дать ответ.\n\n"
            f"{''.join(f'• {e}' + chr(10) for e in provider_errors)}\n"
            f"Проверьте API ключи в .env или запустите Ollama."
        )

    # ── 10. ФОРМИРОВАНИЕ ОТВЕТА ──────────────────────────────────────────
    deliberation = {}
    for phase, res in results.items():
        if res and isinstance(res, dict):
            deliberation[phase] = {
                "model":   res.get("provider", "unknown"),
                "success": not bool(res.get("error")),
                "preview": str(res.get("content", ""))[:300] + "..." if res.get("content") else "Нет данных",
                "tokens":  res.get("tokens", 0),
                "cost_usd": round(res.get("cost_usd", 0), 4),
            }

    logger.info(f"🏁 Делиберация завершена | cost=${total_cost:.4f} | errors={len(errors)}")

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
                              "description": getattr(v, "description", "Участник совета")}
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
        return {"error": "Добавьте ?q=ваш запрос"}
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
    return {
        "query": query,
        "task_profile": {"dimensions": [d.name for d in profile.dimensions],
                         "urgency": profile.urgency, "depth": profile.required_depth},
        "selected_council": selected,
        "council_details": selector.get_council_details(selected),
        "estimated_cost_usd": round(selector._estimate_cost(selected), 4),
    }
