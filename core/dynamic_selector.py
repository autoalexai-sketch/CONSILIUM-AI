"""
Dynamic Director Selector для Consilium AI
Адаптивный выбор директоров на основе TaskProfile
"""

from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from enum import Enum
import json

from core.ai_fallback import fallback_manager


class DirectorType(Enum):
    SCOUT = "scout"
    ANALYST = "analyst"
    ARCHITECT = "architect"
    CHAIRMAN = "chairman"
    OPERATOR = "operator"
    TRANSLATOR = "translator"
    DEVIL = "devil"


@dataclass
class Director:
    type: DirectorType
    name: str
    expertise: List[str]
    cognitive_profile: Dict[str, Any]
    model: str = "google/gemini-2.0-flash-001"
    cost_per_1k: float = 0.001
    temperature: float = 0.7
    priority_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type.value, "name": self.name, "expertise": self.expertise,
                "cognitive_profile": self.cognitive_profile, "model": self.model,
                "priority_score": round(self.priority_score, 2)}


class DirectorPool:
    def __init__(self):
        self.directors = {
            DirectorType.SCOUT: Director(
                type=DirectorType.SCOUT, name="Scout",
                expertise=["information_gathering", "trend_detection", "source_validation"],
                cognitive_profile={"thinking_style": "exploratory", "time_orientation": "future", "complexity_tolerance": "high"},
                model="perplexity/sonar", cost_per_1k=0.001, temperature=0.3),
            DirectorType.ANALYST: Director(
                type=DirectorType.ANALYST, name="Analyst",
                expertise=["pattern_recognition", "root_cause_analysis", "data_synthesis"],
                cognitive_profile={"thinking_style": "analytical", "time_orientation": "past_present", "complexity_tolerance": "very_high"},
                model="deepseek/deepseek-chat", cost_per_1k=0.0005, temperature=0.4),
            DirectorType.ARCHITECT: Director(
                type=DirectorType.ARCHITECT, name="Architect",
                expertise=["system_design", "solution_modeling", "constraint_optimization"],
                cognitive_profile={"thinking_style": "systemic", "time_orientation": "future", "complexity_tolerance": "high"},
                model="anthropic/claude-3.5-sonnet", cost_per_1k=0.003, temperature=0.5),
            DirectorType.CHAIRMAN: Director(
                type=DirectorType.CHAIRMAN, name="Chairman",
                expertise=["decision_synthesis", "stakeholder_alignment", "risk_arbitration"],
                cognitive_profile={"thinking_style": "strategic", "time_orientation": "present", "complexity_tolerance": "medium"},
                model="openai/gpt-4o", cost_per_1k=0.005, temperature=0.6),
            DirectorType.OPERATOR: Director(
                type=DirectorType.OPERATOR, name="Operator",
                expertise=["implementation", "execution_planning", "resource_coordination"],
                cognitive_profile={"thinking_style": "pragmatic", "time_orientation": "present", "complexity_tolerance": "low"},
                model="google/gemini-2.0-flash-001", cost_per_1k=0.00035, temperature=0.4),
            DirectorType.TRANSLATOR: Director(
                type=DirectorType.TRANSLATOR, name="Translator",
                expertise=["domain_bridge", "communication", "concept_mapping"],
                cognitive_profile={"thinking_style": "integrative", "time_orientation": "neutral", "complexity_tolerance": "medium"},
                model="google/gemini-2.0-flash-001", cost_per_1k=0.00035, temperature=0.5),
            DirectorType.DEVIL: Director(
                type=DirectorType.DEVIL, name="Devil's Advocate",
                expertise=["critical_thinking", "risk_identification", "bias_detection", "contrarian_analysis"],
                cognitive_profile={"thinking_style": "skeptical", "time_orientation": "neutral", "complexity_tolerance": "very_high"},
                model="deepseek/deepseek-r1:free", cost_per_1k=0.0005, temperature=0.7),
        }

    def get(self, director_type: DirectorType) -> Optional[Director]:
        return self.directors.get(director_type)

    def get_by_string(self, type_str: str) -> Optional[Director]:
        try:
            return self.directors.get(DirectorType(type_str.lower()))
        except ValueError:
            return None


