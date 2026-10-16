"""Native Windows control via UI Automation (pywinauto, backend="uia").

Lets the Brain read and act on native apps as text (control names and types)
instead of paying for vision. Every function returns a dict and never raises.
"""

from __future__ import annotations

import ctypes
import os
import re
import time
from functools import lru_cache

import win32con
import win32gui
from rapidfuzz import fuzz, process
from rapidfuzz.utils import default_process

_SKIP_APPS = ("uninstall", "readme", "documentation", "release notes", "license")
_IGNORED_TITLES = ("Program Manager", "Windows Input Experience", "Microsoft Text Input Application")
_OVERLAY_PREFIX = "HoloDesk"
_USEFUL_TYPES = {
    "Button", "MenuItem", "Hyperlink", "ListItem", "TabItem", "CheckBox", "RadioButton",
    "Edit", "ComboBox", "TreeItem", "Document", "SplitButton", "MenuBar", "Text",
}
_TYPE_KEYS_SPECIAL = set("+^%~(){}[]")
_apps_refreshed_at = time.time()


def _fail(message: str) -> dict:
    return {"success": False, "response": message}


def ensure_dpi_aware() -> None:
    """Make this process see true pixels.

    Without it, Windows display scaling (125% here) gives three different
    coordinate systems: UI Automation reports physical pixels, GetWindowRect and
    pyautogui report scaled ones. Clicking what a screenshot showed then missed.
    Must run before any window is created or captured.
    """
    try:
        # Pointer-width handle: a plain -4 silently fails and leaves the process unaware.
        set_dpi = ctypes.windll.user32.SetProcessDpiAwarenessContext
        set_dpi.argtypes, set_dpi.restype = [ctypes.c_void_p], ctypes.c_bool
        if set_dpi(ctypes.c_void_p(-4)):  # per-monitor aware v2
            return
    except Exception:
        pass
    for fallback in (lambda: ctypes.windll.shcore.SetProcessDpiAwareness(2),
                     lambda: ctypes.windll.user32.SetProcessDPIAware()):
        try:
            fallback()
            return
        except Exception:
            continue


ensure_dpi_aware()


def _com() -> None:
    # Orchestrator and Brain run on worker threads; COM must be initialized per thread.
    import pythoncom

    pythoncom.CoInitialize()


# ---------------------------------------------------------------------------
# App launch from the Start menu app list (desktop and Store apps)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _installed_apps() -> dict[str, str]:
    """Display name -> AppsFolder id. About 3 s to build, so cached for the process."""
    import win32com.client

    _com()
    items = win32com.client.Dispatch("Shell.Application").NameSpace("shell:AppsFolder").Items()
    apps = {}
    for i in range(items.Count):
        item = items.Item(i)
        if not any(s in item.Name.lower() for s in _SKIP_APPS):
            apps[item.Name] = item.Path
    return apps


def _match_app(name: str, min_score: int) -> tuple[str, str] | None:
    apps = _installed_apps()
    squash = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())  # "note pad" == "Notepad"
    # Shortest squashed match wins so "notepad" is Notepad, not Notepad++.
    exact = min((n for n in apps if squash(n) == squash(name or "")), key=len, default=None)
    if exact:
        return exact, apps[exact]
    # token_set: every spoken word must be in the name ("chrome" -> "Google Chrome").
    # WRatio's partial matching sent "vs code" to "Developer PowerShell for VS 2022".
    match = process.extractOne(name or "", list(apps), scorer=fuzz.token_set_ratio, processor=default_process) if apps else None
    if not match or match[1] < min_score:
        return None
    return match[0], apps[match[0]]


def find_installed_app(name: str, min_score: int = 85) -> dict:
    try:
        found = _match_app(name, min_score)
        global _apps_refreshed_at
        if found is None and time.time() - _apps_refreshed_at > 60:
            # Maybe installed since the cache was built; at most one 3 s rebuild a minute,
            # so misheard names don't each pay for it.
            _apps_refreshed_at = time.time()
            _installed_apps.cache_clear()
            found = _match_app(name, min_score)
        if found is None:
            return _fail(f"No installed app matches {name}.")
        return {"success": True, "name": found[0], "app_id": found[1]}
    except Exception as exc:
        return _fail(f"Couldn't search installed apps: {exc}")


def launch_app(name: str) -> dict:
    found = find_installed_app(name)
    if not found["success"]:
        return found
    try:
        os.startfile("shell:AppsFolder\\" + found["app_id"])
        return {"success": True, "response": f"Opening {found['name']}.", "name": found["name"]}
    except Exception as exc:
        return _fail(f"Couldn't open {found['name']}: {exc}")


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------
def _is_cloaked(hwnd: int) -> bool:
    # Suspended UWP apps report visible but are cloaked by DWM (attribute 14).
    cloaked = ctypes.c_int(0)
    ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
    return bool(cloaked.value)


def _app_windows() -> list[tuple[int, str]]:
    """Visible, titled, top-level app windows in z-order (front first), overlay excluded."""
    out: list[tuple[int, str]] = []

    def collect(hwnd, _):
        title = win32gui.GetWindowText(hwnd).strip()
        if (
            title
            and win32gui.IsWindowVisible(hwnd)
            and not win32gui.GetWindow(hwnd, win32con.GW_OWNER)
            and not title.startswith(_OVERLAY_PREFIX)
            and title not in _IGNORED_TITLES
            and not _is_cloaked(hwnd)
        ):
            out.append((hwnd, title))

    win32gui.EnumWindows(collect, None)
    return out


