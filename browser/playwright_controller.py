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
import queue
import re
import shutil
import subprocess
import threading
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
    return os.path.expandvars(os.getenv("HOLODESK_BROWSER_PROFILE_DIR", r"%LOCALAPPDATA%\HoloDesk\chrome-profile"))


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
                # Chrome 136+ ignores --remote-debugging-port on the default data dir,
                # and a launch into a running default Chrome just opens a window there.
                f"--user-data-dir={_profile_dir()}",
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
        self._page = None  # the tab HoloDesk is working in

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
            if self._page is None or self._page.is_closed() or self._page.context is not context:
                self._page = context.pages[0] if context.pages else context.new_page()
            page = self._page
            if url:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return {"success": True, "page": page, "error": None}
        except Exception as exc:
            return {"success": False, "page": None, "error": f"Couldn't connect to the automation browser: {exc}"}

    def tabs(self) -> list:
        got = self.ensure_page()
        return got["page"].context.pages if got["success"] else []

    def use_tab(self, page) -> None:
        self._page = page
        page.bring_to_front()


controller = PlaywrightController()


# ---------------------------------------------------------------------------
# Browser worker thread. Playwright's sync API only works on the thread that
# started it, and HoloDesk calls in from the orchestrator, its thread pool,
# and confirmation callbacks. Every Playwright call goes through browser_call.
# ---------------------------------------------------------------------------
_calls: "queue.Queue" = queue.Queue()
_worker: threading.Thread | None = None
_worker_lock = threading.Lock()


def _worker_loop() -> None:
    while True:
        fn, args, kwargs, box = _calls.get()
        try:
            box["result"] = fn(*args, **kwargs)
        except Exception as exc:
            box["result"] = {"success": False, "error": f"{type(exc).__name__}: {exc}", "response": f"Browser error: {exc}"}
        box["done"].set()


def browser_call(fn, *args, timeout: float = 90, **kwargs):
    """Run fn(*args, **kwargs) on the single browser thread and return its result."""
    global _worker
    if threading.current_thread() is _worker:
        return fn(*args, **kwargs)
    with _worker_lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_worker_loop, name="BrowserWorker", daemon=True)
            _worker.start()
    box = {"done": threading.Event()}
    _calls.put((fn, args, kwargs, box))
    if not box["done"].wait(timeout):
        return {"success": False, "error": "Browser call timed out.", "response": "The browser didn't respond in time."}
    return box["result"]


def with_page(fn, *args, **kwargs) -> dict[str, Any]:
    """Run fn(page, ...) on the browser thread against HoloDesk's current tab.

    The result always carries the tab's url and title afterwards, so replies
    rest on what the browser shows, not on what we meant to do.
    """

    def job():
        got = controller.ensure_page()
        if not got["success"]:
            return {"success": False, "response": got["error"]}
        page = got["page"]
        result = fn(page, *args, **kwargs)
        try:
            result.setdefault("url", page.url)
            result.setdefault("title", page.title())
        except Exception:
            pass
        return result

    return browser_call(job)


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


# ---------------------------------------------------------------------------
# Generic page tools for the Brain, run through with_page(). They take
# spoken names ("Compose", "Email address") instead of selectors. Password
# field values are never read or written here.
# ---------------------------------------------------------------------------
_SNAPSHOT_JS = r"""
(limit) => {
  const out = [];
  const sel = 'h1,h2,h3,a[href],button,input:not([type=hidden]),textarea,select,' +
              '[role=button],[role=link],[role=tab],[role=menuitem],[role=textbox],[role=checkbox]';
  const nameOf = (el) => {
    if (el.type === 'password') return '(password field)';
    const isField = ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName);
    const label = el.getAttribute('aria-label') || (el.labels && el.labels[0] && el.labels[0].innerText) ||
      el.getAttribute('placeholder') || el.getAttribute('title') || el.getAttribute('alt') ||
      (isField ? el.getAttribute('name') : el.innerText) || '';
    return label.trim().replace(/\s+/g, ' ').slice(0, 80);
  };
  for (const el of document.querySelectorAll(sel)) {
    if (out.length >= limit) break;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height || r.bottom < 0 || r.top > innerHeight * 3) continue;
    const name = nameOf(el);
    if (!name) continue;
    const tag = el.tagName.toLowerCase();
    let role = el.getAttribute('role') ||
      ({a: 'link', h1: 'heading', h2: 'heading', h3: 'heading', textarea: 'textbox', select: 'select'})[tag];
    if (!role && tag === 'input') role = el.type === 'checkbox' ? 'checkbox' : (el.type === 'submit' || el.type === 'button') ? 'button' : 'textbox';
    out.push((role || tag) + ': ' + name);
  }
  return out;
}
"""


def snapshot(page, limit: int = 60) -> dict[str, Any]:
    try:
        items = page.evaluate(_SNAPSHOT_JS, limit)
        return {"success": True, "response": "; ".join(items) or "No visible controls.", "items": items}
    except Exception as exc:
        return {"success": False, "response": f"Couldn't read the page: {exc}"}


def page_text(page, limit: int = 3000) -> dict[str, Any]:
    try:
        text = page.evaluate("() => (document.querySelector('main') || document.body).innerText") or ""
        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())[:limit]
        return {"success": True, "response": text or "The page has no visible text."}
    except Exception as exc:
        return {"success": False, "response": f"Couldn't read the page text: {exc}"}


def _first_visible(locators):
    for loc in locators:
        try:
            if loc.count() and loc.first.is_visible():
                return loc.first
        except Exception:
            continue
    return None


