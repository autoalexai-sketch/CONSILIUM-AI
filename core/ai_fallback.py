"""
AI Fallback Manager для Consilium AI
Цепочка: Groq → Bedrock → DeepSeek V4 → OpenRouter → Gemini → Ollama
Groq добавлен первым — бесплатный, быстрый, свежий ключ.
Bedrock вторым — снимает нагрузку с Groq TPM-лимита (12000/мин), оплачивается
из AWS Activate credits.
DeepSeek V4 третьим — дешевый (~$0.28/1M), MoE-архитектура, OpenAI-совместим.

Per-director temperature/max_tokens (см. core/prompts.py DIRECTOR_CONFIG)
передаются через kwargs temperature/max_tokens в call_with_backup и
применяются на уровне каждого провайдера, где это технически возможно
(Groq, DeepSeek). Остальные провайдеры (OpenRouter/Gemini/Ollama) используют
свои дефолты, так как это backup-уровни, не основной путь.
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
      2. Bedrock      — AWS Activate credits, снимает нагрузку с Groq TPM
      3. DeepSeek V4  — дешево, MoE, OpenAI-совместим
      4. OpenRouter   — платный, все модели
      5. Gemini       — бесплатный лимит
      6. Ollama       — локальный
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

        # Amazon Bedrock (приоритет 2 — AWS Activate credits, снимает нагрузку с Groq)
        self.aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.aws_region = os.getenv("AWS_REGION", "us-east-2")
        self.bedrock_model = os.getenv("BEDROCK_MODEL_ID", "meta.llama3-3-70b-instruct-v1:0")
        self.bedrock_available = bool(self.aws_access_key and self.aws_secret_key)
        if self.bedrock_available:
            import boto3
            self.bedrock_client = boto3.client(
                "bedrock-runtime",
                region_name=self.aws_region,
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
            )
            print("✅ Bedrock доступен (приоритет 2, AWS Activate credits)")
        else:
            self.bedrock_client = None
            print("⚠️ AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY не найдены — Bedrock пропущен")

        # Claude Haiku 4.5 через Bedrock (bedrock-mantle) — второй шанс на Claude
        # для Synthesizer, когда у прямого ANTHROPIC_API_KEY кончился баланс.
        # Авторизация другая, чем у Llama: не IAM access key, а Bedrock API key
        # (bearer token) — boto3 подхватывает его сам из AWS_BEARER_TOKEN_BEDROCK,
        # явно передавать в client() не нужно. In-Region в us-east-1, поэтому без
        # cross-region "us." префикса (проверено по model card AWS docs).
        # Claude Sonnet 5 не выбран: на момент подключения (07-2026) требует
        # ручного запроса доступа через AWS Sales, самостоятельно не включается.
        self.bedrock_claude_api_key = os.getenv("AWS_BEARER_TOKEN_BEDROCK")
        self.bedrock_claude_region = os.getenv("BEDROCK_CLAUDE_REGION", "us-east-1")
        self.bedrock_claude_model = os.getenv("BEDROCK_CLAUDE_MODEL_ID", "anthropic.claude-haiku-4-5-20251001-v1:0")
        self.bedrock_claude_available = bool(self.bedrock_claude_api_key)
        if self.bedrock_claude_available:
            import boto3
            self.bedrock_claude_client = boto3.client(
                "bedrock-runtime",
                region_name=self.bedrock_claude_region,
            )
            print("✅ Claude через Bedrock доступен (Haiku 4.5, для Synthesizer)")
        else:
            self.bedrock_claude_client = None
            print("⚠️ AWS_BEARER_TOKEN_BEDROCK не найден — Claude через Bedrock пропущен")

        # DeepSeek V4 (приоритет 3 — дешево, MoE, OpenAI-совместим)
        self.deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        self.deepseek_available = bool(self.deepseek_key)
        self.deepseek_url = "https://api.deepseek.com/v1/chat/completions"
        self.deepseek_model = "deepseek-v4-pro"
        if self.deepseek_available:
            print("✅ DeepSeek V4 доступен (приоритет 2)")
        else:
            print("⚠️ DEEPSEEK_API_KEY не найден")

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

    # ── DeepSeek V4 вызов ────────────────────────────────────────────────
    async def _call_deepseek(self, prompt: str, model: str = None,
                              temperature: float = 0.7, max_tokens: int = 2000) -> Dict[str, Any]:
        """DeepSeek V4 API (OpenAI-compatible). ~$0.28/1M tokens."""
        target = model or self.deepseek_model
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.deepseek_url,
                    headers={"Authorization": f"Bearer {self.deepseek_key}",
                             "Content-Type": "application/json"},
                    json={
                        "model": target,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    tokens = data.get("usage", {}).get("total_tokens", 0)
                    self.last_provider = "deepseek"
                    return {"success": True, "content": content,
                            "provider": "deepseek", "model": target,
                            "tokens": tokens,
                            "cost_usd": round(tokens * 0.00000028, 6)}
                else:
                    err = response.text[:200]
                    return {"success": False,
                            "error": f"DeepSeek HTTP {response.status_code}: {err}"}
        except Exception as e:
            return {"success": False, "error": f"DeepSeek exception: {str(e)[:100]}"}

    # ── Groq вызов ───────────────────────────────────────────────────────
    async def _call_groq(self, prompt: str, model: str = None,
                          temperature: float = 0.7, max_tokens: int = 2000) -> Dict[str, Any]:
        """Прямой вызов Groq API (OpenAI-compatible).
        temperature/max_tokens: per-director values from core/prompts.py
        DIRECTOR_CONFIG, passed through call_with_backup -> here."""
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
                        "max_tokens": max_tokens,
                        "temperature": temperature,
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

    async def _call_groq_with_system(self, system: str, user_prompt: str, model: str = None,
                                       temperature: float = 0.35, max_tokens: int = 2500) -> dict:
        """Groq call with explicit system + user messages. Used for Chairman."""
        target = model or self.groq_model
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.groq_url,
                    headers={"Authorization": f"Bearer {self.groq_key}",
                             "Content-Type": "application/json"},
                    json={
                        "model": target,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user",   "content": user_prompt},
                        ],
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    tokens = data.get("usage", {}).get("total_tokens", 0)
                    return {"success": True, "content": content,
                            "provider": "groq", "model": target,
                            "tokens": tokens, "cost_usd": 0.0}
                err_body = response.text[:500]
                print(f"[GROQ ERROR] status={response.status_code} body={err_body}")
                return {"success": False, "error": f"Groq HTTP {response.status_code}: {err_body}"}
        except Exception as e:
            return {"success": False, "error": f"Groq system call error: {str(e)[:100]}"}

    # ── Amazon Bedrock вызов ─────────────────────────────────────────────
    async def _call_bedrock(self, prompt: str, model: str = None,
                             temperature: float = 0.7, max_tokens: int = 2000) -> Dict[str, Any]:
        """Amazon Bedrock через Converse API (единый формат для всех моделей Bedrock)."""
        target = model or self.bedrock_model
        try:
            response = await asyncio.to_thread(
                lambda: self.bedrock_client.converse(
                    modelId=target,
                    messages=[{"role": "user", "content": [{"text": prompt}]}],
                    inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
                )
            )
            content = response["output"]["message"]["content"][0]["text"]
            usage = response.get("usage", {})
            tokens = usage.get("inputTokens", 0) + usage.get("outputTokens", 0)
            self.last_provider = "bedrock"
            return {"success": True, "content": content,
                    "provider": "bedrock", "model": target,
                    "tokens": tokens, "cost_usd": 0.0}
        except Exception as e:
            return {"success": False, "error": f"Bedrock error: {str(e)[:200]}"}

    # ── Claude через Bedrock (system + user, для Synthesizer) ────────────
    async def _call_bedrock_with_system(self, system: str, user_prompt: str, model: str = None,
                                         temperature: float = 0.3, max_tokens: int = 1500) -> Dict[str, Any]:
        """Bedrock Converse API с отдельным system-промптом. Второй шанс на Claude,
        когда у прямого Anthropic API кончился баланс — списывается с AWS Activate credits."""
        target = model or self.bedrock_claude_model
        try:
            response = await asyncio.to_thread(
                lambda: self.bedrock_claude_client.converse(
                    modelId=target,
                    system=[{"text": system}],
                    messages=[{"role": "user", "content": [{"text": user_prompt}]}],
                    inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
                )
            )
            content = response["output"]["message"]["content"][0]["text"]
            usage = response.get("usage", {})
            tokens = usage.get("inputTokens", 0) + usage.get("outputTokens", 0)
            self.last_provider = "bedrock-claude"
            return {"success": True, "content": content,
                    "provider": "bedrock-claude", "model": target,
                    "tokens": tokens, "cost_usd": 0.0}
        except Exception as e:
            return {"success": False, "error": f"Bedrock Claude error: {str(e)[:200]}"}

    # ── Main fallback chain ───────────────────────────────────────────────────
    async def call_with_backup(self, primary_func: Callable, *args,
                                temperature: float = 0.7, max_tokens: int = 2000,
                                **kwargs) -> Dict[str, Any]:
        """Цепочка: Groq → Bedrock → DeepSeek V4 → OpenRouter → Gemini → Ollama

        temperature/max_tokens: per-director values from core/prompts.py
        DIRECTOR_CONFIG (council.py passes these in based on the director role).
        Applied directly to Groq, Bedrock and DeepSeek calls; OpenRouter/Gemini/Ollama
        are backup levels and keep their own internal defaults.
        """

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
                result = await self._call_groq(prompt, temperature=temperature, max_tokens=max_tokens)
                if result.get("success"):
                    print("   ✅ Groq fallback для local model")
                    return result
            return {"success": False, "error": "Все провайдеры недоступны",
                    "provider": "none", "content": "[Ошибка: все провайдеры недоступны]"}

        # ── УРОВЕНЬ 1: Groq ─────────────────────────────────────────────
        if self.groq_available:
            try:
                prompt = self._extract_prompt(args, kwargs)
                result = await self._call_groq(prompt, temperature=temperature, max_tokens=max_tokens)
                if result.get("success"):
                    print(f"✅ Groq: {len(result.get('content',''))} chars (temp={temperature})")
                    return result
                else:
                    print(f"⚠️ Groq failed: {result.get('error','')[:80]}")
            except Exception as e:
                print(f"⚠️ Groq exception: {str(e)[:80]}")

        # ── УРОВЕНЬ 2: Amazon Bedrock ────────────────────────────────────
        if self.bedrock_available:
            try:
                prompt = self._extract_prompt(args, kwargs)
                result = await self._call_bedrock(prompt, temperature=temperature, max_tokens=max_tokens)
                if result.get("success"):
                    print(f"✅ Bedrock: {len(result.get('content',''))} chars (temp={temperature})")
                    return result
                else:
                    print(f"⚠️ Bedrock failed: {result.get('error','')[:80]}")
            except Exception as e:
                print(f"⚠️ Bedrock exception: {str(e)[:80]}")

        # ── УРОВЕНЬ 3: DeepSeek V4 ───────────────────────────────────────
        if self.deepseek_available:
            try:
                prompt = self._extract_prompt(args, kwargs)
                result = await self._call_deepseek(prompt, temperature=temperature, max_tokens=max_tokens)
                if result.get("success"):
                    print(f"✅ DeepSeek: {len(result.get('content',''))} chars (temp={temperature})")
                    return result
                else:
                    print(f"⚠️ DeepSeek failed: {result.get('error','')[:80]}")
            except Exception as e:
                print(f"⚠️ DeepSeek exception: {str(e)[:80]}")

        # ── УРОВЕНЬ 4: OpenRouter ────────────────────────────────────────
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

        # ── УРОВЕНЬ 5: Gemini ────────────────────────────────────────────
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

        # ── УРОВЕНЬ 6: Ollama ────────────────────────────────────────────
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
                "error": "All providers failed (Groq → Bedrock → DeepSeek → OpenRouter → Gemini → Ollama)",
                "provider": "none",
                "content": "[Ошибка: все провайдеры недоступны. Проверьте GROQ_API_KEY в .env]"}

    # ── Synthesizer (Claude → Claude via Bedrock → Groq → Gemini → Ollama) ──
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

        # Claude через Bedrock — второй шанс на Claude без баланса Anthropic
        if self.bedrock_claude_available:
            try:
                result = await self._call_bedrock_with_system(system_prompt, user_prompt[:4000])
                if result.get("success"):
                    print("✅ Bedrock Claude synthesis")
                    return result
                else:
                    print(f"⚠️ Bedrock Claude synthesis failed: {result.get('error','')[:80]}")
            except Exception as e:
                print(f"⚠️ Bedrock Claude synthesis exception: {str(e)[:80]}")

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
