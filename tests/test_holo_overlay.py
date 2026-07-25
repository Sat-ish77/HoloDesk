from types import SimpleNamespace

from app.holo_overlay import (
    HoloOverlayState,
    LaserHandsGame,
    TicTacToeGame,
    MODE_CHAT,
    MODE_GAME_MENU,
    MODE_LASER,
    MODE_MISSION,
    MODE_NORMAL,
    MODE_ORB_MENU,
    MODE_TICTACTOE,
)
from core.vision_thread import VisionThread


def test_overlay_state_transitions():
    state = HoloOverlayState(1280, 720)
    assert state.mode == MODE_NORMAL
    state.toggle_chat()
    assert state.mode == MODE_CHAT
    state.start_mission()
    assert state.mode == MODE_MISSION
    assert state.mission.steps[0].status == "active"
    state.start_laser_game()
    assert state.mode == MODE_LASER
    assert state.laser_game.running is True
    state.open_orb_menu()
    assert state.mode == MODE_ORB_MENU
    state.open_game_menu()
    assert state.mode == MODE_GAME_MENU
    state.start_tictactoe()
    assert state.mode == MODE_TICTACTOE
    state.stop_active_mode()
    assert state.mode == MODE_NORMAL


def test_mission_advance_marks_steps():
    state = HoloOverlayState(1280, 720)
    state.start_mission()
    state.mission.advance()
    assert state.mission.steps[0].status == "done"
    assert state.mission.steps[1].status == "active"


def test_chat_scroll_and_maximize_state():
    state = HoloOverlayState(1280, 720)
    state.toggle_chat()
    for idx in range(12):
        state.add_message("holo", f"message {idx}")
    state.scroll_chat(3)
    assert state.chat_scroll == 3
    state.toggle_chat_maximized()
    assert state.chat_maximized is True
    assert state.chat_w > 430
    state.close_chat()
    assert state.mode == MODE_NORMAL


def test_laser_hit_detection_scores_with_two_hands():
    game = LaserHandsGame(1280, 720)
    game.start()
    game.targets[0].x = 320
    game.targets[0].y = 240
    hand = _fake_hand(index=(320 / 1280, 240 / 720), wrist=(0.20, 0.35), pinch=True)
    beams = game.update([{"landmarks": hand, "label": "Left"}, {"landmarks": hand, "label": "Right"}])
    assert len(beams) == 2
    assert game.score > 0


def test_tictactoe_voice_cell_mapping_and_win():
    game = TicTacToeGame()
    game.start()
    assert game.place("top left")
    assert game.place("center")
    assert game.place("top")
    assert game.place("right")
    assert game.place("top right")
    assert game.winner == "X"


def test_vision_thread_builds_two_hand_payload():
    results = SimpleNamespace(
        multi_hand_landmarks=["left_lm", "right_lm"],
        multi_handedness=[
            SimpleNamespace(classification=[SimpleNamespace(label="Left", score=0.91)]),
            SimpleNamespace(classification=[SimpleNamespace(label="Right", score=0.88)]),
        ],
    )
    payload = VisionThread._build_hands_payload(results)
    assert payload == [
        {"landmarks": "left_lm", "label": "Left", "score": 0.91},
        {"landmarks": "right_lm", "label": "Right", "score": 0.88},
    ]


def _fake_hand(index, wrist, pinch=False):
    points = [SimpleNamespace(x=0.0, y=0.0) for _ in range(21)]
    points[0] = SimpleNamespace(x=wrist[0], y=wrist[1])
    points[8] = SimpleNamespace(x=index[0], y=index[1])
    points[4] = SimpleNamespace(x=index[0] + (0.02 if pinch else 0.20), y=index[1])
    return SimpleNamespace(landmark=points)
