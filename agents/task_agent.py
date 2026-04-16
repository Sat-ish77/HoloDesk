import ctypes
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

import pyautogui

try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except Exception:
    PYPERCLIP_AVAILABLE = False

try:
    from rapidfuzz import fuzz, process as rf_process
    RAPIDFUZZ_AVAILABLE = True
except Exception:
    RAPIDFUZZ_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except Exception:
    PSUTIL_AVAILABLE = False

try:
    import win32con
    import win32gui
    WIN32_AVAILABLE = True
except Exception:
    WIN32_AVAILABLE = False

from connectors.groq_client import GroqClient
from connectors.openai_client import OpenAIClient
from core.queues import response_queue


# NEVER execute — no exceptions, no confirmation
BLOCKED_COMMANDS = [
    "rm -rf", "del /f /s",
    "format c:", "format d:",
    "regedit", "drop table",
    "delete from", "system32",
]

# Execute ONLY after reading back and waiting for "yes"
CONFIRM_BEFORE = [
    "shutdown", "restart", "sign out", "log off",
    "delete file", "delete folder",
    "send email", "send message",
    "empty recycle bin",
]

APP_MAP = {
    "chrome": "start chrome",
    "brave": "start brave",
    "firefox": "start firefox",
    "spotify": "start spotify",
    "vscode": "code .",
    "vs code": "code .",
    "notepad": "start notepad",
    "terminal": "start cmd",
    "cmd": "start cmd",
    "powershell": "start powershell",
    "word": "start winword",
    "excel": "start excel",
    "paint": "start mspaint",
    "calculator": "start calc",
    "file explorer": "start explorer",
    "task manager": "start taskmgr",
}

# Deterministic browser executable locations. We search these paths in order
# and hand the URL to the exe as a process argument — this avoids:
#   1. `start <name>` resolving to some other registered handler.
#   2. `webbrowser.open` ignoring our browser choice and using the system default.
# Expanded at class construction time so %LOCALAPPDATA% etc. get resolved.
BROWSER_PATH_CANDIDATES: dict[str, list[str]] = {
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
    ],
    "brave": [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe",
    ],
    "firefox": [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ],
    "edge": [
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ],
}

WEBSITE_MAP = {
    "facebook": "https://facebook.com",
    "instagram": "https://www.instagram.com",
    "youtube": "https://www.youtube.com",
    "netflix": "https://www.netflix.com",
    "gmail": "https://mail.google.com",
    "google": "https://www.google.com",
    "github": "https://www.github.com",
    "canvas": "https://untsystem.instructure.com",
    "reddit": "https://www.reddit.com",
    "twitter": "https://www.twitter.com",
    "linkedin": "https://www.linkedin.com",
    "spotify web": "https://open.spotify.com",
    "chatgpt": "https://chat.openai.com",
    "claude": "https://claude.ai",
    "outlook": "https://outlook.live.com",
    "calendar": "https://calendar.google.com",
    "maps": "https://maps.google.com",
    "amazon": "https://www.amazon.com",
    "stackoverflow": "https://stackoverflow.com",
    "weather": "https://weather.com",
}


