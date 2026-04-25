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

import pyautogui

from connectors.openai_client import OpenAIClient
from vision.ui_parser import UIElement, UIParserAdapter, build_default_parser


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

        website_match = re.search(r"\bopen\s+(.+?)\s+(?:in|using|with)\s+(chrome|brave)\b", low)
        if website_match:
            target = website_match.group(1).strip(" .,!?:;")
            browser = website_match.group(2).strip()
            steps.append(PlanStep("open_application", {"app_name": browser}))
            steps.append(PlanStep("open_website", {"target": target, "browser": browser}))
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
        elif "search" in low and "outlook" in low:
            query = self._extract_after(text, "search")
            steps.append(PlanStep("open_application", {"app_name": "outlook"}))
            steps.append(PlanStep("click_element_by_label", {"label": "Search"}))
            steps.append(PlanStep("type_text", {"text": query}))
        elif "draft email" in low:
            steps.append(PlanStep("open_application", {"app_name": "outlook"}))
            steps.append(PlanStep("click_element_by_label", {"label": "New Mail"}))
            steps.append(PlanStep("type_text", {"text": self._extract_after(text, "draft email") or ""}))
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
        elif low.startswith("click "):
            label = self._extract_after(text, "click")
            steps.append(PlanStep("click_element_by_label", {"label": label}))
        elif low.startswith("type "):
            payload = self._extract_after(text, "type")
            steps.append(PlanStep("type_text", {"text": payload}))

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
        out_dir = Path(screenshot_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        logs: list[dict[str, Any]] = []
        stopped_reason = None

        for i, step in enumerate(plan.steps, start=1):
            before = out_dir / f"step_{i:02d}_before.png"
            after = out_dir / f"step_{i:02d}_after.png"
            self._safe_screenshot(before)

            parse_result = self.parser.parse(str(before))
            if not parse_result.success and step.action in {
                "click_element_by_label",
                "type_text",
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

    def _run_step(self, step: PlanStep, elements: list[UIElement], *, dry_run: bool) -> dict[str, Any]:
        if step.action in {"blocked_send_email", "blocked_delete"}:
            return {"success": False, "response": step.args.get("reason", "Blocked by policy.")}

        if step.action == "noop":
            return {"success": False, "response": step.args.get("reason", "No-op")}

        if step.action == "open_application":
            if dry_run:
                return {"success": True, "response": f"Dry-run: would open {step.args.get('app_name', '')}."}
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
            pyautogui.hotkey("win", "r")
            time.sleep(0.2)
            pyautogui.write(f"{browser} {url}", interval=0.01)
            pyautogui.press("enter")
            return {"success": True, "response": "Website open sequence sent."}

        if step.action == "open_folder":
            folder = step.args.get("path", "")
            if not folder:
                return {"success": False, "response": "Missing folder path."}
            if dry_run:
                return {"success": True, "response": f"Dry-run: would open folder {folder}."}
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
            pyautogui.write(text, interval=0.01)
            return {"success": True, "response": "Typed text."}

        return {"success": False, "response": f"Unsupported step action: {step.action}"}

    @staticmethod
    def _choose_element(elements: list[UIElement], wanted_label: str) -> UIElement | None:
        if not elements:
            return None
        exact = [e for e in elements if e.label.lower() == wanted_label]
        if exact:
            return sorted(exact, key=lambda e: e.confidence, reverse=True)[0]

        partial = [e for e in elements if wanted_label and wanted_label in e.label.lower()]
        if partial:
            return sorted(partial, key=lambda e: e.confidence, reverse=True)[0]

        return None

    @staticmethod
    def _safe_screenshot(path: Path) -> None:
        try:
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
