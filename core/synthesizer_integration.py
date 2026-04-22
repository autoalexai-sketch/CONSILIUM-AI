"""
Synthesizer Phase — Фаза 4 делиберации.
Анализирует противоречия совета, проверяет логическую согласованность.
"""

import json
import time
import re
from typing import Dict, Any

from core.ai_fallback import fallback_manager
from core.cognitive_classifier import TaskProfile


class SynthesizerPhase:
    """ФАЗА 4: Synthesizer анализирует противоречия совета"""

    SYSTEM_PROMPT = """You are Claude Synthesizer - Meta-Cognitive Council Member in Consilium AI.

YOUR ROLE: Analyze contradictions, surface assumptions, verify logic coherence. Audit and veto.

RESPONSE FORMAT (STRICT JSON):
{
  "coherence_score": 0-100,
  "contradictions": [{"director_a": "Scout", "director_b": "Architect",
    "statement_a": "...", "statement_b": "...", "level": "HIGH|MEDIUM|LOW", "resolution": "..."}],
  "assumptions": [{"director": "name", "assumption": "...",
    "validation_level": "verified|plausible|risky", "impact": "high|medium|low"}],
  "logical_gaps": ["gap1", "gap2"],
  "risks": [{"risk": "...", "probability": "high|medium|low", "impact": "high|medium|low"}],
  "clarifying_questions": ["Q1", "Q2"],
  "meta_recommendation": "Финальный вердикт и рекомендации"
}"""

    @staticmethod
    async def execute(query: str, phase_results: Dict[str, Dict[str, Any]],
                      task_profile: TaskProfile, language: str = "pl") -> Dict[str, Any]:
        start_time = time.time()
        council_context = SynthesizerPhase._prepare_context(phase_results)
        user_prompt = SynthesizerPhase._build_user_prompt(query, council_context, task_profile, language)

        print("🧠 [SYNTHESIZER] Анализирую противоречия совета...")
        result = await fallback_manager.call_claude_for_synthesis(
            SynthesizerPhase.SYSTEM_PROMPT, user_prompt)
        elapsed = time.time() - start_time

        if not result["success"]:
            print("   ⚠️ Synthesizer failed, using empty analysis")
            return {"success": False, "content": "[Синтез недоступен]",
                    "provider": result.get("provider", "error"),
                    "tokens": 0, "cost_usd": 0.0, "processing_time_ms": elapsed * 1000}

        try:
            json_match = re.search(r'\{[\s\S]*\}', result["content"])
            analysis_data = json.loads(json_match.group(0)) if json_match else {}
        except Exception:
            analysis_data = {}

        print(f"   ✅ Синтез готов ({result.get('tokens', 0)} токенов, {result.get('provider')})")
        print(f"      Coherence: {analysis_data.get('coherence_score', 0)}")
        print(f"      Contradictions: {len(analysis_data.get('contradictions', []))}")

        return {"success": True, "content": result["content"], "analysis": analysis_data,
                "provider": result["provider"], "tokens": result.get("tokens", 0),
                "cost_usd": result.get("cost_usd", 0.0), "processing_time_ms": elapsed * 1000}

    @staticmethod
    def _prepare_context(phase_results: Dict[str, Dict[str, Any]]) -> str:
        parts = []
        for phase_name, result in phase_results.items():
            if result.get("success"):
                content = result.get("content", "")[:400]
                parts.append(f"## {phase_name.upper()}\n{content}")
        return "\n\n".join(parts)

    @staticmethod
    def _build_user_prompt(query: str, council_context: str,
                            task_profile: TaskProfile, language: str) -> str:
        urgency_note = ""
        if task_profile.urgency > 0.8:
            urgency_note = "\n⚠️ URGENCY: Time-critical. Focus on core contradictions only."
        emotional_note = ""
        if task_profile.emotional_load > 0.6:
            emotional_note = "\n💭 EMOTIONAL: User is stressed. Be careful with assumptions."

        return f"""User Query: "{query}"
{urgency_note}{emotional_note}

COUNCIL DELIBERATION:
{council_context}

TASKS:
1. Find ALL contradictions (be specific)
2. Surface hidden assumptions
3. Identify logical gaps
4. Score coherence (0-100)
5. List key risks
6. Ask 3-5 clarifying questions
7. Give meta-recommendation

RESPOND ONLY WITH VALID JSON."""
