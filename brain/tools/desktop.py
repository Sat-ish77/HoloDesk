"""
Desktop tools: apps, windows, keyboard, mouse, UI elements, screen.

Order of preference when controlling an app (most reliable first):
  1. a dedicated tool (open_app, open_website, window_action ...)
  2. click_ui_element   finds a button by NAME through Windows UI Automation
  3. press_keys / type_text
  4. look_at_screen + mouse_click   vision, slowest and least reliable

Every Windows-only import is inside a function so this module imports
anywhere (tests run on Linux).
"""

from __future__ import annotations

import difflib
import re
import subprocess
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Callable

from ..policy import Risk
from .browser import open_in_automation
from .registry import Tool, ToolContext, ToolError

# Windows whose title contains one of these are never captured or read.
PRIVATE_TITLE_KEYWORDS = [
    "1password", "lastpass", "bitwarden", "dashlane", "keepass", "password manager",
    "banking", "chase", "wells fargo", "bank of america", "citibank", "credit card",
    "private -", "incognito", "inprivate", "social security", "tax return", "payroll",
    "esewa", "khalti", "connectips", "nabil", "nic asia", "global ime", "mobile banking",
]

_SCREENSHOT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "screenshots"


def _pyautogui():
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        return pyautogui
    except Exception as e:
        raise ToolError(f"pyautogui is not available: {e}")


def _win32():
    try:
        import win32con
        import win32gui
        return win32gui, win32con
    except ImportError:
        raise ToolError("window control needs pywin32 (Windows only)")


def _foreground_title() -> str:
    try:
        import win32gui
        return win32gui.GetWindowText(win32gui.GetForegroundWindow()) or ""
    except Exception:
        return ""


def _private_window_open() -> bool:
    title = _foreground_title().lower()
    return any(k in title for k in PRIVATE_TITLE_KEYWORDS)


def _from_task_agent(result: dict) -> dict:
    return {"ok": bool(result.get("success")), "message": result.get("response", "")}


# ---------------------------------------------------------------- windows
def _visible_windows() -> list[tuple[int, str]]:
    win32gui, _ = _win32()
    found: list[tuple[int, str]] = []

    def _cb(hwnd, _extra):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and title not in {"Program Manager", "HoloDesk"}:
                found.append((hwnd, title))
    win32gui.EnumWindows(_cb, None)
    return found


def _find_window(title: str) -> tuple[int, str]:
    windows = _visible_windows()
    want = (title or "").lower().strip()
    if not want:
        win32gui, _ = _win32()
        hwnd = win32gui.GetForegroundWindow()
        return hwnd, win32gui.GetWindowText(hwnd)
    for hwnd, t in windows:
        if want in t.lower():
            return hwnd, t
    close = difflib.get_close_matches(want, [t.lower() for _, t in windows], n=1, cutoff=0.5)
    if close:
        for hwnd, t in windows:
            if t.lower() == close[0]:
                return hwnd, t
    raise ToolError(f"no open window matches '{title}'. Open windows: "
                    + "; ".join(t[:50] for _, t in windows[:12]))


def list_windows(args: dict, ctx: ToolContext) -> dict:
    active = _foreground_title()
    return {"ok": True, "active": active,
            "windows": [t[:100] for _, t in _visible_windows()][:40]}


def _focus(hwnd: int) -> None:
    win32gui, win32con = _win32()
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        # Windows refuses focus changes from background processes unless the
        # caller just sent input; a tap of Alt satisfies that rule.
        pag = _pyautogui()
        pag.press("alt")
        win32gui.SetForegroundWindow(hwnd)


def focus_window(args: dict, ctx: ToolContext) -> dict:
    hwnd, title = _find_window(args.get("title") or "")
    _focus(hwnd)
    return {"ok": True, "message": f"Switched to {title[:80]}."}


