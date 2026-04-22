"""
Dynamic Council Selector for Consilium AI
Выбирает оптимальный состав директоров под конкретную задачу
"""

import dataclasses
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from enum import Enum

from .cognitive_classifier import TaskProfile, CognitiveDimension


@dataclass
class DirectorSpec:
    id: str
    model: str
    cost_per_1k_in: float
    cost_per_1k_out: float
    avg_tokens_in: int
    avg_tokens_out: int
    latency_ms: int
    strengths: List[str]
    handles: List[CognitiveDimension]
    emotional_profile: str
    priority: int
    description: str

    def estimate_cost(self) -> float:
        in_cost = (self.avg_tokens_in / 1000) * self.cost_per_1k_in
        out_cost = (self.avg_tokens_out / 1000) * self.cost_per_1k_out
        return in_cost + out_cost


class CouncilSelector:
    DIRECTORS = {
        "scout": DirectorSpec(
            id="scout", model="perplexity/sonar",
            cost_per_1k_in=0.0001, cost_per_1k_out=0.0001,
            avg_tokens_in=500, avg_tokens_out=1000, latency_ms=3000,
            strengths=["факты", "поиск", "актуальность"],
            handles=[CognitiveDimension.FACTUAL, CognitiveDimension.PRESENT],
            emotional_profile="curious", priority=1,
            description="Ищет актуальные факты и данные"),
        "analyst": DirectorSpec(
            id="analyst", model="google/gemini-2.0-flash-001",
            cost_per_1k_in=0.0001, cost_per_1k_out=0.0001,
            avg_tokens_in=800, avg_tokens_out=1200, latency_ms=2000,
            strengths=["анализ", "структура", "риски"],
            handles=[CognitiveDimension.COMPLEX, CognitiveDimension.COMPLICATED,
                     CognitiveDimension.FACTUAL, CognitiveDimension.PAST],
            emotional_profile="detached", priority=1,
            description="Анализирует цифры, риски, варианты"),
        "architect": DirectorSpec(
            id="architect", model="google/gemini-2.0-flash-001",
            cost_per_1k_in=0.0001, cost_per_1k_out=0.0004,
            avg_tokens_in=1000, avg_tokens_out=1500, latency_ms=2500,
            strengths=["планирование", "системы", "модули"],
            handles=[CognitiveDimension.CREATIVE, CognitiveDimension.FUTURE,
                     CognitiveDimension.PROCEDURAL, CognitiveDimension.COMPLEX],
            emotional_profile="caring", priority=1,
            description="Строит пошаговые планы и системы"),
        "chairman": DirectorSpec(
            id="chairman", model="google/gemini-2.0-flash-001",
            cost_per_1k_in=0.0001, cost_per_1k_out=0.0004,
            avg_tokens_in=2000, avg_tokens_out=1000, latency_ms=4000,
            strengths=["синтез", "решения", "стратегия"],
            handles=[CognitiveDimension.ETHICAL, CognitiveDimension.COMPLEX,
                     CognitiveDimension.CHAOTIC],
            emotional_profile="confident", priority=1,
            description="Синтезирует всё в единое решение"),
        "operator": DirectorSpec(
            id="operator", model="deepseek/deepseek-chat",
            cost_per_1k_in=0.0001, cost_per_1k_out=0.0001,
            avg_tokens_in=1500, avg_tokens_out=800, latency_ms=1500,
            strengths=["исполнение", "план", "чек-листы"],
            handles=[CognitiveDimension.PROCEDURAL, CognitiveDimension.COMPLICATED,
                     CognitiveDimension.FUTURE],
            emotional_profile="pragmatic", priority=2,
            description="Превращает решение в действия"),
        "translator": DirectorSpec(
            id="translator", model="google/gemini-2.0-flash-001",
            cost_per_1k_in=0.0001, cost_per_1k_out=0.0004,
            avg_tokens_in=1000, avg_tokens_out=1000, latency_ms=1000,
            strengths=["перевод", "формат", "адаптация"],
            handles=[CognitiveDimension.COMPLICATED],
            emotional_profile="neutral", priority=3,
            description="Адаптирует формат под аудиторию"),
        "creative": DirectorSpec(
            id="creative", model="anthropic/claude-3.5-sonnet",
            cost_per_1k_in=0.003, cost_per_1k_out=0.015,
            avg_tokens_in=600, avg_tokens_out=1000, latency_ms=3000,
            strengths=["divergent", "metaphorical", "visual", "brainstorming"],
            handles=[CognitiveDimension.CREATIVE, CognitiveDimension.CHAOTIC],
            emotional_profile="inspiring", priority=3,
            description="Генерирует креативные идеи и решения"),
        "devil": DirectorSpec(
            id="devil", model="meta-llama/llama-3.1-70b-instruct",
            cost_per_1k_in=0.0005, cost_per_1k_out=0.001,
            avg_tokens_in=800, avg_tokens_out=800, latency_ms=2500,
            strengths=["contrarian", "risk_detection", "assumption_testing"],
            handles=[CognitiveDimension.COMPLEX, CognitiveDimension.ETHICAL],
            emotional_profile="provocative", priority=3,
            description="Ищет слабые места и риски"),
        "ethics": DirectorSpec(
            id="ethics", model="anthropic/claude-3-opus",
            cost_per_1k_in=0.015, cost_per_1k_out=0.075,
            avg_tokens_in=700, avg_tokens_out=1000, latency_ms=4000,
            strengths=["values_based", "long_term", "stakeholder", "consequences"],
            handles=[CognitiveDimension.ETHICAL, CognitiveDimension.COMPLEX],
            emotional_profile="principled", priority=3,
            description="Оценивает этические последствия"),
        "historian": DirectorSpec(
            id="historian", model="google/gemini-1.5-flash",
            cost_per_1k_in=0.0001, cost_per_1k_out=0.0004,
            avg_tokens_in=300, avg_tokens_out=500, latency_ms=1000,
            strengths=["pattern_recognition", "continuity", "context_aware"],
            handles=[CognitiveDimension.PAST, CognitiveDimension.FACTUAL],
            emotional_profile="wise", priority=2,
            description="Использует историю пользователя для контекста"),
    }

    FREE_MODEL_OVERRIDES: Dict[str, str] = {
        "scout": "llama3:8b", "analyst": "llama3:8b", "architect": "llama3:8b",
        "chairman": "llama3:8b", "operator": "llama3:8b", "creative": "llama3:8b",
        "translator": "llama3:8b", "devil": "llama3:8b",
        "ethics": "llama3:8b", "historian": "llama3:8b",
    }

    def __init__(self, max_budget_usd: float = 0.15, is_free_plan: bool = False):
        self.max_budget = max_budget_usd
        self.is_free_plan = is_free_plan
        self.core_council = ["scout", "analyst", "architect", "chairman"]
        self.free_model_overrides: Dict[str, str] = (
            self.FREE_MODEL_OVERRIDES if is_free_plan else {})
        if is_free_plan:
            print("🆓 Free plan активен: все директора → Ollama (llama3:8b)")

    def get_director(self, director_id: str) -> Optional["DirectorSpec"]:
        spec = self.DIRECTORS.get(director_id)
        if spec is None:
            return None
        if self.free_model_overrides and director_id in self.free_model_overrides:
            return dataclasses.replace(spec, model=self.free_model_overrides[director_id])
        return spec

    def select_council(self, profile: TaskProfile, user_credits: int,
                       user_history_count: int = 0,
                       explicit_keywords: Optional[List[str]] = None) -> List[str]:
        budget_usd = min(user_credits * 0.01, self.max_budget)
        keywords = set(explicit_keywords or [])
        selected = list(self.core_council)

        if self._needs_operator(profile, keywords):  selected.append("operator")
        if self._needs_translator(profile):           selected.append("translator")
        if self._needs_creative(profile, keywords):   selected.append("creative")
        if self._needs_devil(profile):                selected.append("devil")
        if self._needs_ethics(profile):               selected.append("ethics")
        if user_history_count > 2:                    selected.append("historian")

        selected = list(dict.fromkeys(selected))
        selected = self._optimize_for_budget(selected, budget_usd, profile)
        return selected

    def _needs_operator(self, profile: TaskProfile, keywords: Set[str]) -> bool:
        if CognitiveDimension.PROCEDURAL in profile.dimensions and profile.urgency > 0.6:
            return True
        if CognitiveDimension.CHAOTIC in profile.dimensions:
            return True
        action_kw = {"терміново","urgent","asap","зараз","now","checklist","чеклист","actions","дії"}
        return bool(keywords & action_kw)

    def _needs_translator(self, profile: TaskProfile) -> bool:
        if profile.emotional_load > 0.5: return True
        if profile.ambiguity_score > 0.6: return True
        if CognitiveDimension.COMPLICATED in profile.dimensions and profile.required_depth > 6:
            return True
        return False

    def _needs_creative(self, profile: TaskProfile, keywords: Set[str]) -> bool:
        if CognitiveDimension.CREATIVE in profile.dimensions: return True
        if profile.ambiguity_score > 0.7: return True
        creative_kw = {"придумай","назва","name","ідея","idea","creative","brainstorm","варіанти","options"}
        return bool(keywords & creative_kw)

    def _needs_devil(self, profile: TaskProfile) -> bool:
        if CognitiveDimension.COMPLEX in profile.dimensions: return True
        if profile.required_depth > 7 and profile.emotional_load > 0.4: return True
        return False

    def _needs_ethics(self, profile: TaskProfile) -> bool:
        if CognitiveDimension.ETHICAL in profile.dimensions: return True
        ethical_domains = {"employment","legal","health","hr"}
        return any(d in ethical_domains for d in profile.domain_hints.keys())

    def _optimize_for_budget(self, selected: List[str], budget: float,
                              profile: TaskProfile) -> List[str]:
        core_cost = self._estimate_cost(self.core_council)
        if core_cost > budget:
            return ["scout", "analyst", "architect"]

        if self._estimate_cost(selected) <= budget:
            return selected

        result = list(self.core_council)
        remaining = budget - self._estimate_cost(result)
        additional = [d for d in selected if d not in self.core_council]

        def relevance_score(did: str) -> float:
            spec = self.get_director(did)
            if spec is None: return 999.0
            score = spec.priority * 10
            for dim in profile.dimensions:
                if dim in spec.handles: score -= 5
            cost = spec.estimate_cost()
            if cost > 0: score -= (0.05 / cost)
            return score

        additional.sort(key=relevance_score)
        for did in additional:
            cost = self._estimate_cost([did])
            if remaining >= cost:
                result.append(did)
                remaining -= cost
        return result

    def _estimate_cost(self, director_ids: List[str]) -> float:
        return sum(self.DIRECTORS[did].estimate_cost()
                   for did in director_ids if did in self.DIRECTORS)

    def get_council_details(self, director_ids: List[str]) -> List[Dict]:
        result = []
        for did in director_ids:
            spec = self.get_director(did)
            if spec is None: continue
            result.append({"id": did, "model": spec.model,
                           "description": spec.description,
                           "cost_estimate": round(spec.estimate_cost(), 4),
                           "latency_ms": spec.latency_ms,
                           "emotional_profile": spec.emotional_profile,
                           "is_free_plan": self.is_free_plan})
        return result

    def explain_selection(self, profile: TaskProfile, selected: List[str]) -> str:
        lines = [f"🎯 Состав Совета (бюджет: ~${self._estimate_cost(selected):.3f})", ""]
        for did in selected:
            spec = self.get_director(did)
            if spec is None: continue
            lines.append(f"**{did.upper()}** — {spec.description}")
            reasons = []
            if did in self.core_council: reasons.append("базовая роль")
            if any(d in profile.dimensions for d in spec.handles): reasons.append("релевантен задаче")
            if profile.urgency > 0.6 and spec.priority == 2: reasons.append("высокая срочность")
            if reasons: lines.append(f"  Почему: {', '.join(reasons)}")
            lines.append("")
        return "\n".join(lines)
