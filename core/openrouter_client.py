"""
OpenRouter Client для Consilium AI
"""

import asyncio
import aiohttp
import time
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class DirectorSpec:
    id: str
    model: str
    cost_per_1k_in: float
    cost_per_1k_out: float
    avg_tokens_in: int = 500
    avg_tokens_out: int = 500


@dataclass
class DirectorResponse:
    director_id: str
    model: str
    content: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    error: Optional[str] = None
    raw_response: Optional[Dict] = None


class OpenRouterClient:
    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "Consilium AI",
        }
        self.temperature_map = {
            "scout": 0.3, "analyst": 0.2, "architect": 0.4,
            "chairman": 0.5, "operator": 0.3, "translator": 0.6,
            "devil": 0.7, "synthesizer": 0.3,
        }
        self.system_prompts = {
            "scout": "You are Scout - Information Gatherer in Consilium AI. Collect facts, validate sources. Output: facts with confidence markers [HIGH/MEDIUM/LOW].",
            "analyst": "You are Analyst in Consilium AI. Find patterns, root causes, data synthesis. Show your reasoning chain.",
            "architect": "You are Architect in Consilium AI. Design solutions, model systems, optimize constraints. Output: clear architecture with phases.",
            "chairman": "You are Chairman in Consilium AI. Synthesize all opinions, make final decisions. Output: clear decision with rationale.",
            "operator": "You are Operator in Consilium AI. Plan execution, coordinate resources. Output: step-by-step plan.",
            "translator": "You are Translator in Consilium AI. Bridge domains, clarify concepts. Output: clear explanations without jargon.",
            "devil": "You are Devil's Advocate in Consilium AI. Find contradictions, surface risks. Be skeptical but constructive.",
            "synthesizer": "You are Claude Synthesizer in Consilium AI. Analyze contradictions, surface assumptions, verify logic. Output: JSON analysis.",
            "casual": "You are a friendly, helpful AI assistant. Respond naturally and conversationally. Be warm and engaging.",
        }

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def call_director(self, spec, messages: List[Dict[str, str]],
                             temperature: Optional[float] = None,
                             max_tokens: Optional[int] = None,
                             director_type: Optional[str] = None) -> DirectorResponse:
        start_time = datetime.now()
        if temperature is None:
            temperature = self.temperature_map.get(director_type, 0.7)

        model_name = getattr(spec, 'model', str(spec))
        payload = {"model": model_name, "messages": messages,
                   "temperature": temperature, "max_tokens": max_tokens or 2000}

        try:
            if not self.session:
                self.session = aiohttp.ClientSession(headers=self.headers)

            async with self.session.post(
                f"{self.base_url}/chat/completions", json=payload,
                timeout=aiohttp.ClientTimeout(total=300)
            ) as response:
                data = await response.json()
                latency = (datetime.now() - start_time).total_seconds() * 1000
                spec_id = getattr(spec, 'id', 'unknown')

                if response.status != 200:
                    err = data.get("error", {})
                    err_text = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                    return DirectorResponse(director_id=spec_id, model=model_name, content="",
                                            latency_ms=latency, error=f"HTTP {response.status}: {err_text}")

                try:
                    content = data["choices"][0]["message"]["content"]
                except (KeyError, IndexError) as e:
                    return DirectorResponse(director_id=spec_id, model=model_name, content="",
                                            latency_ms=latency, error=f"Invalid response: {e}")

                usage = data.get("usage", {})
                tokens_in = usage.get("prompt_tokens", getattr(spec, 'avg_tokens_in', 0))
                tokens_out = usage.get("completion_tokens", len(content.split()))
                cost_in = (tokens_in / 1000) * getattr(spec, 'cost_per_1k_in', 0.001)
                cost_out = (tokens_out / 1000) * getattr(spec, 'cost_per_1k_out', 0.001)

                return DirectorResponse(director_id=spec_id, model=model_name, content=content,
                                        tokens_in=tokens_in, tokens_out=tokens_out,
                                        cost_usd=cost_in + cost_out, latency_ms=latency)

        except asyncio.TimeoutError:
            return DirectorResponse(director_id=getattr(spec, 'id', 'unknown'), model=model_name,
                                    content="", latency_ms=300000, error="Timeout after 300s")
        except Exception as e:
            return DirectorResponse(director_id=getattr(spec, 'id', 'unknown'), model=model_name,
                                    content="", error=f"Exception: {str(e)}")

    async def call_director_with_system(self, model: str, prompt: str,
                                         system: Optional[str] = None,
                                         temperature: Optional[float] = None,
                                         director_type: Optional[str] = None,
                                         max_tokens: int = 2000) -> Dict[str, Any]:
        start_time = time.time()
        if system is None and director_type:
            system = self.system_prompts.get(director_type)
        if temperature is None:
            temperature = self.temperature_map.get(director_type, 0.7)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": model, "messages": messages,
                   "temperature": temperature, "max_tokens": max_tokens}
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(headers=self.headers)
            async with self.session.post(
                f"{self.base_url}/chat/completions", json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                data = await response.json()
                if response.status != 200:
                    err = data.get("error", {})
                    return {"success": False, "error": str(err), "content": "", "tokens": 0, "cost_usd": 0.0}
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("total_tokens", 0)
                return {"success": True, "content": content, "tokens": tokens,
                        "cost_usd": self._estimate_cost(model, tokens), "model": model,
                        "latency_ms": (time.time() - start_time) * 1000}
        except Exception as e:
            return {"success": False, "error": str(e), "content": "", "tokens": 0, "cost_usd": 0.0}

    def _estimate_cost(self, model: str, tokens: int) -> float:
        prices = {
            "mistralai/mistral-7b-instruct:free": 0.0,
            "google/gemini-2.0-flash-001:free": 0.0,
            "deepseek/deepseek-r1:free": 0.0,
            "openai/gpt-4o-mini": 0.00015,
            "openai/gpt-4o": 0.003,
            "anthropic/claude-3-5-haiku": 0.0008,
            "anthropic/claude-3-5-sonnet": 0.003,
            "deepseek/deepseek-chat": 0.0005,
            "google/gemini-1.5-flash": 0.00075,
            "google/gemini-2.0-flash-001": 0.0001,
            "perplexity/sonar": 0.001,
        }
        return (tokens / 1000) * prices.get(model, 0.001)

    def get_system_prompt(self, director_type: str) -> str:
        return self.system_prompts.get(director_type, "You are a helpful assistant.")
