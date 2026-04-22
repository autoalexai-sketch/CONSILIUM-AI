"""
AI Fallback Manager для Consilium AI
Цепочка: Groq → OpenRouter → Gemini → Ollama
Groq добавлен первым — бесплатный, быстрый, свежий ключ.
"""

import os
import asyncio
import httpx
from typing import Optional, Dict, Any, Callable
from google import genai
from dotenv import load_dotenv
import anthropic

load_dotenv()


class AIFallbackManager:
    """
    Провайдеры в порядке приоритета:
      1. Groq         — бесплатный, быстрый (llama3-70b-8192)
      2. OpenRouter   — платный, все модели
      3. Gemini       — бесплатный лимит
      4. Ollama       — локальный
    """

    def __init__(self):
        # Groq (новый — приоритет 1)
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.groq_available = bool(self.groq_key)
        self.groq_url = "https://api.groq.com/openai/v1/chat/completions"
        self.groq_model = "llama-3.3-70b-versatile"  # актуальная модель Groq 2026
        if self.groq_available:
            print("✅ Groq доступен (приоритет 1)")
        else:
            print("⚠️ GROQ_API_KEY не найден")

        # Claude (для Synthesizer)
        self.claude_key = os.getenv("ANTHROPIC_API_KEY")
        if self.claude_key:
            self.claude_client = anthropic.Anthropic(api_key=self.claude_key)
            self.claude_available = True
            print("✅ Claude доступна (Synthesizer)")
        else:
            self.claude_available = False
            print("⚠️ ANTHROPIC_API_KEY не найден")

        # Gemini
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            self.client = genai.Client(api_key=gemini_key)
            self.gemini_available = True
            print("✅ Gemini доступна")
        else:
            self.gemini_available = False
            print("⚠️ GEMINI_API_KEY не найден")

        # Ollama
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model = "llama3:8b"
        self.ollama_available = self._check_ollama()

        self.last_provider = None

    def _check_ollama(self) -> bool:
        try:
            import urllib.request
            urllib.request.urlopen(f"{self.ollama_url}/api/tags", timeout=2.0)
            print("✅ Ollama доступна")
            return True
        except Exception as e:
            print(f"⚠️ Ollama недоступна: {e}")
            return False

    # ── Groq вызов ───────────────────────────────────────────────────────
    async def _call_groq(self, prompt: str, model: str = None) -> Dict[str, Any]:
        """Прямой вызов Groq API (OpenAI-compatible)."""
        target = model or self.groq_model
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.groq_url,
                    headers={"Authorization": f"Bearer {self.groq_key}",
                             "Content-Type": "application/json"},
                    json={
                        "model": target,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 2000,
                        "temperature": 0.7,
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    tokens = data.get("usage", {}).get("total_tokens", 0)
                    self.last_provider = "groq"
                    return {"success": True, "content": content,
                            "provider": "groq", "model": target,
                            "tokens": tokens, "cost_usd": 0.0}
                else:
                    err = response.text[:200]
                    return {"success": False,
                            "error": f"Groq HTTP {response.status_code}: {err}"}
        except Exception as e:
            return {"success": False, "error": f"Groq exception: {str(e)[:100]}"}

    # ── Главная цепочка ───────────────────────────────────────────────────
    async def call_with_backup(self, primary_func: Callable, *args, **kwargs) -> Dict[str, Any]:
        """Цепочка: Groq → OpenRouter → Gemini → Ollama"""

        # Если локальная модель (без '/') → сразу Ollama
        spec_arg = args[0] if args else None
        model_name = getattr(spec_arg, 'model', '') if spec_arg else ''
        is_local_model = bool(model_name) and '/' not in model_name

        if is_local_model:
            print(f"🔄 Локальная модель ({model_name}): → Ollama")
            prompt = self._extract_prompt(args, kwargs)
            if self.ollama_available:
                result = await self.call_ollama_direct(prompt, model=model_name)
                if result.get("success"):
                    return result
            # Fallback на Groq если Ollama упала
            if self.groq_available:
                result = await self._call_groq(prompt)
                if result.get("success"):
                    print("   ✅ Groq fallback для local model")
                    return result
            return {"success": False, "error": "Все провайдеры недоступны",
                    "provider": "none", "content": "[Ошибка: все провайдеры недоступны]"}

        # ── УРОВЕНЬ 1: Groq ─────────────────────────────────────────────
        if self.groq_available:
            try:
                prompt = self._extract_prompt(args, kwargs)
                result = await self._call_groq(prompt)
                if result.get("success"):
                    print(f"✅ Groq: {len(result.get('content',''))} chars")
                    return result
                else:
                    print(f"⚠️ Groq failed: {result.get('error','')[:80]}")
            except Exception as e:
                print(f"⚠️ Groq exception: {str(e)[:80]}")

        # ── УРОВЕНЬ 2: OpenRouter ────────────────────────────────────────
        try:
            result = await asyncio.wait_for(primary_func(*args, **kwargs), timeout=60.0)
            if result and hasattr(result, '__dataclass_fields__'):
                if not result.error:
                    self.last_provider = "openrouter"
                    return {"success": True, "content": result.content,
                            "provider": "openrouter", "model": result.model,
                            "tokens": getattr(result, 'tokens_in', 0) + getattr(result, 'tokens_out', 0),
                            "cost_usd": getattr(result, 'cost_usd', 0)}
                else:
                    raise Exception(f"OpenRouter error: {result.error}")
            if result and isinstance(result, dict) and result.get("success", True):
                self.last_provider = "openrouter"
                return {"success": True,
                        "content": result.get("content") or result.get("text"),
                        "provider": "openrouter", "model": result.get("model", "unknown"),
                        "tokens": result.get("tokens_used", 0) or result.get("tokens", 0),
                        "cost_usd": result.get("cost_usd", 0)}
            raise Exception("OpenRouter returned error response")
        except asyncio.TimeoutError:
            print("⏱️ OpenRouter timeout (60s)")
        except Exception as e:
            print(f"⚠️ OpenRouter failed: {str(e)[:100]}")

        # ── УРОВЕНЬ 3: Gemini ────────────────────────────────────────────
        if self.gemini_available:
            try:
                prompt = self._extract_prompt(args, kwargs)
                response = self.client.models.generate_content(
                    model="gemini-2.0-flash", contents=prompt[:8000])
                self.last_provider = "gemini"
                print("✅ Gemini backup")
                return {"success": True, "content": response.text,
                        "provider": "gemini", "model": "gemini-2.0-flash",
                        "tokens": self._estimate_tokens(prompt, response.text),
                        "cost_usd": 0.0}
            except Exception as e:
                print(f"⚠️ Gemini failed: {str(e)[:100]}")

        # ── УРОВЕНЬ 4: Ollama ────────────────────────────────────────────
        if self.ollama_available:
            try:
                prompt = self._extract_prompt(args, kwargs)
                print(f"🔄 Переключение на Ollama ({self.ollama_model})...")
                result = await self.call_ollama_direct(prompt)
                if result.get("success"):
                    print("✅ Ollama successful")
                    return result
                else:
                    raise Exception(result.get("error", "Unknown Ollama error"))
            except Exception as e:
                print(f"⚠️ Ollama failed: {str(e)[:120]}")

        return {"success": False,
                "error": "All providers failed (Groq → OpenRouter → Gemini → Ollama)",
                "provider": "none",
                "content": "[Ошибка: все провайдеры недоступны. Проверьте GROQ_API_KEY в .env]"}

    # ── Synthesizer (Claude → Groq → Gemini → Ollama) ───────────────────
    async def call_claude_for_synthesis(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        if not user_prompt or len(user_prompt.strip()) < 50:
            return {"success": False, "error": "Empty context", "content": ""}

        # Claude
        if self.claude_available:
            try:
                response = await asyncio.to_thread(
                    lambda: self.claude_client.messages.create(
                        model="claude-3-5-sonnet-20241022",
                        max_tokens=1500, system=system_prompt,
                        messages=[{"role": "user", "content": user_prompt[:4000]}],
                        temperature=0.3))
                self.last_provider = "claude"
                return {"success": True, "content": response.content[0].text,
                        "provider": "claude", "model": "claude-3-5-sonnet",
                        "tokens": response.usage.input_tokens + response.usage.output_tokens,
                        "cost_usd": 0.003}
            except Exception as e:
                err_str = str(e)
                print(f"⚠️ Claude failed: {err_str[:100]}")
                if any(x in err_str.lower() for x in ["credit", "billing", "400", "invalid_request"]):
                    self.claude_available = False

        # Groq для синтеза
        if self.groq_available:
            try:
                combined = f"{system_prompt[:500]}\n\n{user_prompt[:3000]}"
                result = await self._call_groq(combined, model="llama3-70b-8192")
                if result.get("success"):
                    print("✅ Groq synthesis backup")
                    return result
            except Exception as e:
                print(f"⚠️ Groq synthesis failed: {str(e)[:80]}")

        # Gemini
        if self.gemini_available:
            try:
                combined = f"{system_prompt}\n\n{user_prompt[:3000]}"
                response = self.client.models.generate_content(
                    model="gemini-2.0-flash", contents=combined)
                self.last_provider = "gemini"
                print("✅ Gemini synthesis backup")
                return {"success": True, "content": response.text,
                        "provider": "gemini", "model": "gemini-2.0-flash",
                        "tokens": self._estimate_tokens(user_prompt, response.text),
                        "cost_usd": 0.0}
            except Exception as e:
                print(f"⚠️ Gemini synthesis failed: {str(e)[:100]}")

        # Ollama
        if self.ollama_available:
            try:
                return await self.call_ollama_direct(user_prompt[:2000], fast_mode=False)
            except Exception as e:
                print(f"⚠️ Ollama synthesis failed: {str(e)[:100]}")

        return {"success": False, "error": "All synthesis providers failed",
                "content": "[Синтез недоступен]"}

    # ── Ollama direct ─────────────────────────────────────────────────────
    async def call_ollama_direct(self, prompt: str, model: str = None,
                                  fast_mode: bool = False) -> Dict[str, Any]:
        target_model = model if model else self.ollama_model
        num_predict = 350 if fast_mode else 512
        num_ctx     = 2048 if fast_mode else 2048  # меньше контекст = быстрее
        timeout_sec = 60.0 if fast_mode else 90.0  # быстрый fail → следующий провайдер

        payload = {
            "model": target_model,
            "prompt": str(prompt)[:4000],   # ограничиваем длину
            "stream": False,
            "options": {"num_predict": num_predict, "temperature": 0.7,
                        "num_ctx": num_ctx, "num_thread": 4},
        }
        try:
            print(f"   🔄 Ollama: {target_model} (predict={num_predict})...")
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout_sec, read=timeout_sec, connect=10.0)
            ) as client:
                response = await client.post(f"{self.ollama_url}/api/generate", json=payload)
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("response", "").strip()
                    if not content:
                        return {"success": False, "error": "Ollama returned empty response"}
                    return {"success": True, "content": content, "model": target_model,
                            "provider": "ollama",
                            "tokens": data.get("eval_count", 0), "cost_usd": 0.0}
                else:
                    return {"success": False,
                            "error": f"Ollama HTTP {response.status_code}: {response.text[:100]}"}
        except httpx.ConnectError:
            return {"success": False, "error": "Ollama не запущена (Connection refused)"}
        except httpx.TimeoutException:
            return {"success": False, "error": f"Ollama timeout ({timeout_sec}s)"}
        except Exception as e:
            return {"success": False, "error": f"{type(e).__name__}: {str(e)[:100]}"}

    # ── Helpers ───────────────────────────────────────────────────────────
    def _extract_prompt(self, args, kwargs) -> str:
        """Извлекает текст промпта из args/kwargs любого формата."""
        # Именованный аргумент
        if 'prompt' in kwargs:
            return str(kwargs['prompt'])
        # messages как kwarg
        if 'messages' in kwargs:
            msgs = kwargs['messages']
            if isinstance(msgs, list):
                return "\n".join(m.get('content', '') for m in msgs
                                 if isinstance(m, dict))
            return str(msgs)
        # args[1] — второй позиционный (список messages или строка)
        if args and len(args) >= 2:
            arg1 = args[1]
            if isinstance(arg1, list):
                # Список dict messages
                return "\n".join(
                    m.get('content', '') for m in arg1
                    if isinstance(m, dict)
                )
            return str(arg1)
        # args[0] как строка
        if args and isinstance(args[0], str):
            return args[0]
        return str(args[0]) if args else ""

    def _estimate_tokens(self, prompt: str, response: str) -> int:
        return (len(prompt) + len(response)) // 4


# Глобальный экземпляр
fallback_manager = AIFallbackManager()
