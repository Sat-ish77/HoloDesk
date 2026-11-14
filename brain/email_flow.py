"""Guided email: HOLO asks for each missing piece, code runs the Gmail steps,
and the send waits for the user's yes.

Live tests showed the free-form agent loop guessing instead of asking
(drafting a reply when a new email was wanted, searching files for a
contact). Here the model is not involved at all: the order of questions,
the tool calls and the confirmation are fixed.
"""
from __future__ import annotations

import re
import time

# ponytail: English questions only; add Nepali wording when voice tests use it.
_START = re.compile(r"\b(draft|write|compose|send)\b(\s+\S+){0,3}?\s+(e-?mail|mail)\b"
                    r"|\b(e-?mail|mail)\s+to\b|इमेल", re.I)
_ASKING_ABOUT = re.compile(r"^\s*(did|have|has|was|were|is|are|can you check)\b", re.I)
_CANCEL = re.compile(r"^\s*(cancel|never ?mind|forget (it|that)|drop it|रद्द)\b", re.I)
_REPLY = re.compile(r"\b(reply|respond|existing|thread|old|previous|जवाफ|jawaf)\b", re.I)
_NEW = re.compile(r"\b(new|fresh|naya|नयाँ)\b", re.I)
# "send an email to Smarika Koirala" -> recipient known up front.
_TO_NAME = re.compile(r"\bto\s+([A-Z][\w.'@-]*(?:\s+[A-Z][\w.'@-]*){0,2})")
TIMEOUT_SEC = 300

QUESTIONS = {
    "to": "Who should the email go to?",
    "mode": "Is this a new email, or a reply to an existing thread?",
    "subject": "What's the subject?",
    "body": "What should the email say?",
}


def wants_email(text: str) -> bool:
    return bool(_START.search(text)) and not _ASKING_ABOUT.search(text)


def is_cancel(text: str) -> bool:
    return bool(_CANCEL.search(text))


class EmailFlow:
    def __init__(self, request: str = ""):
        self.to = self.mode = self.subject = self.body = None
        self.started = time.time()
        m = _TO_NAME.search(request or "")
        if m:
            self.to = m.group(1).strip()

    def expired(self) -> bool:
        return time.time() - self.started > TIMEOUT_SEC

    def next_slot(self) -> str | None:
        for slot in ("to", "mode", "subject", "body"):
            if slot == "subject" and self.mode == "reply":
                continue    # a reply keeps the thread's subject
            if getattr(self, slot) is None:
                return slot
        return None

    def question(self) -> str | None:
        slot = self.next_slot()
        return QUESTIONS[slot] if slot else None

    def take(self, answer: str) -> str | None:
        """Store the answer to the current question. Returns a re-ask when
        the answer doesn't fit, else None."""
        answer = " ".join((answer or "").split()).strip(" .")
        slot = self.next_slot()
        if slot is None or not answer:
            return None
        if slot == "mode":
            if _REPLY.search(answer):
                self.mode = "reply"
            elif _NEW.search(answer):
                self.mode = "new"
            else:
                return "Sorry, a new email or a reply to an existing thread?"
            return None
        setattr(self, slot, answer)
        return None
