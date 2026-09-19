from vision.gesture_detector import SwipeDetector


def feed(det, xs):
    return [g for g in (det.update(x) for x in xs) if g]


def test_fast_sweep_fires_once_in_its_direction():
    assert feed(SwipeDetector(), [0.30, 0.40, 0.50, 0.60, 0.70, 0.72, 0.73]) == ["SWIPE_RIGHT"]
    assert feed(SwipeDetector(), [0.70, 0.55, 0.40, 0.30]) == ["SWIPE_LEFT"]


def test_slow_drift_and_jitter_do_not_fire():
    drift = [0.30 + i * 0.01 for i in range(40)]  # 0.40 of the frame, but over ~2.5 s
    jitter = [0.50, 0.52, 0.49, 0.51, 0.50] * 6
    assert feed(SwipeDetector(), drift) == []
    assert feed(SwipeDetector(), jitter) == []


def test_moving_hand_suppresses_static_gestures_until_it_settles():
    det = SwipeDetector()
    for x in (0.50, 0.50, 0.50):
        det.update(x)
    assert not det.is_moving()
    for x in (0.55, 0.60):
        det.update(x)
    assert det.is_moving()