def target_window() -> tuple[int, str] | None:
    """The window the user means by 'this': foreground, unless that is the HoloDesk overlay."""
    fg = win32gui.GetForegroundWindow()
    title = win32gui.GetWindowText(fg).strip()
    if fg and title and not title.startswith(_OVERLAY_PREFIX):
        return fg, title
    windows = _app_windows()
    return windows[0] if windows else None


def list_windows(limit: int = 20) -> dict:
    try:
        titles = [t for _, t in _app_windows()][:limit]
        return {"success": True, "response": "; ".join(titles) or "No app windows are open.", "windows": titles}
    except Exception as exc:
        return _fail(f"Couldn't list windows: {exc}")


def focus_window(title_substring: str) -> dict:
    try:
        windows = _app_windows()
        match = process.extractOne(title_substring or "", [t for _, t in windows], scorer=fuzz.WRatio, processor=default_process) if windows else None
        if not match or match[1] < 70:
            return _fail(f"No open window matches {title_substring}.")
        hwnd = windows[match[2]][0]
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        _uia(hwnd).set_focus()
        time.sleep(0.3)
        now = win32gui.GetWindowText(win32gui.GetForegroundWindow())
        return {"success": now == match[0], "response": f"Now in front: {now}.", "active_window": now}
    except Exception as exc:
        return _fail(f"Couldn't switch to {title_substring}: {exc}")


# ---------------------------------------------------------------------------
# Controls in the target window
# ---------------------------------------------------------------------------
def _uia(hwnd: int):
    from pywinauto import Desktop

    _com()
    return Desktop(backend="uia").window(handle=hwnd).wrapper_object()


def _controls(hwnd: int) -> list:
    # pywinauto 0.6.9's descendants(depth=...) raises AttributeError, so no depth limit.
    return [c for c in _uia(hwnd).descendants() if c.element_info.name and c.element_info.control_type in _USEFUL_TYPES]


def read_controls(limit: int = 40) -> dict:
    try:
        target = target_window()
        if target is None:
            return _fail("No app window is open.")
        hwnd, title = target
        seen, lines = set(), []
        for c in _controls(hwnd):
            key = (c.element_info.control_type, c.element_info.name.strip()[:80])
            if key not in seen:
                seen.add(key)
                lines.append(f"{key[0]}: {key[1]}")
            if len(lines) >= limit:
                break
        return {"success": True, "response": f"{title}: " + "; ".join(lines), "window": title, "controls": lines}
    except Exception as exc:
        return _fail(f"Couldn't read the window's controls: {exc}")


def _find_control(name: str, control_type: str | None = None, types: set[str] | None = None):
    target = target_window()
    if target is None:
        return None, None, "No app window is open."
    hwnd, title = target
    candidates = [
        c for c in _controls(hwnd)
        if (control_type is None or c.element_info.control_type.lower() == control_type.lower())
        and (types is None or c.element_info.control_type in types)
    ]
    if not candidates:
        return None, title, f"No matching controls in {title}."
    if types:
        # A ComboBox wraps an Edit with the same name; the Edit is the one that takes text.
        order = ["Edit", "Document", "ComboBox"]
        candidates.sort(key=lambda c: order.index(c.element_info.control_type) if c.element_info.control_type in order else 99)
    wanted = (name or "").strip().lower()
    exact = [c for c in candidates if c.element_info.name.strip().lower() == wanted]
    if exact:
        return exact[0], title, None
    names = [c.element_info.name for c in candidates]
    match = process.extractOne(name or "", names, scorer=fuzz.WRatio, processor=default_process)
    if not match or match[1] < 80:
        nearby = ", ".join(sorted(set(names))[:15])
        return None, title, f"No control named {name} in {title}. Visible: {nearby}."
    return candidates[match[2]], title, None


def click_control(name: str, control_type: str | None = None) -> dict:
    try:
        control, title, error = _find_control(name, control_type)
        if control is None:
            return _fail(error)
        label = f"{control.element_info.control_type} '{control.element_info.name}'"
        try:
            control.invoke()  # no mouse movement; works when the control is covered
        except Exception:
            control.click_input()
        time.sleep(0.3)
        now = win32gui.GetWindowText(win32gui.GetForegroundWindow())
        return {"success": True, "response": f"Clicked {label} in {title}.", "active_window": now}
    except Exception as exc:
        return _fail(f"Couldn't click {name}: {exc}")


def _escape_type_keys(text: str) -> str:
    return "".join("{" + ch + "}" if ch in _TYPE_KEYS_SPECIAL else ch for ch in text)


def set_text(name: str, text: str) -> dict:
    """Replace the text of an edit field (by name) and read it back."""
    try:
        control, title, error = _find_control(name, types={"Edit", "Document", "ComboBox"})
        if control is None:
            return _fail(error)
        try:
            control.set_edit_text(text)
        except Exception:
            control.set_focus()
            control.type_keys("^a{BACKSPACE}" + _escape_type_keys(text), with_spaces=True, with_newlines=True)
        time.sleep(0.2)
        try:
            value = control.iface_value.CurrentValue
        except Exception:
            value = control.window_text()
        ok = text.strip() in (value or "")
        return {
            "success": ok,
            "response": f"Set '{control.element_info.name}' in {title}." if ok else f"Typed into '{control.element_info.name}' but it reads back differently.",
            "value": (value or "")[:200],
        }
    except Exception as exc:
        return _fail(f"Couldn't set {name}: {exc}")
