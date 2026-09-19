"""BrainAgent: one Claude tool-calling loop for commands the deterministic router can't match.

Every tool wraps existing HoloDesk code and returns an observation dict
({"success", "response", ...}). The reply is built from those observations;
risky tools go through TaskAgent's existing confirmation gate.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from typing import Any, Callable

from agents.memory_agent import _get_active_window
from agents.task_agent import pyautogui
from automation import win_ui

SYSTEM_PROMPT = """You are HoloDesk, a voice assistant that operates this Windows laptop for a user who cannot comfortably use a mouse or keyboard. Your replies are spoken aloud: one or two short sentences, no markdown, no lists.

Act only through the tools. Each tool returns an observation. Base every statement about what happened on those observations, and never say you did something no tool observed. If a tool fails, say so plainly with the reason.

If the request is ambiguous (which app, which window, which text), ask one short question instead of guessing.

Sending, submitting, deleting, closing apps, and powering off need the user's confirmation. When a tool says confirmation is pending, stop and repeat its question.

For plain conversation or questions you can answer from knowledge, answer directly without tools."""

# Past-tense action claims that must be backed by at least one tool call.
# ponytail: regex heuristic; a model that phrases a false claim differently slips through.
_CLAIM_RE = re.compile(
    r"\b(i(?:'ve| have)?\s+(?:opened|closed|clicked|sent|typed|scrolled|minimi[sz]ed|maximi[sz]ed|submitted|launched|pressed)|all done|done!)",
    re.IGNORECASE,
)
_RISKY_CLICK_RE = re.compile(
    r"\b(send|submit|delete|remove|erase|buy|pay|purchase|order|checkout|uninstall|sign out|log out|format|discard|empty)\b",
    re.IGNORECASE,
)
_FAILURE_WORDS = ("couldn't", "could not", "can't", "cannot", "failed", "didn't", "unable", "not able", "error")


def _schema(props: dict | None = None, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": props or {},
        "required": required or [],
        "additionalProperties": False,
    }


class BrainAgent:
    MAX_TOOL_CALLS = 8
    MAX_SECONDS = 45  # voice thread waits 120 s, so a reply always lands first
    HISTORY_TURNS = 6

    def __init__(self, task_agent, memory_agent=None, screen_agent=None, client=None, model: str | None = None):
        self.task = task_agent
        self.memory = memory_agent
        self.screen = screen_agent
        self._client = client
        self.model = model or os.getenv("HOLODESK_BRAIN_MODEL", "claude-sonnet-5")
        self.history: list[dict] = []
        self.tools: dict[str, tuple[dict, Callable[..., dict]]] = self._build_tools()

    @property
    def available(self) -> bool:
        return self._client is not None or bool(os.getenv("ANTHROPIC_API_KEY", "").strip())

    def _get_client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(timeout=30.0, max_retries=1)
        return self._client

    # Orchestrator calls agent.execute(action, context) for unknown agent types.
    def execute(self, action: str = "run", context: dict | None = None) -> dict:
        return self.run((context or {}).get("raw", ""))

    # ------------------------------------------------------------------
    # Loop
    # ------------------------------------------------------------------
    def run(self, text: str) -> dict:
        text = (text or "").strip()
        if not text:
            return {"success": False, "response": "I didn't catch a command.", "tool_log": []}

        messages: list[dict] = list(self.history) + [{"role": "user", "content": text}]
        tool_log: list[dict] = []
        started = time.time()
        reply = ""

        try:
            client = self._get_client()
            while True:
                response = client.messages.create(
                    model=self.model,
                    max_tokens=2048,
                    system=self._system(text),
                    tools=self._tool_defs(),
                    messages=messages,
                    output_config={"effort": "low"},
                )
                if response.stop_reason == "refusal":
                    reply = "I can't help with that one."
                    break
                if response.stop_reason != "tool_use":
                    reply = " ".join(b.text for b in response.content if b.type == "text").strip()
                    break

                messages.append({"role": "assistant", "content": response.content})
                results, pending = [], None
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    if pending is not None or len(tool_log) >= self.MAX_TOOL_CALLS:
                        obs = {"success": False, "response": "Skipped: step limit or pending confirmation."}
                    else:
                        obs = self._call_tool(block.name, block.input)
                        tool_log.append({"tool": block.name, "input": block.input, **obs})
                        if obs.get("pending_confirmation"):
                            pending = obs
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(obs, default=str),
                        "is_error": not obs.get("success", False),
                    })

                if pending is not None:
                    # The gate owns the next turn: "yes"/"cancel" is caught by the orchestrator.
                    reply = pending["response"]
                    break
                if len(tool_log) >= self.MAX_TOOL_CALLS or time.time() - started > self.MAX_SECONDS:
                    reply = "I stopped after " + self._summarize(tool_log)
                    break
                messages.append({"role": "user", "content": results})
        except Exception as exc:
            done = f" Before that: {self._summarize(tool_log)}" if tool_log else ""
            return {"success": False, "response": f"I couldn't reach my brain: {type(exc).__name__}.{done}", "tool_log": tool_log}

        reply = self._enforce_honesty(reply, tool_log)
        self._remember_turn(text, reply)
        return {"success": all(t.get("success") for t in tool_log) if tool_log else True, "response": reply, "tool_log": tool_log}

    def _call_tool(self, name: str, args: Any) -> dict:
        entry = self.tools.get(name)
        if entry is None:
            return {"success": False, "response": f"Unknown tool {name}."}
        before = getattr(self.task, "_pending_confirm", None)
        try:
            obs = entry[1](**(args or {}))
        except Exception as exc:
            obs = {"success": False, "response": f"{name} failed: {exc}"}
        after = getattr(self.task, "_pending_confirm", None)
        if after is not None and after is not before:
            obs = {**obs, "pending_confirmation": True}
        return obs

    @staticmethod
    def _summarize(tool_log: list[dict]) -> str:
        if not tool_log:
            return "doing nothing."
        return "; ".join(f"{t['tool']}: {t.get('response') or ('ok' if t.get('success') else 'failed')}" for t in tool_log) + "."

    def _enforce_honesty(self, reply: str, tool_log: list[dict]) -> str:
        if not reply:
            reply = self._summarize(tool_log) if tool_log else "I don't have an answer for that."
        if not tool_log and _CLAIM_RE.search(reply):
            return "I didn't take any action for that, so I can't say it's done."
        failed = [t for t in tool_log if not t.get("success") and not t.get("pending_confirmation")]
        if failed and not any(w in reply.lower() for w in _FAILURE_WORDS):
            reply += " Note: " + "; ".join(f"{t['tool']} failed: {t.get('response', '')}" for t in failed)
        return reply

    def _remember_turn(self, user: str, reply: str) -> None:
        self.history += [{"role": "user", "content": user}, {"role": "assistant", "content": reply}]
        self.history = self.history[-self.HISTORY_TURNS * 2:]

    def _system(self, text: str) -> list[dict]:
        # The cache breakpoint covers tools + the fixed prompt; per-request memory goes after it.
        blocks = [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]
        if self.memory is not None:
            try:
                facts = self.memory.recall(text)
                habits = self.memory.format_habits_for_prompt()
            except Exception:
                facts, habits = [], ""
            context = "Usage habits: " + (habits or "none yet.")
            if facts:
                context += "\nThings the user asked you to remember: " + "; ".join(facts)
            blocks.append({"type": "text", "text": context})
        return blocks

    def _tool_defs(self) -> list[dict]:
        return [{"name": n, "description": s["description"], "input_schema": s["input_schema"]} for n, (s, _) in self.tools.items()]

    # ------------------------------------------------------------------
    # Tools (thin wrappers over existing code)
    # ------------------------------------------------------------------
    @staticmethod
    def _window_after(result: dict, wait: float = 1.2) -> dict:
        """Attach the foreground window title so the reply rests on an observation."""
        if result.get("success"):
            time.sleep(wait)
            app, title = _get_active_window()
            result = {**result, "active_window": title or app}
        return result

    def _build_tools(self) -> dict:
        t = self.task
        tools: dict[str, tuple[dict, Callable[..., dict]]] = {}

        def add(name, description, fn, props=None, required=None):
            tools[name] = ({"description": description, "input_schema": _schema(props, required)}, fn)

        add("open_app", "Open a desktop application by name, e.g. notepad, calculator, chrome, spotify.",
            lambda name: self._window_after(t.open_app(name)),
            {"name": {"type": "string"}}, ["name"])
        add("open_website", "Open a website by name or URL in the default browser, e.g. youtube, gmail, canvas, https://example.com.",
            lambda target: self._window_after(t.open_website(target, raw=target), 2.0),
            {"target": {"type": "string"}}, ["target"])
        add("scroll", "Scroll the window under the mouse up or down. amount is 1-20 notches, default 5.",
            self._scroll,
            {"direction": {"type": "string", "enum": ["up", "down"]}, "amount": {"type": "integer"}}, ["direction"])
        add("type_text", "Type text into the focused field of the active window. Does not press Enter.",
            self._type_text, {"text": {"type": "string"}}, ["text"])
        add("press_keys", "Press a key or key combination, e.g. ['enter'], ['ctrl','t'], ['alt','tab'].",
            self._press_keys, {"keys": {"type": "array", "items": {"type": "string"}}}, ["keys"])
        add("minimize", "Minimize the active window.", lambda: self._window_after(t.minimize_active_window(), 0.5))
        add("maximize", "Maximize the active window.", lambda: self._window_after(t.maximize_active_window(), 0.5))
        add("close_app", "Close an application by name. Asks the user to confirm first.",
            lambda name: t.close_app_with_confirm(name, raw=f"close {name}"),
            {"name": {"type": "string"}}, ["name"])
        add("get_active_window", "Return the title and process of the window currently in front.", self._active_window)
        add("lock_screen", "Lock the PC.", t.lock_screen)
        add("sleep_pc", "Put the PC to sleep.", self._sleep)
        add("shutdown", "Shut down the PC. Asks the user to confirm first.", t.shutdown_with_confirm)
        add("restart", "Restart the PC. Asks the user to confirm first.", t.restart_with_confirm)
        add("volume", "Change system volume.", self._volume,
            {"action": {"type": "string", "enum": ["up", "down", "mute"]}, "steps": {"type": "integer"}}, ["action"])
        add("list_windows", "List the open app windows, front first.", lambda: win_ui.list_windows())
        add("switch_to", "Bring an open window to the front by (part of) its title.",
            lambda window: win_ui.focus_window(window), {"window": {"type": "string"}}, ["window"])
        add("read_screen_controls", "Read the buttons, fields, and text of the front app window as text. Fast; use before clicking in a native app.",
            lambda: win_ui.read_controls())
        add("click", "Click a named control in the front native app window, e.g. 'Seven', 'Save', 'File'. Risky buttons (send, delete, buy...) ask the user first.",
            self._click, {"name": {"type": "string"}, "control_type": {"type": "string"}}, ["name"])
        add("set_field", "Replace the text in a named edit field of the front native app window and read it back.",
            lambda name, text: win_ui.set_text(name, text),
            {"name": {"type": "string"}, "text": {"type": "string"}}, ["name", "text"])
        if self.memory is not None:
            add("remember", "Save a fact the user wants remembered, e.g. 'my advisor is Dr. Lee'. Never passwords or keys.",
                lambda fact: self.memory.remember(fact), {"fact": {"type": "string"}}, ["fact"])
            add("recall", "Search facts the user asked you to remember.", self._recall,
                {"query": {"type": "string"}}, ["query"])
        if self.screen is not None:
            add("look_at_screen", "Look at the screen and answer a question about what is visible. Slow (10-20 s); use only when the user asks about the screen.",
                lambda question: self.screen.execute(question=question),
                {"question": {"type": "string"}}, ["question"])
        return tools

    def _click(self, name: str, control_type: str | None = None) -> dict:
        if _RISKY_CLICK_RE.search(name or ""):
            return self.task._set_pending_confirm(
                f"Clicking '{name}' can't be undone easily. Say 'yes' to click it, or 'cancel'.",
                lambda: win_ui.click_control(name, control_type),
                kind="click",
            )
        return win_ui.click_control(name, control_type)

    def _recall(self, query: str) -> dict:
        facts = self.memory.recall(query)
        if not facts:
            return {"success": True, "response": "Nothing remembered about that.", "facts": []}
        return {"success": True, "response": "; ".join(facts), "facts": facts}

    def _scroll(self, direction: str, amount: int = 5) -> dict:
        amount = max(1, min(int(amount or 5), 20))
        result = self.task.scroll(direction=direction, amount=amount)
        if result.get("success"):
            return {"success": True, "response": f"Scrolled {direction} {amount}."}
        return result

    def _type_text(self, text: str) -> dict:
        result = self.task.type_text(text, send=False)
        if result.get("success"):
            app, title = _get_active_window()
            return {"success": True, "response": f"Typed {len(text)} characters.", "active_window": title or app}
        return result

    def _press_keys(self, keys: list[str]) -> dict:
        keys = [k.strip().lower() for k in keys or [] if k and k.strip()]
        if not keys:
            return {"success": False, "response": "No keys given."}
        unknown = [k for k in keys if k not in pyautogui.KEYBOARD_KEYS]
        if unknown:
            return {"success": False, "response": f"Unknown key names: {', '.join(unknown)}."}
        combo = "+".join(keys)
        if "delete" in keys or "del" in keys or {"alt", "f4"} <= set(keys):
            return self.task._set_pending_confirm(
                f"Pressing {combo} can delete or close things. Say 'yes' to press it, or 'cancel'.",
                lambda: self._do_press(keys),
                kind="keys",
            )
        return self._do_press(keys)

    def _do_press(self, keys: list[str]) -> dict:
        pyautogui.hotkey(*keys)
        return self._window_after({"success": True, "response": f"Pressed {'+'.join(keys)}."}, 0.5)

    @staticmethod
    def _active_window() -> dict:
        app, title = _get_active_window()
        if not app and not title:
            return {"success": False, "response": "The active window is private or unreadable."}
        return {"success": True, "response": f"{title} ({app})", "title": title, "process": app}

    @staticmethod
    def _sleep() -> dict:
        subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
        return {"success": True, "response": "Sleep command sent."}

    @staticmethod
    def _volume(action: str, steps: int = 5) -> dict:
        key = {"up": "volumeup", "down": "volumedown", "mute": "volumemute"}.get(action)
        if key is None:
            return {"success": False, "response": f"Unknown volume action {action}."}
        presses = 1 if action == "mute" else max(1, min(int(steps or 5), 25))
        pyautogui.press(key, presses=presses)
        return {"success": True, "response": f"Volume {action}" + ("" if action == "mute" else f" by {presses} steps") + "."}