def window_action(args: dict, ctx: ToolContext) -> dict:
    win32gui, win32con = _win32()
    action = (args.get("action") or "").lower()
    hwnd, title = _find_window(args.get("title") or "")
    if action == "minimize":
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
    elif action == "maximize":
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
    elif action == "restore":
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    elif action == "close":
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)  # polite: app may ask to save
    else:
        raise ToolError("action must be minimize, maximize, restore or close")
    return {"ok": True, "message": f"{action.capitalize()}d {title[:80]}."}


# ---------------------------------------------------------------- UI Automation
def _uia_window(title: str):
    try:
        from pywinauto import Desktop
    except ImportError:
        raise ToolError("UI element control needs pywinauto (pip install pywinauto)")
    if not title:
        title = _foreground_title()
    if not title:
        raise ToolError("no window title given and no active window found")
    win = Desktop(backend="uia").window(title_re="(?i).*" + re.escape(title) + ".*", found_index=0)
    try:
        win.wait("exists", timeout=3)
    except Exception:
        raise ToolError(f"no window matches '{title}'")
    return win


_INTERACTIVE = {"Button", "MenuItem", "Hyperlink", "Edit", "CheckBox", "RadioButton",
                "ComboBox", "ListItem", "TabItem", "TreeItem", "SplitButton"}


def list_ui_elements(args: dict, ctx: ToolContext) -> dict:
    if _private_window_open():
        raise ToolError("a private window (banking or passwords) is in front; I won't read it")
    win = _uia_window(args.get("window_title") or "")
    limit = max(5, min(int(args.get("limit") or 60), 150))
    needle = (args.get("filter") or "").lower()
    items = []
    for el in win.descendants():
        info = el.element_info
        name, ctype = (info.name or "").strip(), info.control_type or ""
        if not name or ctype not in _INTERACTIVE:
            continue
        if needle and needle not in name.lower():
            continue
        items.append(f"{ctype}: {name[:60]}")
        if len(items) >= limit:
            break
    return {"ok": True, "elements": items}


def click_ui_element(args: dict, ctx: ToolContext) -> dict:
    name = (args.get("name") or "").strip()
    if not name:
        raise ToolError("name is required")
    win = _uia_window(args.get("window_title") or "")
    want_type = (args.get("control_type") or "").lower()
    candidates = []
    for el in win.descendants():
        info = el.element_info
        el_name, ctype = (info.name or "").strip(), info.control_type or ""
        if not el_name or (want_type and ctype.lower() != want_type):
            continue
        if el_name.lower() == name.lower():
            candidates.insert(0, (el, el_name, ctype))
        elif name.lower() in el_name.lower() and ctype in _INTERACTIVE:
            candidates.append((el, el_name, ctype))
    if not candidates:
        raise ToolError(f"no element named '{name}' in that window; call list_ui_elements to see names")
    el, el_name, ctype = candidates[0]
    el.click_input()
    return {"ok": True, "message": f"Clicked {ctype} '{el_name[:60]}'."}


# ---------------------------------------------------------------- apps / web
def _plain_url(target: str) -> str:
    return target if re.match(r"^https?://", target) else (
        "https://" + target if "." in target else f"https://www.{target}.com")


def make_app_tools(task_agent_provider: Callable[[], object | None]):
    def open_app(args: dict, ctx: ToolContext) -> dict:
        name = (args.get("name") or "").strip()
        if not name:
            raise ToolError("name is required")
        agent = task_agent_provider()
        if agent is not None:
            return _from_task_agent(agent.open_app(name))
        subprocess.Popen(f'start "" "{name}"', shell=True)
        return {"ok": True, "message": f"Opening {name}."}

    def open_website(args: dict, ctx: ToolContext) -> dict:
        target = (args.get("target") or "").strip()
        browser = (args.get("browser") or "").strip().lower()
        if not target:
            raise ToolError("target is required")
        agent = task_agent_provider()
        if browser in ("", "chrome"):
            # Same tab the browser_* tools act on; None means automation is
            # off or unavailable and the normal browser is used as before.
            build_url = getattr(agent, "_build_url_from_site_name", None)
            routed = open_in_automation(build_url(target) if build_url else _plain_url(target))
            if routed is not None:
                return routed
        if agent is not None:
            if browser:
                return _from_task_agent(agent.open_web_in_browser(target=target, browser=browser))
            return _from_task_agent(agent.open_website(target))
        url = _plain_url(target)
        webbrowser.open(url)
        return {"ok": True, "message": f"Opened {url}."}

    return open_app, open_website


