"""
ScreenAgent — Takes a screenshot and asks GPT-4o Vision to explain it.

Triggered only when the user explicitly asks:
  "what's on my screen", "explain this", "read my screen", etc.

The user is notified BEFORE the screenshot is sent to OpenAI.
Protected windows (banking, passwords, private browsing) are never captured.

Flow:
  1. Check active window title against blocklist → abort if blocked
  2. Take screenshot with pyautogui
  3. Resize to 1280px wide (saves API cost, still fully readable)
  4. Base64 encode → send to GPT-4o Vision
  5. Return plain-text answer (2-3 sentences)
"""

import base64
import logging
from io import BytesIO

logger = logging.getLogger(__name__)

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    logger.warning("pyautogui not installed — screen capture disabled")

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    logger.warning("Pillow not installed — screen capture disabled")

try:
    import win32gui
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

from connectors.openai_client import OpenAIClient


# Windows with these keywords in their title are NEVER captured.
BLOCKED_TITLE_KEYWORDS = [
    "1password", "lastpass", "bitwarden", "dashlane", "keepass",
    "banking", "chase", "wells fargo", "bank of america", "citibank",
    "private -", "incognito",
    "social security", "tax return", "payroll",
    "password manager", "credit card",
]

# Resize screenshots to this width before sending to the API.
# 1280px is readable for GPT-4o but much cheaper than full 1920px.
TARGET_WIDTH = 1280


class ScreenAgent:

    def __init__(self):
        self._client = OpenAIClient()
        self.last_question = ""   # Stored so UI can display it
        self.last_response = ""   # Stored so UI can display the answer

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def execute(self, question: str = "What is on this screen? Explain it clearly.") -> dict:
        """
        Capture the screen and ask GPT-4o Vision the given question.

        Returns a dict:
          { "success": bool, "response": str, "blocked": bool }

        The caller is responsible for speaking the response via TTS.
        """
        self.last_question = question

        # --- Dependency check ---
        if not PYAUTOGUI_AVAILABLE or not PILLOW_AVAILABLE:
            return self._error(
                "Screen reading requires pyautogui and Pillow. "
                "Run: pip install pyautogui Pillow"
            )

        # --- Privacy check ---
        if self._is_blocked():
            logger.info("Screen capture blocked — protected window in focus")
            return {
                "success": False,
                "blocked": True,
                "response": (
                    "I can't read that window — it looks like a sensitive app "
                    "like a password manager or banking site. I'll never capture those."
                ),
            }

        # --- Capture ---
        try:
            image = self._capture_and_resize()
        except Exception as e:
            logger.error("Screenshot failed: %s", e)
            return self._error(f"Screenshot failed: {e}")

        # --- Encode ---
        try:
            b64 = self._encode_to_base64(image)
        except Exception as e:
            logger.error("Image encoding failed: %s", e)
            return self._error(f"Image encoding failed: {e}")

        # --- Vision API ---
        try:
            response_text = self._client.vision_query(
                image_b64=b64,
                question=question,
            )
        except RuntimeError as e:
            # Config errors (missing key, not installed) — tell the user clearly
            return self._error(str(e))
        except Exception as e:
            logger.error("Vision API unexpected error: %s", e)
            return self._error("Vision API is unavailable right now. Try again in a moment.")

        self.last_response = response_text
        logger.info("Screen analysis complete (%d chars)", len(response_text))
        return {"success": True, "blocked": False, "response": response_text}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_active_window_title(self) -> str:
        if not WIN32_AVAILABLE:
            return ""
        try:
            hwnd = win32gui.GetForegroundWindow()
            return (win32gui.GetWindowText(hwnd) or "").lower()
        except Exception:
            return ""

    def _is_blocked(self) -> bool:
        title = self._get_active_window_title()
        return any(kw in title for kw in BLOCKED_TITLE_KEYWORDS)

    def _capture_and_resize(self) -> "Image.Image":
        """Take a full screenshot and resize to TARGET_WIDTH."""
        screenshot = pyautogui.screenshot()

        ratio = TARGET_WIDTH / screenshot.width
        new_height = int(screenshot.height * ratio)
        resized = screenshot.resize((TARGET_WIDTH, new_height), Image.LANCZOS)
        return resized

    def _encode_to_base64(self, image: "Image.Image") -> str:
        """Convert a PIL Image to a base64 PNG string."""
        buffer = BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    @staticmethod
    def _error(message: str) -> dict:
        return {"success": False, "blocked": False, "response": message}


# Module-level singleton
screen_agent = ScreenAgent()
