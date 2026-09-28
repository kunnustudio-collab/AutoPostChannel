"""
MedQuiz AI - Abstract AI Provider
Defines the interface for all AI backends (OpenRouter, OpenAI, Custom).
"""

from abc import ABC, abstractmethod
from typing import Tuple


class AIProvider(ABC):
    """Abstract Base Class for AI API Providers."""

    @abstractmethod
    async def generate_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model_override: str = ""
    ) -> str:
        """
        Sends completion request to the AI provider and returns raw response string.
        Raises RuntimeError or httpx.HTTPError on failure.
        """
        pass

    @abstractmethod
    async def test_connection(self) -> Tuple[bool, str]:
        """
        Tests API credentials and server availability with a minimal query.
        Returns (success_flag, status_message).
        """
        pass
