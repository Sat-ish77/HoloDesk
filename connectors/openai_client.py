"""
OpenAI client for HoloDesk vision, chat, and production planning.

Screen analysis is still only triggered explicitly by the user. Text planning
is used for command understanding when deterministic routing is not enough.
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)


class OpenAIClient:
    VISION_MODEL = os.getenv("HOLODESK_OPENAI_VISION_MODEL", "gpt-4o")
    PLANNER_MODEL = os.getenv("HOLODESK_OPENAI_PLANNER_MODEL", "gpt-5.2")
    CHAT_MODEL = os.getenv("HOLODESK_OPENAI_CHAT_MODEL", "gpt-5.2-chat-latest")
    MAX_TOKENS = 300

    def __init__(self):
        self._client = None

    def _get_client(self):
        """Lazy-load the OpenAI client. Raises clear error if key is missing."""
        if self._client is not None:
            return self._client

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package not installed. Run: pip install openai") from exc

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key.startswith("sk-YOUR"):
            raise RuntimeError(
                "OPENAI_API_KEY not set. Add it to your .env file:\n"
                "  OPENAI_API_KEY=sk-..."
            )

        self._client = OpenAI(api_key=api_key)
        return self._client

    def vision_query(
        self,
        image_b64: str,
        question: str,
        system: str | None = None,
    ) -> str:
        """Send a base64-encoded image to OpenAI Vision and return plain text."""
        if system is None:
            system = (
                "You are HoloDesk, an ambient AI assistant embedded in the user's desktop. "
                "The user triggered screen reading manually. Analyze what is on screen. "
                "Reply in 2-3 sentences maximum. Be direct and specific. "
                "For error messages: state the cause and the fix. "
                "For code: explain what it does in plain English. "
                "For documents: state the single most important point. "
                "Never say 'I can see' or 'the image shows'. Just answer directly."
            )

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.VISION_MODEL,
                max_tokens=self.MAX_TOKENS,
                messages=[
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_b64}",
                                    "detail": "low",
                                },
                            },
                            {"type": "text", "text": question},
                        ],
                    },
                ],
            )
            return (response.choices[0].message.content or "").strip()
        except RuntimeError:
            raise
        except Exception as exc:
            logger.error("OpenAI Vision API error: %s", exc)
            raise RuntimeError(f"Vision API failed: {exc}") from exc

    def text_query(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        max_tokens: int = 500,
    ) -> str:
        """Return a short text completion from the configured OpenAI chat model."""
        client = self._get_client()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(
            model=model or self.CHAT_MODEL,
            max_tokens=max_tokens,
            messages=messages,
        )
        return (response.choices[0].message.content or "").strip()

    def json_query(
        self,
        prompt: str,
        *,
        system: str,
        model: str | None = None,
        max_tokens: int = 900,
    ) -> dict:
        """Ask OpenAI for one JSON object and parse it defensively."""
        text = self.text_query(
            prompt,
            system=system + "\nReturn only valid JSON. Do not wrap it in markdown.",
            model=model or self.PLANNER_MODEL,
            max_tokens=max_tokens,
        )
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start : end + 1])
            raise RuntimeError(f"OpenAI did not return valid JSON: {text[:200]}")
