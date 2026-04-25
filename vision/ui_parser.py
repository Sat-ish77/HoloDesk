"""UI parser adapters for desktop grounding.

This module provides a stable parser contract:
- input: screenshot path
- output: structured UI elements with labels, types, boxes, and confidence

OmniParser integration is optional and blocker-aware. If OmniParser is not
installed, callers still receive a structured result with install blocker info.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class UIElement:
    label: str
    element_type: str
    bbox: dict[str, int]
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UIParseResult:
    success: bool
    parser_name: str
    elements: list[UIElement]
    blockers: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "parser_name": self.parser_name,
            "elements": [e.to_dict() for e in self.elements],
            "blockers": list(self.blockers),
        }


class UIParserAdapter:
    parser_name = "base"

    def parse(self, screenshot_path: str) -> UIParseResult:
        raise NotImplementedError


class OmniParserAdapter(UIParserAdapter):
    """Best-effort OmniParser adapter.

    Notes:
    - This repo does not hard-depend on OmniParser.
    - This adapter resolves import at runtime and reports exact blockers.
    - We intentionally keep this integration conservative and non-destructive.
    """

    parser_name = "omniparser"

    def __init__(self) -> None:
        self._backend = None
        self._blockers: list[str] = []

        # Multiple import names are attempted because OmniParser packaging
        # can vary by source and install path.
        for module_name in ("omniparser", "omni_parser"):
            try:
                mod = __import__(module_name)
                self._backend = mod
                break
            except Exception as exc:  # pragma: no cover - env dependent
                self._blockers.append(f"import {module_name} failed: {exc}")

    @property
    def available(self) -> bool:
        return self._backend is not None

    def parse(self, screenshot_path: str) -> UIParseResult:
        shot = Path(screenshot_path)
        if not shot.exists():
            return UIParseResult(
                success=False,
                parser_name=self.parser_name,
                elements=[],
                blockers=[f"screenshot not found: {shot}"],
            )

        if not self.available:
            return UIParseResult(
                success=False,
                parser_name=self.parser_name,
                elements=[],
                blockers=self._blockers
                + [
                    "OmniParser is unavailable in this environment.",
                    "Install OmniParser manually on the Windows test machine, then rerun.",
                ],
            )

        # Placeholder for real OmniParser invocation. We keep a strict contract now
        # so the rest of grounding pipeline can be tested before model install.
        return UIParseResult(
            success=False,
            parser_name=self.parser_name,
            elements=[],
            blockers=[
                "OmniParser backend imported, but runtime invocation is not wired yet.",
                "Use MockUIParser for dry-runs or complete OmniParser call wiring.",
            ],
        )


class MockUIParser(UIParserAdapter):
    """Deterministic parser for local tests and dry-runs without paid APIs."""

    parser_name = "mock"

    def parse(self, screenshot_path: str) -> UIParseResult:
        shot = Path(screenshot_path)
        if not shot.exists():
            return UIParseResult(
                success=False,
                parser_name=self.parser_name,
                elements=[],
                blockers=[f"screenshot not found: {shot}"],
            )

        elements = [
            UIElement(
                label="Address bar",
                element_type="input",
                bbox={"x": 200, "y": 50, "width": 700, "height": 42},
                confidence=0.84,
            ),
            UIElement(
                label="Search field",
                element_type="input",
                bbox={"x": 420, "y": 280, "width": 500, "height": 56},
                confidence=0.79,
            ),
            UIElement(
                label="Compose",
                element_type="button",
                bbox={"x": 70, "y": 210, "width": 140, "height": 44},
                confidence=0.74,
            ),
        ]
        return UIParseResult(
            success=True,
            parser_name=self.parser_name,
            elements=elements,
            blockers=[],
        )


def build_default_parser() -> UIParserAdapter:
    omni = OmniParserAdapter()
    if omni.available:
        return omni
    return MockUIParser()
