"""UI parser adapters for desktop grounding.

This module provides a stable parser contract:
- input: screenshot path
- output: structured UI elements with labels, types, boxes, and confidence

OmniParser integration is optional and blocker-aware. If OmniParser is not
installed, callers still receive a structured result with install blocker info.
"""

from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import requests

from connectors.openai_client import OpenAIClient


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


class OmniParserServerAdapter(UIParserAdapter):
    """HTTP adapter for a local OmniParser server.

    Recommended production shape: run OmniParser as its own process/server,
    then point HoloDesk at it with OMNIPARSER_SERVER_URL=http://127.0.0.1:8000.
    The Microsoft server uses /parse/; some community servers use
    /process_image, so we support both response shapes.
    """

    parser_name = "omniparser_server"

    def __init__(self, base_url: str | None = None, timeout_s: float = 45.0) -> None:
        self.base_url = (base_url or os.getenv("OMNIPARSER_SERVER_URL", "")).strip().rstrip("/")
        self.timeout_s = timeout_s

    @property
    def available(self) -> bool:
        return bool(self.base_url)

    def parse(self, screenshot_path: str) -> UIParseResult:
        shot = Path(screenshot_path)
        if not shot.exists():
            return UIParseResult(False, self.parser_name, [], [f"screenshot not found: {shot}"])
        if not self.base_url:
            return UIParseResult(False, self.parser_name, [], ["OMNIPARSER_SERVER_URL is not set."])

        errors = []
        for endpoint in ("/parse/", "/process_image"):
            try:
                result = self._post_image(shot, endpoint)
                elements = self._elements_from_response(result)
                if elements:
                    return UIParseResult(True, self.parser_name, elements, [])
                errors.append(f"{endpoint} returned no elements")
            except Exception as exc:
                errors.append(f"{endpoint} failed: {exc}")
        return UIParseResult(False, self.parser_name, [], errors)

    def _post_image(self, shot: Path, endpoint: str) -> Any:
        url = self.base_url + endpoint
        with shot.open("rb") as f:
            files = {"image": (shot.name, f, "image/png")}
            resp = requests.post(url, files=files, timeout=self.timeout_s)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _elements_from_response(payload: Any) -> list[UIElement]:
        if isinstance(payload, dict):
            candidates = (
                payload.get("parsed_content_list")
                or payload.get("elements")
                or payload.get("detections")
                or payload.get("result")
                or []
            )
        else:
            candidates = payload

        elements: list[UIElement] = []
        if not isinstance(candidates, list):
            return elements

        for item in candidates:
            if not isinstance(item, dict):
                continue
            label = (
                item.get("text")
                or item.get("caption")
                or item.get("label")
                or item.get("description")
                or item.get("content")
                or ""
            )
            raw_box = item.get("box") or item.get("bbox") or item.get("coordinate") or item.get("coordinates")
            bbox = _normalize_bbox(raw_box)
            if not label or bbox is None:
                continue
            elements.append(
                UIElement(
                    label=str(label),
                    element_type=str(item.get("class") or item.get("type") or "ui"),
                    bbox=bbox,
                    confidence=float(item.get("confidence") or item.get("score") or 0.75),
                )
            )
        return elements


class OpenAIVisionUIParser(UIParserAdapter):
    """Vision parser fallback that returns clickable UI boxes as JSON."""

    parser_name = "openai_vision"

    def __init__(self, model: str | None = None) -> None:
        self.client = OpenAIClient()
        self.model = model or os.getenv("HOLODESK_UI_VISION_MODEL", "gpt-4o")

    def parse(self, screenshot_path: str) -> UIParseResult:
        shot = Path(screenshot_path)
        if not shot.exists():
            return UIParseResult(False, self.parser_name, [], [f"screenshot not found: {shot}"])

        try:
            from PIL import Image

            with Image.open(shot) as img:
                width, height = img.size
        except Exception:
            width, height = 1280, 720

        image_b64 = base64.b64encode(shot.read_bytes()).decode("utf-8")
        system = (
            "You are a UI grounding parser for a Windows desktop automation assistant. "
            "Return only strict JSON. No markdown. Detect clickable buttons, tabs, links, "
            "text fields, search fields, message boxes, app controls, and visible person/chat rows. "
            "Coordinates must be pixel boxes in the screenshot coordinate system."
        )
        prompt = (
            f"Screenshot size is {width}x{height}. Return JSON with this schema: "
            '{"elements":[{"label":"Search","type":"input|button|link|text|row",'
            '"bbox":{"x":0,"y":0,"width":100,"height":40},"confidence":0.0}]}. '
            "Use short labels that a user might say aloud, including visible text and common synonyms."
        )

        try:
            client = self.client._get_client()
            resp = client.chat.completions.create(
                model=self.model,
                max_tokens=1200,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_b64}",
                                    "detail": "high",
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    },
                ],
            )
            data = json.loads(resp.choices[0].message.content)
            elements = self._elements_from_json(data, width, height)
            if not elements:
                return UIParseResult(False, self.parser_name, [], ["OpenAI vision returned no UI elements."])
            return UIParseResult(True, self.parser_name, elements, [])
        except Exception as exc:
            return UIParseResult(False, self.parser_name, [], [f"OpenAI UI vision failed: {exc}"])

    @staticmethod
    def _elements_from_json(data: Any, width: int, height: int) -> list[UIElement]:
        items = data.get("elements", []) if isinstance(data, dict) else []
        elements: list[UIElement] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or item.get("text") or "").strip()
            bbox = _normalize_bbox(item.get("bbox") or item.get("box"), width=width, height=height)
            if not label or bbox is None:
                continue
            elements.append(
                UIElement(
                    label=label,
                    element_type=str(item.get("type") or item.get("element_type") or "ui"),
                    bbox=bbox,
                    confidence=float(item.get("confidence") or 0.70),
                )
            )
        return elements


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
    server = OmniParserServerAdapter()
    if server.available:
        return server
    if os.getenv("OPENAI_API_KEY", "").strip():
        return OpenAIVisionUIParser()
    omni = OmniParserAdapter()
    if omni.available:
        return omni
    return MockUIParser()


def _normalize_bbox(raw_box: Any, *, width: int | None = None, height: int | None = None) -> dict[str, int] | None:
    if isinstance(raw_box, dict):
        if all(k in raw_box for k in ("x", "y", "width", "height")):
            x = float(raw_box["x"])
            y = float(raw_box["y"])
            w = float(raw_box["width"])
            h = float(raw_box["height"])
        elif all(k in raw_box for k in ("x1", "y1", "x2", "y2")):
            x1 = float(raw_box["x1"])
            y1 = float(raw_box["y1"])
            x2 = float(raw_box["x2"])
            y2 = float(raw_box["y2"])
            x, y, w, h = x1, y1, x2 - x1, y2 - y1
        else:
            return None
    elif isinstance(raw_box, (list, tuple)) and len(raw_box) == 4:
        x1, y1, x2, y2 = [float(v) for v in raw_box]
        if width and height and 0 <= x1 <= 1 and 0 <= y1 <= 1 and 0 <= x2 <= 1 and 0 <= y2 <= 1:
            x1, x2 = x1 * width, x2 * width
            y1, y2 = y1 * height, y2 * height
        x, y, w, h = x1, y1, x2 - x1, y2 - y1
    else:
        return None

    if w <= 0 or h <= 0:
        return None
    return {"x": int(x), "y": int(y), "width": int(w), "height": int(h)}
