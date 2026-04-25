"""
Wake-word adapter for HoloDesk.

Design goals:
- Keep wake-word support optional and env-controlled.
- Do not change existing voice/VAD tuning in app/main.py.
- Trigger the existing wake path by calling a callback supplied by startup.
- Fail gracefully when optional dependencies are unavailable.
"""

from __future__ import annotations

import logging
import os
import queue
import re
import tempfile
import threading
import time
import wave
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def _env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip() == "1"


def _norm_text(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s]+", " ", (text or "").lower())
    return re.sub(r"\s+", " ", cleaned).strip()


@dataclass
class WakeWordConfig:
    enabled: bool
    phrase: str
    engine: str
    whisper_model: str
    listen_timeout_s: float
    phrase_limit_s: float
    cooldown_s: float
    porcupine_access_key: str

    @classmethod
    def from_env(cls) -> "WakeWordConfig":
        engine = os.getenv("HOLODESK_WAKE_WORD_ENGINE", "simple").strip().lower()
        if engine not in {"simple", "whisper", "porcupine"}:
            logger.warning("[WAKE] Unknown engine '%s'. Falling back to 'simple'.", engine)
            engine = "simple"

        phrase = _norm_text(os.getenv("HOLODESK_WAKE_WORD_PHRASE", "hey desk")) or "hey desk"

        return cls(
            enabled=_env_flag("HOLODESK_WAKE_WORD_ENABLED", "0"),
            phrase=phrase,
            engine=engine,
            whisper_model=os.getenv("HOLODESK_WAKE_WORD_WHISPER_MODEL", "tiny").strip() or "tiny",
            listen_timeout_s=float(os.getenv("HOLODESK_WAKE_WORD_LISTEN_TIMEOUT", "1.0")),
            phrase_limit_s=float(os.getenv("HOLODESK_WAKE_WORD_PHRASE_LIMIT", "2.0")),
            cooldown_s=float(os.getenv("HOLODESK_WAKE_WORD_COOLDOWN", "2.0")),
            porcupine_access_key=os.getenv("HOLODESK_PORCUPINE_ACCESS_KEY", "").strip(),
        )


