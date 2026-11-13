"""Production control brain for multilingual desktop commands.

This layer turns speech/chat text into canonical command data and orchestrator
intents. It uses deterministic rules for the demo-critical paths and can use
OpenAI structured output as a fallback for multilingual/unknown commands.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import os
import re
from typing import Any

from connectors.openai_client import OpenAIClient


@dataclass
class CanonicalCommand:
    original_text: str
    language: str = "en"
    reply_language: str = "en"
    intent: str = "unknown"
    app: str | None = None
    target: str | None = None
    recipient_name: str | None = None
    message_body: str | None = None
    ui_reference: str | None = None
    spatial_reference: str | None = None
    requires_confirmation: bool = False
    user_feedback_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkflowStep:
    action: str
    target: str | None = None
    text: str | None = None
    safety: str = "safe"
    success_condition: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UITarget:
    label: str
    role: str | None = None
    bbox: dict[str, int] | None = None
    confidence: float = 0.0
    source: str = "omniparser"
    rank_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProductionRoute:
    canonical: CanonicalCommand
    normalized_text: str
    intents: list[tuple[str, str, dict]] = field(default_factory=list)
    workflow: list[WorkflowStep] = field(default_factory=list)
    used_llm: bool = False


class ProductionControlAgent:
    """Strict orchestration adapter: understand, plan, then hand off safely."""

    NEPALI_MARKERS = {
        "khola", "khol", "banda", "gara", "garirakha", "khoja", "bhanne",
        "bhanera", "teslai", "malai", "aauna", "dhilo", "hunxa", "lekhna",
        "lagau", "row", "box", "ma", "ta", "gmail", "facebook",
    }

    RISKY_INTENTS = {
        "send_email", "send_message", "delete", "shutdown", "restart",
        "payment", "login",
    }

    def __init__(self, openai_client: OpenAIClient | None = None) -> None:
        self.openai = openai_client or OpenAIClient()
        self.llm_enabled = os.getenv("HOLODESK_OPENAI_PLANNER_ENABLED", "1") == "1"

    def route(self, command: str) -> ProductionRoute:
        text = (command or "").strip()
        canonical = self._deterministic_canonical(text)
        if canonical.intent == "unknown" and self.llm_enabled and self._should_use_llm(text):
            canonical = self._llm_canonical(text) or canonical

        normalized = self._canonical_to_command_text(canonical)
        workflow = self._workflow_for(canonical)
        intents = self._canonical_to_intents(canonical, normalized)
        return ProductionRoute(canonical=canonical, normalized_text=normalized, intents=intents, workflow=workflow)

    def _deterministic_canonical(self, text: str) -> CanonicalCommand:
        low = self._clean(text)
        lang = "ne" if self._looks_nepali(text) else "en"
        reply = lang

        tic_cell = self._parse_tictactoe_cell(low)
        if tic_cell:
            return CanonicalCommand(
                original_text=text,
                language=lang,
                reply_language=reply,
                intent="game_move",
                app="tic_tac_toe",
                target=tic_cell,
                spatial_reference=tic_cell,
                user_feedback_text="ठिक छ, त्यो box मा राख्दैछु।" if lang == "ne" else "Okay, placing it there.",
            )

        if any(p in low for p in ("game menu khola", "games khola", "open game menu", "show games")):
            return CanonicalCommand(text, lang, reply, "open_game_menu", app="holodesk")

        if "tic tac toe" in low or "tictactoe" in low:
            return CanonicalCommand(text, lang, reply, "open_game", app="tic_tac_toe", target="tic tac toe")

        if "laser" in low:
            return CanonicalCommand(text, lang, reply, "open_game", app="laser_hands", target="laser hands")

        app_open = self._parse_open(low)
        if app_open:
            app, kind = app_open
            return CanonicalCommand(text, lang, reply, "open_site" if kind == "site" else "open_app", app=app, target=app)

        gmail = self._parse_gmail(low, text)
        if gmail:
            recipient, body, search_only = gmail
            return CanonicalCommand(
                original_text=text,
                language=lang,
                reply_language=reply,
                intent="search_contact" if search_only else "draft_email",
                app="gmail",
                target=recipient,
                recipient_name=recipient,
                message_body=body,
                ui_reference="Gmail contact/search/compose",
                user_feedback_text=(
                    f"Gmail मा {recipient} खोजेर draft तयार गर्छु।"
                    if lang == "ne" and not search_only
                    else f"I will search {recipient} in Gmail and prepare a draft."
                ),
            )

        if re.match(r"^(click|press|tap)\s+", low) or self._has_spatial_ui_reference(low):
            return CanonicalCommand(
                original_text=text,
                language=lang,
                reply_language=reply,
                intent="click_ui",
                target=self._extract_click_target(text),
                ui_reference=self._extract_click_target(text),
                spatial_reference=self._extract_spatial_reference(low),
            )

        if "scroll" in low or "scroll gara" in low:
            direction = "up" if any(p in low for p in ("up", "mathi")) else "down"
            continuous = any(p in low for p in ("garirakha", "continue", "keep"))
            return CanonicalCommand(
                text,
                lang,
                reply,
                "scroll",
                target=f"{'keep ' if continuous else ''}scroll {direction}",
            )

        return CanonicalCommand(original_text=text, language=lang, reply_language=reply)

    def _llm_canonical(self, text: str) -> CanonicalCommand | None:
        system = (
            "You are HoloDesk's Language + Intent Agent. Convert any user command "
            "into a canonical desktop-control JSON object. Preserve language and "
            "reply_language. Never invent that an action was completed."
        )
        prompt = (
            "Schema keys: language, reply_language, intent, app, target, recipient_name, "
            "message_body, ui_reference, spatial_reference, requires_confirmation, "
            "user_feedback_text.\n"
            f"User command: {text}"
        )
        try:
            data = self.openai.json_query(prompt, system=system)
        except Exception:
            return None
        return CanonicalCommand(
            original_text=text,
            language=str(data.get("language") or "en"),
            reply_language=str(data.get("reply_language") or data.get("language") or "en"),
            intent=str(data.get("intent") or "unknown"),
            app=data.get("app"),
            target=data.get("target"),
            recipient_name=data.get("recipient_name"),
            message_body=data.get("message_body"),
            ui_reference=data.get("ui_reference"),
            spatial_reference=data.get("spatial_reference"),
            requires_confirmation=bool(data.get("requires_confirmation", False)),
            user_feedback_text=str(data.get("user_feedback_text") or ""),
        )

    def _canonical_to_intents(self, canonical: CanonicalCommand, normalized: str) -> list[tuple[str, str, dict]]:
        ctx = {
            "raw": normalized,
            "original_raw": canonical.original_text,
            "reply_language": canonical.reply_language,
            "canonical": canonical.to_dict(),
        }
        if canonical.intent == "open_site":
            return [("task_agent", "open_web", {**ctx, "target": canonical.target or canonical.app or ""})]
        if canonical.intent == "open_app":
            return [("task_agent", "open_app", {**ctx, "app_name": canonical.app or canonical.target or ""})]
        if canonical.intent in {"draft_email", "search_contact", "click_ui"}:
            return [("task_agent", "grounded_desktop", ctx)]
        if canonical.intent == "scroll":
            return [("task_agent", "scroll", ctx)]
        if canonical.intent == "open_game_menu":
            return [("overlay_agent", "open_game_menu", ctx)]
        if canonical.intent == "open_game":
            action = {
                "tic_tac_toe": "start_tictactoe",
                "laser_hands": "start_laser_game",
            }.get(canonical.app or "", "open_game_menu")
            return [("overlay_agent", action, ctx)]
        if canonical.intent == "game_move":
            return [("overlay_agent", "place_tictactoe", {**ctx, "cell": canonical.target})]
        if canonical.intent in self.RISKY_INTENTS:
            return [("task_agent", canonical.intent, ctx)]
        return []

    def _canonical_to_command_text(self, canonical: CanonicalCommand) -> str:
        if canonical.intent == "open_site":
            return f"open {canonical.target or canonical.app}"
        if canonical.intent == "open_app":
            return f"open {canonical.app or canonical.target}"
        if canonical.intent == "draft_email":
            parts = ["open gmail"]
            if canonical.recipient_name:
                parts.append(f"and search for {canonical.recipient_name}")
            if canonical.message_body:
                parts.append(f"and draft an email saying {canonical.message_body}")
            return " ".join(parts)
        if canonical.intent == "search_contact":
            return f"search {canonical.recipient_name or canonical.target} in Gmail"
        if canonical.intent == "click_ui":
            return f"click {canonical.ui_reference or canonical.target or canonical.spatial_reference}"
        if canonical.intent == "scroll":
            return canonical.target or "scroll down"
        if canonical.intent == "open_game_menu":
            return "open game menu"
        if canonical.intent == "open_game":
            return f"open {canonical.target or canonical.app}"
        if canonical.intent == "game_move":
            return f"place {canonical.target}"
        return canonical.original_text

    def _workflow_for(self, canonical: CanonicalCommand) -> list[WorkflowStep]:
        if canonical.intent == "draft_email" and canonical.app == "gmail":
            return [
                WorkflowStep("open_url", target="https://mail.google.com", success_condition="Gmail is visible"),
                WorkflowStep("click_ui", target="Search mail", success_condition="Search box focused"),
                WorkflowStep("type_text", text=canonical.recipient_name or ""),
                WorkflowStep("press_key", target="enter", success_condition="matching messages or contacts visible"),
                WorkflowStep("click_ui", target="Compose", success_condition="compose draft opens"),
                WorkflowStep("click_ui", target="To", success_condition="recipient field focused"),
                WorkflowStep("type_text", text=canonical.recipient_name or ""),
                WorkflowStep("click_ui", target="Message Body", success_condition="message body focused"),
                WorkflowStep("type_text", text=canonical.message_body or ""),
                WorkflowStep("verify", safety="safe", success_condition="draft exists and send was not clicked"),
                WorkflowStep("ask_confirmation", target="send", safety="confirm"),
            ]
        if canonical.intent == "click_ui":
            return [WorkflowStep("click_ui", target=canonical.ui_reference or canonical.target or "visible target")]
        return []

    def _parse_open(self, low: str) -> tuple[str, str] | None:
        sites = {"facebook", "youtube", "gmail", "netflix", "instagram", "messenger", "chatgpt", "github"}
        apps = {"chrome", "brave", "outlook", "cursor", "notepad", "calculator"}
        for name in sites:
            if re.search(rf"\b{name}\b.*\b(khola|open)\b|\b(open|khola)\b.*\b{name}\b", low):
                return name, "site"
        for name in apps:
            if re.search(rf"\b{name}\b.*\b(khola|open)\b|\b(open|khola)\b.*\b{name}\b", low):
                return name, "app"
        return None

    def _parse_gmail(self, low: str, original: str) -> tuple[str, str, bool] | None:
        if "gmail" not in low and "mail" not in low:
            return None
        if not any(k in low for k in ("khoja", "search", "find", "draft", "lekh", "mail")):
            return None

        recipient = ""
        for pattern in (
            r"gmail\s+ma\s+(.+?)\s+(?:bhanne|khoja|search|find)",
            r"(.+?)\s+bhanne\s+manxe\s+khoja",
            r"search\s+(?:for\s+)?(.+?)\s+(?:in|on)\s+gmail",
            r"find\s+(.+?)\s+(?:in|on)\s+gmail",
        ):
            match = re.search(pattern, low)
            if match:
                recipient = self._title_name(match.group(1))
                break

        body = ""
        if any(k in low for k in ("draft", "lekh", "bhanera", "saying")):
            body = self._extract_message_body(low, original)

        if not recipient and "gmail" in low and ("khola" in low or "open" in low):
            return None
        return (recipient or "the contact", body, not bool(body))

    def _extract_message_body(self, low: str, original: str) -> str:
        if "malai aauna dhilo hunxa" in low or "malai auna dhilo hunxa" in low:
            return "I will be late"
        for key in ("bhanera", "saying", "that"):
            idx = low.find(key)
            if idx >= 0:
                return original[idx + len(key):].strip(" .,:;") or "I will be late"
        return "I will be late"

    def _parse_tictactoe_cell(self, low: str) -> str | None:
        if not any(k in low for k in ("row", "box", "lagau", "place", "put", "mark")):
            return None
        row_map = {
            "first row": "top", "1st row": "top", "top row": "top",
            "second row": "center", "2nd row": "center", "middle row": "center",
            "third row": "bottom", "3rd row": "bottom", "bottom row": "bottom",
            "pahilo row": "top", "dosro row": "center", "tesro row": "bottom",
        }
        col_map = {
            "first box": "left", "1st box": "left", "left box": "left",
            "second box": "center", "2nd box": "center", "middle box": "center",
            "third box": "right", "3rd box": "right", "right box": "right",
            "pahilo box": "left", "dosro box": "center", "tesro box": "right",
        }
        row = next((v for k, v in row_map.items() if k in low), None)
        col = next((v for k, v in col_map.items() if k in low), None)
        if row and col:
            return f"{row} {col}"
        return None

    def _has_spatial_ui_reference(self, low: str) -> bool:
        return any(p in low for p in ("first profile", "second profile", "top right", "top left", "nearest search"))

    def _extract_click_target(self, text: str) -> str:
        cleaned = re.sub(r"^(click|press|tap)\s+", "", text.strip(), flags=re.IGNORECASE)
        return cleaned.strip(" .,:;") or text

    def _extract_spatial_reference(self, low: str) -> str | None:
        for phrase in ("top right", "top left", "bottom right", "bottom left", "first", "second", "third", "nearest"):
            if phrase in low:
                return phrase
        return None

    def _should_use_llm(self, text: str) -> bool:
        return bool(text and (self._looks_nepali(text) or len(text.split()) >= 6))

    def _looks_nepali(self, text: str) -> bool:
        low = self._clean(text)
        has_devanagari = any("\u0900" <= ch <= "\u097f" for ch in text)
        words = set(low.split())
        return has_devanagari or bool(words & self.NEPALI_MARKERS)

    @staticmethod
    def _title_name(value: str) -> str:
        cleaned = re.sub(r"\b(?:ma|lai|ta|the|person|manxe)\b", " ", value).strip(" .,:;")
        return " ".join(part.capitalize() for part in cleaned.split())

    @staticmethod
    def _clean(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").lower()).strip(" .,!?:;")
