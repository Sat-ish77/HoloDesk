"""CLI demo for first-pass desktop UI grounding.

This script is designed for manual Windows testing without changing the main
real-time HoloDesk loop yet.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agents.desktop_grounding_agent import (
    DesktopActionExecutor,
    DesktopActionPlanner,
    VerifyWithChatGPTVision,
)


def cmd_plan(command: str) -> int:
    planner = DesktopActionPlanner()
    plan = planner.build_plan(command)
    print(json.dumps(plan.to_dict(), indent=2))
    return 0


def cmd_execute(command: str, dry_run: bool, screenshot_dir: str) -> int:
    planner = DesktopActionPlanner()
    plan = planner.build_plan(command)
    executor = DesktopActionExecutor()
    result = executor.execute_plan(plan, dry_run=dry_run, screenshot_dir=screenshot_dir)
    print(json.dumps(result, indent=2))
    return 0 if result.get("success") else 2


def cmd_verify(question: str, screenshot: str) -> int:
    shot = Path(screenshot)
    if not shot.exists():
        print(json.dumps({"success": False, "response": f"Screenshot not found: {shot}"}, indent=2))
        return 2

    verifier = VerifyWithChatGPTVision()
    result = verifier.run(question=question, screenshot_path=str(shot))
    print(json.dumps(result, indent=2))
    return 0 if result.get("success") else 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="HoloDesk UI grounding desktop control demo")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan", help="Build a safe action plan")
    p_plan.add_argument("--command", required=True, help="Natural language desktop command")

    p_exec = sub.add_parser("execute", help="Execute plan with grounding loop")
    p_exec.add_argument("--command", required=True, help="Natural language desktop command")
    p_exec.add_argument("--dry-run", action="store_true", help="Do not perform live desktop actions")
    p_exec.add_argument("--screenshot-dir", default="artifacts/ui_grounding", help="Path to screenshot artifact directory")

    p_verify = sub.add_parser("verify", help="Verify screenshot with OpenAI vision")
    p_verify.add_argument("--question", required=True, help="Verification question")
    p_verify.add_argument("--screenshot", required=True, help="Path to screenshot image")

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.cmd == "plan":
        return cmd_plan(args.command)
    if args.cmd == "execute":
        return cmd_execute(args.command, dry_run=args.dry_run, screenshot_dir=args.screenshot_dir)
    if args.cmd == "verify":
        return cmd_verify(args.question, args.screenshot)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
