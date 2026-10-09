"""
tests/test_ai_fallback.py — цепочка провайдеров AIFallbackManager.

Сценарий: OpenRouter (уровень 4) отвечает HTTP 400 → запрос уходит в Gemini (уровень 5).

Важно: при 400 OpenRouterClient.call_director НЕ бросает исключение,
а возвращает DirectorResponse(error="HTTP 400: ..."). Тесты моделируют
именно этот контракт, а не raise.

Сеть не используется: Groq/Bedrock/DeepSeek отключены флагами,
Gemini и Ollama замоканы.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.ai_fallback import AIFallbackManager
from core.openrouter_client import DirectorResponse, DirectorSpec, OpenRouterClient

PROMPT = "Оцени риски выхода на рынок Польши"
SPEC = DirectorSpec(
    id="analyst",
    model="openai/gpt-4o",  # содержит "/" → идёт по облачной цепочке, не в Ollama
    cost_per_1k_in=0.0,
    cost_per_1k_out=0.0,
)
MESSAGES = [{"role": "user", "content": PROMPT}]
OPENROUTER_400 = DirectorResponse(
    director_id="analyst",
    model=SPEC.model,
    content="",
    error="HTTP 400: Invalid request: max_tokens exceeds context",
)


@pytest.fixture
def manager():
    """Менеджер с отключёнными уровнями 1–3 и замоканными Gemini/Ollama."""
    # _check_ollama ходит в сеть (urlopen) — глушим на время __init__
    with patch.object(AIFallbackManager, "_check_ollama", return_value=False):
        m = AIFallbackManager()

    # Уровни 1–3 выключены: проверяем изолированно переход OpenRouter → Gemini
    m.groq_available = False
    m.bedrock_available = False
    m.deepseek_available = False

    # Уровень 5: Gemini (синхронный SDK-вызов)
    m.gemini_available = True
    m.client = MagicMock()
    m.client.models.generate_content.return_value = SimpleNamespace(text="gemini answer")

    # Уровень 6: Ollama — доступна, но вызываться не должна
    m.ollama_available = True
    m.call_ollama_direct = AsyncMock(
        return_value={"success": True, "content": "ollama answer", "provider": "ollama"}
    )
    return m


async def test_openrouter_400_falls_back_to_gemini(manager):
    openrouter = AsyncMock(return_value=OPENROUTER_400)

    result = await manager.call_with_backup(openrouter, SPEC, MESSAGES)

    # OpenRouter был вызван ровно один раз с исходными аргументами
    openrouter.assert_awaited_once_with(SPEC, MESSAGES)

    # Ответ пришёл от Gemini
    assert result["success"] is True
    assert result["provider"] == "gemini"
    assert result["content"] == "gemini answer"
    assert manager.last_provider == "gemini"

    # Gemini получил тот же промпт, что ушёл в OpenRouter
    manager.client.models.generate_content.assert_called_once()
    kwargs = manager.client.models.generate_content.call_args.kwargs
    assert kwargs["contents"] == PROMPT

    # До уровня 6 не дошли
    manager.call_ollama_direct.assert_not_awaited()


async def test_openrouter_400_via_real_client_falls_back_to_gemini(manager):
    """То же, но через настоящий OpenRouterClient.call_director:
    подменяется только HTTP-сессия aiohttp, разбор 400 — боевой код."""

    class _Fake400Response:
        status = 400
        headers = {}

        async def json(self):
            return {"error": {"message": "Bad Request", "code": 400}}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    client = OpenRouterClient(api_key="test-key")
    client.session = MagicMock()
    client.session.post.return_value = _Fake400Response()

    result = await manager.call_with_backup(client.call_director, SPEC, MESSAGES)

    client.session.post.assert_called_once()
    assert result["provider"] == "gemini"
    assert result["content"] == "gemini answer"
    manager.call_ollama_direct.assert_not_awaited()


async def test_openrouter_success_does_not_call_gemini(manager):
    """Контроль: без ошибки fallback не срабатывает."""
    ok = DirectorResponse(
        director_id="analyst", model=SPEC.model, content="openrouter answer",
        tokens_in=10, tokens_out=20,
    )
    openrouter = AsyncMock(return_value=ok)

    result = await manager.call_with_backup(openrouter, SPEC, MESSAGES)

    assert result["provider"] == "openrouter"
    assert result["content"] == "openrouter answer"
    assert result["tokens"] == 30
    manager.client.models.generate_content.assert_not_called()


async def test_openrouter_400_and_gemini_down_falls_to_ollama(manager):
    """Граница: если Gemini тоже упал — цепочка доходит до Ollama."""
    manager.client.models.generate_content.side_effect = RuntimeError("quota exceeded")
    openrouter = AsyncMock(return_value=OPENROUTER_400)

    result = await manager.call_with_backup(openrouter, SPEC, MESSAGES)

    assert result["provider"] == "ollama"
    manager.call_ollama_direct.assert_awaited_once()
