"""
VisionThread — reads camera frames, runs MediaPipe, detects gestures.

Outputs to two queues:
  landmark_queue — hand_landmarks object (or None when no hand visible)
  gesture_queue  — "V_GESTURE" | "OPEN_PALM" strings (only on confirmed trigger)

MediaPipe is initialized HERE, on this thread, not on the main thread.
model_complexity=0 is the lightweight model — fast enough for 30fps on CPU,
still accurate for the gestures we need.
"""

import threading
import queue
import logging

logger = logging.getLogger(__name__)

try:
    cv2 = None
    mp = None
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    logger.warning("mediapipe or opencv not installed — VisionThread disabled")

from core.queues import frame_queue, landmark_queue, gesture_queue
from vision.gesture_detector import GestureDetector


class VisionThread(threading.Thread):

    def __init__(self):
        super().__init__(name="VisionThread", daemon=True)
        self._running = False
        self._detector = GestureDetector()

    def run(self):
        if not MEDIAPIPE_AVAILABLE:
            return
        global cv2, mp
        if cv2 is None or mp is None:
            try:
                import cv2 as _cv2
                import mediapipe as _mp
                cv2 = _cv2
                mp = _mp
            except Exception as exc:
                logger.warning("mediapipe/opencv unavailable - VisionThread disabled: %s", exc)
                return

        # Initialize MediaPipe on THIS thread (not the main thread)
        hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            model_complexity=0,          # Faster than default (1), good enough for gestures
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        self._running = True
        while self._running:
            # Block up to 0.1s waiting for a frame — avoids busy-spinning the CPU
            try:
                frame = frame_queue.get(timeout=0.1)
            except queue.Empty:
                # No frame yet — signal "no hand" so main loop cursor disappears
                self._put_landmarks([])
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb)

            if results.multi_hand_landmarks:
                hands_payload = self._build_hands_payload(results)
                self._put_landmarks(hands_payload)

                # Run debounced gesture detector (intent zone + 8-frame buffer)
                gesture = self._detector.detect(hands_payload[0]["landmarks"])
                if gesture is not None:
                    try:
                        gesture_queue.put_nowait(gesture)
                        logger.debug("Gesture queued: %s", gesture)
                    except queue.Full:
                        pass  # Drop if queue full — no backlog
            else:
                self._put_landmarks([])

        hands.close()

    def _put_landmarks(self, landmarks):
        """Replace stale landmark data with fresh (maxsize=1 queue)."""
        try:
            landmark_queue.put_nowait(landmarks)
        except queue.Full:
            try:
                landmark_queue.get_nowait()
                landmark_queue.put_nowait(landmarks)
            except Exception:
                pass

    @staticmethod
    def _build_hands_payload(results):
        payload = []
        handedness = results.multi_handedness or []
        for idx, hand_lm in enumerate(results.multi_hand_landmarks):
            label = ""
            score = 0.0
            if idx < len(handedness) and handedness[idx].classification:
                cls = handedness[idx].classification[0]
                label = cls.label or ""
                score = float(cls.score or 0.0)
            payload.append({"landmarks": hand_lm, "label": label, "score": score})
        return payload

    def stop(self):
        self._running = False
        logger.info("VisionThread stopped")
