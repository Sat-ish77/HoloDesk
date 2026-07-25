"""Fast command normalization before intent routing.

English commands return unchanged. A small deterministic phrase layer handles
common Nepali / romanized Nepali desktop commands without adding model latency.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class NormalizedCommand:
    original: str
    text: str
    changed: bool = False
    language_hint: str = "en"


class CommandNormalizer:
    ROMANIZED_MARKERS = {
        "khola", "kholnu", "banda", "band", "gara", "gar", "mero", "screen",
        "lekha", "patha", "pathau", "khoja", "her", "dekhau", "suna",
    }

    NEPALI_TRANSLATIONS = {
        "chrome khola": "open chrome",
        "brave khola": "open brave",
        "facebook khola": "open facebook",
        "youtube khola": "open youtube",
        "gmail khola": "open gmail",
        "outlook khola": "open outlook",
        "chrome banda gara": "close chrome",
        "brave banda gara": "close brave",
        "facebook banda gara": "close facebook",
        "screen padha": "read my screen",
        "mero screen padha": "read my screen",
        "screen hera": "analyze my screen",
        "mero screen hera": "analyze my screen",
        "message lekha": "draft a message",
        "email lekha": "draft an email",
        "khoja": "search for",
        "scroll tala": "scroll down",
        "scroll mathi": "scroll up",
    }

    WORD_REPLACEMENTS = [
        (r"\bkhola\b|\bkholnu\b", "open"),
        (r"\bbanda\s+gara\b|\bband\s+gara\b|\bbanda\b", "close"),
        (r"\bkhoja\b", "search for"),
        (r"\blekha\b", "write"),
        (r"\bpatha(?:u)?\b", "send"),
        (r"\bhera\b|\bher\b", "analyze"),
        (r"\bmero\b", "my"),
        (r"\btala\b", "down"),
        (r"\bmathi\b", "up"),
    ]

    def normalize(self, command: str) -> NormalizedCommand:
        original = (command or "").strip()
        if not original:
            return NormalizedCommand(original="", text="")

        lowered = re.sub(r"\s+", " ", original.lower()).strip(" .,!?:;")
        has_devanagari = any("\u0900" <= ch <= "\u097f" for ch in original)
        has_romanized_marker = any(marker in lowered.split() for marker in self.ROMANIZED_MARKERS)

        if not has_devanagari and not has_romanized_marker:
            return NormalizedCommand(original=original, text=original)

        normalized = lowered
        for phrase, replacement in sorted(self.NEPALI_TRANSLATIONS.items(), key=lambda item: len(item[0]), reverse=True):
            normalized = re.sub(rf"\b{re.escape(phrase)}\b", replacement, normalized)

        for pattern, replacement in self.WORD_REPLACEMENTS:
            normalized = re.sub(pattern, replacement, normalized)

        normalized = re.sub(r"\s+", " ", normalized).strip()
        if not normalized:
            normalized = original
        return NormalizedCommand(
            original=original,
            text=normalized,
            changed=normalized.lower() != original.lower(),
            language_hint="ne" if has_devanagari or has_romanized_marker else "en",
        )