def close_app(args: dict, ctx: ToolContext) -> dict:
    """Polite close: sends WM_CLOSE so the app can ask to save."""
    name = (args.get("name") or "").strip().lower().removesuffix(".exe")
    if not name:
        raise ToolError("name is required")
    closed = 0
    win32gui, win32con = _win32()
    for hwnd, title in _visible_windows():
        if name in title.lower():
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            closed += 1
    if not closed:
        proc = subprocess.run(["taskkill", "/IM", f"{name}.exe"], capture_output=True, text=True)
        if proc.returncode != 0:
            return {"ok": False, "error": f"nothing called '{name}' seems to be open"}
        closed = 1
    return {"ok": True, "message": f"Asked {name} to close ({closed} window(s))."}


def search_in_browser(args: dict, ctx: ToolContext) -> dict:
    query = (args.get("query") or "").strip()
    if not query:
        raise ToolError("query is required")
    engine = (args.get("engine") or "google").lower()
    q = urllib.parse.quote_plus(query)
    url = {"youtube": f"https://www.youtube.com/results?search_query={q}",
           "maps": f"https://www.google.com/maps/search/{q}"}.get(engine, f"https://www.google.com/search?q={q}")
    routed = open_in_automation(url)
    if routed is not None:
        routed["message"] = (f"Opened a {engine} search for '{query}'. Use browser_open_result "
                             "to open one of the results.")
        return routed
    webbrowser.open(url)
    return {"ok": True, "message": f"Opened a {engine} search for '{query}' in the browser. "
                                   "(This opens the page; it does not read the results.)"}


# ---------------------------------------------------------------- input
def type_text(args: dict, ctx: ToolContext) -> dict:
    text = args.get("text")
    if not isinstance(text, str) or not text:
        raise ToolError("text is required")
    pag = _pyautogui()
    try:
        import pyperclip
        previous = pyperclip.paste()
        pyperclip.copy(text)          # paste handles Devanagari; key-by-key typing does not
        pag.hotkey("ctrl", "v")
        time.sleep(0.15)
        pyperclip.copy(previous)
    except ImportError:
        pag.write(text, interval=0.01)
    if args.get("press_enter"):
        pag.press("enter")
    return {"ok": True, "message": "Typed it."}


_KEY_ALIASES = {"control": "ctrl", "windows": "win", "cmd": "win", "escape": "esc",
                "return": "enter", "del": "delete", "pgup": "pageup", "pgdn": "pagedown"}


def press_keys(args: dict, ctx: ToolContext) -> dict:
    combo = (args.get("keys") or "").lower().replace(" ", "")
    if not combo:
        raise ToolError("keys is required, like 'ctrl+s' or 'enter'")
    keys = [_KEY_ALIASES.get(k, k) for k in combo.split("+") if k]
    pag = _pyautogui()
    unknown = [k for k in keys if k not in pag.KEYBOARD_KEYS]
    if unknown:
        raise ToolError(f"unknown key(s): {unknown}")
    repeat = max(1, min(int(args.get("repeat") or 1), 20))
    for _ in range(repeat):
        pag.hotkey(*keys) if len(keys) > 1 else pag.press(keys[0])
    return {"ok": True, "message": f"Pressed {'+'.join(keys)}."}


