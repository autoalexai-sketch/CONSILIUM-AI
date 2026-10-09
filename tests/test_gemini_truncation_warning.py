"""
tests/test_gemini_truncation_warning.py — обрезка промпта для Gemini видна в логах.

Gemini (уровень 5) получает prompt[:8000]. Раньше обрезка была молчаливой.
Теперь при len(prompt) > 8000 пишется logger.warning с исходной длиной и лимитом.
Сама обрезка не меняется: в Gemini по-прежнему уходят первые 8000 символов.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from loguru import logger

from core.ai_fallback import AIFallbackManager
from core.openrouter_client import DirectorResponse, DirectorSpec

SPEC = DirectorSpec(id="analyst", model="openai/gpt-4o",
                    cost_per_1k_in=0.0, cost_per_1k_out=0.0)
OPENROUTER_400 = DirectorResponse(director_id="analyst", model=SPEC.model,
                                  content="", error="HTTP 400: Bad Request")


async def _openrouter_400(*args, **kwargs):
    return OPENROUTER_400


@pytest.fixture
def manager():
    with patch.object(AIFallbackManager, "_check_ollama", return_value=False):
        m = AIFallbackManager()
    m.groq_available = False
    m.bedrock_available = False
    m.deepseek_available = False
    m.ollama_available = False
    m.gemini_available = True
    m.client = MagicMock()
    m.client.models.generate_content.return_value = SimpleNamespace(text="ok")
    return m


@pytest.fixture
def warnings():
    """Собирает WARNING-сообщения loguru (caplog их не видит)."""
    messages = []
    sink_id = logger.add(lambda msg: messages.append(msg.record["message"]),
                         level="WARNING")
    yield messages
    logger.remove(sink_id)


async def test_long_prompt_truncation_is_logged(manager, warnings):
    prompt = "x" * 9000

    result = await manager.call_with_backup(
        _openrouter_400, SPEC, [{"role": "user", "content": prompt}])

    assert result["provider"] == "gemini"
    gemini_warnings = [m for m in warnings if "Gemini" in m]
    assert len(gemini_warnings) == 1
    assert "9000" in gemini_warnings[0]   # исходная длина
    assert "8000" in gemini_warnings[0]   # лимит


async def test_truncation_itself_is_unchanged(manager, warnings):
    prompt = "a" * 8000 + "b" * 1000

    await manager.call_with_backup(
        _openrouter_400, SPEC, [{"role": "user", "content": prompt}])

    sent = manager.client.models.generate_content.call_args.kwargs["contents"]
    assert sent == "a" * 8000


async def test_short_prompt_no_warning(manager, warnings):
    prompt = "x" * 8000  # ровно на лимите — не обрезается

    await manager.call_with_backup(
        _openrouter_400, SPEC, [{"role": "user", "content": prompt}])

    assert not [m for m in warnings if "Gemini" in m]
