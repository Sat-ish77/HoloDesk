"""
OpenAI client for GPT-4o Vision.

Only used for screen analysis — triggered explicitly by the user,
never called automatically. User is notified every time a screenshot
is sent to OpenAI's servers.

Cost: ~$0.002 per call at 1280px width. $100 credit = ~50,000 screen reads.
"""

import os
import base64
import logging
from io import BytesIO

logger = logging.getLogger(__name__)


class OpenAIClient:

    VISION_MODEL = "gpt-4o"
    MAX_TOKENS = 300  # Keep responses concise — spoken answers, not essays

    def __init__(self):
        self._client = None  # Lazy-loaded on first use

    def _get_client(self):
        """Lazy-load the OpenAI client. Raises clear error if key is missing."""
        if self._client is not None:
            return self._client

        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError(
                "openai package not installed. Run: pip install openai"
            )

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key.startswith("sk-YOUR"):
            raise RuntimeError(
                "OPENAI_API_KEY not set. Add it to your .env file:\n"
                "  OPENAI_API_KEY=sk-..."
            )

        self._client = OpenAI(api_key=api_key)
        return self._client

    def vision_query(self, image_b64: str, question: str,
                     system: str | None = None) -> str:
        """
        Send a base64-encoded image to GPT-4o Vision and return the response.

        Args:
            image_b64: Base64-encoded PNG or JPEG string (no data: prefix).
            question:  What to ask about the image.
            system:    Optional system prompt. Defaults to HoloDesk assistant prompt.

        Returns:
            Plain text response string.
        """
        if system is None:
            system = (
                "You are HoloDesk, an ambient AI assistant embedded in the user's desktop. "
                "The user triggered screen reading manually — analyze what is on screen. "
                "Reply in 2-3 sentences maximum. Be direct and specific. "
                "For error messages: state the cause and the fix. "
                "For code: explain what it does in plain English. "
                "For documents: state the single most important point. "
                "Never say 'I can see' or 'the image shows' — just answer directly."
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
                                    "detail": "low",  # "low" = cheaper, still readable at 1280px
                                },
                            },
                            {"type": "text", "text": question},
                        ],
                    },
                ],
            )
            return response.choices[0].message.content.strip()

        except RuntimeError:
            raise  # Re-raise config errors so screen_agent can report them cleanly
        except Exception as e:
            logger.error("GPT-4o Vision API error: %s", e)
            raise RuntimeError(f"Vision API failed: {e}") from e
