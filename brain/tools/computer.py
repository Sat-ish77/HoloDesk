"""Eye + mouse control: Claude looks at screenshots and drives the real mouse
and keyboard, for anything the page map and the Windows UI tree can't reach
(native file pickers, canvas apps, unusual dialogs).

Loop: the model asks for a screenshot, decides, acts (click / type / key /
scroll ...), asks for another screenshot to check, and so on. Uses the
computer toolset (computer_toolset_20260801) on Claude Opus 5.5.
"""
from __future__ import annotations

import base64
import io
import os
import time

from ..policy import Risk
from .registry import Tool, ToolContext, ToolError

MODEL = os.getenv("HOLODESK_COMPUTER_MODEL", "claude-opus-5-5")
MAX_TURNS = 30
LONG_EDGE = 1366      # screenshot size sent to the model; smaller = faster, cheaper

_SYSTEM = (
    "You operate the user's Windows laptop for them through screenshots, the mouse and the "
    "keyboard. Take a screenshot first, act, then take another screenshot to check the result "
    "before you say something worked. Never type passwords or payment details. Before anything "
    "that can't be undone or that other people will see (send, post, comment, submit, delete, "
    "buy, pay, close unsaved work), stop and reply with one line starting 'NEEDS OK:' that says "
    "exactly what you are about to do. When finished, reply in one or two plain sentences that "
    "say what you verified on screen; if you could not do it, say where you got stuck."
)

# xdotool-style names the model uses -> pyautogui names
_KEYS = {"return": "enter", "enter": "enter", "escape": "esc", "esc": "esc", "backspace": "backspace",
         "tab": "tab", "delete": "delete", "space": "space", "page_down": "pagedown",
         "page_up": "pageup", "home": "home", "end": "end", "up": "up", "down": "down",
         "left": "left", "right": "right", "super": "win", "cmd": "win", "meta": "win",
         "ctrl": "ctrl", "control": "ctrl", "alt": "alt", "shift": "shift"}


def _keys(combo: str) -> list[str]:
    return [_KEYS.get(k.strip().lower(), k.strip().lower()) for k in (combo or "").split("+") if k.strip()]


class _Screen:
    """Screenshots in model space and the scale back to pyautogui's space."""

    def __init__(self, pyautogui):
        self.pg = pyautogui

    def grab(self):
        img = self.pg.screenshot()
        sw, sh = self.pg.size()
        self.scale = min(1.0, LONG_EDGE / max(img.width, img.height))
        # model px -> raw screenshot px -> pyautogui (logical) px; they differ under display scaling
        self.to_screen = (sw / img.width) / self.scale
        if self.scale < 1.0:
            img = img.resize((round(img.width * self.scale), round(img.height * self.scale)))
        self.last = img
        return img

    def xy(self, coord) -> tuple[int, int]:
        if not hasattr(self, "to_screen"):
            self.grab()
        return round(coord[0] * self.to_screen), round(coord[1] * self.to_screen)


def _png(img) -> dict:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                        "data": base64.standard_b64encode(buf.getvalue()).decode()}}


def run_action(name: str, args: dict, screen: _Screen):
    """Executes one toolset member. Returns tool_result content."""
    pg = screen.pg
    mods = _keys(args.get("text", "")) if name.endswith("click") or name == "scroll" else []
    if name == "screenshot":
        return [_png(screen.grab())]
    if name == "zoom":
        x0, y0, x1, y1 = args["region"]
        crop = screen.grab().crop((x0, y0, x1, y1))
        f = min(LONG_EDGE / max(crop.width, crop.height), 4.0)
        return [_png(crop.resize((max(1, round(crop.width * f)), max(1, round(crop.height * f)))))]
    if name == "cursor_position":
        x, y = pg.position()
        return f"{round(x / screen.to_screen)}, {round(y / screen.to_screen)}" if hasattr(screen, "to_screen") else f"{x}, {y}"
    for m in mods:
        pg.keyDown(m)
    try:
        if name in ("left_click", "right_click", "middle_click", "double_click", "triple_click"):
            x, y = screen.xy(args["coordinate"]) if args.get("coordinate") else pg.position()
            button = {"right_click": "right", "middle_click": "middle"}.get(name, "left")
            clicks = {"double_click": 2, "triple_click": 3}.get(name, 1)
            pg.click(x, y, clicks=clicks, interval=0.08, button=button)
        elif name == "left_click_drag":
            pg.moveTo(*screen.xy(args["start_coordinate"]))
            pg.dragTo(*screen.xy(args["coordinate"]), duration=0.4, button="left")
        elif name == "mouse_move":
            pg.moveTo(*screen.xy(args["coordinate"]))
        elif name == "left_mouse_down":
            pg.mouseDown()
        elif name == "left_mouse_up":
            pg.mouseUp()
        elif name == "scroll":
            if args.get("coordinate"):
                pg.moveTo(*screen.xy(args["coordinate"]))
            n = int(args.get("scroll_amount") or 3)
            d = args.get("scroll_direction", "down")
            if d in ("up", "down"):
                pg.scroll(n * 120 * (1 if d == "up" else -1))   # Windows: 120 per wheel click
            else:
                pg.hscroll(n * 120 * (1 if d == "right" else -1))
        elif name == "type":
            text = args.get("text", "")
            if text.isascii():
                pg.write(text, interval=0.01)
            else:   # pyautogui can't type non-ASCII (Devanagari, curly quotes): paste it
                import pyperclip
                pyperclip.copy(text)
                pg.hotkey("ctrl", "v")
        elif name == "key":
            for _ in range(int(args.get("repeat") or 1)):
                pg.hotkey(*_keys(args.get("text", "")))
        elif name == "hold_key":
            keys = _keys(args.get("text", ""))
            for k in keys:
                pg.keyDown(k)
            time.sleep(min(float(args.get("duration") or 1), 30))
            for k in reversed(keys):
                pg.keyUp(k)
        elif name == "wait":
            time.sleep(min(float(args.get("duration") or 1), 30))
        else:
            raise ToolError(f"unknown action {name}")
    finally:
        for m in reversed(mods):
            pg.keyUp(m)
    time.sleep(0.3)   # let the UI react before the next screenshot
    return "OK"


