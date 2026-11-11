"""
Neural text-to-speech for Nepali.

Windows SAPI ships no Nepali voice, so Devanagari text read by SAPI is
silence or noise. edge-tts gives free neural Nepali voices and needs no GPU
(it does need internet). English keeps using SAPI, which is instant.

    speak_neural(text, should_stop) -> True if it spoke, False to fall back
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
import time
from typing import Callable

logger = logging.getLogger(__name__)

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_MARKDOWN = re.compile(r"[*_`#>]+")


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def is_nepali(text: str) -> bool:
    """True when enough of the text is Devanagari that SAPI cannot read it."""
    letters = [c for c in (text or "") if c.isalpha() or _DEVANAGARI.match(c)]
    if not letters:
        return False
    deva = sum(1 for c in letters if _DEVANAGARI.match(c))
    return deva / len(letters) >= 0.3


def wants_neural(text: str) -> bool:
    mode = _env("HOLODESK_NEURAL_TTS", "nepali").lower()   # nepali | always | off
    if mode == "off":
        return False
    return mode == "always" or is_nepali(text)


def pick_voice(text: str) -> str:
    if is_nepali(text):
        return _env("HOLODESK_TTS_VOICE_NE", "ne-NP-SagarNeural")   # or ne-NP-HemkalaNeural
    return _env("HOLODESK_TTS_VOICE_EN", "en-US-AndrewNeural")


def clean_for_speech(text: str) -> str:
    text = _MARKDOWN.sub("", text or "")
    text = re.sub(r"https?://\S+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def synthesize(text: str, path: str, voice: str | None = None) -> bool:
    """Write speech for `text` to an mp3 at `path`."""
    try:
        import edge_tts
    except ImportError:
        logger.warning("edge-tts not installed (pip install edge-tts); Nepali speech disabled")
        return False
    text = clean_for_speech(text)
    if not text:
        return False
    try:
        asyncio.run(edge_tts.Communicate(text, voice or pick_voice(text)).save(path))
        return os.path.exists(path) and os.path.getsize(path) > 0
    except Exception as e:
        logger.warning("Neural TTS synthesis failed: %s", e)
        return False


def speak_neural(text: str, should_stop: Callable[[], bool] = lambda: False) -> bool:
    """Synthesize and play. Returns False (without speaking) on any failure so
    the caller can fall back to SAPI."""
    try:
        import pygame
    except ImportError:
        return False
    fd, path = tempfile.mkstemp(suffix=".mp3", prefix="holodesk_tts_")
    os.close(fd)
    try:
        if not synthesize(text, path):
            return False
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            if should_stop():
                pygame.mixer.music.stop()
                break
            time.sleep(0.05)
        return True
    except Exception as e:
        logger.warning("Neural TTS playback failed: %s", e)
        return False
    finally:
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.unload()
        except Exception:
            pass
        try:
            os.unlink(path)
        except OSError:
            pass