class TaskAgent:
    """
    TaskAgent: Desktop automation on Windows with strong safety guardrails.

    Public API: execute(action: str, context: dict) -> dict
      returns: {success: bool, response: str, data?: dict}
    """

    def __init__(self, screen_agent=None):
        self.screen_agent = screen_agent
        self.groq = GroqClient()
        self.openai = OpenAIClient()
        self._pending_confirm: dict | None = None
        self._confirm_lock = threading.Lock()
        self._active_timer: threading.Timer | None = None
        self._cancel_shutdown = threading.Event()

        # pyautogui tuning
        pyautogui.PAUSE = 0
        pyautogui.FAILSAFE = False

        # Entity resolution tuning
        self.entity_min_score = 78  # conservative; reduces wrong app launches

    # ---------------------------
    # Entry point
    # ---------------------------
    def execute(self, action: str, context: dict) -> dict:
        try:
            raw = (context.get("raw") if isinstance(context, dict) else "") or ""
            if self._contains_blocked(raw):
                return {"success": False, "response": "I can’t help with that command."}

            # Global confirmation resolution (user says "yes"/"cancel")
            if self._pending_confirm:
                # If user is responding to a confirmation prompt, consume it first.
                if self._looks_like_yes(raw):
                    return self._confirm_yes()
                if self._looks_like_cancel(raw):
                    return self._confirm_cancel()

            # Dispatch actions
            if action == "open_app":
                return self.open_app(context.get("app_name", ""))
            if action == "close_app":
                return self.close_app(context.get("app_name", ""))
            if action == "open_web":
                return self.open_website(context.get("target", ""), raw=raw)
            if action == "open_web_in_browser":
                return self.open_web_in_browser(
                    target=context.get("target", ""),
                    browser=context.get("browser", ""),
                    raw=raw,
                )
            if action == "type_text":
                return self.type_text(self._extract_text_payload(raw), send=False)
            if action == "draft_email":
                return self.draft_email({"raw": raw})
            if action == "search":
                return self.search(self._extract_search_query(raw), engine=self._extract_search_engine(raw))
            if action == "scroll":
                direction, amount = self._parse_scroll(raw)
                return self.scroll(direction=direction, amount=amount)
            if action == "clipboard":
                return self.clipboard_action_from_raw(raw)
            if action == "ask_chatgpt":
                prompt = context.get("prompt") or raw
                return self.ask_chatgpt(prompt=prompt)
            if action == "take_screenshot_and_save":
                return self.take_screenshot_and_save()
            if action == "set_timer":
                minutes = int(context.get("minutes") or 1)
                return self.set_timer(minutes=minutes)
            if action == "weather":
                return self.open_website("weather")
            if action == "lock_screen":
                return self.lock_screen()
            if action == "minimize":
                return self.minimize_active_window()
            if action == "maximize":
                return self.maximize_active_window()
            if action == "shutdown":
                return self.shutdown_with_confirm()
            if action == "restart":
                return self.restart_with_confirm()
            if action == "declared_task_unsupported":
                # The user clearly asked for an action but we have no handler.
                # Be honest about it instead of letting chat_agent roleplay.
                return {
                    "success": False,
                    "response": (
                        "I heard you ask me to do something, but I can't do that "
                        "reliably yet. I won't pretend I did."
                    ),
                }

            return {"success": False, "response": "I’m not sure how to do that yet."}
        except Exception as e:
            return {"success": False, "response": f"That action failed: {e}"}

    # ---------------------------
    # Safety helpers
    # ---------------------------
    @staticmethod
    def _contains_blocked(text: str) -> bool:
        t = (text or "").lower()
        return any(b in t for b in BLOCKED_COMMANDS)

    def _needs_confirmation(self, text: str) -> bool:
        t = (text or "").lower()
        return any(x in t for x in CONFIRM_BEFORE)

    @staticmethod
    def _looks_like_yes(text: str) -> bool:
        t = (text or "").strip().lower()
        return t in {"yes", "yep", "yeah", "do it", "confirm", "okay", "ok"}

    @staticmethod
    def _looks_like_cancel(text: str) -> bool:
        t = (text or "").strip().lower()
        return t in {"cancel", "stop", "no", "nope", "don't", "dont"}

    def _confirm_yes(self) -> dict:
        with self._confirm_lock:
            pending = self._pending_confirm
            self._pending_confirm = None
        if not pending:
            return {"success": True, "response": "Okay."}
        fn = pending.get("fn")
        if callable(fn):
            return fn()
        return {"success": True, "response": "Done."}

    def _confirm_cancel(self) -> dict:
        with self._confirm_lock:
            pending = self._pending_confirm
            self._pending_confirm = None
        if pending and pending.get("kind") == "shutdown":
            self._cancel_shutdown.set()
            return {"success": True, "response": "Shutdown cancelled."}
        return {"success": True, "response": "Cancelled."}

    def _set_pending_confirm(self, message: str, fn, kind: str = "generic") -> dict:
        with self._confirm_lock:
            self._pending_confirm = {"message": message, "fn": fn, "ts": time.time(), "kind": kind}
        return {"success": True, "response": message}

    # ---------------------------
    # App + Web
    # ---------------------------
    def open_app(self, app_name: str) -> dict:
        app_raw = (app_name or "").strip()
        app = app_raw.lower()
        if not app:
            return {"success": False, "response": "Which app should I open?"}

        resolved = self._resolve_app_name(app_raw)
        if not resolved["success"]:
            return resolved
        app = resolved["name"]

        cmd = APP_MAP.get(app)
        try:
            if cmd:
                subprocess.Popen(cmd, shell=True)
                return {"success": True, "response": f"Opening {app}."}

            # Try direct open via start
            subprocess.Popen(f'start "" "{app}"', shell=True)
            return {"success": True, "response": f"Opening {app}."}
        except Exception as e:
            return {"success": False, "response": f"I couldn't open {app}: {e}"}

    def close_app(self, app_name: str) -> dict:
        if not PSUTIL_AVAILABLE:
            return {"success": False, "response": "I can’t close apps because psutil isn’t installed."}
        target_raw = (app_name or "").strip()
        target = target_raw.lower()
        if not target:
            return {"success": False, "response": "Which app should I close?"}

        resolved = self._resolve_running_process_name(target_raw)
        if not resolved["success"]:
            # fall back to fuzzy app-map resolution if no process match
            fallback = self._resolve_app_name(target_raw, allow_nonrunning=True)
            if fallback.get("success"):
                target = fallback["name"]
            else:
                return resolved
        else:
            target = resolved["name"]

        # confirmation not required by your list, but still safe to do without force-kill
        closed = 0
        for p in psutil.process_iter(["name"]):
            try:
                name = (p.info.get("name") or "").lower()
                if target in name or name.replace(".exe", "") == target:
                    p.terminate()
                    closed += 1
            except Exception:
                continue
        if closed:
            return {"success": True, "response": f"Closed {target}."}
        return {"success": False, "response": f"I couldn’t find a running process for {target}."}

    def open_website(self, url_or_name: str, raw: str = "") -> dict:
        target_raw = self._sanitize_site_target(url_or_name, raw=raw)
        target = target_raw.lower()
        if not target:
            return {"success": False, "response": "Which website should I open?"}

        resolved_site = self._resolve_website_name(target_raw)
        if resolved_site.get("resolved_name"):
            target = resolved_site["resolved_name"]

        url = WEBSITE_MAP.get(target)
        if not url:
            if target.startswith("http://") or target.startswith("https://"):
                url = target
            elif any(x in target for x in [".com", ".org", ".net", ".io"]):
                url = "https://" + target
            else:
                url = "https://" + target + ".com"

        try:
            webbrowser.open(url)
            return {"success": True, "response": f"Opening {target} in your browser."}
        except Exception as e:
            return {"success": False, "response": f"I couldn't open that site: {e}"}

    def open_web_in_browser(self, target: str, browser: str, raw: str = "") -> dict:
        """
        Deterministic two-step behavior:
          1) resolve a real browser executable path (NOT the default handler)
          2) launch that exe with the URL as a direct argv argument

        Using `subprocess.Popen([exe, url])` with a resolved path guarantees we
        actually open the URL in the browser the user asked for, regardless of
        what the Windows default handler is set to. The old
        `start <name> "<url>"` form silently fell back to the default browser
        when the name didn't resolve to a registered app alias.
        """
        target_clean = self._sanitize_site_target(target, raw=raw)
        if not target_clean:
            return {"success": False, "response": "Which site should I open?"}

        browser_clean = self._resolve_browser_name(browser or raw)
        if not browser_clean:
            return {"success": False, "response": "Which browser should I use? Chrome or Brave?"}

        url = self._build_url_from_site_name(target_clean)

        exe_path = self._find_browser_executable(browser_clean)
        if not exe_path:
            # Be explicit about failure rather than silently falling back to
            # webbrowser.open() (which would use the default browser — the
            # exact roleplay/mismatch failure mode we're fixing).
            return {
                "success": False,
                "response": (
                    f"I couldn't find {browser_clean} installed on this PC, "
                    f"so I didn't open {target_clean}. Install it or try a different browser."
                ),
            }

        try:
            subprocess.Popen([exe_path, url])
            return {"success": True, "response": f"Opening {target_clean} in {browser_clean}."}
        except Exception as e:
            return {"success": False, "response": f"I couldn't open that in {browser_clean}: {e}"}

    @staticmethod
    def _build_url_from_site_name(target_clean: str) -> str:
        """Turn 'facebook' / 'facebook.com' / 'https://...' into a usable URL."""
        key = target_clean.lower()
        if key in WEBSITE_MAP:
            return WEBSITE_MAP[key]
        if target_clean.startswith("http://") or target_clean.startswith("https://"):
            return target_clean
        if any(x in target_clean for x in [".com", ".org", ".net", ".io"]):
            return "https://" + target_clean
        return "https://" + target_clean + ".com"

    @staticmethod
    def _find_browser_executable(browser: str) -> str | None:
        """
        Resolve a browser name ('chrome', 'brave', ...) to an absolute exe path.
        Checks known install locations first, then falls back to PATH lookup.
        Returns None if the browser can't be found — caller must handle that.
        """
        for raw_path in BROWSER_PATH_CANDIDATES.get(browser, []):
            path = os.path.expandvars(raw_path)
            if os.path.isfile(path):
                return path
        # shutil.which handles the case where the browser was added to PATH
        # (e.g. Chocolatey/Scoop installs) without us having to guess the dir.
        which = shutil.which(browser) or shutil.which(f"{browser}.exe")
        return which

    # ---------------------------
    # Interaction (basic)
    # ---------------------------
    def type_text(self, text: str, send: bool = False) -> dict:
        if not text.strip():
            return {"success": False, "response": "What should I type?"}
        try:
            if PYPERCLIP_AVAILABLE:
                pyperclip.copy(text)
                pyautogui.hotkey("ctrl", "v")
            else:
                pyautogui.write(text, interval=0.01)
            if send:
                pyautogui.press("enter")
            return {"success": True, "response": "Done."}
        except Exception as e:
            return {"success": False, "response": f"I couldn't type that: {e}"}

    # ---------------------------
    # Email drafting (v1: generate + open Gmail + copy)
    # ---------------------------
    def draft_email(self, context: dict) -> dict:
        raw = (context or {}).get("raw", "")
        # Minimal extraction; production would ask clarifying questions.
        recipient = self._extract_email_recipient(raw)
        subject = self._extract_subject(raw) or " "
        instructions = raw
        tone = "professional"

        system = (
            "You are an expert email writer. Write a complete email body only. "
            "Do not include a subject line. Keep it concise and clear."
        )
        prompt = f"Write an email to {recipient or 'the recipient'}.\nTone: {tone}\nInstructions: {instructions}"
        try:
            body = self.groq.complete(prompt=prompt, system=system, max_tokens=300)
        except Exception as e:
            return {"success": False, "response": f"I couldn't draft the email: {e}"}

        try:
            webbrowser.open(WEBSITE_MAP["gmail"])
        except Exception:
            pass

        # Copy full draft as backup
        if PYPERCLIP_AVAILABLE:
            try:
                pyperclip.copy(body)
            except Exception:
                pass

        return {
            "success": True,
            "response": "Email drafted. I opened Gmail and copied the email body to your clipboard.",
            "data": {"subject": subject, "recipient": recipient, "body": body},
        }

    # ---------------------------
    # Search / Scroll / Clipboard
    # ---------------------------
    def search(self, query: str, engine: str = "google") -> dict:
        q = (query or "").strip()
        if not q:
            return {"success": False, "response": "What should I search for?"}
        engine = (engine or "google").lower()
        try:
            if engine == "youtube":
                webbrowser.open(f"https://youtube.com/results?search_query={q}")
                return {"success": True, "response": f"Searching YouTube for {q}."}
            webbrowser.open(f"https://google.com/search?q={q}")
            return {"success": True, "response": f"Searching Google for {q}."}
        except Exception as e:
            return {"success": False, "response": f"I couldn't start the search: {e}"}

    def scroll(self, direction: str, amount: int = 5) -> dict:
        try:
            amt = int(amount)
            if direction == "down":
                pyautogui.scroll(-amt * 200)
            else:
                pyautogui.scroll(amt * 200)
            return {"success": True, "response": ""}  # silent action
        except Exception as e:
            return {"success": False, "response": f"I couldn't scroll: {e}"}

    def clipboard_action_from_raw(self, raw: str) -> dict:
        t = (raw or "").lower()
        if "read" in t or "what" in t:
            return self.clipboard_action("read")
        if "copy" in t:
            payload = self._extract_after(raw, "copy")
            return self.clipboard_action("copy", payload)
        if "paste" in t:
            return self.type_text(self.clipboard_action("read").get("response", ""), send=False)
        return {"success": False, "response": "What should I do with the clipboard?"}

    def clipboard_action(self, action: str, text: str = "") -> dict:
        if not PYPERCLIP_AVAILABLE:
            return {"success": False, "response": "Clipboard actions require pyperclip."}
        try:
            if action == "read":
                return {"success": True, "response": pyperclip.paste() or "(clipboard is empty)"}
            if action == "copy":
                pyperclip.copy(text)
                return {"success": True, "response": "Copied to clipboard."}
            return {"success": False, "response": "Unknown clipboard action."}
        except Exception as e:
            return {"success": False, "response": f"Clipboard failed: {e}"}

    # ---------------------------
    # ChatGPT tool (OpenAI text)
    # ---------------------------
    def ask_chatgpt(self, prompt: str, screen_context: str | None = None) -> dict:
        full_prompt = prompt.strip()
        if screen_context:
            full_prompt = f"{full_prompt}\n\nScreen context: {screen_context}"
        system = (
            "You are HoloDesk. Answer helpfully and concisely (2-4 sentences). "
            "If the user asks for steps, give a short ordered list."
        )
        try:
            # Reuse OpenAIClient's underlying OpenAI SDK for text as well.
            client = self.openai._get_client()
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=350,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": full_prompt},
                ],
            )
            text = resp.choices[0].message.content.strip()
        except Exception as e:
            return {"success": False, "response": f"I couldn't reach ChatGPT right now: {e}"}

        if PYPERCLIP_AVAILABLE:
            try:
                pyperclip.copy(text)
            except Exception:
                pass

        return {"success": True, "response": text}

    # ---------------------------
    # Screenshot / Timer / Lock
    # ---------------------------
    def take_screenshot_and_save(self) -> dict:
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            desktop = Path.home() / "Desktop"
            desktop.mkdir(parents=True, exist_ok=True)
            path = desktop / f"holodesk_capture_{ts}.png"
            img = pyautogui.screenshot()
            img.save(str(path))
            return {"success": True, "response": f"Screenshot saved to your Desktop: {path.name}"}
        except Exception as e:
            return {"success": False, "response": f"I couldn't take a screenshot: {e}"}

    def set_timer(self, minutes: int) -> dict:
        mins = max(1, int(minutes))
        seconds = mins * 60

        # Timer must trigger speech; orchestrator/voice owns speaking, so we emit a VOICE_STATE
        # and rely on UI/main to call speak is not safe here. We'll just return confirmation
        # and the voice loop can speak when this task is invoked.
        # The actual timer callback will push a message into response_queue for main/voice.
        try:
            if self._active_timer:
                try:
                    self._active_timer.cancel()
                except Exception:
                    pass
                self._active_timer = None

            def _timer_done():
                try:
                    response_queue.put_nowait({"type": "TIMER_DONE", "text": "Timer done."})
                except Exception:
                    pass

            self._active_timer = threading.Timer(seconds, _timer_done)
            self._active_timer.daemon = True
            self._active_timer.start()
            return {"success": True, "response": f"Okay. Timer set for {mins} minutes."}
        except Exception as e:
            return {"success": False, "response": f"I couldn't set a timer: {e}"}

    def lock_screen(self) -> dict:
        try:
            ctypes.windll.user32.LockWorkStation()
            return {"success": True, "response": "Locked your screen."}
        except Exception as e:
            return {"success": False, "response": f"I couldn't lock the screen: {e}"}

    # ---------------------------
    # Shutdown / Restart — confirm-before with 10s cancel window
    # ---------------------------
    def shutdown_with_confirm(self) -> dict:
        """
        Two-stage safety:
          1. First call arms the pending confirmation. User must say 'yes'
             (handled in execute() via _looks_like_yes) before we do anything.
          2. When confirmed, we schedule the actual shutdown 10 seconds out
             and leave a cancel window — the user can still say 'cancel'
             within that window to abort via _confirm_cancel().
        """
        return self._set_pending_confirm(
            "I'm about to shut down this PC. Say 'yes' to confirm, or 'cancel' to stop.",
            self._schedule_shutdown,
            kind="shutdown",
        )

    def restart_with_confirm(self) -> dict:
        return self._set_pending_confirm(
            "I'm about to restart this PC. Say 'yes' to confirm, or 'cancel' to stop.",
            self._schedule_restart,
            kind="shutdown",
        )

    def _schedule_shutdown(self) -> dict:
        return self._schedule_power_action("shutdown /s /t 0", "Shutting down in 10 seconds. Say 'cancel' to abort.")

    def _schedule_restart(self) -> dict:
        return self._schedule_power_action("shutdown /r /t 0", "Restarting in 10 seconds. Say 'cancel' to abort.")

    def _schedule_power_action(self, shell_cmd: str, spoken: str) -> dict:
        self._cancel_shutdown.clear()
        # Re-arm the pending slot so the user saying 'cancel' during the
        # 10-second window still routes through _confirm_cancel() and sets
        # the event below.
        self._set_pending_confirm(spoken, lambda: {"success": True, "response": "Already scheduled."}, kind="shutdown")

        def _do_power_action():
            # wait(10.0) returns True if cancel was signaled, False on timeout.
            if self._cancel_shutdown.wait(10.0):
                return
            try:
                subprocess.Popen(shell_cmd, shell=True)
            except Exception:
                pass

        threading.Thread(target=_do_power_action, daemon=True).start()
        return {"success": True, "response": spoken}

    # ---------------------------
    # Window controls
    # ---------------------------
    def minimize_active_window(self) -> dict:
        if not WIN32_AVAILABLE:
            return {"success": False, "response": "Window control requires pywin32."}
        try:
            hwnd = win32gui.GetForegroundWindow()
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            return {"success": True, "response": "Minimized."}
        except Exception as e:
            return {"success": False, "response": f"I couldn't minimize: {e}"}

    def maximize_active_window(self) -> dict:
        if not WIN32_AVAILABLE:
            return {"success": False, "response": "Window control requires pywin32."}
        try:
            hwnd = win32gui.GetForegroundWindow()
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            return {"success": True, "response": "Maximized."}
        except Exception as e:
            return {"success": False, "response": f"I couldn't maximize: {e}"}

    # ---------------------------
    # Parsing helpers
    # ---------------------------
    @staticmethod
    def _extract_text_payload(raw: str) -> str:
        # "type hello world" -> "hello world"
        m = re.search(r"\b(type|write|paste)\b\s+(.*)$", raw, flags=re.IGNORECASE)
        return m.group(2).strip() if m else raw.strip()

    @staticmethod
    def _extract_search_query(raw: str) -> str:
        t = raw.lower()
        for key in ["search youtube for", "search google for", "search for", "google", "look up", "find"]:
            idx = t.find(key)
            if idx >= 0:
                return raw[idx + len(key):].strip(" :.-")
        return raw

    @staticmethod
    def _extract_search_engine(raw: str) -> str:
        t = raw.lower()
        if "youtube" in t:
            return "youtube"
        return "google"

    @staticmethod
    def _parse_scroll(raw: str) -> tuple[str, int]:
        t = raw.lower()
        direction = "down" if "down" in t else "up"
        amount = 5
        if "a lot" in t or "lot" in t:
            amount = 15
        elif "a little" in t or "little" in t:
            amount = 3
        return direction, amount

    @staticmethod
    def _extract_after(text: str, key: str) -> str:
        lower = text.lower()
        idx = lower.find(key)
        if idx < 0:
            return ""
        return text[idx + len(key):].strip(" :.-")

    @staticmethod
    def _extract_email_recipient(raw: str) -> str:
        m = re.search(r"\bto\s+([\\w.+'-]+@[\\w.-]+)", raw, flags=re.IGNORECASE)
        return m.group(1) if m else ""

    @staticmethod
    def _extract_subject(raw: str) -> str:
        m = re.search(r"\bsubject\s*:\s*(.+)$", raw, flags=re.IGNORECASE)
        return m.group(1).strip() if m else ""

    # ---------------------------
    # Entity resolution helpers
    # ---------------------------
    def _resolve_app_name(self, app_name: str, allow_nonrunning: bool = True) -> dict:
        """
        Resolve misheard app names using APP_MAP keys (and optionally running processes).
        Returns: {success: bool, name?: str, score?: int, response?: str}
        """
        raw = (app_name or "").strip().lower()
        if not raw:
            return {"success": False, "response": "Which app?"}

        candidates = list(APP_MAP.keys())
        if allow_nonrunning and PSUTIL_AVAILABLE:
            candidates.extend(self._list_running_process_basenames(limit=50))
        candidates = sorted(set(candidates))

        if raw in candidates:
            return {"success": True, "name": raw, "score": 100}

        if not RAPIDFUZZ_AVAILABLE:
            return {"success": True, "name": raw, "score": 0}

        match = rf_process.extractOne(raw, candidates, scorer=fuzz.WRatio)
        if not match:
            return {"success": False, "response": "I couldn’t figure out which app you meant. Please repeat."}
        best, score, _ = match
        if score < self.entity_min_score:
            return {"success": False, "response": f"I heard '{raw}', but I'm not confident which app that is. Please repeat."}
        return {"success": True, "name": best, "score": int(score)}

    def _resolve_running_process_name(self, app_name: str) -> dict:
        """
        Resolve to an actually running process basename (best for close_app).
        """
        raw = (app_name or "").strip().lower()
        if not raw:
            return {"success": False, "response": "Which app should I close?"}
        if not PSUTIL_AVAILABLE:
            return {"success": False, "response": "psutil is required to close apps."}

        running = self._list_running_process_basenames(limit=150)
        if not running:
            return {"success": False, "response": "I couldn’t read running apps right now."}
        if raw in running:
            return {"success": True, "name": raw, "score": 100}
        if not RAPIDFUZZ_AVAILABLE:
            return {"success": False, "response": f"I couldn’t find a running process for {raw}."}

        match = rf_process.extractOne(raw, running, scorer=fuzz.WRatio)
        if not match:
            return {"success": False, "response": f"I couldn’t find a running process for {raw}."}
        best, score, _ = match
        if score < self.entity_min_score:
            return {"success": False, "response": f"I heard '{raw}', but I’m not sure which running app that is. Please repeat."}
        return {"success": True, "name": best, "score": int(score)}

    def _resolve_website_name(self, site: str) -> dict:
        raw = (site or "").strip().lower()
        if not raw:
            return {"resolved_name": None, "score": 0}
        keys = list(WEBSITE_MAP.keys())
        if raw in keys:
            return {"resolved_name": raw, "score": 100}
        if not RAPIDFUZZ_AVAILABLE:
            return {"resolved_name": None, "score": 0}
        match = rf_process.extractOne(raw, keys, scorer=fuzz.WRatio)
        if not match:
            return {"resolved_name": None, "score": 0}
        best, score, _ = match
        if score < self.entity_min_score:
            return {"resolved_name": None, "score": int(score)}
        return {"resolved_name": best, "score": int(score)}

    def _resolve_browser_name(self, text: str) -> str:
        t = (text or "").lower()
        # direct hits
        for b in ["chrome", "brave", "firefox", "edge"]:
            if b in t:
                return b
        if not RAPIDFUZZ_AVAILABLE:
            return ""
        match = rf_process.extractOne(t.strip(), ["chrome", "brave", "firefox", "edge"], scorer=fuzz.WRatio)
        if not match:
            return ""
        best, score, _ = match
        return best if score >= self.entity_min_score else ""

    # Filler words/phrases that humans routinely tack onto voice commands.
    # We strip these before resolving a site/app name so "facebook for me"
    # resolves cleanly to "facebook" instead of failing.
    _SPEECH_FILLER = (
        "for me", "please", "can you", "could you", "would you",
        "right now", "now", "up", "home", "homepage",
    )

    def _strip_speech_filler(self, text: str) -> str:
        t = (text or "").lower().strip()
        if not t:
            return t
        # Repeatedly trim trailing filler phrases (in order of length so
        # multi-word filler like "for me" wins over single-word "me").
        filler_sorted = sorted(self._SPEECH_FILLER, key=len, reverse=True)
        changed = True
        while changed:
            changed = False
            for f in filler_sorted:
                if t.endswith(" " + f):
                    t = t[: -(len(f) + 1)].strip()
                    changed = True
                elif t == f:
                    return ""
        return t.strip(" .,!?:;\"'")

    def _sanitize_site_target(self, target: str, raw: str = "") -> str:
        """
        Extract a usable site/url token from noisy speech like:
          'facebook.com for me in brave home'
        """
        combined = f"{target or ''} {raw or ''}".strip().lower()
        if not combined:
            return ""

        tokens = re.split(r"\s+", combined)
        # prioritize explicit url tokens
        for tok in tokens:
            t = tok.strip(" .,!?:;\"'")
            if t.startswith("http://") or t.startswith("https://"):
                return t
        # then domain-like tokens
        for tok in tokens:
            t = tok.strip(" .,!?:;\"'")
            if any(x in t for x in [".com", ".org", ".net", ".io"]):
                return t
        # then known site keys
        for tok in tokens:
            t = tok.strip(" .,!?:;\"'")
            if t in WEBSITE_MAP:
                return t

        # Fall back to the trimmed target with filler removed. This is what
        # lets "facebook for me" survive as "facebook" rather than failing
        # entity resolution because "for me" was treated as part of the name.
        fallback = self._strip_speech_filler((target or "").strip().lower())
        return fallback

    @staticmethod
    def _list_running_process_basenames(limit: int = 100) -> list[str]:
        if not PSUTIL_AVAILABLE:
            return []
        names = []
        for p in psutil.process_iter(["name"]):
            try:
                n = (p.info.get("name") or "").lower()
                if not n:
                    continue
                n = n.replace(".exe", "")
                names.append(n)
            except Exception:
                continue
            if len(names) >= limit:
                break
        return sorted(set(names))