def _result(block_id: str, content, error: bool = False) -> dict:
    out = {"type": "tool_result", "tool_use_id": block_id, "toolset_name": "computer",
           "content": content if isinstance(content, list) else str(content)}
    if error:
        out["is_error"] = True
    return out


def computer_task(args: dict, ctx: ToolContext, client=None, pyautogui=None) -> dict:
    goal = (args.get("goal") or "").strip()
    if not goal:
        raise ToolError("goal is required")
    if client is None:
        import anthropic
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ToolError("eye + mouse control needs ANTHROPIC_API_KEY in .env")
        client = anthropic.Anthropic()
    if pyautogui is None:
        import pyautogui
        pyautogui.FAILSAFE = True     # slam the mouse into a corner to abort
    screen = _Screen(pyautogui)
    messages = [{"role": "user", "content": goal}]
    actions = 0
    for _ in range(MAX_TURNS):
        engine = getattr(ctx, "engine", None)
        if engine is not None and engine.policy.halted:
            return {"ok": False, "error": "Stopped: HoloDesk is halted.", "actions": actions}
        response = client.beta.messages.create(
            model=MODEL, max_tokens=16000, system=_SYSTEM,
            tools=[{"type": "computer_toolset_20260801"}],
            messages=messages,
            betas=["server-side-fallback-2026-07-01"],
            # anthropic 0.85 predates these parameters; extra_body sends them as-is.
            extra_body={"output_config": {"effort": "medium"}, "fallbacks": "default"},
        )
        if response.stop_reason == "refusal":
            return {"ok": False, "error": "The vision model declined this task.", "actions": actions}
        content = [b.model_dump(exclude_none=True) for b in response.content]
        messages.append({"role": "assistant", "content": content})
        uses = [b for b in content if b.get("type") == "tool_use"]
        if not uses:
            text = " ".join(b.get("text", "") for b in content if b.get("type") == "text").strip()
            if text.startswith("NEEDS OK:"):
                return {"ok": True, "paused": True, "actions": actions,
                        "message": "Paused before: " + text[9:].strip()
                                   + " Ask the user; if they agree, run computer_task again saying they approved it."}
            return {"ok": True, "message": text or "Done.", "actions": actions}
        results, failed = [], False
        for b in uses:                 # a batch runs in order and stops at the first failure
            if failed:
                results.append(_result(b["id"], "Not executed: an earlier computer action in this turn failed.", True))
                continue
            try:
                results.append(_result(b["id"], run_action(b["name"], b.get("input") or {}, screen)))
                actions += b["name"] not in ("screenshot", "zoom", "cursor_position")
            except Exception as e:   # pyautogui.FailSafeException included: the user aborted
                failed = True
                results.append(_result(b["id"], f"Error: {type(e).__name__}: {e}", True))
                if type(e).__name__ == "FailSafeException":
                    return {"ok": False, "error": "Stopped: you moved the mouse into a corner.", "actions": actions}
        messages.append({"role": "user", "content": results})
    return {"ok": False, "error": f"Not finished after {MAX_TURNS} turns.", "actions": actions}


def build() -> list[Tool]:
    return [
        Tool(name="computer_task",
             description=("See the screen and use the real mouse and keyboard to do a task in ANY app or "
                          "window, e.g. a Windows file picker, a desktop app, or a page the browser tools "
                          "can't handle. Slower than the other tools: use it when they don't fit or failed. "
                          "Describe the whole goal in one sentence. It pauses before anything irreversible."),
             parameters={"type": "object", "properties": {
                 "goal": {"type": "string", "description": "What to get done, in one or two sentences."}},
                 "required": ["goal"]},
             handler=computer_task, risk=Risk.ACT,
             keywords=("click", "screen", "mouse", "window", "app", "file picker", "upload", "select",
                       "dialog", "button", "क्लिक", "स्क्रिन", "thich")),
    ]
