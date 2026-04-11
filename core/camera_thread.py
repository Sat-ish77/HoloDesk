"""
CameraThread — captures webcam frames on a dedicated daemon thread.

The main thread never calls cap.read(). Frames are pushed into frame_queue
and the vision thread reads them. If the vision thread is slow, old frames
are dropped automatically (maxsize=1 queue).

Windows note: cv2.CAP_DSHOW is the DirectShow backend — roughly 2x faster
to initialize than the default MSMF backend on Windows.
"""

import threading
import queue
import logging

logger = logging.getLogger(__name__)

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("opencv-python not installed — CameraThread disabled")

from core.queues import frame_queue


class CameraThread(threading.Thread):

    def __init__(self, camera_indices=(0, 1, 2)):
        super().__init__(name="CameraThread", daemon=True)
        self._camera_indices = camera_indices
        self._running = False
        self._cap = None

    def run(self):
        if not CV2_AVAILABLE:
            return

        # Try multiple indices — handles laptops where built-in is not index 0
        for idx in self._camera_indices:
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if cap.isOpened():
                self._cap = cap
                logger.info("Camera opened at index %d", idx)
                break

        if self._cap is None:
            logger.warning("No camera found — gesture features disabled gracefully")
            return

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self._cap.set(cv2.CAP_PROP_FPS, 30)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Don't buffer old frames in driver

        self._running = True
        while self._running:
            ret, frame = self._cap.read()
            if not ret:
                continue

            # Mirror horizontally so gestures feel natural (like a mirror)
            frame = cv2.flip(frame, 1)

            # Non-blocking put: if queue is full, drop the stale frame and put the new one
            try:
                frame_queue.put_nowait(frame)
            except queue.Full:
                try:
                    frame_queue.get_nowait()
                    frame_queue.put_nowait(frame)
                except Exception:
                    pass

    def stop(self):
        self._running = False
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        logger.info("CameraThread stopped")