class WakeWordAdapter:
    """Background wake-word listener with multiple optional engines."""

    def __init__(self, callback: Callable[[], bool], config: Optional[WakeWordConfig] = None):
        self.config = config or WakeWordConfig.from_env()
        self._callback = callback
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_trigger_ts = 0.0

    def start(self) -> bool:
        if not self.config.enabled:
            logger.info("[WAKE] Wake-word disabled (HOLODESK_WAKE_WORD_ENABLED=0).")
            return False
        if self._thread and self._thread.is_alive():
            return True

        self._thread = threading.Thread(target=self._run, name="wake-word-listener", daemon=True)
        self._thread.start()
        logger.info(
            "[WAKE] Wake-word listener started. engine=%s phrase='%s'",
            self.config.engine,
            self.config.phrase,
        )
        return True

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        try:
            if self.config.engine == "porcupine":
                if not self._run_porcupine():
                    logger.warning("[WAKE] Porcupine unavailable, falling back to simple engine.")
                    self._run_simple()
                return

            if self.config.engine == "whisper":
                if not self._run_whisper():
                    logger.warning("[WAKE] Whisper wake-word engine unavailable, falling back to simple.")
                    self._run_simple()
                return

            self._run_simple()
        except Exception as exc:
            logger.warning("[WAKE] Wake-word listener stopped after error: %s", exc)

    def _should_trigger(self) -> bool:
        now = time.time()
        if now - self._last_trigger_ts < self.config.cooldown_s:
            return False
        self._last_trigger_ts = now
        return True

    def _trigger(self, transcript: str) -> None:
        if not self._should_trigger():
            return

        logger.info("[WAKE] Wake phrase detected: '%s'", transcript)
        try:
            ok = bool(self._callback())
            if not ok:
                logger.debug("[WAKE] Wake callback returned false; app may not be ready yet.")
        except Exception as exc:
            logger.warning("[WAKE] Wake callback failed: %s", exc)

    def _is_wake_phrase(self, transcript: str) -> bool:
        t = _norm_text(transcript)
        if not t:
            return False
        phrase = self.config.phrase
        return t == phrase or phrase in t

    def _run_simple(self) -> None:
        """
        Lightweight engine using SpeechRecognition + Google's free recognizer.

        This requires network access, but does not require paid API keys.
        If speech recognition fails, we keep listening and preserve existing behavior.
        """
        try:
            import speech_recognition as sr
        except Exception:
            logger.warning("[WAKE] speech_recognition not available; simple engine cannot start.")
            return

        recognizer = sr.Recognizer()

        try:
            mic = sr.Microphone()
        except Exception as exc:
            logger.warning("[WAKE] Microphone unavailable for wake-word listener: %s", exc)
            return

        with mic as source:
            try:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
            except Exception:
                pass

        while not self._stop.is_set():
            try:
                with mic as source:
                    audio = recognizer.listen(
                        source,
                        timeout=self.config.listen_timeout_s,
                        phrase_time_limit=self.config.phrase_limit_s,
                    )
                transcript = recognizer.recognize_google(audio)
                if self._is_wake_phrase(transcript):
                    self._trigger(transcript)
            except queue.Empty:
                continue
            except Exception:
                continue

    def _run_whisper(self) -> bool:
        try:
            import speech_recognition as sr
            from faster_whisper import WhisperModel
        except Exception:
            return False

        recognizer = sr.Recognizer()
        try:
            mic = sr.Microphone()
        except Exception as exc:
            logger.warning("[WAKE] Microphone unavailable for whisper wake-word: %s", exc)
            return False

        model = WhisperModel(self.config.whisper_model, device="cpu", compute_type="int8")

        while not self._stop.is_set():
            try:
                with mic as source:
                    audio = recognizer.listen(
                        source,
                        timeout=self.config.listen_timeout_s,
                        phrase_time_limit=self.config.phrase_limit_s,
                    )
            except Exception:
                continue

            tmp_path = None
            try:
                fd, tmp_path = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                wav_bytes = audio.get_wav_data()
                with wave.open(tmp_path, "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(16000)
                    wav_file.writeframes(wav_bytes)

                segments, _ = model.transcribe(
                    tmp_path,
                    beam_size=1,
                    language="en",
                    temperature=0.0,
                    condition_on_previous_text=False,
                )
                transcript = " ".join(seg.text for seg in segments).strip()
                if self._is_wake_phrase(transcript):
                    self._trigger(transcript)
            except Exception:
                continue
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

        return True

    def _run_porcupine(self) -> bool:
        """
        Optional Porcupine engine.

        Notes:
        - Porcupine requires pvporcupine + pyaudio and an access key.
        - If unavailable/misconfigured, this returns False and caller falls back.
        """
        try:
            import pvporcupine
            import pyaudio
        except Exception:
            return False

        if not self.config.porcupine_access_key:
            logger.warning("[WAKE] Porcupine engine selected but HOLODESK_PORCUPINE_ACCESS_KEY is missing.")
            return False

        phrase = self.config.phrase
        porcupine = None
        pa = None
        stream = None

        try:
            try:
                porcupine = pvporcupine.create(
                    access_key=self.config.porcupine_access_key,
                    keywords=[phrase],
                )
            except Exception as exc:
                logger.warning("[WAKE] Porcupine could not use phrase '%s': %s", phrase, exc)
                return False

            pa = pyaudio.PyAudio()
            stream = pa.open(
                rate=porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=porcupine.frame_length,
            )

            while not self._stop.is_set():
                pcm = stream.read(porcupine.frame_length, exception_on_overflow=False)
                keyword_index = porcupine.process(
                    memoryview(pcm).cast("h")
                )
                if keyword_index >= 0:
                    self._trigger(self.config.phrase)
        except Exception as exc:
            logger.warning("[WAKE] Porcupine runtime error: %s", exc)
            return False
        finally:
            try:
                if stream is not None:
                    stream.stop_stream()
                    stream.close()
            except Exception:
                pass
            try:
                if pa is not None:
                    pa.terminate()
            except Exception:
                pass
            try:
                if porcupine is not None:
                    porcupine.delete()
            except Exception:
                pass

        return True


_WAKE_WORD_ADAPTER: Optional[WakeWordAdapter] = None


def launch_wake_word_listener(trigger_callback: Callable[[], bool]) -> bool:
    global _WAKE_WORD_ADAPTER
    if _WAKE_WORD_ADAPTER is not None:
        return True

    adapter = WakeWordAdapter(callback=trigger_callback)
    started = adapter.start()
    if started:
        _WAKE_WORD_ADAPTER = adapter
    return started
