"""
GestureDetector — debounced V_GESTURE and OPEN_PALM detection.

ONLY these two gestures live here. They are "global action" gestures that
trigger system-level events (start voice / stop everything).

Thumbs up, thumbs down, and pinch are NOT here — they depend on cursor
screen coordinates and live in the main loop reading from latest_landmarks.

Two mechanisms that eliminate false positives:

1. INTENT_ZONE_Y = 0.75
   The wrist (landmark 0) must be in the TOP 75% of the camera frame.
   This filters out hands at desk level (typing position) which sit in the
   bottom ~25% of a laptop camera frame. Any visible raised hand passes.
   Note: only applied to V_GESTURE, not OPEN_PALM (stop gesture works anywhere).

2. REQUIRED_FRAMES = 6
   The same gesture must be classified on 6 consecutive frames (~0.2s at
   30fps) before it fires. A brief accidental hand position won't trigger.
   Combined with COOLDOWN_FRAMES=15 (~0.5s block after firing), rapid
   repeated triggers are prevented.
"""


class GestureDetector:

    REQUIRED_FRAMES = 6    # Consecutive frames gesture must be held (~0.2s at 30fps)
    INTENT_ZONE_Y   = 0.75 # Wrist y < 0.75 (top 75% of frame) — filters typing-level hands only
    COOLDOWN_FRAMES = 15   # Frames blocked after a gesture fires (~0.5s at 30fps)

    def __init__(self):
        self._last_gesture = None
        self._frame_count  = 0
        self._cooldown     = 0

    def detect(self, landmarks) -> str | None:
        """
        Analyze one frame of hand landmarks.
        Returns "V_GESTURE", "OPEN_PALM", or None.
        Called every frame by VisionThread.
        """
        # Still cooling down from last trigger — don't fire again yet
        if self._cooldown > 0:
            self._cooldown -= 1
            return None

        # Classify gesture first — we need to know WHAT we have before
        # deciding whether to apply the intent zone filter.
        gesture = self._classify(landmarks)

        # OPEN_PALM is a "stop everything" gesture — the user uses it at
        # any hand height (e.g. reaching forward to stop scrolling).
        # Do NOT apply the intent zone filter to it.
        if gesture == "OPEN_PALM":
            if gesture == self._last_gesture:
                self._frame_count += 1
            else:
                self._frame_count  = 1
                self._last_gesture = gesture
            if self._frame_count >= self.REQUIRED_FRAMES:
                self._reset()
                self._cooldown = self.COOLDOWN_FRAMES
                return "OPEN_PALM"
            return None

        # For V_GESTURE: apply the intent zone.
        # Wrist must be in the top 40% of frame (hand raised deliberately).
        # This eliminates false V-gesture triggers from typing/eating/etc.
        wrist_y = landmarks.landmark[0].y
        if wrist_y > self.INTENT_ZONE_Y:
            self._reset()
            return None

        if gesture is not None and gesture == self._last_gesture:
            self._frame_count += 1
        else:
            self._frame_count  = 1
            self._last_gesture = gesture

        if self._frame_count >= self.REQUIRED_FRAMES:
            confirmed = self._last_gesture
            self._reset()
            self._cooldown = self.COOLDOWN_FRAMES
            return confirmed

        return None

    def _reset(self):
        self._last_gesture = None
        self._frame_count  = 0

    def _classify(self, landmarks) -> str | None:
        """
        Classify the current hand pose into a gesture name or None.
        Uses tip-vs-base comparisons on normalized MediaPipe landmarks.

        Landmark indices used:
          0  = wrist
          5  = index MCP (knuckle)      8  = index tip
          9  = middle MCP              12  = middle tip
          13 = ring MCP                16  = ring tip
          17 = pinky MCP               20  = pinky tip
        """
        lm = landmarks.landmark

        index_up  = self._finger_up(lm, 8, 5)
        middle_up = self._finger_up(lm, 12, 9)
        ring_up   = self._finger_up(lm, 16, 13)
        pinky_up  = self._finger_up(lm, 20, 17)

        # V-GESTURE: index + middle up, ring + pinky down
        if index_up and middle_up and not ring_up and not pinky_up:
            return "V_GESTURE"

        # OPEN PALM: all four fingers up
        if index_up and middle_up and ring_up and pinky_up:
            return "OPEN_PALM"

        return None

    @staticmethod
    def _finger_up(lm, tip_idx: int, base_idx: int) -> bool:
        """
        Return True if the fingertip is above its base joint.
        In MediaPipe's normalized coords, y=0 is the top of the image,
        so 'above' means tip.y < base.y.
        """
        return lm[tip_idx].y < lm[base_idx].y
