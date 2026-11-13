"""Nepali text-to-speech.

Windows ships only English voices on this machine (David, Zira), so a Nepali
reply came out with an English accent. Microsoft's edge-tts endpoint has real
Nepali neural voices, is free and needs no key: about 0.6 s to synthesise.

speak_nepali() returns False when it can't do the job (no network, no audio
device, not Nepali text) so the caller falls back to the Windows voice.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time

# Devanagari block. Romanised Nepali ("notepad kholnus") is indistinguishable from
# English to a script check, so the Brain is told to answer Nepali in Devanagari.
_DEVANAGARI = range(0x0900, 0x0980)
NEPALI_VOICE = os.getenv("HOLODESK_NEPALI_VOICE", "ne-NP-SagarNeural")


def is_nepali(text: str) -> bool:
    return any(ord(ch) in _DEVANAGARI for ch in text or "")


def _synthesize(text: str, path: str) -> None:
    import edge_tts

    async def run() -> None:
        await edge_tts.Communicate(text, NEPALI_VOICE).save(path)

    asyncio.run(run())


def speak_nepali(text: str, *, timeout: float = 20.0) -> bool:
    """Speak Devanagari text aloud. False means the caller should use Windows TTS."""
    if not is_nepali(text):
        return False

    path = os.path.join(tempfile.gettempdir(), f"holodesk_ne_{int(time.time() * 1000)}.mp3")
    try:
        _synthesize(text, path)
    except Exception as exc:
        print(f"[VOICE] Nepali voice unavailable ({type(exc).__name__}), using the English voice", flush=True)
        return False

    try:
        import pygame

        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        deadline = time.time() + timeout
        while pygame.mixer.music.get_busy() and time.time() < deadline:
            time.sleep(0.05)
        pygame.mixer.music.unload()
        return True
    except Exception as exc:
        print(f"[VOICE] Couldn't play the Nepali audio ({type(exc).__name__}), using the English voice", flush=True)
        return False
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def stop_nepali() -> None:
    """Cut Nepali playback short (open palm / abort)."""
    try:
        import pygame

        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except Exception:
        pass
