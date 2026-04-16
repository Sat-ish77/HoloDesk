import queue
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.queues import command_queue, response_queue, voice_reply_queue


class OrchestratorAgent(threading.Thread):
    """
    OrchestratorAgent
    - Reads natural language commands from command_queue
    - Detects intent(s)
    - Dispatches to the correct agent(s), in parallel when appropriate
    - Replies to the voice thread via voice_reply_queue
    - Emits optional status updates to response_queue for UI/debug
    """

    def __init__(self, agents: dict):
        super().__init__(daemon=True)
        self.agents = agents
        self.thread_pool = ThreadPoolExecutor(max_workers=5)
        self.running = True

    def stop(self):
        self.running = False

    def run(self):
        while self.running:
            try:
                item = command_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                text = (item.get("text") if isinstance(item, dict) else str(item)) or ""
                text = text.strip()
                if not text:
                    continue
                self._process(text)
            except Exception as e:
                self._reply({"text": f"Something went wrong routing that: {e}", "prompt": False})

    # Short yes/cancel words that should only be recognized as confirmation
    # when a TaskAgent confirmation is actually pending.
    _CONFIRM_WORDS = {
        "yes", "yep", "yeah", "do it", "confirm", "okay", "ok",
        "cancel", "stop", "no", "nope", "don't", "dont",
    }

    def _process(self, command: str):
        # If a TaskAgent confirmation is pending (e.g. an armed shutdown),
        # short yes/cancel utterances MUST be delivered to TaskAgent so the
        # scheduled action actually fires or aborts. Otherwise "cancel"
        # would be classified as an EXIT phrase or fall through to chat.
        task_agent = self.agents.get("task_agent")
        if (
            task_agent is not None
            and getattr(task_agent, "_pending_confirm", None)
            and command.lower().strip().rstrip(".!?,") in self._CONFIRM_WORDS
        ):
            result = task_agent.execute(action="__confirm_reply__", context={"raw": command})
            self._reply({"text": result.get("response", "Okay."), "prompt": True})
            return

        intents = self._detect_intents(command)

        if not intents:
            # Guard against the "roleplay" failure mode: if the user clearly
            # declared an ACTION verb but we don't have a handler, DO NOT fall
            # through to the chat model — it will cheerfully pretend it did the
            # thing ("signed you in!", "maximized the window!"). Route to the
            # TaskAgent's honest-refusal path instead.
            if self._looks_like_declared_action(command):
                intents = [("task_agent", "declared_task_unsupported", {"raw": command})]
            else:
                intents = [("chat_agent", "chat", {"message": command})]

        # If any task-agent intent matched, drop chat_agent intents so the
        # deterministic action speaks for itself (no "opening X" + chat reply
        # about X). Screen/memory intents are preserved so combined commands
        # like "open facebook and read my screen" still work.
        if any(i[0] == "task_agent" for i in intents):
            intents = [i for i in intents if i[0] != "chat_agent"]

        # Parallel dispatch only when user explicitly combines tasks.
        wants_parallel = self._looks_parallel(command) and len(intents) > 1

        if wants_parallel:
            futures = []
            for agent_name, action, ctx in intents:
                futures.append(self.thread_pool.submit(self._execute_one, agent_name, action, ctx))
            results = []
            for fut in as_completed(futures):
                results.append(fut.result())
        else:
            results = [self._execute_one(*intents[0])]

        merged = self._merge_results(results)
        self._reply({"text": merged, "prompt": True})

    def _reply(self, payload: dict):
        try:
            # voice thread expects dict: {"text": str, "prompt": bool}
            voice_reply_queue.put_nowait(payload)
        except queue.Full:
            # If voice thread isn't ready, drop rather than deadlock.
            pass

    def _execute_one(self, agent_name: str, action: str, ctx: dict) -> dict:
        try:
            agent = self.agents.get(agent_name)
            if agent is None:
                return {"success": False, "response": f"I don't have an agent called {agent_name}."}

            if agent_name == "screen_agent":
                # ScreenAgent API: execute(question) -> dict
                question = ctx.get("question") or "What's on my screen? Explain it clearly."
                return agent.execute(question=question)

            if agent_name == "memory_agent":
                # MemoryAgent: support a few queries via methods if they exist.
                # Fall back to a friendly summary.
                if hasattr(agent, "detect_habits"):
                    habits = agent.detect_habits()
                    return {"success": True, "response": self._format_habits(habits)}
                return {"success": True, "response": "I’m still learning your habits. Keep using HoloDesk and I’ll summarize your patterns soon."}

            if agent_name == "chat_agent":
                message = ctx.get("message", "")
                return agent.execute(message=message, context=ctx.get("context"))

            if agent_name == "task_agent":
                return agent.execute(action=action, context=ctx)

            # Unknown agent type
            if hasattr(agent, "execute"):
                return agent.execute(action=action, context=ctx)

            return {"success": False, "response": f"{agent_name} can't execute tasks yet."}
        except Exception as e:
            return {"success": False, "response": f"That task failed: {e}"}

    @staticmethod
    def _format_habits(habits) -> str:
        if not habits:
            return "I don’t have enough history yet to see a clear pattern."
        if isinstance(habits, str):
            return habits
        if isinstance(habits, list):
            top = habits[:3]
            parts = []
            for h in top:
                app = h.get("app_name", "an app")
                days = h.get("days_per_week", 0)
                hour = h.get("hour_of_day", None)
                if hour is None:
                    parts.append(f"{app} about {days} days a week")
                else:
                    parts.append(f"{app} around {hour}:00")
            return "Here are a few habits I’ve noticed: " + "; ".join(parts) + "."
        return "I found some habit patterns, but couldn’t summarize them cleanly yet."

    # Verbs that clearly describe a desktop/web ACTION the user wants performed.
    # If any of these appear and no task handler matches, we refuse honestly
    # rather than letting chat_agent pretend it performed the action.
    DECLARED_ACTION_VERBS = (
        "sign in", "log in", "log into", "login", "sign into",
        "click", "submit", "press the", "tap the",
        "maximize", "minimize", "shutdown", "shut down", "restart", "reboot",
        "close all", "quit all",
        "send the", "send this", "send an email",
        "type this", "paste this",
    )

    def _looks_like_declared_action(self, command: str) -> bool:
        c = (command or "").lower()
        return any(v in c for v in self.DECLARED_ACTION_VERBS)

    def _detect_intents(self, command: str) -> list[tuple[str, str, dict]]:
        """
        Returns a list of (agent_name, action, context).
        """
        c = command.lower().strip()
        c = c.replace("hey holo", "").strip()

        intents: list[tuple[str, str, dict]] = []
        matched_open_in_browser = False  # suppresses conflicting open_app/open_web/search

        # "open <site> in/using/with <browser>" (two-step browser open, then url)
        m = re.search(r"\bopen\s+(.+?)\s+(?:in|using|with)\s+(chrome|brave|firefox|edge)\b", c)
        if m:
            target = (m.group(1) or "").strip(" .,!?:;")
            browser = (m.group(2) or "").strip()
            if target:
                intents.append(("task_agent", "open_web_in_browser", {"target": target, "browser": browser, "raw": command}))
                matched_open_in_browser = True

        # Shutdown / restart — handed to TaskAgent which enforces confirm+cancel.
        if re.search(r"\b(shut\s*down|power\s*off)\b", c):
            intents.append(("task_agent", "shutdown", {"raw": command}))
        elif re.search(r"\b(restart|reboot)\b", c):
            intents.append(("task_agent", "restart", {"raw": command}))

        # Screen intents
        screen_phrases = [
            "what's on my screen", "whats on", "read my screen",
            "explain this", "explain this error", "what is this",
            "what does this say", "read this", "summarize this",
            "what code is this", "debug this", "what went wrong",
            "look at my screen", "describe my screen",
        ]
        if any(p in c for p in screen_phrases):
            intents.append(("screen_agent", "vision", {"question": command}))

        # Time intent -> chat_agent (simple)
        if re.search(r"\bwhat time is it\b|\btime now\b", c):
            intents.append(("chat_agent", "chat", {"message": "Tell me the current local time in a single short sentence."}))

        # Timer
        if "set a timer" in c or re.search(r"\btimer for\b", c):
            minutes = self._extract_number(c)
            intents.append(("task_agent", "set_timer", {"minutes": minutes, "raw": command}))

        # Weather
        if "what's the weather" in c or "whats the weather" in c or "weather" == c.strip():
            intents.append(("task_agent", "weather", {"raw": command}))

        # Screenshot
        if "take a screenshot" in c or "screenshot" == c.strip():
            intents.append(("task_agent", "take_screenshot_and_save", {"raw": command}))

        # Lock screen
        if "lock my screen" in c or "lock screen" == c.strip():
            intents.append(("task_agent", "lock_screen", {"raw": command}))

        # App launching / closing / window controls
        if not matched_open_in_browser and any(k in c for k in ["open ", "launch ", "start "]):
            app = self._extract_after_any(c, ["open ", "launch ", "start "])
            if app:
                # Special-case common websites under open -> open_web
                if self._looks_like_site_name_or_url(app):
                    intents.append(("task_agent", "open_web", {"target": app, "raw": command}))
                else:
                    intents.append(("task_agent", "open_app", {"app_name": app, "raw": command}))

        if "close " in c:
            app = self._extract_after_any(c, ["close "])
            if app:
                intents.append(("task_agent", "close_app", {"app_name": app, "raw": command}))

        if "minimize" in c:
            intents.append(("task_agent", "minimize", {"raw": command}))
        if "maximize" in c:
            intents.append(("task_agent", "maximize", {"raw": command}))

        # Navigation / websites
        nav_phrases = ["go to ", "navigate to ", "visit ", "browse to ", "open "]
        if (
            not matched_open_in_browser
            and any(p in c for p in nav_phrases)
            and self._looks_like_web_intent(c)
        ):
            target = self._extract_urlish(c)
            if target:
                intents.append(("task_agent", "open_web", {"target": target, "raw": command}))

        # Typing / messaging
        if any(p in c for p in ["type ", "write ", "paste ", "send message", "draft", "compose", "text "]):
            intents.append(("task_agent", "type_text", {"raw": command}))

        # Email
        if any(p in c for p in ["draft an email", "write an email", "compose email", "send email to", "email to", "open gmail and"]):
            intents.append(("task_agent", "draft_email", {"raw": command}))

        # Search — but not when the user already asked to open a site in a
        # specific browser. "open google in brave" must NOT trigger a search.
        if (
            not matched_open_in_browser
            and any(p in c for p in ["search for", "look up", "find", "search google for", "search youtube for"])
        ):
            intents.append(("task_agent", "search", {"raw": command}))
        elif not matched_open_in_browser and re.search(r"\bgoogle\s+\S", c) and "search" in c:
            intents.append(("task_agent", "search", {"raw": command}))

        # Scrolling
        if any(p in c for p in ["scroll up", "scroll down", "page down", "page up", "scroll "]):
            intents.append(("task_agent", "scroll", {"raw": command}))

        # Clipboard
        if any(p in c for p in ["copy this", "copy that", "what's in my clipboard", "whats in my clipboard", "paste this", "read my clipboard"]):
            intents.append(("task_agent", "clipboard", {"raw": command}))

        # Ask ChatGPT tool
        if any(p in c for p in ["ask chatgpt", "ask gpt", "chatgpt can you", "use chatgpt"]):
            prompt = self._extract_after_any(command, ["ask chatgpt", "ask gpt", "use chatgpt", "chatgpt can you"])
            intents.append(("task_agent", "ask_chatgpt", {"prompt": prompt or command}))

        # Memory
        if any(p in c for p in ["what did i work on", "what was i doing", "yesterday", "last time", "my habits", "what do i usually", "history"]):
            intents.append(("memory_agent", "memory", {"raw": command}))

        # De-dup: keep order but unique by (agent, action)
        seen = set()
        uniq = []
        for it in intents:
            key = (it[0], it[1])
            if key in seen:
                continue
            seen.add(key)
            uniq.append(it)
        return uniq

    @staticmethod
    def _looks_parallel(command: str) -> bool:
        c = command.lower()
        return " and " in c or " also " in c

    @staticmethod
    def _merge_results(results: list[dict]) -> str:
        if not results:
            return "I didn't get any result back."

        # Prefer successful responses; still mention failures briefly.
        success_parts = []
        fail_parts = []
        for r in results:
            ok = bool(r.get("success", True))
            text = r.get("response") or r.get("text") or ""
            if not text:
                continue
            if ok:
                success_parts.append(text.strip())
            else:
                fail_parts.append(text.strip())

        if success_parts and not fail_parts:
            return " ".join(success_parts)
        if success_parts and fail_parts:
            return " ".join(success_parts) + " " + " ".join(fail_parts)
        return " ".join(fail_parts) or "That didn't work."

    @staticmethod
    def _extract_after_any(text: str, prefixes: list[str]) -> str:
        lower = text.lower()
        for p in prefixes:
            idx = lower.find(p)
            if idx >= 0:
                return text[idx + len(p):].strip(" :.-")
        return ""

    @staticmethod
    def _extract_number(text: str) -> int:
        m = re.search(r"(\d+)", text)
        return int(m.group(1)) if m else 1

    @staticmethod
    def _looks_like_web_intent(text: str) -> bool:
        return any(x in text for x in [".com", ".org", ".net", "http://", "https://"]) or any(
            site in text for site in ["instagram", "youtube", "netflix", "gmail", "github", "spotify", "reddit", "twitter", "claude", "chatgpt"]
        )

    @staticmethod
    def _looks_like_site_name_or_url(app: str) -> bool:
        return any(x in app for x in [".com", ".org", ".net", "http://", "https://"]) or app.strip().lower() in {
            "instagram", "youtube", "netflix", "gmail", "github", "spotify", "reddit", "twitter", "claude", "chatgpt", "facebook"
        }

    @staticmethod
    def _extract_urlish(text: str) -> str:
        # prefer an explicit URL-like token if present, otherwise fall back to last token
        tokens = re.split(r"\s+", text.strip())
        if not tokens:
            return ""
        # If there's an explicit URL, use it
        for t in tokens:
            if t.startswith("http://") or t.startswith("https://"):
                return t
        # Prefer domain-like tokens
        for t in tokens:
            tt = t.strip(" .,!?:;")
            if any(x in tt for x in [".com", ".org", ".net", ".io"]):
                return tt
        # Otherwise grab trailing word
        return tokens[-1].strip(" .,!?:;")

