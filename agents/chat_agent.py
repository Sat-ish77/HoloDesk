import time
from dataclasses import dataclass

from connectors.groq_client import GroqClient


@dataclass
class ChatResult:
    success: bool
    response: str


class ChatAgent:
    """
    General conversation agent.
    - Keeps short rolling history (MAX_HISTORY turns).
    - Uses Groq llama-3.3-70b-versatile for fast, high-quality replies.
    """

    MAX_HISTORY = 10

    def __init__(self):
        self.groq = GroqClient()
        # history entries: {"role": "user"|"assistant", "content": str}
        self.history: list[dict] = []

    def clear_history(self):
        self.history = []

    def execute(self, message: str, context: dict | None = None) -> dict:
        """
        Returns: {success: bool, response: str}
        """
        context = context or {}
        habits = context.get("habits", "")
        today_context = context.get("context", "")

        system = (
            "You are HoloDesk, an ambient AI assistant living as a transparent overlay "
            "on the user's Windows desktop. You are helpful, concise, and friendly. "
            "Keep responses to 2-3 sentences maximum. "
            "Never say 'As an AI language model'. "
            "If asked to do something on the desktop, respond with what you'll do and keep it brief.\n\n"
            f"User habits (summary): {habits}\n"
            f"Today's context: {today_context}"
        )

        # GroqClient wrapper currently supports one user prompt + optional system.
        # To preserve memory, we fold a short history into the prompt itself.
        prompt = self._build_prompt(message)

        try:
            reply = self.groq.complete(prompt=prompt, system=system, max_tokens=220)
        except Exception as e:
            return {"success": False, "response": f"I couldn't reach the AI right now: {e}"}

        self._append_turn(message, reply)
        return {"success": True, "response": reply}

    def _append_turn(self, user: str, assistant: str):
        self.history.append({"role": "user", "content": user})
        self.history.append({"role": "assistant", "content": assistant})
        # keep last MAX_HISTORY turns (user+assistant pairs)
        max_msgs = self.MAX_HISTORY * 2
        if len(self.history) > max_msgs:
            self.history = self.history[-max_msgs:]

    def _build_prompt(self, message: str) -> str:
        if not self.history:
            return message

        # Compact transcript. Avoid huge prompts.
        lines = []
        for h in self.history[-(self.MAX_HISTORY * 2):]:
            role = "User" if h["role"] == "user" else "Assistant"
            lines.append(f"{role}: {h['content']}")
        lines.append(f"User: {message}")
        lines.append("Assistant:")
        return "\n".join(lines)