def mouse_click(args: dict, ctx: ToolContext) -> dict:
    pag = _pyautogui()
    try:
        x, y = int(args["x"]), int(args["y"])
    except (KeyError, TypeError, ValueError):
        raise ToolError("x and y pixel coordinates are required")
    width, height = pag.size()
    if not (0 <= x < width and 0 <= y < height):
        raise ToolError(f"({x},{y}) is off the {width}x{height} screen")
    button = args.get("button") if args.get("button") in ("left", "right", "middle") else "left"
    pag.click(x=x, y=y, button=button, clicks=2 if args.get("double") else 1)
    return {"ok": True, "message": f"Clicked at ({x},{y})."}


def scroll(args: dict, ctx: ToolContext) -> dict:
    pag = _pyautogui()
    amount = max(1, min(int(args.get("amount") or 5), 50)) * 200
    pag.scroll(-amount if (args.get("direction") or "down").lower() == "down" else amount)
    return {"ok": True}


def clipboard(args: dict, ctx: ToolContext) -> dict:
    try:
        import pyperclip
    except ImportError:
        raise ToolError("clipboard needs pyperclip")
    if (args.get("action") or "read").lower() == "write":
        pyperclip.copy(str(args.get("text") or ""))
        return {"ok": True, "message": "Copied to the clipboard."}
    return {"ok": True, "content": (pyperclip.paste() or "")[:4000]}


# ---------------------------------------------------------------- screen
def take_screenshot(args: dict, ctx: ToolContext) -> dict:
    if _private_window_open():
        raise ToolError("a private window (banking or passwords) is in front; I won't capture it")
    pag = _pyautogui()
    _SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = _SCREENSHOT_DIR / f"screen_{time.strftime('%Y%m%d_%H%M%S')}.png"
    pag.screenshot().save(str(path))
    return {"ok": True, "photo_path": str(path), "active_window": _foreground_title()[:100],
            "message": "Screenshot taken." + (" It will be sent to the phone." if ctx.source == "telegram" else "")}


def make_look_at_screen(screen_agent_provider: Callable[[], object | None]):
    def look_at_screen(args: dict, ctx: ToolContext) -> dict:
        question = (args.get("question") or "What is on the screen? Describe it briefly.").strip()
        if _private_window_open():
            raise ToolError("a private window (banking or passwords) is in front; I won't read it")
        # Preferred: a vision model on the same endpoint as the brain (free on
        # Groq). Fallback: the original GPT-4o ScreenAgent (needs OpenAI credit).
        model = getattr(ctx.cfg, "vision_model", "") if ctx.cfg else ""
        if model and ctx.engine is not None:
            try:
                answer = _vision_answer(ctx.engine.backend, model, question)
                if answer:
                    return {"ok": True, "answer": answer}
            except Exception as e:
                vision_error = str(e)
            else:
                vision_error = "empty answer"
        else:
            vision_error = "no vision model available"
        agent = screen_agent_provider()
        if agent is None:
            raise ToolError(f"screen vision is not available ({vision_error}; and no OPENAI_API_KEY "
                            "for the fallback)")
        result = agent.execute(question=question)
        return {"ok": bool(result.get("success")), "answer": result.get("response", "")}
    return look_at_screen


def _vision_answer(backend, model: str, question: str) -> str:
    import base64
    from io import BytesIO
    pag = _pyautogui()
    shot = pag.screenshot().convert("RGB")
    width = 1280
    if shot.width > width:
        shot = shot.resize((width, int(shot.height * width / shot.width)))
    buf = BytesIO()
    shot.save(buf, format="JPEG", quality=80)
    data_url = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    response = backend.chat(
        [{"role": "user", "content": [
            {"type": "text", "text": question + " Answer in at most four sentences. If you point "
                                                "to something, give its approximate pixel position "
                                                f"on a {pag.size()[0]}x{pag.size()[1]} screen."},
            {"type": "image_url", "image_url": {"url": data_url}}]}],
        model=model, max_tokens=350, temperature=0.0)
    return response.content