def click_best(page, target: str) -> dict[str, Any]:
    loc = _first_visible([
        page.get_by_role("button", name=target), page.get_by_role("link", name=target),
        page.get_by_role("tab", name=target), page.get_by_role("menuitem", name=target),
        page.get_by_label(target), page.get_by_text(target),
    ])
    if loc is None:
        return {"success": False, "response": f"Nothing clickable named '{target}' on this page.", "visible": snapshot(page, 25).get("items", [])}
    try:
        loc.click(timeout=8000)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:
            pass
        return {"success": True, "response": f"Clicked '{target}'."}
    except Exception as exc:
        return {"success": False, "response": f"Couldn't click '{target}': {exc}"}


def fill_field(page, label: str, value: str) -> dict[str, Any]:
    loc = _first_visible([
        page.get_by_label(label), page.get_by_placeholder(label),
        page.get_by_role("textbox", name=label), page.get_by_role("combobox", name=label),
    ])
    if loc is None:
        return {"success": False, "response": f"No field named '{label}' on this page.", "visible": snapshot(page, 25).get("items", [])}
    try:
        if (loc.get_attribute("type") or "").lower() == "password":
            return {"success": False, "response": "I never type passwords. Chrome's password manager fills those."}
        loc.fill(value, timeout=8000)
        got = loc.input_value()
        ok = got == value
        return {"success": ok, "response": f"Filled '{label}'." if ok else f"Filled '{label}' but it reads back as '{got[:80]}'.", "value": got[:200]}
    except Exception as exc:
        return {"success": False, "response": f"Couldn't fill '{label}': {exc}"}


def press(page, key: str) -> dict[str, Any]:
    try:
        page.keyboard.press(key)
        return {"success": True, "response": f"Pressed {key}."}
    except Exception as exc:
        return {"success": False, "response": f"Couldn't press {key}: {exc}"}


def list_tabs(page) -> dict[str, Any]:
    pages = page.context.pages
    lines = [f"{i}: {p.title()[:70] or p.url}" + (" (current)" if p is page else "") for i, p in enumerate(pages)]
    return {"success": True, "response": "; ".join(lines), "tabs": lines}


def switch_tab(page, index: int) -> dict[str, Any]:
    pages = page.context.pages
    if not 0 <= index < len(pages):
        return {"success": False, "response": f"There is no tab {index}; there are {len(pages)}."}
    controller.use_tab(pages[index])
    return {"success": True, "response": f"Switched to tab {index}.", "url": pages[index].url, "title": pages[index].title()}


def new_tab(page, url: str) -> dict[str, Any]:
    tab = page.context.new_page()
    controller.use_tab(tab)
    opened = open_url(tab, url)
    if not opened["success"]:
        return {"success": False, "response": f"Opened a tab but couldn't load {url}: {opened['error']}", "url": tab.url}
    return {"success": True, "response": f"Opened {url} in a new tab.", "url": tab.url, "title": tab.title()}


def close_tab(page) -> dict[str, Any]:
    context = page.context
    title = page.title()
    page.close()
    remaining = context.pages
    if remaining:
        controller.use_tab(remaining[-1])
        return {"success": True, "response": f"Closed '{title}'.", "url": remaining[-1].url, "title": remaining[-1].title()}
    controller._page = None
    return {"success": True, "response": f"Closed '{title}'. No tabs left.", "url": "", "title": ""}


_USERNAME_SELECTOR = (
    "input[autocomplete~=username], input[type=email], input[name*=user i], input[id*=user i], "
    "input[name*=email i], input[id*=email i], input[name*=login i], input[id*=login i]"
)


def login_autofill(page) -> dict[str, Any]:
    """Sign in with the credential Chrome saved for this site in the automation profile.

    Clicks the username field (a real click is the user gesture Chrome waits for),
    picks Chrome's saved login from its dropdown with ArrowDown + Enter, and submits.
    Only whether the password field is non-empty is checked; its value is never read.
    """
    password = page.locator("input[type=password]").first

    def password_filled() -> bool:
        try:
            return bool(password.count()) and bool(password.evaluate("el => el.value.length > 0"))
        except Exception:
            return False

    def pick_saved(field) -> None:
        field.click(timeout=8000)
        page.wait_for_timeout(600)
        if not password_filled():
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(400)
            page.keyboard.press("Enter")
            page.wait_for_timeout(800)

    def submit() -> None:
        button = _first_visible([
            page.locator("button[type=submit], input[type=submit]"),
            page.get_by_role("button", name=re.compile(r"sign in|log in|login|next|continue", re.I)),
        ])
        if button is not None:
            button.click(timeout=8000)
        else:
            page.keyboard.press("Enter")

    try:
        user = _first_visible([page.locator(_USERNAME_SELECTOR)])
        if user is None and not password.count():
            return {"success": False, "response": "I don't see a login form on this page."}
        if user is not None:
            pick_saved(user)
        if not password.count():
            # Two-step logins (Google, Microsoft): username first, then a password page.
            submit()
            try:
                password.wait_for(state="visible", timeout=10000)
            except Exception:
                return {"success": False, "response": "The password step never appeared after the username."}
        if not password_filled():
            pick_saved(password)
        if not password_filled():
            return {"success": False, "response": "Chrome didn't fill a saved password here. Log in once by hand in the HoloDesk Chrome window and let Chrome save it."}
        submit()
        try:
            page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass
        still_login = password.count() and password.is_visible()
        return {"success": not still_login, "response": "Submitted the saved login." if not still_login else "Submitted, but the login form is still showing."}
    except Exception as exc:
        return {"success": False, "response": f"Autofill login failed: {exc}"}
