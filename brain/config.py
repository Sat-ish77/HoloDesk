"""
Brain configuration. Everything is an environment variable with a sane default,
so the brain runs with nothing but GROQ_API_KEY set.

No GPU is assumed anywhere: the LLM and the heavy speech model run on Groq's
hosted hardware. Point HOLODESK_LLM_BASE_URL at Ollama / LM Studio later and
the same code runs fully local.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name, "1" if default else "0").lower()
    return raw in {"1", "true", "yes", "on"}


def _env_ids(name: str) -> set[int]:
    out: set[int] = set()
    for part in _env(name).replace(";", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            out.add(int(part))
    return out


# Best first. Separate models for the two tiers also means separate
# rate-limit buckets on providers that meter per model.
CHAT_MODEL_PREFERENCES = [
    "openai/gpt-oss-120b", "llama-3.3-70b-versatile", "qwen/qwen3.8-27b",
    "moonshotai/kimi-k2-instruct", "openai/gpt-oss-20b",
]
FAST_MODEL_PREFERENCES = [
    "openai/gpt-oss-20b", "llama-3.1-8b-instant", "qwen/qwen3.8-27b", "openai/gpt-oss-120b",
]
VISION_MODEL_PREFERENCES = [
    "meta-llama/llama-4-scout-17b-16e-instruct", "meta-llama/llama-4-maverick-17b-128e-instruct",
]


@dataclass
class BrainConfig:
    # --- LLM (any OpenAI-compatible endpoint) ---
    llm_base_url: str = field(default_factory=lambda: _env(
        "HOLODESK_LLM_BASE_URL", "https://api.groq.com/openai/v1"))
    llm_api_key: str = field(default_factory=lambda: _env(
        "HOLODESK_LLM_API_KEY") or _env("GROQ_API_KEY"))
    # Chat tier: does the tool calling. Fast tier: routing and background jobs.
    # Empty means "auto": on first use the engine asks the provider which
    # models exist and takes the first match from the preference lists below.
    # Hosted model line-ups change every few months; a hard-coded name is how
    # an assistant silently dies.
    chat_model: str = field(default_factory=lambda: _env("HOLODESK_CHAT_MODEL"))
    fast_model: str = field(default_factory=lambda: _env("HOLODESK_FAST_MODEL"))
    # Optional image-capable model for look_at_screen. Empty = auto / none.
    vision_model: str = field(default_factory=lambda: _env("HOLODESK_VISION_MODEL"))
    llm_timeout_sec: int = field(default_factory=lambda: _env_int(
        "HOLODESK_LLM_TIMEOUT_SEC", 45))
    # Used when the primary (Groq) call fails. Empty key = no fallback.
    fallback_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    fallback_model: str = field(default_factory=lambda: _env(
        "HOLODESK_FALLBACK_MODEL", "gpt-4o-mini"))

    # --- Agent loop ---
    max_turns: int = field(default_factory=lambda: _env_int("HOLODESK_MAX_TURNS", 8))
    max_tools_per_request: int = field(default_factory=lambda: _env_int(
        "HOLODESK_MAX_TOOLS", 10))
    llm_router: bool = field(default_factory=lambda: _env_bool("HOLODESK_LLM_ROUTER", True))
    tool_result_max_chars: int = field(default_factory=lambda: _env_int(
        "HOLODESK_TOOL_RESULT_MAX_CHARS", 4000))
    history_turns: int = field(default_factory=lambda: _env_int(
        "HOLODESK_HISTORY_TURNS", 12))

    # --- Identity / language ---
    assistant_name: str = field(default_factory=lambda: _env(
        "HOLODESK_ASSISTANT_NAME", "HoloDesk"))
    user_name: str = field(default_factory=lambda: _env("HOLODESK_USER_NAME"))

    # --- Memory ---
    memory_enabled: bool = field(default_factory=lambda: _env_bool(
        "HOLODESK_MEMORY", True))

    # --- Safety ---
    # Extra folders (besides the home directory) the file tools may touch.
    extra_file_roots: str = field(default_factory=lambda: _env(
        "HOLODESK_FILE_ROOTS"))
    confirm_timeout_sec: int = field(default_factory=lambda: _env_int(
        "HOLODESK_CONFIRM_TIMEOUT_SEC", 120))

    # --- Phone bridge ---
    telegram_token: str = field(default_factory=lambda: _env("TELEGRAM_BOT_TOKEN"))
    telegram_allowed_ids: set[int] = field(default_factory=lambda: _env_ids(
        "TELEGRAM_ALLOWED_USER_IDS"))

    @property
    def llm_ready(self) -> bool:
        key = self.llm_api_key
        if "localhost" in self.llm_base_url or "127.0.0.1" in self.llm_base_url:
            return True  # local servers need no key
        return bool(key) and len(key) >= 20 and "your_" not in key.lower()


def load_config() -> BrainConfig:
    return BrainConfig()
