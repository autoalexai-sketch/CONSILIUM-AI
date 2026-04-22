"""
Deliberation Engine для Consilium AI
Трехуровневый fallback: OpenRouter → Gemini → Ollama
"""

import asyncio
import os
import aiohttp
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import json

from core.dynamic_selector import dynamic_selector, DirectorType, get_director_prompt
from core.ai_fallback import fallback_manager


class DeliberationPhase(Enum):
    SCOUT = "scout"
    ANALYSIS = "analysis"
    GENERATION = "generation"
    TRIAL = "trial"
    SYNTHESIS = "synthesis"


@dataclass
class PhaseResult:
    phase: DeliberationPhase
    director_type: str
    content: str
    tokens_used: int = 0
    execution_time_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None


@dataclass
class DeliberationResult:
    user_input: str
    task_profile: Dict[str, Any]
    selected_directors: List[str]
    phases: List[PhaseResult] = field(default_factory=list)
    final_decision: Optional[str] = None
    total_tokens: int = 0
    total_time_ms: float = 0.0
    fallback_used: bool = False


class DeliberationEngine:
    PHASE_DIRECTOR_MAP = {
        DeliberationPhase.SCOUT:      DirectorType.SCOUT,
        DeliberationPhase.ANALYSIS:   DirectorType.ANALYST,
        DeliberationPhase.GENERATION: DirectorType.ARCHITECT,
        DeliberationPhase.TRIAL:      DirectorType.OPERATOR,
        DeliberationPhase.SYNTHESIS:  DirectorType.CHAIRMAN,
    }
    PHASE_MODELS = {
        DeliberationPhase.SCOUT:      "openai/gpt-4o-mini",
        DeliberationPhase.ANALYSIS:   "anthropic/claude-3.5-sonnet",
        DeliberationPhase.GENERATION: "openai/gpt-4o",
        DeliberationPhase.TRIAL:      "google/gemini-1.5-flash",
        DeliberationPhase.SYNTHESIS:  "anthropic/claude-3.5-sonnet",
    }

    def __init__(self):
        self.history: List[DeliberationResult] = []
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        self.ollama_available = self._check_ollama()

    def _check_ollama(self) -> bool:
        try:
            import urllib.request
            urllib.request.urlopen("http://localhost:11434", timeout=2)
            return True
        except Exception:
            return False

    async def deliberate(self, user_input: str,
                          skip_phases: Optional[List[DeliberationPhase]] = None) -> DeliberationResult:
        skip_phases = skip_phases or []
        start_time = asyncio.get_event_loop().time()
        council = await dynamic_selector.create_council(user_input)
        task_profile = council["task_profile"]
        directors = council["directors"]
        director_types = {d["type"] for d in directors}

        print(f"\n🔷 Consilium AI: Начало делиберации")
        print(f"   Запрос: {user_input[:60]}...")
        print(f"   Совет: {len(directors)} директоров")

        phases_results: List[PhaseResult] = []
        phase_context = {"user_input": user_input, "task_profile": task_profile}
        fallback_used = False

        for phase in DeliberationPhase:
            if phase in skip_phases:
                continue
            required_director = self.PHASE_DIRECTOR_MAP[phase]
            if required_director.value not in director_types:
                print(f"   ⏭️ Фаза {phase.value}: пропущена")
                continue

            phase_result = await self._execute_phase_real(phase, phase_context, phases_results)
            phases_results.append(phase_result)
            phase_context[f"{phase.value}_result"] = phase_result.content
            if not phase_result.success:
                fallback_used = True
            status = "✅" if phase_result.success else "⚠️"
            print(f"   {status} Фаза {phase.value}: {len(phase_result.content)} символов")

        final_decision = None
        if phases_results and phases_results[-1].phase == DeliberationPhase.SYNTHESIS:
            final_decision = phases_results[-1].content

        total_time = (asyncio.get_event_loop().time() - start_time) * 1000
        total_tokens = sum(p.tokens_used for p in phases_results)

        result = DeliberationResult(
            user_input=user_input, task_profile=task_profile,
            selected_directors=[d["type"] for d in directors],
            phases=phases_results, final_decision=final_decision,
            total_tokens=total_tokens, total_time_ms=total_time, fallback_used=fallback_used)
        self.history.append(result)
        print(f"   🏁 Делиберация завершена: {len(phases_results)} фаз, {total_time:.0f}ms")
        return result

    async def _execute_phase_real(self, phase: DeliberationPhase, context: Dict,
                                    previous_results: List[PhaseResult]) -> PhaseResult:
        director_type = self.PHASE_DIRECTOR_MAP[phase].value
        phase_start = asyncio.get_event_loop().time()
        phase_context = {
            "phase": phase.value, "context": context,
            "previous_phases": [{"phase": p.phase.value, "summary": p.content[:100] + "..."}
                                 for p in previous_results[-1:]]
        }
        prompt = get_director_prompt(director_type, phase_context)
        content, tokens, success, error = await self._real_ai_call(director_type, prompt, phase)
        execution_time = (asyncio.get_event_loop().time() - phase_start) * 1000
        return PhaseResult(phase, director_type, content, tokens, execution_time, success, error)

    async def _real_ai_call(self, director_type: str, prompt: str, phase: DeliberationPhase) -> tuple:
        if self.openrouter_key:
            try:
                content, tokens = await self._call_openrouter(prompt, self.PHASE_MODELS[phase], director_type)
                return content, tokens, True, None
            except Exception as e:
                print(f"   ⚠️ OpenRouter: {str(e)[:50]}")

        try:
            content = await self._call_gemini_with_retry(prompt, director_type)
            return content, len(prompt) // 4 + len(content) // 4, True, None
        except Exception as e:
            print(f"   ⚠️ Gemini: {str(e)[:50]}")

        try:
            print("   🔄 Переключение на Ollama...")
            content = await self._call_ollama(prompt, director_type)
            print("   ✅ Ollama успешно")
            return content, len(prompt) // 4 + len(content) // 4, True, None
        except Exception as e:
            print(f"   ⚠️ Ollama: {str(e)[:50]}")

        error_msg = "All providers failed"
        return f"[ERROR: {error_msg}]", 0, False, error_msg

    async def _call_openrouter(self, prompt: str, model: str, director_type: str) -> tuple:
        headers = {"Authorization": f"Bearer {self.openrouter_key}",
                   "Content-Type": "application/json",
                   "HTTP-Referer": "http://localhost:8000", "X-Title": "Consilium AI"}
        payload = {"model": model,
                   "messages": [{"role": "system", "content": f"Ты — {director_type} в Consilium AI."},
                                 {"role": "user", "content": prompt}],
                   "temperature": 0.7, "max_tokens": 2000}
        async with aiohttp.ClientSession() as session:
            async with session.post("https://openrouter.ai/api/v1/chat/completions",
                                    headers=headers, json=payload,
                                    timeout=aiohttp.ClientTimeout(total=45)) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")
                data = await response.json()
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("total_tokens", len(prompt) // 4)
                return content, tokens

    async def _call_gemini_with_retry(self, prompt: str, director_type: str, max_retries: int = 2) -> str:
        for attempt in range(max_retries):
            try:
                if not fallback_manager.gemini_available:
                    raise Exception("Gemini недоступен")
                full_prompt = f"Ты — {director_type} в Consilium AI.\n\n{prompt}"
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None, lambda: fallback_manager.client.models.generate_content(
                        model="gemini-2.0-flash", contents=full_prompt))
                return response.text
            except Exception as e:
                if "429" in str(e) and attempt < max_retries - 1:
                    await asyncio.sleep(20 * (2 ** attempt))
                else:
                    raise

    async def _call_ollama(self, prompt: str, director_type: str, model: str = "llama3:8b") -> str:
        async with aiohttp.ClientSession() as session:
            payload = {"model": model,
                       "prompt": f"Ты — {director_type} в Consilium AI.\n\n{prompt}",
                       "stream": False, "options": {"temperature": 0.7, "num_predict": 2000}}
            async with session.post("http://localhost:11434/api/generate",
                                    json=payload, timeout=aiohttp.ClientTimeout(total=600)) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("response", "")
                raise Exception(f"Ollama HTTP {response.status}")

    def export_result(self, result: DeliberationResult, format: str = "json") -> str:
        if format == "json":
            return json.dumps({
                "user_input": result.user_input, "final_decision": result.final_decision,
                "phases": [{"phase": p.phase.value, "director": p.director_type,
                             "content": p.content[:500]} for p in result.phases],
                "metrics": {"total_time_ms": result.total_time_ms,
                             "total_tokens": result.total_tokens,
                             "fallback_used": result.fallback_used}
            }, ensure_ascii=False, indent=2)
        return ""


deliberation_engine = DeliberationEngine()


async def quick_deliberate(user_input: str) -> str:
    result = await deliberation_engine.deliberate(user_input)
    return result.final_decision or "Решение не принято"
