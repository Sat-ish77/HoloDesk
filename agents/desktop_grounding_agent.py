"""Desktop UI grounding planner/executor (first version).

Design goals:
- Safe-by-default: never auto-run risky actions.
- Testable without live desktop side effects using dry_run mode.
- Screenshot -> parse -> target selection loop before every UI step.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import re
import time

class _LazyPyAutoGUI:
    def __init__(self):
        self._module = None

    def _load(self):
        if self._module is None:
            import pyautogui as module
            module.PAUSE = 0
            module.FAILSAFE = False
            self._module = module
        return self._module

    def __getattr__(self, name):
        return getattr(self._load(), name)


pyautogui = _LazyPyAutoGUI()
PYAUTOGUI_AVAILABLE = True

from connectors.openai_client import OpenAIClient
from vision.ui_parser import UIElement, UIParserAdapter, build_default_parser
from browser import playwright_controller as browser_controller
from browser.sites import facebook as site_facebook, gmail as site_gmail, instagram as site_instagram

BROWSER_SITE_MODULES = {"gmail": site_gmail, "facebook": site_facebook, "instagram": site_instagram}


def _detect_browser_target(command: str) -> str | None:
    """Which real-browser adapter (if any) this command targets.

    Kept as a plain function (not tied to safety/regex parsing above) so the
    executor can check it without depending on DesktopActionPlanner.
    """
    low = (command or "").lower()
    if "gmail" in low or "mail.google" in low:
        return "gmail"
    if "instagram" in low:
        return "instagram"
    if "messenger" in low or "facebook" in low:
        return "facebook"
    return None


@dataclass
class PlanStep:
    action: str
    args: dict[str, Any]
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ActionPlan:
    command: str
    safe: bool
    blocked_reason: str | None
    steps: list[PlanStep]

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "safe": self.safe,
            "blocked_reason": self.blocked_reason,
            "steps": [s.to_dict() for s in self.steps],
        }


class GroundingSafetyPolicy:
    """Central policy for unsafe action classes."""

    BLOCKED_KEYWORDS = (
        "payment",
        "bank",
        "banking",
        "wire transfer",
        "transfer money",
        "login",
        "log in",
        "sign in",
        "password",
    )

    CONFIRM_KEYWORDS = (
        "send email",
        "send message",
        "send it",
        "delete file",
        "delete folder",
        "remove file",
        "remove folder",
        "shutdown",
        "restart",
    )

    def classify(self, command: str) -> tuple[bool, str | None, bool]:
        text = (command or "").lower()

        if any(k in text for k in self.BLOCKED_KEYWORDS):
            if any(action in text for action in ("click", "press", "tap")):
                return True, None, True
            return False, "Blocked by safety policy (login/payment/banking/password flow).", False

        needs_confirm = any(k in text for k in self.CONFIRM_KEYWORDS)
        return True, None, needs_confirm


class DesktopActionPlanner:
    """Rule-based planner for first-pass grounded desktop actions."""

    def __init__(self, safety: GroundingSafetyPolicy | None = None) -> None:
        self.safety = safety or GroundingSafetyPolicy()

    def build_plan(self, command: str) -> ActionPlan:
        safe, blocked_reason, needs_confirm = self.safety.classify(command)
        text = (command or "").strip()

        if not safe:
            return ActionPlan(command=text, safe=False, blocked_reason=blocked_reason, steps=[])

        steps: list[PlanStep] = []
        low = text.lower()

        website_match = re.search(r"\bopen\s+(.+?)\s+(?:in|inside|on|using|with)\s+(chrome|brave|firefox|edge)\b", low)
        if website_match:
            target = website_match.group(1).strip(" .,!?:;")
            browser = website_match.group(2).strip()
            steps.append(PlanStep("open_application", {"app_name": browser}))
            steps.append(PlanStep("open_website", {"target": target, "browser": browser}))
            return ActionPlan(command=text, safe=True, blocked_reason=None, steps=steps)

        facebook_message = self._parse_social_message(text)
        if facebook_message:
            site, person, message = facebook_message
            steps.append(PlanStep("open_website", {"target": site, "browser": "chrome"}))
            steps.append(PlanStep("wait", {"seconds": 2.0}))
            steps.append(PlanStep("click_element_by_label", {"label": "Search|Search Facebook|Search Messenger|Search"}))
            steps.append(PlanStep("type_text", {"text": person}))
            steps.append(PlanStep("press_key", {"key": "enter"}))
            steps.append(PlanStep("wait", {"seconds": 1.0}))
            steps.append(PlanStep("click_element_by_label", {"label": person}))
            steps.append(PlanStep("wait", {"seconds": 1.0}))
            steps.append(PlanStep("click_element_by_label", {"label": "Message|Type a message|Aa|Write a message"}))
            steps.append(PlanStep("type_text", {"text": message}))
            steps.append(PlanStep("verify_draft", {"message": message, "person": person}))
            return ActionPlan(command=text, safe=True, blocked_reason=None, steps=steps)

        if low.startswith("open chrome"):
            steps.append(PlanStep("open_application", {"app_name": "chrome"}))
        elif low.startswith("open brave"):
            steps.append(PlanStep("open_application", {"app_name": "brave"}))
        elif "open folder" in low or "open subfolder" in low:
            path = self._extract_path(text)
            steps.append(PlanStep("open_folder", {"path": path or ""}))
        elif "open outlook" in low:
            steps.append(PlanStep("open_application", {"app_name": "outlook"}))
        elif ("search" in low or "find" in low) and "outlook" in low:
            key = "search" if "search" in low else "find"
            query = self._clean_outlook_query(self._extract_after(text, key))
            steps.append(PlanStep("open_application", {"app_name": "outlook"}))
            steps.append(PlanStep("click_element_by_label", {"label": "Search"}))
            steps.append(PlanStep("type_text", {"text": query}))
        elif "gmail" in low and any(k in low for k in ("search", "find", "draft", "compose", "write email", "draft email")):
            recipient = self._extract_gmail_recipient(text)
            message = self._extract_email_draft_text(text)
            steps.append(PlanStep("open_website", {"target": "gmail", "browser": "chrome"}))
            steps.append(PlanStep("wait", {"seconds": 2.0}))
            if recipient:
                steps.append(PlanStep("click_element_by_label", {"label": "Search mail|Search"}))
                steps.append(PlanStep("type_text", {"text": recipient}))
                steps.append(PlanStep("press_key", {"key": "enter"}))
                steps.append(PlanStep("wait", {"seconds": 1.0}))
            if any(k in low for k in ("draft", "compose", "write email", "draft email")):
                steps.append(PlanStep("click_element_by_label", {"label": "Compose|New Mail"}))
                if recipient:
                    steps.append(PlanStep("click_element_by_label", {"label": "To|Recipients"}))
                    steps.append(PlanStep("type_text", {"text": recipient}))
                    steps.append(PlanStep("press_key", {"key": "enter"}))
                steps.append(PlanStep("click_element_by_label", {"label": "Message Body|Body|Compose"}))
                steps.append(PlanStep("type_text", {"text": message}))
                steps.append(PlanStep("verify_draft", {"message": message, "person": recipient}))
        elif "draft email" in low or "draft an email" in low or "compose email" in low or "write email" in low or ("gmail" in low and "draft" in low):
            if "gmail" in low:
                steps.append(PlanStep("open_website", {"target": "gmail", "browser": "chrome"}))
                steps.append(PlanStep("wait", {"seconds": 2.0}))
            else:
                steps.append(PlanStep("open_application", {"app_name": "outlook"}))
            steps.append(PlanStep("click_element_by_label", {"label": "New Mail|Compose"}))
            steps.append(PlanStep("type_text", {"text": self._extract_email_draft_text(text)}))
        elif "send email" in low:
            steps.append(
                PlanStep(
                    "blocked_send_email",
                    {"reason": "Sending email requires explicit confirmation."},
                    requires_confirmation=True,
                )
            )
        elif "delete" in low and "file" in low:
            steps.append(
                PlanStep(
                    "blocked_delete",
                    {"reason": "Deleting files requires explicit confirmation."},
                    requires_confirmation=True,
                )
            )
        elif low.startswith("click ") or low.startswith("press ") or low.startswith("tap "):
            verb = low.split(maxsplit=1)[0]
            label = self._extract_after(text, verb)
            steps.append(PlanStep("click_element_by_label", {"label": label}))
        elif low.startswith("type "):
            payload = self._extract_after(text, "type")
            steps.append(PlanStep("type_text", {"text": payload}))
        elif "search" in low and any(site in low for site in ("facebook", "messenger", "instagram")):
            query = self._extract_social_search_query(text)
            site = "messenger" if "messenger" in low else "facebook"
            steps.append(PlanStep("open_website", {"target": site, "browser": "chrome"}))
            steps.append(PlanStep("click_element_by_label", {"label": "Search|Search Facebook|Search Messenger|Search"}))
            steps.append(PlanStep("type_text", {"text": query}))
            steps.append(PlanStep("press_key", {"key": "enter"}))

        if not steps:
            steps.append(PlanStep("noop", {"reason": "No supported grounded action parsed."}))

        if needs_confirm:
            for step in steps:
                step.requires_confirmation = True

        return ActionPlan(command=text, safe=True, blocked_reason=None, steps=steps)

    @staticmethod
    def _extract_after(text: str, key: str) -> str:
        idx = text.lower().find(key.lower())
        if idx < 0:
            return ""
        return text[idx + len(key):].strip(" .,:;")

    @staticmethod
    def _extract_path(text: str) -> str:
        m = re.search(r"([A-Za-z]:\\[^\n\r\t]+)", text)
        if m:
            return m.group(1).strip()
        return ""

    @staticmethod
    def _clean_outlook_query(text: str) -> str:
        cleaned = re.sub(r"\b(in|inside|on)\s+outlook\b", "", text, flags=re.IGNORECASE)
        return cleaned.strip(" .,:;") or text.strip(" .,:;")

    def _extract_email_draft_text(self, text: str) -> str:
        for key in ("saying", "that", "bhanera"):
            payload = self._extract_after(text, key)
            if payload:
                return payload
        for key in ("draft an email", "draft email", "compose email", "write email"):
            payload = self._extract_after(text, key)
            if payload:
                return payload
        return text.strip()

    @staticmethod
    def _extract_gmail_recipient(text: str) -> str:
        patterns = [
            r"\bsearch\s+(?:for\s+)?(.+?)\s+and\s+(?:draft|compose|write)\b",
            r"\bsearch\s+(?:for\s+)?(.+?)\s+(?:in|on)\s+gmail\b",
            r"\bfind\s+(.+?)\s+(?:in|on)\s+gmail\b",
            r"\bgmail\s+ma\s+(.+?)\s+(?:bhanne|khoja|search|find)\b",
            r"\b(.+?)\s+bhanne\s+manxe\s+khoja\b",
            r"\bto\s+(.+?)\s+(?:saying|that)\b",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, flags=re.IGNORECASE)
            if m:
                return m.group(1).strip(" .,:;")
        return ""

    def _parse_social_message(self, text: str) -> tuple[str, str, str] | None:
        low = text.lower()
        if not any(site in low for site in ("facebook", "messenger", "instagram")):
            return None
        if not any(k in low for k in ("tell ", "message ", "text ", "dm ", "say ")):
            return None

        site = "instagram" if "instagram" in low else "messenger"
        person = self._extract_person_name(text)
        message = self._extract_message_text(text)
        if not person or not message:
            return None
        return site, person, message

    @staticmethod
    def _extract_person_name(text: str) -> str:
        patterns = [
            r"\bsearch\s+for\s+(.+?)\s+(?:and\s+)?(?:tell|message|text|dm|say)\b",
            r"\bfind\s+(.+?)\s+(?:and\s+)?(?:tell|message|text|dm|say)\b",
            r"\bto\s+(.+?)\s+(?:that|saying|say)\b",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, flags=re.IGNORECASE)
            if m:
                return m.group(1).strip(" .,:;")
        return ""

    @staticmethod
    def _extract_message_text(text: str) -> str:
        patterns = [
            r"\b(?:tell|message|text|dm)\s+(?:him|her|them|[A-Za-z .'-]+)?\s*(?:that|saying)?\s+(.+)$",
            r"\bsay\s+(.+)$",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, flags=re.IGNORECASE)
            if m:
                return m.group(1).strip(" .,:;")
        return ""

    @staticmethod
    def _extract_social_search_query(text: str) -> str:
        m = re.search(r"\bsearch(?:\s+for)?\s+(.+?)(?:\s+inside|\s+in|\s+on)?\s+(?:facebook|messenger|instagram)\b", text, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip(" .,:;")
        return text.strip(" .,:;")


class DesktopActionExecutor:
    """Executes plans through screenshot-grounded UI selection.

    Every step can capture pre/post screenshots. If parser confidence is low
    or element cannot be found, execution stops safely.
    """

    def __init__(self, parser: UIParserAdapter | None = None) -> None:
        self.parser = parser or build_default_parser()

    def execute_plan(
        self,
        plan: ActionPlan,
        *,
        dry_run: bool = True,
        screenshot_dir: str = "artifacts/ui_grounding",
    ) -> dict[str, Any]:
        if not dry_run:
            browser_result = self._try_browser_send_flow(plan, screenshot_dir)
            if browser_result is not None:
                return browser_result

        out_dir = Path(screenshot_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        logs: list[dict[str, Any]] = []
        stopped_reason = None

        for i, step in enumerate(plan.steps, start=1):
            before = out_dir / f"step_{i:02d}_before.png"
            after = out_dir / f"step_{i:02d}_after.png"
            self._safe_screenshot(before)

            parse_result = self.parser.parse(str(before))
            if (
                not dry_run
                and self.parser.parser_name == "mock"
                and step.action in {"click_element_by_label", "type_text", "press_key", "verify_draft"}
            ):
                stopped_reason = (
                    "Stopping before live UI targeting: OmniParser or another real parser is required. "
                    "Mock parser is only for dry-runs."
                )
                logs.append(
                    {
                        "step": step.to_dict(),
                        "status": "stopped",
                        "reason": stopped_reason,
                        "parser": parse_result.to_dict(),
                    }
                )
                break
            if not parse_result.success and step.action in {
                "click_element_by_label",
                "type_text",
                "verify_draft",
            }:
                stopped_reason = (
                    f"Stopping at step {i}: parser unavailable/unclear ({'; '.join(parse_result.blockers)})."
                )
                logs.append(
                    {
                        "step": step.to_dict(),
                        "status": "stopped",
                        "reason": stopped_reason,
                        "parser": parse_result.to_dict(),
                    }
                )
                break

            step_result = self._run_step(step, parse_result.elements, dry_run=dry_run)
            self._safe_screenshot(after)
            logs.append(
                {
                    "step": step.to_dict(),
                    "status": "ok" if step_result["success"] else "error",
                    "result": step_result,
                    "parser": parse_result.to_dict(),
                    "before": str(before),
                    "after": str(after),
                }
            )

            if not step_result["success"]:
                stopped_reason = f"Stopping at step {i}: {step_result['response']}"
                break

            time.sleep(0.2)

        return {
            "success": stopped_reason is None,
            "stopped_reason": stopped_reason,
            "dry_run": dry_run,
            "parser": self.parser.parser_name,
            "logs": logs,
        }

    def _try_browser_send_flow(self, plan: ActionPlan, screenshot_dir: str) -> dict[str, Any] | None:
        """Real browser automation for Gmail/Facebook/Instagram drafts.

        Returns None (meaning "fall through to the pixel/vision path below")
        when browser automation is disabled, the command doesn't target one
        of these sites, or too little was parsed out of the command to act
        on. Otherwise returns the same shaped result dict execute_plan()
        normally returns, plus `requires_confirmation` / `browser_site` so
        the caller (TaskAgent.grounded_desktop_action) can gate the actual
        Send behind a voice confirmation instead of sending immediately.
        """
        if not browser_controller.is_enabled():
            return None
        site = _detect_browser_target(plan.command)
        if site is None:
            return None

        planner = DesktopActionPlanner()
        text = plan.command

        if site == "gmail":
            recipient = planner._extract_gmail_recipient(text)
            message = planner._extract_email_draft_text(text)
            if not recipient or not message:
                return None

            page_result = browser_controller.controller.ensure_page()
            if not page_result["success"]:
                return None  # automation unavailable; fall back to the vision path

            page = page_result["page"]
            site_gmail.open_inbox(page)
            site_gmail.compose(page)
            site_gmail.fill_recipient(page, recipient)
            fill = site_gmail.fill_message(page, message)
            ready = bool(fill["success"] and site_gmail.is_draft_ready(page))
        else:
            match = planner._parse_social_message(text)
            if not match:
                return None
            _, person, message = match

            page_result = browser_controller.controller.ensure_page()
            if not page_result["success"]:
                return None

            page = page_result["page"]
            module = BROWSER_SITE_MODULES[site]
            open_fn = getattr(module, "open_inbox", None) or getattr(module, "open_messenger", None)
            if open_fn:
                open_fn(page)
            found = module.find_contact(page, person)
            fill = module.fill_message(page, message) if found["success"] else found
            ready = bool(found["success"] and fill["success"] and module.is_draft_ready(page))

        shot_path = str(Path(screenshot_dir) / f"browser_draft_{int(time.time())}.png")
        browser_controller.screenshot(page, shot_path)

        if not ready:
            return {
                "success": False,
                "stopped_reason": f"Couldn't prepare the {site} draft — the page structure may have changed.",
                "dry_run": False,
                "parser": "browser",
                "logs": [],
            }

        return {
            "success": True,
            "stopped_reason": f"{site.capitalize()} draft ready. Say 'yes' to send it, or 'cancel' to leave it as a draft.",
            "dry_run": False,
            "parser": "browser",
            "logs": [],
            "requires_confirmation": True,
            "browser_site": site,
            "screenshot": shot_path,
        }

    def _run_step(self, step: PlanStep, elements: list[UIElement], *, dry_run: bool) -> dict[str, Any]:
        if step.action in {"blocked_send_email", "blocked_delete"}:
            return {"success": False, "response": step.args.get("reason", "Blocked by policy.")}

        if step.action == "noop":
            return {"success": False, "response": step.args.get("reason", "No-op")}

        if step.action == "open_application":
            if dry_run:
                return {"success": True, "response": f"Dry-run: would open {step.args.get('app_name', '')}."}
            if not PYAUTOGUI_AVAILABLE:
                return {"success": False, "response": "Desktop control requires pyautogui."}
            pyautogui.hotkey("win", "r")
            time.sleep(0.2)
            pyautogui.write(step.args.get("app_name", ""), interval=0.01)
            pyautogui.press("enter")
            return {"success": True, "response": "Application open sequence sent."}

        if step.action == "open_website":
            target = step.args.get("target", "")
            browser = step.args.get("browser", "chrome")
            url = target if target.startswith("http") else f"https://{target}"
            if dry_run:
                return {"success": True, "response": f"Dry-run: would open {url} in {browser}."}
            if not PYAUTOGUI_AVAILABLE:
                return {"success": False, "response": "Desktop control requires pyautogui."}
            pyautogui.hotkey("win", "r")
            time.sleep(0.2)
            pyautogui.write(f"{browser} {url}", interval=0.01)
            pyautogui.press("enter")
            return {"success": True, "response": "Website open sequence sent."}

        if step.action == "wait":
            seconds = float(step.args.get("seconds") or 0.5)
            if not dry_run:
                time.sleep(max(0.1, min(seconds, 5.0)))
            return {"success": True, "response": f"Waited {seconds:.1f}s."}

        if step.action == "open_folder":
            folder = step.args.get("path", "")
            if not folder:
                return {"success": False, "response": "Missing folder path."}
            if dry_run:
                return {"success": True, "response": f"Dry-run: would open folder {folder}."}
            if not PYAUTOGUI_AVAILABLE:
                return {"success": False, "response": "Desktop control requires pyautogui."}
            pyautogui.hotkey("win", "r")
            time.sleep(0.2)
            pyautogui.write(folder, interval=0.01)
            pyautogui.press("enter")
            return {"success": True, "response": "Folder open sequence sent."}

        if step.action == "click_element_by_label":
            label = (step.args.get("label") or "").lower().strip()
            target = self._choose_element(elements, label)
            if target is None:
                return {"success": False, "response": f"UI element not found: {label}"}
            if dry_run:
                return {
                    "success": True,
                    "response": f"Dry-run: would click '{target.label}' ({target.confidence:.2f}).",
                }
            if not PYAUTOGUI_AVAILABLE:
                return {"success": False, "response": "Desktop control requires pyautogui."}
            x = target.bbox["x"] + target.bbox["width"] // 2
            y = target.bbox["y"] + target.bbox["height"] // 2
            pyautogui.click(x=x, y=y)
            return {"success": True, "response": f"Clicked '{target.label}'."}

        if step.action == "type_text":
            text = step.args.get("text", "")
            if not text:
                return {"success": False, "response": "No text to type."}
            if dry_run:
                return {"success": True, "response": "Dry-run: would type text into focused field."}
            if not PYAUTOGUI_AVAILABLE:
                return {"success": False, "response": "Desktop control requires pyautogui."}
            pyautogui.write(text, interval=0.01)
            return {"success": True, "response": "Typed text."}

        if step.action == "press_key":
            key = step.args.get("key", "enter")
            if dry_run:
                return {"success": True, "response": f"Dry-run: would press {key}."}
            if not PYAUTOGUI_AVAILABLE:
                return {"success": False, "response": "Desktop control requires pyautogui."}
            pyautogui.press(key)
            return {"success": True, "response": f"Pressed {key}."}

        if step.action == "verify_draft":
            return {"success": True, "response": "Draft prepared. Review it on screen. Say 'yes, send it' only if you want me to send."}

        return {"success": False, "response": f"Unsupported step action: {step.action}"}

    @staticmethod
    def _choose_element(elements: list[UIElement], wanted_label: str) -> UIElement | None:
        if not elements:
            return None
        selector = DesktopActionExecutor._parse_selector(wanted_label)
        wanted_labels = [p.strip() for p in selector["label"].split("|") if p.strip()]
        exact = [e for e in elements if e.label.lower() in wanted_labels]
        if exact:
            return DesktopActionExecutor._select_ranked(exact, selector)

        partial = [
            e
            for e in elements
            if any(wanted and wanted in e.label.lower() for wanted in wanted_labels)
        ]
        if partial:
            return DesktopActionExecutor._select_ranked(partial, selector)

        if selector["ordinal"] or selector["spatial"]:
            return DesktopActionExecutor._select_ranked(elements, selector)

        return None

    @staticmethod
    def _parse_selector(wanted_label: str) -> dict[str, Any]:
        raw = (wanted_label or "").lower().strip()
        ordinal_index = None
        ordinal_words = {
            "first": 0, "1st": 0, "one": 0,
            "second": 1, "2nd": 1, "two": 1,
            "third": 2, "3rd": 2, "three": 2,
            "fourth": 3, "4th": 3,
        }
        for word, idx in ordinal_words.items():
            if re.search(rf"\b{word}\b", raw):
                ordinal_index = idx
                raw = re.sub(rf"\b{word}\b", " ", raw)
                break

        spatial = None
        for phrase in ("top right", "top left", "bottom right", "bottom left", "nearest", "top", "bottom", "left", "right"):
            if phrase in raw:
                spatial = phrase
                raw = raw.replace(phrase, " ")
                break

        label = re.sub(r"\s+", " ", raw).strip(" .,:;")
        return {
            "label": label,
            "ordinal": ordinal_index is not None,
            "ordinal_index": ordinal_index,
            "spatial": spatial,
        }

    @staticmethod
    def _rank_elements(elements: list[UIElement], selector: dict[str, Any]) -> list[UIElement]:
        spatial = selector.get("spatial")

        def center(e: UIElement) -> tuple[float, float]:
            return (
                e.bbox.get("x", 0) + e.bbox.get("width", 0) / 2,
                e.bbox.get("y", 0) + e.bbox.get("height", 0) / 2,
            )

        if spatial == "top right":
            return sorted(elements, key=lambda e: (center(e)[1], -center(e)[0], -e.confidence))
        if spatial == "top left":
            return sorted(elements, key=lambda e: (center(e)[1], center(e)[0], -e.confidence))
        if spatial == "bottom right":
            return sorted(elements, key=lambda e: (-center(e)[1], -center(e)[0], -e.confidence))
        if spatial == "bottom left":
            return sorted(elements, key=lambda e: (-center(e)[1], center(e)[0], -e.confidence))
        if spatial == "top":
            return sorted(elements, key=lambda e: (center(e)[1], -e.confidence))
        if spatial == "bottom":
            return sorted(elements, key=lambda e: (-center(e)[1], -e.confidence))
        if spatial == "left":
            return sorted(elements, key=lambda e: (center(e)[0], -e.confidence))
        if spatial == "right":
            return sorted(elements, key=lambda e: (-center(e)[0], -e.confidence))
        return sorted(elements, key=lambda e: (center(e)[1], center(e)[0], -e.confidence))

    @staticmethod
    def _select_ranked(elements: list[UIElement], selector: dict[str, Any]) -> UIElement | None:
        ranked = DesktopActionExecutor._rank_elements(elements, selector)
        if not ranked:
            return None
        idx = selector.get("ordinal_index")
        if idx is None:
            idx = 0
        return ranked[min(idx, len(ranked) - 1)]

    @staticmethod
    def _safe_screenshot(path: Path) -> None:
        try:
            if not PYAUTOGUI_AVAILABLE:
                path.write_bytes(b"")
                return
            img = pyautogui.screenshot()
            img.save(str(path))
        except Exception:
            # Keep execution resilient in headless test environments.
            path.write_bytes(b"")


class VerifyWithChatGPTVision:
    """OpenAI Vision verifier command handler.

    Uses OpenAI API directly and never automates the ChatGPT website.
    """

    def __init__(self) -> None:
        self.client = OpenAIClient()

    def run(self, question: str, screenshot_path: str) -> dict[str, Any]:
        shot = Path(screenshot_path)
        if not shot.exists():
            return {"success": False, "response": f"Screenshot not found: {shot}"}

        image_b64 = self._to_b64_png(shot)
        try:
            answer = self.client.vision_query(
                image_b64=image_b64,
                question=(question or "Verify the current desktop state and summarize concisely."),
                system=(
                    "You are verifying a Windows desktop state for an automation assistant. "
                    "Answer in <=3 concise sentences with any mismatch or uncertainty first."
                ),
            )
        except Exception as exc:
            return {"success": False, "response": f"OpenAI vision verify failed: {exc}"}

        return {"success": True, "response": answer}

    @staticmethod
    def _to_b64_png(path: Path) -> str:
        import base64

        return base64.b64encode(path.read_bytes()).decode("utf-8")


class DesktopGroundingAgent:
    """Live agent wrapper used by the orchestrator/task flow."""

    def __init__(
        self,
        planner: DesktopActionPlanner | None = None,
        executor: DesktopActionExecutor | None = None,
        verifier: VerifyWithChatGPTVision | None = None,
        screenshot_dir: str = "artifacts/ui_grounding",
    ) -> None:
        self.planner = planner or DesktopActionPlanner()
        self.executor = executor or DesktopActionExecutor()
        self.verifier = verifier or VerifyWithChatGPTVision()
        self.screenshot_dir = screenshot_dir

    def plan(self, command: str) -> dict[str, Any]:
        plan = self.planner.build_plan(command)
        data = plan.to_dict()
        data["requires_confirmation"] = any(step.requires_confirmation for step in plan.steps)
        return data

    def execute(self, action: str, context: dict | None = None) -> dict[str, Any]:
        ctx = context or {}
        raw = ctx.get("raw", "") or ""

        if action == "execute_command":
            return self.execute_command(raw, dry_run=bool(ctx.get("dry_run", False)))
        if action == "analyze_screen":
            return self.analyze_current_screen()
        if action == "verify_screen":
            question = ctx.get("question") or raw or "Verify the current desktop state."
            return self.verify_current_screen(question)
        if action == "test_parser":
            return self.test_parser()

        return {"success": False, "response": f"Unsupported grounding action: {action}"}

    def execute_command(self, command: str, *, dry_run: bool = False) -> dict[str, Any]:
        plan = self.planner.build_plan(command)
        if not plan.safe:
            return {"success": False, "response": plan.blocked_reason or "That action is blocked."}
        if any(step.requires_confirmation for step in plan.steps):
            return {
                "success": False,
                "response": "That desktop action requires confirmation before I run it.",
                "data": {"plan": plan.to_dict(), "requires_confirmation": True},
            }

        result = self.executor.execute_plan(
            plan,
            dry_run=dry_run,
            screenshot_dir=self.screenshot_dir,
        )
        if result.get("requires_confirmation"):
            return {
                "success": True,
                "response": result.get("stopped_reason") or "Draft ready. Want me to send it?",
                "data": result,
            }
        if result.get("success"):
            return {
                "success": True,
                "response": "Desktop grounding action completed." if not dry_run else "Desktop grounding dry-run completed.",
                "data": result,
            }

        return {
            "success": False,
            "response": result.get("stopped_reason") or "Desktop grounding stopped safely.",
            "data": result,
        }

    def analyze_current_screen(self) -> dict[str, Any]:
        shot = self._capture_current_screen("analyze")
        parse_result = self.executor.parser.parse(str(shot))
        if not parse_result.success:
            return {
                "success": False,
                "response": "I couldn't ground the current screen yet: " + "; ".join(parse_result.blockers),
                "data": parse_result.to_dict(),
            }

        labels = [element.label for element in parse_result.elements[:8] if element.label]
        if not labels:
            return {"success": True, "response": "I captured the screen, but no UI labels were detected.", "data": parse_result.to_dict()}
        return {
            "success": True,
            "response": "I found these UI elements: " + ", ".join(labels) + ".",
            "data": parse_result.to_dict(),
        }

    def test_parser(self) -> dict[str, Any]:
        shot = self._capture_current_screen("parser_test")
        parse_result = self.executor.parser.parse(str(shot))
        data = parse_result.to_dict()
        data["screenshot"] = str(shot)
        result_path = Path(self.screenshot_dir) / f"parser_test_{int(time.time())}.json"
        try:
            import json

            result_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            data["result_path"] = str(result_path)
        except Exception:
            pass
        if not parse_result.success:
            return {
                "success": False,
                "response": f"{self.executor.parser.parser_name} is not ready: " + "; ".join(parse_result.blockers),
                "data": data,
            }
        labels = [element.label for element in parse_result.elements[:10] if element.label]
        return {
            "success": True,
            "response": f"{self.executor.parser.parser_name} detected {len(parse_result.elements)} UI elements. Top labels: " + ", ".join(labels),
            "data": data,
        }

    def verify_current_screen(self, question: str) -> dict[str, Any]:
        shot = self._capture_current_screen("verify")
        return self.verifier.run(question=question, screenshot_path=str(shot))

    def _capture_current_screen(self, prefix: str) -> Path:
        out_dir = Path(self.screenshot_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{prefix}_{int(time.time())}.png"
        DesktopActionExecutor._safe_screenshot(path)
        return path