class DynamicSelector:
    CORE_DIRECTORS = [DirectorType.ANALYST, DirectorType.ARCHITECT, DirectorType.CHAIRMAN]
    MAX_DIRECTORS = 6

    def __init__(self):
        self.pool = DirectorPool()
        from core.cognitive_classifier import CognitiveClassifier
        self.classifier = CognitiveClassifier()

    def _get_dimension_names(self, task_profile) -> Set[str]:
        dimensions = getattr(task_profile, 'dimensions', set())
        return {d.name for d in dimensions if hasattr(d, 'name')}

    def select(self, task_profile, user_credits: int = 15, force_devil: bool = False) -> List[Director]:
        selected = []
        dim_names = self._get_dimension_names(task_profile)
        urgency = getattr(task_profile, 'urgency', 0)
        ambiguity = getattr(task_profile, 'ambiguity_score', 0)
        depth = getattr(task_profile, 'required_depth', 5)

        for core_type in self.CORE_DIRECTORS:
            d = self.pool.get(core_type)
            if d:
                d.priority_score = 1.0
                selected.append(d)

        if 'FUTURE' in dim_names or ambiguity > 0.6:
            scout = self.pool.get(DirectorType.SCOUT)
            if scout and scout not in selected:
                scout.priority_score = 0.9
                selected.append(scout)

        if 'PROCEDURAL' in dim_names or depth <= 3:
            op = self.pool.get(DirectorType.OPERATOR)
            if op and op not in selected:
                op.priority_score = 0.85
                selected.append(op)

        if 'COMPLICATED' in dim_names:
            translator = self.pool.get(DirectorType.TRANSLATOR)
            if translator and translator not in selected:
                translator.priority_score = 0.8
                selected.append(translator)

        needs_devil = (force_devil or depth >= 6 or 'COMPLEX' in dim_names
                       or 'CHAOTIC' in dim_names or
                       (len(selected) >= 4 and ambiguity > 0.5))
        if needs_devil and user_credits >= 3:
            devil = self.pool.get(DirectorType.DEVIL)
            if devil and devil not in selected:
                devil.priority_score = 0.75
                selected.append(devil)

        selected = sorted(selected, key=lambda x: x.priority_score, reverse=True)
        return selected[:self.MAX_DIRECTORS]

    def select_by_strings(self, task_profile, user_credits: int = 15) -> List[str]:
        return [d.type.value for d in self.select(task_profile, user_credits)]

    async def create_council(self, user_input: str, user_credits: int = 15) -> Dict[str, Any]:
        task_profile = await self.classifier.analyze(user_input)
        selected = self.select(task_profile, user_credits)
        dim_names = self._get_dimension_names(task_profile)
        return {
            "task_profile": {
                "dimensions": list(dim_names),
                "urgency": getattr(task_profile, 'urgency', 0),
                "emotional_load": getattr(task_profile, 'emotional_load', 0),
                "language": getattr(task_profile, 'suggested_language', 'unknown'),
                "confidence": getattr(task_profile, 'confidence_score', 0),
                "depth": getattr(task_profile, 'required_depth', 5),
            },
            "council_size": len(selected),
            "directors": [d.to_dict() for d in selected],
            "primary_director": selected[0].type.value if selected else None,
            "fallback_ready": fallback_manager.gemini_available,
        }


dynamic_selector = DynamicSelector()


def get_director_prompt(director_type: str, task_context: Dict[str, Any]) -> str:
    prompts = {
        "scout":     "Твоя роль — Scout. Собери факты и источники. Не делай выводов.",
        "analyst":   "Твоя роль — Analyst. Проведи глубокий анализ. Выяви паттерны и причины.",
        "architect": "Твоя роль — Architect. Спроектируй оптимальное решение.",
        "chairman":  "Твоя роль — Chairman. Синтезируй предложения и прими решение.",
        "operator":  "Твоя роль — Operator. Разработай конкретный план действий.",
        "translator": "Твоя роль — Translator. Устрани барьеры понимания.",
        "devil":     "Твоя роль — Devil's Advocate. Найди слабые места и риски. Будь конструктивно скептичен.",
    }
    base = prompts.get(director_type, "Ты директор Consilium AI.")
    return f"{base}\n\nКонтекст:\n{json.dumps(task_context, ensure_ascii=False, indent=2)}"
