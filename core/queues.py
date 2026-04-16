"""
Shared queues + small shared state — the only communication channel between threads.

Rules:
  - Threads NEVER call each other directly. Everything goes through a queue.
  - maxsize=1 on frame/landmark queues: always process the LATEST data,
    discard stale. Prevents lag buildup when a thread is slower than the camera.
  - maxsize=5 on gesture_queue: keep up to 5 pending gesture events so rapid
    gestures are not lost, but queue cannot grow unboundedly.
  - tts_state: lightweight shared dict so the voice thread can reason about
    whether a transcription is an echo of what we JUST spoke (text + end_ts).
    Updated by speak(), read by the echo guard. Not a queue because it's a
    single-writer / single-reader fact, not an event stream.
"""

import queue
import threading

# Orchestrator command queue (voice/UI -> orchestrator)
# Kept bounded so runaway loops can't eat RAM.
command_queue = queue.Queue(maxsize=50)

# Orchestrator replies (orchestrator -> voice thread)
# maxsize=1 enforces strict request/response sequencing.
voice_reply_queue = queue.Queue(maxsize=1)

# Raw BGR frames from the camera (latest only — old frames discarded)
frame_queue = queue.Queue(maxsize=1)

# MediaPipe hand_landmarks object OR None when no hand detected (latest only)
landmark_queue = queue.Queue(maxsize=1)

# Confirmed gesture strings: "V_GESTURE" | "OPEN_PALM"
# Only fires after 8-frame debounce + intent zone check in GestureDetector
gesture_queue = queue.Queue(maxsize=5)

# Cross-thread status/response events (voice thread -> UI/main loop)
response_queue = queue.Queue(maxsize=50)

# Shared TTS state — updated by speak(), read by the echo guard.
# text:       the exact phrase we most recently spoke (lowercased).
# end_ts:     monotonic-ish wall clock when speech finished (0.0 if never spoken).
# The lock is held only for the brief assignment; reads can be dirty — that's
# fine because a stale read just makes the echo guard slightly more lenient.
tts_state = {
    "text": "",
    "end_ts": 0.0,
}
tts_state_lock = threading.Lock()


def record_tts_finished(text: str) -> None:
    """Called by speak() after a TTS utterance completes."""
    import time as _t
    with tts_state_lock:
        tts_state["text"] = (text or "").lower().strip()
        tts_state["end_ts"] = _t.time()


def read_tts_state() -> tuple[str, float]:
    with tts_state_lock:
        return tts_state["text"], tts_state["end_ts"]
