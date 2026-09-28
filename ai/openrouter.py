"""
MedQuiz AI - OpenRouter / OpenAI Compatible Provider
Handles asynchronous API requests to OpenRouter or compatible endpoints with fallback and rate tracking.
"""

import httpx
import asyncio
from typing import Tuple, Optional
from ai.base import AIProvider
from config import (
    AI_API_KEY, AI_BASE_URL, AI_MODEL, AI_FALLBACK_MODEL,
    MAX_GENERATIONS_PER_HOUR, MAX_GENERATIONS_PER_DAY
)
import database
from utils.logger import logger


class OpenRouterProvider(AIProvider):
    """Client for OpenRouter and OpenAI-compatible API providers."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None
    ):
        self.api_key = api_key or AI_API_KEY
        self.base_url = (base_url or AI_BASE_URL).rstrip("/")
        self.default_model = default_model or AI_MODEL
        self.timeout = httpx.Timeout(connect=10.0, read=45.0, write=10.0, pool=10.0)

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/medquiz-ai",
            "X-Title": "MedQuiz AI Telegram Bot",
            "Content-Type": "application/json"
        }

    async def _check_rate_limits(self) -> None:
        """Enforces configured hourly and daily generation caps."""
        hourly_usage = await database.get_ai_usage_in_window(hours=1)
        if hourly_usage >= MAX_GENERATIONS_PER_HOUR:
            raise RuntimeError(f"Rate limit exceeded: {hourly_usage}/{MAX_GENERATIONS_PER_HOUR} calls in the past hour.")

        daily_usage = await database.get_ai_usage_in_window(hours=24)
        if daily_usage >= MAX_GENERATIONS_PER_DAY:
            raise RuntimeError(f"Daily generation cap reached: {daily_usage}/{MAX_GENERATIONS_PER_DAY} calls today.")

    async def generate_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model_override: str = ""
    ) -> str:
        """Executes chat completion with fallback support on failure."""
        await self._check_rate_limits()

        # Check if model is overridden in database settings
        db_model = await database.get_setting("ai_model", "")
        model_to_use = model_override or db_model or self.default_model

        models_to_try = [model_to_use]
        if AI_FALLBACK_MODEL and AI_FALLBACK_MODEL != model_to_use:
            models_to_try.append(AI_FALLBACK_MODEL)

        last_error = ""

        for attempt, model in enumerate(models_to_try):
            url = f"{self.base_url}/chat/completions"
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens
            }

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=payload, headers=self._get_headers())

                    if response.status_code == 200:
                        data = response.json()
                        if "error" in data or not data.get("choices"):
                            err_text = data.get("error", {}).get("message") or response.text
                            logger.warning(f"AI API error in payload (model: {model}): {err_text}")
                            last_error = f"API error: {err_text}"
                            await database.record_ai_usage(model=model, tokens=0, success=False, error_msg=last_error)
                            continue

                        msg = data["choices"][0]["message"]
                        content = msg.get("content") or ""
                        if not content.strip() and msg.get("reasoning"):
                            content = msg.get("reasoning")

                        tokens = data.get("usage", {}).get("total_tokens", 0)

                        # Record successful usage
                        await database.record_ai_usage(model=model, tokens=tokens, success=True)
                        return content
                    else:
                        err_text = response.text
                        logger.warning(f"AI API request failed (model: {model}, status {response.status_code}): {err_text}")
                        last_error = f"HTTP {response.status_code}: {err_text}"
                        await database.record_ai_usage(model=model, tokens=0, success=False, error_msg=last_error)

            except httpx.TimeoutException:
                last_error = f"Request timed out for model {model}"
                logger.warning(last_error)
                await database.record_ai_usage(model=model, tokens=0, success=False, error_msg=last_error)
            except Exception as e:
                last_error = f"Request error for model {model}: {e}"
                logger.warning(last_error)
                await database.record_ai_usage(model=model, tokens=0, success=False, error_msg=str(e))

            # Small backoff before fallback
            if attempt < len(models_to_try) - 1:
                await asyncio.sleep(1.5)

        raise RuntimeError(f"All AI models failed. Last error: {last_error}")

    async def test_connection(self) -> Tuple[bool, str]:
        """Performs a lightweight sanity check against the AI endpoint."""
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.default_model,
            "messages": [{"role": "user", "content": "Respond strictly with the single word: OK"}],
            "max_tokens": 10,
            "temperature": 0.0
        }

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                res = await client.post(url, json=payload, headers=self._get_headers())
                if res.status_code == 200:
                    return True, "AI Connection Successful! Response 200 OK."
                return False, f"AI Server returned HTTP {res.status_code}: {res.text}"
        except Exception as e:
            return False, f"Connection test failed: {e}"