# ---------------------------------------------------------------- timer
def set_timer(args: dict, ctx: ToolContext) -> dict:
    try:
        minutes = float(args.get("minutes"))
    except (TypeError, ValueError):
        raise ToolError("minutes is required")
    if not 0 < minutes <= 24 * 60:
        raise ToolError("minutes must be between 0 and 1440")
    label = (args.get("label") or "Timer").strip()[:60]
    notify = ctx.notify

    def _done():
        text = f"{label}: time is up ({minutes:g} min)."
        try:  # the overlay speaks TIMER_DONE events
            from core.queues import response_queue
            response_queue.put_nowait({"type": "TIMER_DONE", "text": text})
        except Exception:
            pass
        if notify:
            try:
                notify("⏰ " + text)
            except Exception:
                pass
    timer = threading.Timer(minutes * 60, _done)
    timer.daemon = True
    timer.start()
    return {"ok": True, "message": f"Timer set for {minutes:g} minutes."}


def build(task_agent_provider=lambda: None, screen_agent_provider=lambda: None) -> list[Tool]:
    open_app, open_website = make_app_tools(task_agent_provider)
    title_param = {"type": "string", "description": "Part of the window title. Empty means the active window."}
    return [
        Tool(name="open_app", description="Open (launch) a desktop application by name.",
             parameters={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
             handler=open_app, risk=Risk.ACT,
             keywords=("open", "launch", "start", "खोल", "khol", "kholdeu", "chalau")),
        Tool(name="close_app",
             description=("Close a whole application politely (it may ask to save). Use kill_process if it "
                          "is frozen. To close one browser tab use browser_close_tab, not this."),
             parameters={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
             handler=close_app, risk=Risk.ACT,
             keywords=("close", "quit", "exit", "बन्द", "banda")),
        Tool(name="open_website",
             description="Open a website or URL in the browser. Accepts names like 'youtube' or full URLs.",
             parameters={"type": "object", "properties": {
                 "target": {"type": "string"},
                 "browser": {"type": "string", "enum": ["chrome", "brave", "firefox", "edge"]}},
                 "required": ["target"]},
             handler=open_website, risk=Risk.ACT,
             keywords=("website", "site", "url", "go to", "visit", "browser", "youtube", "gmail", "facebook")),
        Tool(name="search_in_browser",
             description=("Open a Google, YouTube or Maps search in the browser for the user to look "
                          "at. It does NOT return the results to you."),
             parameters={"type": "object", "properties": {
                 "query": {"type": "string"},
                 "engine": {"type": "string", "enum": ["google", "youtube", "maps"]}}, "required": ["query"]},
             handler=search_in_browser, risk=Risk.ACT,
             keywords=("search", "google", "look up", "play", "song", "video", "खोज", "khoja", "bajau")),
        Tool(name="list_windows", description="List the titles of all open windows and which one is active.",
             handler=list_windows, keywords=("windows", "open apps", "what's open", "which app")),
        Tool(name="focus_window", description="Bring a window to the front.",
             parameters={"type": "object", "properties": {"title": title_param}, "required": ["title"]},
             handler=focus_window, risk=Risk.ACT, keywords=("switch to", "bring up", "focus", "go to")),
        Tool(name="window_action", description="Minimize, maximize, restore or close a window.",
             parameters={"type": "object", "properties": {
                 "action": {"type": "string", "enum": ["minimize", "maximize", "restore", "close"]},
                 "title": title_param}, "required": ["action"]},
             handler=window_action, risk=Risk.ACT,
             keywords=("minimize", "maximize", "restore", "full screen", "window")),
        Tool(name="list_ui_elements",
             description=("List the clickable elements (buttons, menus, fields) of a window by name. "
                          "Call before click_ui_element when you don't know the exact name."),
             parameters={"type": "object", "properties": {
                 "window_title": title_param, "filter": {"type": "string"}, "limit": {"type": "integer"}}},
             handler=list_ui_elements, keywords=("button", "buttons", "menu", "click", "elements")),
        Tool(name="click_ui_element",
             description=("Click a button, menu item, link or field in a window by its visible name. "
                          "More reliable than clicking coordinates."),
             parameters={"type": "object", "properties": {
                 "name": {"type": "string", "description": "Visible name of the element."},
                 "window_title": title_param,
                 "control_type": {"type": "string", "description": "Optional, e.g. Button, MenuItem, Edit."}},
                 "required": ["name"]},
             handler=click_ui_element, risk=Risk.ACT, keywords=("click", "press", "button", "tap", "थिच", "click gara")),
        Tool(name="type_text",
             description="Type text into whatever is focused. Works for Nepali text too.",
             parameters={"type": "object", "properties": {
                 "text": {"type": "string"}, "press_enter": {"type": "boolean"}}, "required": ["text"]},
             handler=type_text, risk=Risk.ACT, keywords=("type", "write", "enter text", "टाइप", "lekha")),
        Tool(name="press_keys",
             description="Press a key or shortcut, like 'enter', 'ctrl+s', 'alt+tab', 'win+d'.",
             parameters={"type": "object", "properties": {
                 "keys": {"type": "string"}, "repeat": {"type": "integer"}}, "required": ["keys"]},
             handler=press_keys, risk=Risk.ACT,
             keywords=("press", "shortcut", "hotkey", "key", "save", "copy", "paste", "undo", "tab")),
        Tool(name="mouse_click",
             description=("Click at screen pixel coordinates. Last resort: use only after "
                          "look_at_screen told you where something is."),
             parameters={"type": "object", "properties": {
                 "x": {"type": "integer"}, "y": {"type": "integer"},
                 "button": {"type": "string", "enum": ["left", "right", "middle"]},
                 "double": {"type": "boolean"}}, "required": ["x", "y"]},
             handler=mouse_click, risk=Risk.ACT, keywords=("click", "mouse", "double click", "right click")),
        Tool(name="scroll", description="Scroll the active window up or down.",
             parameters={"type": "object", "properties": {
                 "direction": {"type": "string", "enum": ["up", "down"]}, "amount": {"type": "integer"}}},
             handler=scroll, risk=Risk.ACT, keywords=("scroll", "page down", "page up")),
        Tool(name="clipboard", description="Read the clipboard, or put text on it.",
             parameters={"type": "object", "properties": {
                 "action": {"type": "string", "enum": ["read", "write"]}, "text": {"type": "string"}},
                 "required": ["action"]},
             handler=clipboard, risk=lambda a: Risk.ACT if a.get("action") == "write" else Risk.SAFE,
             keywords=("clipboard", "copied", "copy", "paste")),
        Tool(name="take_screenshot",
             description=("Capture the screen to a file. From the phone, the picture is sent back "
                          "so the user can see their laptop."),
             handler=take_screenshot,
             keywords=("screenshot", "capture", "show me my screen", "picture of screen", "स्क्रिनसट")),
        Tool(name="look_at_screen",
             description=("Look at the screen with a vision model and answer a question about it: "
                          "read an error, describe a page, find where a button is."),
             parameters={"type": "object", "properties": {"question": {"type": "string"}}},
             handler=make_look_at_screen(screen_agent_provider),
             keywords=("screen", "see", "look", "what's on", "explain this", "read this", "error",
                       "स्क्रिन", "हेर", "yo ke ho", "screen ma ke cha")),
        Tool(name="set_timer", description="Set a timer; announces on the laptop and the phone when done.",
             parameters={"type": "object", "properties": {
                 "minutes": {"type": "number"}, "label": {"type": "string"}}, "required": ["minutes"]},
             handler=set_timer, keywords=("timer", "remind", "alarm", "minutes", "टाइमर", "samjhau")),
    ]
