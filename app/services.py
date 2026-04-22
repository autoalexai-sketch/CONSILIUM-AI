"""
app/services.py — Общие экземпляры AI-сервисов.
"""

from loguru import logger

from core.ai_fallback import fallback_manager, AIFallbackManager
from core.cognitive_classifier import CognitiveClassifier
from core.openrouter_client import OpenRouterClient
from app.config import settings

# Тест провайдеров при старте
_fb_test = AIFallbackManager()
logger.info(
    f"✅ Fallback: Claude={_fb_test.claude_available}, "
    f"Gemini={_fb_test.gemini_available}, "
    f"Ollama={_fb_test.ollama_available}"
)

# Клиент OpenRouter
openrouter = OpenRouterClient(settings.OPENROUTER_API_KEY or "")
logger.info("✅ OpenRouter client initialized")

# Классификатор задач
classifier = CognitiveClassifier()
logger.info("✅ Cognitive classifier initialized")

__all__ = ["openrouter", "classifier", "fallback_manager"]
