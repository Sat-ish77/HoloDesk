"""Playwright-based browser automation controller.

Drives a dedicated Chrome profile ("HoloDesk Automation" by default) via the
Chrome DevTools Protocol so HoloDesk can read real page structure (roles,
placeholders, visible text) instead of guessing pixel coordinates or relying
on a vision model. The user's everyday Chrome window/profile is never
touched by this module — it only launches/attaches to the separate
automation profile, and reuses it if it's already running.

Every public function here returns a plain dict and never raises: callers in
agents/task_agent.py already follow the "return {'success': False, ...}"
contract everywhere else, and this module keeps that contract so a Playwright
timeout or a missing dependency becomes a spoken error message instead of a
crash.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import requests


class _LazyPlaywright:
    """Defers importing `playwright` until automation is actually used, the
    same lazy-import pattern task_agent.py already uses for pyautogui."""

    def __init__(self) -> None:
        self._module = None

    def _load(self):
        if self._module is None:
            import playwright.sync_api as module
            self._module = module
        return self._module

    def __getattr__(self, name):
        return getattr(self._load(), name)


playwright_api = _LazyPlaywright()

CHROME_PATH_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
]


def _find_chrome_executable() -> str | None:
    for raw_path in CHROME_PATH_CANDIDATES:
        path = os.path.expandvars(raw_path)
        if os.path.isfile(path):
            return path
    return shutil.which("chrome") or shutil.which("chrome.exe")


def _profile_dir() -> str:
    return os.getenv("HOLODESK_BROWSER_PROFILE_DIR", "HoloDesk Automation")


def _debug_port() -> int:
    try:
        return int(os.getenv("HOLODESK_BROWSER_DEBUG_PORT", "9222"))
    except ValueError:
        return 9222


def is_enabled() -> bool:
    return os.getenv("HOLODESK_BROWSER_AUTOMATION_ENABLED", "0") == "1"


def _debug_port_open(port: int) -> bool:
    try:
        resp = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=1.5)
        return resp.status_code == 200
    except Exception:
        return False


def _launch_automation_chrome(port: int) -> dict[str, Any]:
    exe = _find_chrome_executable()
    if not exe:
        return {"success": False, "error": "Chrome not found on this PC."}
    try:
        subprocess.Popen(
            [
                exe,
                f"--remote-debugging-port={port}",
                f"--profile-directory={_profile_dir()}",
                "--no-first-run",
                "--no-default-browser-check",
            ]
        )
    except Exception as exc:
        return {"success": False, "error": f"Couldn't launch Chrome: {exc}"}

    for _ in range(20):
        if _debug_port_open(port):
            return {"success": True, "error": None}
        time.sleep(0.5)
    return {"success": False, "error": "Chrome launched but its debugging port never opened."}


class PlaywrightController:
    """Owns the connection to the automation Chrome profile.

    A single module-level instance (`controller` below) is reused across
    calls so voice commands don't pay a reconnect cost every time.
    """

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None

    def ensure_page(self, url: str | None = None):
        """Return {"success", "page", "error"}. Never raises."""
        if not is_enabled():
            return {
                "success": False,
                "page": None,
                "error": "Browser automation is disabled (set HOLODESK_BROWSER_AUTOMATION_ENABLED=1 to turn it on).",
            }

        port = _debug_port()
        if not _debug_port_open(port):
            launch = _launch_automation_chrome(port)
            if not launch["success"]:
                return {"success": False, "page": None, "error": launch["error"]}

        try:
            if self._playwright is None:
                self._playwright = playwright_api.sync_playwright().start()
            if self._browser is None or not self._browser.is_connected():
                self._browser = self._playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")

            context = self._browser.contexts[0] if self._browser.contexts else self._browser.new_context()
            page = context.pages[0] if context.pages else context.new_page()
            if url:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return {"success": True, "page": page, "error": None}
        except Exception as exc:
            return {"success": False, "page": None, "error": f"Couldn't connect to the automation browser: {exc}"}


controller = PlaywrightController()


# ---------------------------------------------------------------------------
# Action primitives — operate on a `page` object passed in directly, so they
# can be unit tested with a fake/mock page, independent of real
# Playwright/Chrome (see tests/test_browser_automation.py).
# ---------------------------------------------------------------------------

def open_url(page, url: str) -> dict[str, Any]:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        return {"success": True, "error": None}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _locator(page, *, role: str | None = None, name: str | None = None, placeholder: str | None = None, text: str | None = None, label: str | None = None):
    if role is not None:
        return page.get_by_role(role, name=name) if name else page.get_by_role(role)
    if label is not None:
        return page.get_by_label(label)
    if placeholder is not None:
        return page.get_by_placeholder(placeholder)
    if text is not None:
        return page.get_by_text(text)
    raise ValueError("Must provide role, label, placeholder, or text to locate an element.")


def click(page, *, role: str | None = None, name: str | None = None, placeholder: str | None = None, text: str | None = None, label: str | None = None, timeout_ms: int = 8000) -> dict[str, Any]:
    try:
        locator = _locator(page, role=role, name=name, placeholder=placeholder, text=text, label=label)
        locator.first.click(timeout=timeout_ms)
        return {"success": True, "error": None}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def type_into(page, text: str, *, role: str | None = None, name: str | None = None, placeholder: str | None = None, label: str | None = None, timeout_ms: int = 8000) -> dict[str, Any]:
    try:
        locator = _locator(page, role=role, name=name, placeholder=placeholder, label=label)
        locator.first.click(timeout=timeout_ms)
        locator.first.fill(text, timeout=timeout_ms)
        return {"success": True, "error": None}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def press_key(page, key: str, *, role: str | None = None, name: str | None = None, placeholder: str | None = None, label: str | None = None, timeout_ms: int = 8000) -> dict[str, Any]:
    try:
        locator = _locator(page, role=role, name=name, placeholder=placeholder, label=label)
        locator.first.press(key, timeout=timeout_ms)
        return {"success": True, "error": None}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def read_text(page, *, role: str | None = None, name: str | None = None, placeholder: str | None = None, label: str | None = None, timeout_ms: int = 8000) -> dict[str, Any]:
    try:
        locator = _locator(page, role=role, name=name, placeholder=placeholder, label=label)
        value = locator.first.inner_text(timeout=timeout_ms)
        return {"success": True, "text": value, "error": None}
    except Exception as exc:
        return {"success": False, "text": None, "error": str(exc)}


def is_visible(page, *, role: str | None = None, name: str | None = None, placeholder: str | None = None, text: str | None = None, label: str | None = None) -> bool:
    try:
        locator = _locator(page, role=role, name=name, placeholder=placeholder, text=text, label=label)
        return bool(locator.first.is_visible())
    except Exception:
        return False


def screenshot(page, path: str) -> dict[str, Any]:
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=path)
        return {"success": True, "error": None}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
