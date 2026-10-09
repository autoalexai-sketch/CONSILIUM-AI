"""
tests/test_gemini_nonblocking.py — Gemini-вызов не блокирует event loop.

google-genai `generate_content` синхронный. Если вызвать его прямо внутри
async-функции, весь сервер (включая WebSocket /ws/council) стоит, пока
Gemini думает. Фикс: `await asyncio.to_thread(...)`, как у Bedrock.

Проверка: мок Gemini делает time.sleep(0.3). Параллельно работает другая
корутина с asyncio.sleep(0.01). Если loop не заблокирован, она завершается
раньше, чем Gemini вернул ответ.
"""
import asyncio
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.ai_fallback import AIFallbackManager
from core.openrouter_client import DirectorResponse, DirectorSpec

GEMINI_THINK_SEC = 0.3
OTHER_SLEEP_SEC = 0.01


@pytest.fixture
def manager_and_events():
    """Менеджер, где отвечает только Gemini; events — порядок завершения."""
    with patch.object(AIFallbackManager, "_check_ollama", return_value=False):
        m = AIFallbackManager()

    m.groq_available = False
    m.bedrock_available = False
    m.deepseek_available = False
    m.claude_available = False
    m.bedrock_claude_available = False
    m.ollama_available = False

    events = []

    def slow_generate_content(**kwargs):
        time.sleep(GEMINI_THINK_SEC)  # синхронный SDK "думает"
        events.append("gemini_done")
        return SimpleNamespace(text="gemini answer")

    m.gemini_available = True
    m.client = MagicMock()
    m.client.models.generate_content.side_effect = slow_generate_content
    return m, events


async def _other_coroutine(events):
    await asyncio.sleep(OTHER_SLEEP_SEC)
    events.append("other_done")


async def test_gemini_backup_does_not_block_event_loop(manager_and_events):
    m, events = manager_and_events
    spec = DirectorSpec(id="analyst", model="openai/gpt-4o",
                        cost_per_1k_in=0.0, cost_per_1k_out=0.0)
    openrouter_400 = DirectorResponse(director_id="analyst", model=spec.model,
                                      content="", error="HTTP 400: Bad Request")

    async def openrouter(*args, **kwargs):
        return openrouter_400

    result, _ = await asyncio.gather(
        m.call_with_backup(openrouter, spec, [{"role": "user", "content": "q"}]),
        _other_coroutine(events),
    )

    assert result["provider"] == "gemini"
    assert events == ["other_done", "gemini_done"], (
        "другая корутина не смогла выполниться, пока Gemini думал — "
        "event loop заблокирован"
    )


async def test_gemini_synthesis_does_not_block_event_loop(manager_and_events):
    m, events = manager_and_events
    m.groq_available = False  # синтез: Claude → Bedrock Claude → Groq → Gemini

    result, _ = await asyncio.gather(
        m.call_claude_for_synthesis("system", "x" * 100),
        _other_coroutine(events),
    )

    assert result["provider"] == "gemini"
    assert events == ["other_done", "gemini_done"], (
        "другая корутина не смогла выполниться, пока Gemini думал — "
        "event loop заблокирован"
    )
