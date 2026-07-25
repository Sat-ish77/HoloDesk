"""Futuristic HoloDesk overlay widgets.

This module keeps the visual/chat/game state out of app/main.py. The classes
are intentionally lightweight so the transparent Pygame overlay stays fast.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
import json
from pathlib import Path


MODE_NORMAL = "normal"
MODE_CHAT = "chat_expanded"
MODE_MISSION = "mission"
MODE_LASER = "laser_game"
MODE_ORB_MENU = "orb_menu"
MODE_GAME_MENU = "game_menu"
MODE_FLAPPY = "flappy_game"
MODE_TICTACTOE = "tictactoe_game"


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def point_in_circle(point: tuple[int, int], center: tuple[int, int], radius: float) -> bool:
    dx = point[0] - center[0]
    dy = point[1] - center[1]
    return (dx * dx + dy * dy) <= radius * radius


@dataclass
class ChatMessage:
    role: str
    text: str
    ts: float = field(default_factory=time.time)


@dataclass
class MissionStep:
    title: str
    status: str = "pending"


class MissionState:
    def __init__(self):
        self.steps = [
            MissionStep("Open Outlook"),
            MissionStep("Search contact"),
            MissionStep("Draft response"),
            MissionStep("Verify screen"),
            MissionStep("Wait for confirmation"),
        ]
        self.active = False

    def start(self):
        self.active = True
        for step in self.steps:
            step.status = "pending"
        self.steps[0].status = "active"

    def stop(self):
        self.active = False

    def advance(self):
        if not self.active:
            self.start()
            return
        for idx, step in enumerate(self.steps):
            if step.status == "active":
                step.status = "done"
                if idx + 1 < len(self.steps):
                    self.steps[idx + 1].status = "active"
                return
        self.active = False

    @property
    def progress(self) -> tuple[int, int]:
        done = sum(1 for step in self.steps if step.status == "done")
        return done, len(self.steps)


@dataclass
class LaserTarget:
    x: float
    y: float
    radius: float
    vx: float
    vy: float


class LaserHandsGame:
    DURATION_SECONDS = 45.0

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.running = False
        self.started_at = 0.0
        self.score = 0
        self.combo = 0
        self.targets: list[LaserTarget] = []
        self._rng = random.Random(73)

    def start(self):
        self.running = True
        self.started_at = time.time()
        self.score = 0
        self.combo = 0
        self.targets = [self._spawn_target() for _ in range(4)]

    def stop(self):
        self.running = False
        self.combo = 0

    def remaining(self) -> int:
        if not self.running:
            return 0
        return max(0, int(self.DURATION_SECONDS - (time.time() - self.started_at)))

    def update(self, hands: list[dict]) -> list[tuple[tuple[int, int], tuple[int, int], bool]]:
        if not self.running:
            return []
        if self.remaining() <= 0:
            self.running = False
            return []

        for target in self.targets:
            target.x += target.vx
            target.y += target.vy
            if target.x < target.radius or target.x > self.width - target.radius:
                target.vx *= -1
            if target.y < target.radius or target.y > self.height - target.radius:
                target.vy *= -1

        beams = []
        hits_this_frame = 0
        for hand in hands[:2]:
            lm = getattr(hand.get("landmarks"), "landmark", None)
            if not lm:
                continue
            index_tip = lm[8]
            wrist = lm[0]
            start = (int(wrist.x * self.width), int(wrist.y * self.height))
            end = (int(index_tip.x * self.width), int(index_tip.y * self.height))
            charged = self._is_pinching(lm)
            hit = self._hit_target(end, charged=charged)
            if hit:
                hits_this_frame += 1
            beams.append((start, end, charged))

        if hits_this_frame:
            self.combo += hits_this_frame
            self.score += hits_this_frame * (10 + min(self.combo, 10) * 2)
        else:
            self.combo = max(0, self.combo - 1)
        return beams

    def _hit_target(self, point: tuple[int, int], charged: bool = False) -> bool:
        hit_radius_bonus = 18 if charged else 0
        for idx, target in enumerate(self.targets):
            dx = point[0] - target.x
            dy = point[1] - target.y
            if math.hypot(dx, dy) <= target.radius + hit_radius_bonus:
                self.targets[idx] = self._spawn_target()
                return True
        return False

    def _spawn_target(self) -> LaserTarget:
        return LaserTarget(
            x=self._rng.randint(180, max(181, self.width - 180)),
            y=self._rng.randint(130, max(131, self.height - 160)),
            radius=self._rng.randint(20, 34),
            vx=self._rng.choice([-1, 1]) * self._rng.uniform(1.2, 3.0),
            vy=self._rng.choice([-1, 1]) * self._rng.uniform(0.9, 2.4),
        )

    @staticmethod
    def _is_pinching(lm) -> bool:
        thumb = lm[4]
        index = lm[8]
        return math.hypot(thumb.x - index.x, thumb.y - index.y) < 0.055


class FlappyHoloGame:
    DURATION_SECONDS = 45.0

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.running = False
        self.started_at = 0.0
        self.x = 230
        self.y = height / 2
        self.vy = 0.0
        self.score = 0
        self.obstacles: list[dict] = []
        self._rng = random.Random(91)

    def start(self):
        self.running = True
        self.started_at = time.time()
        self.x = 230
        self.y = self.height / 2
        self.vy = 0.0
        self.score = 0
        self.obstacles = [self._spawn_obstacle(self.width + i * 290) for i in range(4)]

    def stop(self):
        self.running = False

    def remaining(self) -> int:
        if not self.running:
            return 0
        return max(0, int(self.DURATION_SECONDS - (time.time() - self.started_at)))

    def update(self, hands: list[dict]):
        if not self.running:
            return
        if self.remaining() <= 0:
            self.running = False
            return

        hand_y = self._hand_y(hands)
        if hand_y is not None:
            target_y = hand_y * self.height
            self.vy += (target_y - self.y) * 0.035
        else:
            self.vy += 0.32
        self.vy = clamp(self.vy, -9, 9)
        self.y += self.vy

        for obstacle in self.obstacles:
            obstacle["x"] -= 4.2
            if obstacle["x"] < -80:
                obstacle.update(self._spawn_obstacle(self.width + 80))
                self.score += 1

        if self.y < 20 or self.y > self.height - 20 or self._collides():
            self.running = False

    def _spawn_obstacle(self, x: float) -> dict:
        gap = self._rng.randint(160, 220)
        center = self._rng.randint(150, max(151, self.height - 150))
        return {"x": x, "gap_y": center, "gap": gap, "w": 70}

    @staticmethod
    def _hand_y(hands: list[dict]) -> float | None:
        if not hands:
            return None
        lm = getattr(hands[0].get("landmarks"), "landmark", None)
        if not lm:
            return None
        return lm[8].y

    def _collides(self) -> bool:
        for obstacle in self.obstacles:
            if obstacle["x"] <= self.x <= obstacle["x"] + obstacle["w"]:
                half_gap = obstacle["gap"] / 2
                if self.y < obstacle["gap_y"] - half_gap or self.y > obstacle["gap_y"] + half_gap:
                    return True
        return False


class TicTacToeGame:
    CELLS = {
        "top left": 0, "top": 1, "top center": 1, "top right": 2,
        "left": 3, "middle left": 3, "center": 4, "middle": 4, "right": 5, "middle right": 5,
        "bottom left": 6, "bottom": 7, "bottom center": 7, "bottom right": 8,
    }

    def __init__(self):
        self.board = [""] * 9
        self.current = "X"
        self.winner = ""
        self.running = False

    def start(self):
        self.board = [""] * 9
        self.current = "X"
        self.winner = ""
        self.running = True

    def stop(self):
        self.running = False

    def place(self, cell: int | str) -> bool:
        idx = self.cell_index(cell)
        if idx is None or self.winner or self.board[idx]:
            return False
        self.board[idx] = self.current
        self.winner = self._winner()
        if not self.winner:
            self.current = "O" if self.current == "X" else "X"
        return True

    @classmethod
    def cell_index(cls, cell: int | str) -> int | None:
        if isinstance(cell, int):
            return cell if 0 <= cell < 9 else None
        text = str(cell).strip().lower()
        if text.isdigit():
            n = int(text) - 1
            return n if 0 <= n < 9 else None
        return cls.CELLS.get(text)

    def _winner(self) -> str:
        wins = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6))
        for a, b, c in wins:
            if self.board[a] and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        if all(self.board):
            return "draw"
        return ""


class HoloOverlayState:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.mode = MODE_NORMAL
        self.chat_messages: list[ChatMessage] = []
        self.input_text = ""
        self.chat_x = 34
        self.chat_y = 70
        self.chat_w = 430
        self.chat_h = 500
        self.chat_scroll = 0
        self.chat_maximized = False
        self.dragging_chat = False
        self._chat_drag_offset = (0, 0)
        self.orb_x = width - 74
        self.orb_y = height // 2
        self.orb_radius = 28
        self.dragging_orb = False
        self.mission = MissionState()
        self.laser_game = LaserHandsGame(width, height)
        self.flappy_game = FlappyHoloGame(width, height)
        self.tictactoe_game = TicTacToeGame()
        self.last_beams: list[tuple[tuple[int, int], tuple[int, int], bool]] = []
        self.quick_actions = self._load_quick_actions()

    def toggle_chat(self):
        self.mode = MODE_NORMAL if self.mode == MODE_CHAT else MODE_CHAT
        self.chat_scroll = 0

    def open_orb_menu(self):
        self.mode = MODE_ORB_MENU

    def open_game_menu(self):
        self.mode = MODE_GAME_MENU

    def close_chat(self):
        if self.mode == MODE_CHAT:
            self.mode = MODE_NORMAL

    def toggle_chat_maximized(self):
        self.chat_maximized = not self.chat_maximized
        if self.chat_maximized:
            self.chat_x = 24
            self.chat_y = 40
            self.chat_w = min(720, self.width - 48)
            self.chat_h = min(620, self.height - 80)
        else:
            self.chat_x = 34
            self.chat_y = 70
            self.chat_w = 430
            self.chat_h = 500

    def scroll_chat(self, amount: int):
        max_scroll = max(0, len(self.chat_messages) - 6)
        self.chat_scroll = int(clamp(self.chat_scroll + amount, 0, max_scroll))

    def start_mission(self):
        self.mode = MODE_MISSION
        self.mission.start()

    def start_laser_game(self):
        self.mode = MODE_LASER
        self.laser_game.start()

    def start_flappy_game(self):
        self.mode = MODE_FLAPPY
        self.flappy_game.start()

    def start_tictactoe(self):
        self.mode = MODE_TICTACTOE
        self.tictactoe_game.start()

    def stop_active_mode(self):
        if self.mode == MODE_LASER:
            self.laser_game.stop()
        if self.mode == MODE_FLAPPY:
            self.flappy_game.stop()
        if self.mode == MODE_TICTACTOE:
            self.tictactoe_game.stop()
        if self.mode == MODE_MISSION:
            self.mission.stop()
        self.mode = MODE_NORMAL

    def add_message(self, role: str, text: str):
        cleaned = (text or "").strip()
        if not cleaned:
            return
        self.chat_messages.append(ChatMessage(role=role, text=cleaned))
        self.chat_messages = self.chat_messages[-40:]
        if role == "you":
            self.chat_scroll = 0

    def handle_text_key(self, event, pygame_module) -> str | None:
        if self.mode != MODE_CHAT:
            return None
        if event.key == pygame_module.K_BACKSPACE:
            self.input_text = self.input_text[:-1]
            return None
        if event.key == pygame_module.K_PAGEUP:
            self.scroll_chat(3)
            return None
        if event.key == pygame_module.K_PAGEDOWN:
            self.scroll_chat(-3)
            return None
        if event.key == pygame_module.K_HOME:
            self.chat_scroll = max(0, len(self.chat_messages) - 6)
            return None
        if event.key == pygame_module.K_END:
            self.chat_scroll = 0
            return None
        if event.key == pygame_module.K_F11:
            self.toggle_chat_maximized()
            return None
        if event.key == pygame_module.K_RETURN:
            msg = self.input_text.strip()
            self.input_text = ""
            if msg:
                self.add_message("you", msg)
                return msg
            return None
        if event.key == pygame_module.K_ESCAPE:
            self.mode = MODE_NORMAL
            return None
        if event.unicode and len(event.unicode) == 1 and event.unicode.isprintable():
            if len(self.input_text) < 180:
                self.input_text += event.unicode
        return None

    def update_hand_interaction(self, cursor: tuple[int, int], is_pinching: bool):
        if self.mode == MODE_CHAT and is_pinching and (self.dragging_chat or self._point_in_chat_header(cursor)):
            if not self.dragging_chat:
                self._chat_drag_offset = (cursor[0] - self.chat_x, cursor[1] - self.chat_y)
            self.dragging_chat = True
            self.chat_maximized = False
            self.chat_x = int(clamp(cursor[0] - self._chat_drag_offset[0], 8, self.width - self.chat_w - 8))
            self.chat_y = int(clamp(cursor[1] - self._chat_drag_offset[1], 8, self.height - self.chat_h - 8))
            return
        if not is_pinching:
            self.dragging_chat = False

        if is_pinching and (self.dragging_orb or point_in_circle(cursor, (self.orb_x, self.orb_y), self.orb_radius + 12)):
            self.dragging_orb = True
            self.orb_x = int(clamp(cursor[0], 70, self.width - 70))
            self.orb_y = int(clamp(cursor[1], 70, self.height - 70))
        elif not is_pinching:
            if self.dragging_orb and point_in_circle(cursor, (self.orb_x, self.orb_y), self.orb_radius + 8):
                self.open_orb_menu()
            self.dragging_orb = False

    def handle_mouse_down(self, pos: tuple[int, int], button: int):
        if self.mode != MODE_CHAT:
            return
        if button == 4:
            self.scroll_chat(2)
            return
        if button == 5:
            self.scroll_chat(-2)
            return
        if button != 1:
            return
        rect = self.chat_rect()
        close_rect = (rect.right - 34, rect.y + 12, 22, 22)
        max_rect = (rect.right - 62, rect.y + 12, 22, 22)
        min_rect = (rect.right - 90, rect.y + 12, 22, 22)
        if self._point_in_rect(pos, close_rect):
            self.close_chat()
        elif self._point_in_rect(pos, max_rect):
            self.toggle_chat_maximized()
        elif self._point_in_rect(pos, min_rect):
            self.mode = MODE_NORMAL

    def chat_rect(self):
        return self._rect_type()(self.chat_x, self.chat_y, self.chat_w, self.chat_h)

    def _point_in_chat_header(self, pos: tuple[int, int]) -> bool:
        return self.chat_x <= pos[0] <= self.chat_x + self.chat_w and self.chat_y <= pos[1] <= self.chat_y + 48

    @staticmethod
    def _point_in_rect(pos: tuple[int, int], rect_tuple: tuple[int, int, int, int]) -> bool:
        x, y, w, h = rect_tuple
        return x <= pos[0] <= x + w and y <= pos[1] <= y + h

    @staticmethod
    def _rect_type():
        # Late import keeps pure state tests independent from pygame.
        import pygame
        return pygame.Rect

    def update_game(self, hands: list[dict]):
        if self.mode == MODE_LASER:
            self.last_beams = self.laser_game.update(hands)
            if not self.laser_game.running:
                self.mode = MODE_NORMAL
        elif self.mode == MODE_FLAPPY:
            self.flappy_game.update(hands)
            if not self.flappy_game.running:
                self.mode = MODE_GAME_MENU
        else:
            self.last_beams = []

    @staticmethod
    def _load_quick_actions() -> list[dict]:
        default = [
            {"label": "Facebook", "command": "open facebook in chrome"},
            {"label": "YouTube", "command": "open youtube in chrome"},
            {"label": "Netflix", "command": "open netflix in chrome"},
            {"label": "Gmail", "command": "open gmail in chrome"},
            {"label": "Games", "command": "game menu"},
            {"label": "Mission", "command": "mission mode"},
        ]
        path = Path(__file__).resolve().parent.parent / "config" / "quick_actions.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list) and all(isinstance(item, dict) for item in data):
                return data
        except Exception:
            pass
        return default


class HoloOverlayRenderer:
    def __init__(self, pygame_module):
        self.pg = pygame_module
        self.font = pygame_module.font.Font(None, 25)
        self.small = pygame_module.font.Font(None, 20)
        self.medium = pygame_module.font.Font(None, 32)
        self.large = pygame_module.font.Font(None, 46)

    def draw(self, surface, state: HoloOverlayState, voice_state: str, audio_level: float, frame_count: int):
        self._draw_orb(surface, state, voice_state, audio_level, frame_count)
        if state.mode == MODE_CHAT:
            self._draw_chat(surface, state)
        elif state.mode == MODE_ORB_MENU:
            self._draw_orb_menu(surface, state, frame_count)
        elif state.mode == MODE_GAME_MENU:
            self._draw_game_menu(surface, state, frame_count)
        elif state.mode == MODE_MISSION:
            self._draw_mission(surface, state)
        elif state.mode == MODE_LASER:
            self._draw_laser_game(surface, state)
        elif state.mode == MODE_FLAPPY:
            self._draw_flappy(surface, state)
        elif state.mode == MODE_TICTACTOE:
            self._draw_tictactoe(surface, state)

    def _draw_orb(self, surface, state, voice_state: str, audio_level: float, frame_count: int):
        pg = self.pg
        pulse = (math.sin(frame_count * 0.12) + 1) / 2
        active = voice_state in {"WAKE", "LISTENING", "PROCESSING", "SPEAKING"} or state.mode != MODE_NORMAL
        radius = state.orb_radius + int(8 * pulse * (1 + audio_level))
        core = (50, 210, 255) if active else (95, 140, 185)
        if state.mode == MODE_LASER:
            core = (255, 70, 180)
        elif state.mode == MODE_MISSION:
            core = (80, 255, 145)
        for i in range(4, 0, -1):
            alpha_color = tuple(max(0, min(255, c - i * 18)) for c in core)
            pg.draw.circle(surface, alpha_color, (state.orb_x, state.orb_y), radius + i * 9, 1)
        pg.draw.circle(surface, (18, 28, 42), (state.orb_x, state.orb_y), radius + 2)
        pg.draw.circle(surface, core, (state.orb_x, state.orb_y), radius, 2)
        pg.draw.circle(surface, (235, 250, 255), (state.orb_x - radius // 4, state.orb_y - radius // 4), max(4, radius // 5))
        for angle_offset in (0, 70, 140):
            angle = frame_count * 0.04 + math.radians(angle_offset)
            rx = int(math.cos(angle) * (radius + 13))
            ry = int(math.sin(angle) * (radius * 0.45))
            pg.draw.circle(surface, (170, 240, 255), (state.orb_x + rx, state.orb_y + ry), 3)

    def _draw_orb_menu(self, surface, state: HoloOverlayState, frame_count: int):
        pg = self.pg
        center = (state.width - 190, state.height // 2)
        pg.draw.circle(surface, (6, 12, 22), center, 122)
        pg.draw.circle(surface, (70, 210, 255), center, 122, 2)
        pg.draw.circle(surface, (35, 80, 115), center, 52, 1)
        pg.draw.circle(surface, (80, 220, 255), center, 24)
        title = self.medium.render("Holo Orb", True, (225, 250, 255))
        surface.blit(title, (center[0] - 55, center[1] - 156))
        actions = state.quick_actions[:9]
        for idx, action in enumerate(actions):
            angle = frame_count * 0.012 + (math.tau * idx / max(1, len(actions)))
            radius = 82 + (idx % 2) * 26
            x = center[0] + int(math.cos(angle) * radius)
            y = center[1] + int(math.sin(angle) * radius * 0.72)
            pg.draw.circle(surface, (24, 42, 62), (x, y), 24)
            pg.draw.circle(surface, (110, 235, 255), (x, y), 24, 1)
            label = str(action.get("label", "?"))[:8]
            text = self.small.render(label, True, (230, 250, 255))
            surface.blit(text, text.get_rect(center=(x, y)))

    def _draw_game_menu(self, surface, state: HoloOverlayState, frame_count: int):
        pg = self.pg
        rect = pg.Rect(state.width - 430, 105, 390, 360)
        pg.draw.rect(surface, (7, 12, 24), rect, border_radius=8)
        pg.draw.rect(surface, (110, 190, 255), rect, 2, border_radius=8)
        surface.blit(self.large.render("Games", True, (225, 245, 255)), (rect.x + 22, rect.y + 20))
        games = [("Laser Hands", "F5 / say play laser"), ("Tic Tac Toe", "say tic tac toe")]
        for idx, (name, hint) in enumerate(games):
            y = rect.y + 96 + idx * 76
            pg.draw.rect(surface, (18, 32, 52), pg.Rect(rect.x + 24, y, rect.width - 48, 54), border_radius=6)
            pg.draw.circle(surface, (255, 80 + idx * 50, 190 - idx * 35), (rect.x + 52, y + 27), 13)
            surface.blit(self.medium.render(name, True, (235, 248, 255)), (rect.x + 78, y + 8))
            surface.blit(self.small.render(hint, True, (150, 180, 205)), (rect.x + 78, y + 34))

    def _draw_chat(self, surface, state: HoloOverlayState):
        pg = self.pg
        rect = pg.Rect(state.chat_x, state.chat_y, state.chat_w, state.chat_h)
        pg.draw.rect(surface, (12, 20, 28), rect, border_radius=8)
        pg.draw.rect(surface, (80, 220, 255), rect, 2, border_radius=8)
        title = self.medium.render("HoloDesk", True, (220, 245, 255))
        surface.blit(title, (rect.x + 18, rect.y + 14))
        self._draw_window_button(surface, rect.right - 82, rect.y + 14, "_")
        self._draw_window_button(surface, rect.right - 54, rect.y + 14, "[]")
        self._draw_window_button(surface, rect.right - 26, rect.y + 14, "x")
        y = rect.y + 58
        messages = state.chat_messages
        if state.chat_scroll:
            end = max(0, len(messages) - state.chat_scroll)
            visible = messages[max(0, end - 6):end]
        else:
            visible = messages[-6:]
        for msg in visible:
            color = (170, 255, 205) if msg.role == "you" else (210, 225, 255)
            label = "You" if msg.role == "you" else "Holo"
            for line in self._wrap(f"{label}: {msg.text}", max(36, (rect.width - 40) // 8)):
                if y > rect.bottom - 72:
                    break
                surface.blit(self.font.render(line, True, color), (rect.x + 18, y))
                y += 24
            y += 6
        input_rect = pg.Rect(rect.x + 16, rect.bottom - 54, rect.width - 32, 36)
        pg.draw.rect(surface, (20, 33, 45), input_rect, border_radius=6)
        pg.draw.rect(surface, (70, 120, 150), input_rect, 1, border_radius=6)
        typed = state.input_text or "type here, enter to send"
        surface.blit(self.font.render(typed[-48:], True, (235, 245, 255) if state.input_text else (120, 140, 155)), (input_rect.x + 10, input_rect.y + 9))

    def _draw_window_button(self, surface, x: int, y: int, label: str):
        pg = self.pg
        rect = pg.Rect(x, y, 20, 20)
        pg.draw.rect(surface, (24, 42, 54), rect, border_radius=4)
        pg.draw.rect(surface, (78, 155, 185), rect, 1, border_radius=4)
        text = self.small.render(label, True, (215, 240, 250))
        surface.blit(text, text.get_rect(center=rect.center))

    def _draw_mission(self, surface, state: HoloOverlayState):
        pg = self.pg
        rect = pg.Rect(34, 86, 390, 320)
        pg.draw.rect(surface, (9, 24, 22), rect, border_radius=8)
        pg.draw.rect(surface, (80, 255, 145), rect, 2, border_radius=8)
        done, total = state.mission.progress
        surface.blit(self.medium.render(f"Mission Mode {done}/{total}", True, (205, 255, 225)), (rect.x + 18, rect.y + 16))
        y = rect.y + 62
        colors = {"pending": (120, 145, 150), "active": (255, 235, 120), "done": (90, 255, 150), "blocked": (255, 110, 110)}
        for step in state.mission.steps:
            color = colors.get(step.status, (200, 220, 220))
            pg.draw.circle(surface, color, (rect.x + 28, y + 9), 7)
            surface.blit(self.font.render(step.title, True, color), (rect.x + 46, y))
            y += 36

    def _draw_laser_game(self, surface, state: HoloOverlayState):
        pg = self.pg
        game = state.laser_game
        pg.draw.rect(surface, (4, 7, 14), pg.Rect(0, 0, state.width, state.height))
        for idx in range(0, state.width, 80):
            shade = 22 if idx % 160 == 0 else 14
            pg.draw.line(surface, (shade, shade + 4, shade + 18), (idx, 0), (idx, state.height), 1)
        for idx in range(0, state.height, 80):
            shade = 22 if idx % 160 == 0 else 14
            pg.draw.line(surface, (shade, shade + 4, shade + 18), (0, idx), (state.width, idx), 1)
        for target in game.targets:
            pg.draw.circle(surface, (255, 60, 175), (int(target.x), int(target.y)), int(target.radius + 9), 1)
            pg.draw.circle(surface, (255, 230, 120), (int(target.x), int(target.y)), int(target.radius), 2)
        for start, end, charged in state.last_beams:
            color = (255, 245, 120) if charged else (70, 225, 255)
            pg.draw.line(surface, color, start, end, 5 if charged else 3)
            pg.draw.circle(surface, color, end, 9 if charged else 6)
        hud = f"Laser Hands  Score {game.score}  Combo {game.combo}  Time {game.remaining()}s"
        surface.blit(self.medium.render(hud, True, (255, 235, 255)), (34, 34))

    def _draw_flappy(self, surface, state: HoloOverlayState):
        pg = self.pg
        game = state.flappy_game
        pg.draw.rect(surface, (5, 12, 22), pg.Rect(0, 0, state.width, state.height))
        for obstacle in game.obstacles:
            x = int(obstacle["x"])
            w = int(obstacle["w"])
            gap_y = int(obstacle["gap_y"])
            half = int(obstacle["gap"] / 2)
            color = (70, 240, 180)
            pg.draw.rect(surface, color, pg.Rect(x, 0, w, gap_y - half), border_radius=5)
            pg.draw.rect(surface, color, pg.Rect(x, gap_y + half, w, state.height - gap_y), border_radius=5)
        pg.draw.circle(surface, (255, 220, 80), (int(game.x), int(game.y)), 18)
        pg.draw.circle(surface, (255, 255, 230), (int(game.x + 6), int(game.y - 6)), 5)
        hud = f"Flappy Holo  Score {game.score}  Time {game.remaining()}s"
        surface.blit(self.medium.render(hud, True, (235, 250, 255)), (34, 34))

    def _draw_tictactoe(self, surface, state: HoloOverlayState):
        pg = self.pg
        game = state.tictactoe_game
        rect = pg.Rect(state.width // 2 - 180, 90, 360, 360)
        pg.draw.rect(surface, (8, 14, 24), rect, border_radius=8)
        pg.draw.rect(surface, (120, 210, 255), rect, 2, border_radius=8)
        cell = rect.width // 3
        for i in (1, 2):
            pg.draw.line(surface, (90, 150, 190), (rect.x + i * cell, rect.y + 18), (rect.x + i * cell, rect.bottom - 18), 3)
            pg.draw.line(surface, (90, 150, 190), (rect.x + 18, rect.y + i * cell), (rect.right - 18, rect.y + i * cell), 3)
        for idx, mark in enumerate(game.board):
            if not mark:
                continue
            x = rect.x + (idx % 3) * cell + cell // 2
            y = rect.y + (idx // 3) * cell + cell // 2
            color = (255, 225, 105) if mark == "X" else (105, 235, 255)
            text = self.large.render(mark, True, color)
            surface.blit(text, text.get_rect(center=(x, y)))
        status = f"{game.winner.upper()} wins" if game.winner and game.winner != "draw" else ("Draw" if game.winner else f"{game.current}'s turn")
        surface.blit(self.medium.render(f"Tic Tac Toe - {status}", True, (235, 250, 255)), (rect.x, rect.bottom + 22))

    @staticmethod
    def _wrap(text: str, width: int) -> list[str]:
        words = text.split()
        lines: list[str] = []
        cur = ""
        for word in words:
            candidate = f"{cur} {word}".strip()
            if len(candidate) > width and cur:
                lines.append(cur)
                cur = word
            else:
                cur = candidate
        if cur:
            lines.append(cur)
        return lines[:3]
