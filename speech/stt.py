"""
Cloud speech-to-text over the OpenAI-compatible /audio/transcriptions API.

Default is Groq's hosted whisper-large-v3 (free tier, no GPU needed here).
Returns "" on any failure so callers can fall back to the local model.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Whisper often labels Nepali audio as one of its neighbours and then writes
# it with that language's spelling. When that happens we ask again as Nepali.
_NEPALI_LOOKALIKES = {"hi", "hindi", "mr", "marathi", "sa", "sanskrit", "bn", "bengali",
                      "ur", "urdu"}

# A short bias prompt: Whisper continues "in the style of" this text, which
# nudges it toward Devanagari Nepali and correct spelling of names it hears a lot.
DEFAULT_PROMPT = ("HoloDesk. नेपाली र English मिसिएको कुराकानी। "
                  "Chrome, YouTube, Gmail, Google, Facebook, Instagram, Google Drive, VS Code, "
                  "WhatsApp, Notepad, Downloads, screenshot, tab.")


def _prompt() -> str:
    # HOLODESK_STT_NAMES: people and channels you say often ("Kapil Sharma"), kept
    # in .env so private names stay out of the repo. Whisper spells what it has seen.
    names = _env("HOLODESK_STT_NAMES")
    return _env("HOLODESK_STT_PROMPT", DEFAULT_PROMPT) + (f" {names}." if names else "")


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


class CloudSTT:
    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 model: str | None = None, language: str | None = None,
                 prefer_nepali: bool | None = None, session=None, timeout_sec: int = 30):
        self.base_url = (base_url or _env("HOLODESK_STT_BASE_URL",
                                          "https://api.groq.com/openai/v1")).rstrip("/")
        self.api_key = api_key if api_key is not None else (
            _env("HOLODESK_STT_API_KEY") or _env("GROQ_API_KEY"))
        self.model = model or _env("HOLODESK_STT_MODEL", "whisper-large-v3")
        # "auto" detects per utterance; "ne" or "en" forces one language.
        self.language = (language or _env("HOLODESK_STT_LANGUAGE", "auto")).lower()
        self.prefer_nepali = prefer_nepali if prefer_nepali is not None else (
            _env("HOLODESK_STT_PREFER_NEPALI", "1") == "1")
        self.timeout_sec = timeout_sec
        self._session = session

    @property
    def ready(self) -> bool:
        return bool(self.api_key) and len(self.api_key) >= 20 and "your_" not in self.api_key.lower()

    def _http(self):
        if self._session is None:
            import requests
            self._session = requests.Session()
        return self._session

    def _post(self, audio: bytes, filename: str, language: str | None) -> dict:
        data = {"model": self.model, "response_format": "verbose_json", "temperature": "0",
                "prompt": _prompt()}
        if language and language != "auto":
            data["language"] = language
        resp = self._http().post(
            f"{self.base_url}/audio/transcriptions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            data=data, files={"file": (filename, audio)}, timeout=self.timeout_sec)
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    def transcribe(self, audio: bytes | str | Path, filename: str = "audio.wav") -> dict:
        """Returns {"text": str, "language": str}. Empty text means failure."""
        if not self.ready:
            return {"text": "", "language": ""}
        if isinstance(audio, (str, Path)):
            filename = Path(audio).name
            audio = Path(audio).read_bytes()
        try:
            result = self._post(audio, filename, self.language)
            detected = str(result.get("language") or "").lower()
            if (self.language == "auto" and self.prefer_nepali
                    and detected in _NEPALI_LOOKALIKES):
                retry = self._post(audio, filename, "ne")
                if (retry.get("text") or "").strip():
                    result, detected = retry, "ne"
            if _looks_like_silence(result):
                return {"text": "", "language": detected, "silence": True}
            text = _drop_prompt_echo((result.get("text") or "").strip())
            return {"text": text, "language": detected}
        except Exception as e:
            logger.warning("Cloud STT failed, caller should fall back: %s", e)
            return {"text": "", "language": ""}


_HALLUCINATIONS = {"thank you", "thanks for watching", "thank you for watching", "you", "bye",
                   "subscribe", "please subscribe"}
_ALWAYS_NOISE = _HALLUCINATIONS - {"bye"}   # "bye" alone is a real way to end


def _looks_like_silence(result: dict) -> bool:
    """Whisper invents fluent text from room noise. Its own per-segment
    confidence numbers are the best signal that it did."""
    text = (result.get("text") or "").strip().lower().strip(" .!?।")
    # A lone "Thank you." arrived with low no_speech_prob and ended a live
    # conversation; nobody gives a command that is only these words.
    if text in _ALWAYS_NOISE:
        return True
    segments = result.get("segments") or []
    if segments:
        no_speech = [float(s.get("no_speech_prob") or 0.0) for s in segments]
        logprob = [float(s.get("avg_logprob") or 0.0) for s in segments]
        if min(no_speech) >= 0.8:
            return True
        if sum(logprob) / len(logprob) < -1.2:
            return True
        if text in _HALLUCINATIONS and max(no_speech) >= 0.3:
            return True
    return False


def _drop_prompt_echo(text: str) -> str:
    """On near-silence Whisper sometimes just repeats the bias prompt."""
    stripped = text.strip(" .।")
    if not stripped:
        return ""
    prompt = _prompt()
    if prompt.strip(" .।") in stripped or (len(stripped) > 25 and stripped in prompt):
        return ""
    return text


_default: CloudSTT | None = None


def transcribe_command(wav_path: str) -> str:
    """Convenience for the voice loop: text, or "" to signal 'use local STT'."""
    global _default
    if _env("HOLODESK_CLOUD_STT", "1") != "1":
        return ""
    if _default is None:
        _default = CloudSTT()
    result = _default.transcribe(wav_path)
    if result.get("silence"):
        # Confidently nothing there: do not let the local model have a go at
        # hallucinating from the same noise.
        return " "
    return result["text"]
