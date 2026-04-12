"""
GroqClient — wrapper around the Groq Python SDK.

Used by morning_briefing.py and any future agent that needs fast LLM responses.
The existing grok_client in main.py is untouched — this is a separate object.

Model: llama-3.3-70b-versatile
  - Best reasoning quality available on Groq
  - Handles 300-token responses in ~0.5s
  - Free tier is generous enough for this use case
"""

import os
import logging

logger = logging.getLogger(__name__)


class GroqClient:

    MODEL = "llama-3.3-70b-versatile"

    def __init__(self):
        self._client = None  # Lazy-loaded on first call

    def _get_client(self):
        """Initialize the Groq client on first use. Raises clearly if key is missing."""
        if self._client is not None:
            return self._client

        try:
            from groq import Groq
        except ImportError:
            raise RuntimeError(
                "groq package not installed. Run: pip install groq"
            )

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key or api_key.startswith("gsk_YOUR") or len(api_key) < 20:
            raise RuntimeError(
                "GROQ_API_KEY not set or invalid. "
                "Add it to your .env file:\n  GROQ_API_KEY=gsk_..."
            )

        self._client = Groq(api_key=api_key)
        return self._client

    def complete(self, prompt: str, system: str = None,
                 max_tokens: int = 300) -> str:
        """
        Send a prompt to Groq and return the response text.

        Args:
            prompt:     The user message content.
            system:     Optional system prompt. Sets AI persona and constraints.
            max_tokens: Cap on response length. 300 is right for spoken briefings.

        Returns:
            Response text as a plain string.

        Raises:
            RuntimeError: If API key is missing or package not installed.
            Exception:    Propagates Groq API errors so callers can catch them.
        """
        client = self._get_client()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=self.MODEL,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.8,  # Slightly creative — briefings should feel natural
        )

        return response.choices[0].message.content.strip()
