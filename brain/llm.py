"""
LLM backends.

One tiny interface (`chat`) so the engine never knows which provider it talks
to. `OpenAICompatibleBackend` speaks the /chat/completions wire format that
Groq, OpenAI, Ollama, LM Studio and llama.cpp all share. `FakeBackend` replays
scripted responses so the engine can be tested with no network and no key.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any


class LLMError(RuntimeError):
    pass


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    raw_arguments: str = ""
    parse_error: str = ""


@dataclass
class LLMResponse:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)

    def as_assistant_message(self) -> dict:
        msg: dict[str, Any] = {"role": "assistant", "content": self.content or ""}
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": tc.raw_arguments or json.dumps(tc.arguments),
                    },
                }
                for tc in self.tool_calls
            ]
        return msg


class LLMBackend:
    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             model: str | None = None, max_tokens: int = 700,
             temperature: float = 0.2) -> LLMResponse:
        raise NotImplementedError


def _parse_tool_calls(raw_calls: list[dict] | None) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for i, rc in enumerate(raw_calls or []):
        fn = rc.get("function") or {}
        raw_args = fn.get("arguments")
        parse_error = ""
        if isinstance(raw_args, dict):
            args, raw_text = raw_args, json.dumps(raw_args)
        else:
            raw_text = raw_args or "{}"
            try:
                args = json.loads(raw_text)
                # Some models double-encode: "\"{...}\""
                if isinstance(args, str):
                    args = json.loads(args)
                if not isinstance(args, dict):
                    raise ValueError("arguments must be a JSON object")
            except (ValueError, TypeError) as e:
                args, parse_error = {}, f"could not decode arguments: {e}"
        calls.append(ToolCall(
            id=rc.get("id") or f"call_{i}_{int(time.time() * 1000)}",
            name=(fn.get("name") or "").strip(),
            arguments=args,
            raw_arguments=raw_text,
            parse_error=parse_error,
        ))
    return calls


class OpenAICompatibleBackend(LLMBackend):
    """Plain `requests` on purpose: no SDK version drift, trivial to mock."""

    def __init__(self, base_url: str, api_key: str, default_model: str,
                 timeout_sec: int = 45, session=None, attempts: int = 3):
        self.attempts = attempts
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model
        self.timeout_sec = timeout_sec
        self._session = session

    def _http(self):
        if self._session is None:
            import requests
            self._session = requests.Session()
        return self._session

    def chat(self, messages, tools=None, model=None, max_tokens=700,
             temperature=0.2) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        last_error = ""
        for attempt in range(self.attempts):
            try:
                resp = self._http().post(
                    f"{self.base_url}/chat/completions",
                    headers=headers, json=payload, timeout=self.timeout_sec,
                )
            except Exception as e:  # network errors
                last_error = f"network error: {e}"
                time.sleep(1.0 * (attempt + 1))
                continue

            if resp.status_code == 429 or resp.status_code >= 500:
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                # Free tiers meter tokens per minute; the provider says how
                # long to wait. Waiting beats failing a spoken request.
                retry_after = resp.headers.get("retry-after", "")
                wait = float(retry_after) if retry_after.replace(".", "", 1).isdigit() else 2.0 * (attempt + 1)
                time.sleep(min(wait, 25.0))
                continue
            if resp.status_code >= 400:
                raise LLMError(f"HTTP {resp.status_code}: {resp.text[:300]}")

            try:
                data = resp.json()
                message = data["choices"][0]["message"]
            except Exception as e:
                raise LLMError(f"malformed response: {e}")
            return LLMResponse(
                content=(message.get("content") or "").strip(),
                tool_calls=_parse_tool_calls(message.get("tool_calls")),
            )
        raise LLMError(last_error or "LLM request failed")


    def list_models(self) -> list[str]:
        """Model ids the provider currently serves ([] if it won't say)."""
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            resp = self._http().get(f"{self.base_url}/models", headers=headers, timeout=8)
            return [m.get("id", "") for m in (resp.json().get("data") or []) if m.get("id")]
        except Exception:
            return []


def resolve_models(cfg, backend) -> None:
    """Fill in any model the user did not pin, from what the provider serves."""
    from .config import (CHAT_MODEL_PREFERENCES, FAST_MODEL_PREFERENCES,
                         VISION_MODEL_PREFERENCES)
    if cfg.chat_model and cfg.fast_model and cfg.vision_model:
        return
    lister = getattr(backend, "list_models", None)
    available = set(lister() if lister else [])

    def pick(preferences: list[str], fallback: str) -> str:
        for name in preferences:
            if name in available:
                return name
        return fallback

    if not cfg.chat_model:
        cfg.chat_model = pick(CHAT_MODEL_PREFERENCES, CHAT_MODEL_PREFERENCES[0])
    if not cfg.fast_model:
        cfg.fast_model = pick(FAST_MODEL_PREFERENCES, cfg.chat_model)
    if not cfg.vision_model:
        cfg.vision_model = pick(VISION_MODEL_PREFERENCES, "")
    if hasattr(backend, "default_model"):
        backend.default_model = cfg.chat_model


class FakeBackend(LLMBackend):
    """Scripted backend for tests. Each entry is an LLMResponse or a callable
    (messages, tools) -> LLMResponse."""

    def __init__(self, script: list):
        self.script = list(script)
        self.calls: list[dict] = []

    def chat(self, messages, tools=None, model=None, max_tokens=700,
             temperature=0.2) -> LLMResponse:
        self.calls.append({"messages": [dict(m) for m in messages],
                           "tools": tools, "model": model})
        if not self.script:
            return LLMResponse(content="(no more scripted responses)")
        nxt = self.script.pop(0)
        return nxt(messages, tools) if callable(nxt) else nxt


class FallbackBackend(LLMBackend):
    """Groq's free tier rate-limits and sometimes rejects a tool call; a paid
    key answers those at once instead of making a spoken request wait."""

    def __init__(self, primary: LLMBackend, fallback: LLMBackend, cooldown_sec: float = 600):
        self.primary = primary
        self.fallback = fallback
        self.cooldown_sec = cooldown_sec
        self._skip_primary_until = 0.0

    def chat(self, messages, tools=None, model=None, max_tokens=700,
             temperature=0.2) -> LLMResponse:
        if time.time() >= self._skip_primary_until:
            try:
                return self.primary.chat(messages, tools=tools, model=model,
                                         max_tokens=max_tokens, temperature=temperature)
            except LLMError as e:
                print(f"LLM ERROR on primary, using fallback for {self.cooldown_sec / 60:.0f} min: {e}")
                # A daily-quota 429 won't clear in seconds; don't pay a failed round trip every turn.
                self._skip_primary_until = time.time() + self.cooldown_sec
        # Primary model names (e.g. Groq's) mean nothing to the fallback provider.
        return self.fallback.chat(messages, tools=tools, max_tokens=max_tokens,
                                  temperature=temperature)

    def list_models(self) -> list[str]:
        return self.primary.list_models()


def make_backend(cfg) -> LLMBackend:
    primary = OpenAICompatibleBackend(
        base_url=cfg.llm_base_url,
        api_key=cfg.llm_api_key,
        default_model=cfg.chat_model or "auto",
        timeout_sec=cfg.llm_timeout_sec,
        # With a fallback, one failed try reroutes immediately instead of retrying.
        attempts=1 if cfg.fallback_api_key else 3,
    )
    if not cfg.fallback_api_key:
        return primary
    return FallbackBackend(primary, OpenAICompatibleBackend(
        base_url="https://api.openai.com/v1",
        api_key=cfg.fallback_api_key,
        default_model=cfg.fallback_model,
        timeout_sec=cfg.llm_timeout_sec,
    ))
