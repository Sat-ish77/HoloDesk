"""
Shared queues — the only communication channel between threads.

Rules:
  - Threads NEVER call each other directly. Everything goes through a queue.
  - maxsize=1 on frame/landmark queues: always process the LATEST data,
    discard stale. Prevents lag buildup when a thread is slower than the camera.
  - maxsize=5 on gesture_queue: keep up to 5 pending gesture events so rapid
    gestures are not lost, but queue cannot grow unboundedly.
"""

import queue

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
