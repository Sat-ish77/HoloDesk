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
# "tell her I'll be late" describes an email; "Hey, how are you?" is the email.
_DESCRIBES = re.compile(r"^\s*(please\s+)?(write|tell|ask|let (her|him|them)|thank|invite|remind|explain|"
                        r"apologi[sz]e|wish|make it|draft|compose|something about|about)\b", re.I)
_YOU_CHOOSE = re.compile(r"^\s*(you (choose|decide|pick|write it|come up)|anything|whatever|up to you|"
                         r"make (one|it) up|your choice)\b", re.I)
TIMEOUT_SEC = 300


def needs_writer(answer: str | None) -> bool:
    return bool(answer) and bool(_DESCRIBES.search(answer) or _YOU_CHOOSE.search(answer))


def you_choose(answer: str | None) -> bool:
    return bool(answer) and bool(_YOU_CHOOSE.search(answer))

QUESTIONS = {
    "to": "Who should the email go to?",
    "mode": "Is this a new email, or a reply to an existing thread?",
    "subject": "What's the subject?",
    "body": "What should the email say?",
    "attachment": "Any attachment? Say no, or tell me the file name.",
}
_NO_ATTACHMENT = re.compile(r"^\s*(no|nope|none|nothing|skip|no attachments?|not needed|chaina|chhaina|पर्दैन)\b", re.I)
_ORDINALS = {"first": 0, "one": 0, "1": 0, "second": 1, "two": 1, "2": 1, "third": 2, "three": 2,
             "3": 2, "fourth": 3, "four": 3, "4": 3, "fifth": 4, "five": 4, "5": 4, "last": -1}


def wants_email(text: str) -> bool:
    return bool(_START.search(text)) and not _ASKING_ABOUT.search(text)


def is_cancel(text: str) -> bool:
    return bool(_CANCEL.search(text))


class EmailFlow:
    def __init__(self, request: str = ""):
        self.to = self.mode = self.subject = self.body = None
        self.attachment = None          # what the user called the file; "" = no attachment
        self.attachment_path = None
        self.choices: list[str] = []    # several files matched: the user picks one
        self.started = time.time()
        m = _TO_NAME.search(request or "")
        if m:
            self.to = m.group(1).strip()

    def expired(self) -> bool:
        return time.time() - self.started > TIMEOUT_SEC

    def next_slot(self) -> str | None:
        for slot in ("to", "mode", "subject", "body", "attachment"):
            if slot == "subject" and self.mode == "reply":
                continue    # a reply keeps the thread's subject
            if getattr(self, slot) is None:
                return slot
        if self.choices and not self.attachment_path:
            return "pick"
        return None

    def question(self) -> str | None:
        slot = self.next_slot()
        if slot == "pick":
            listed = "; ".join(f"{i}, {_describe_file(p)}" for i, p in enumerate(self.choices, 1))
            return f"I found {len(self.choices)} files: {listed}. Which one?"
        return QUESTIONS[slot] if slot else None

    def take(self, answer: str) -> str | None:
        """Store the answer to the current question. Returns a re-ask when
        the answer doesn't fit, else None."""
        answer = " ".join((answer or "").split()).strip(" .")
        slot = self.next_slot()
        if slot is None or not answer:
            return None
        if slot == "attachment":
            self.attachment = "" if _NO_ATTACHMENT.search(answer) else answer
            return None
        if slot == "pick":
            words = re.findall(r"[a-z0-9]+", answer.lower())
            pos = next((_ORDINALS[w] for w in words if w in _ORDINALS), None)
            if pos is None:     # or name part of the file: "the PDF one", "resume"
                hits = [p for p in self.choices if any(w in _basename(p).lower() for w in words if len(w) > 2)]
                pos = self.choices.index(hits[0]) if len(hits) == 1 else None
            if pos is None:
                return "Which one? Say first, second, or part of the file name."
            self.attachment_path = self.choices[pos]
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


def _parts(path: str) -> list[str]:
    return re.split(r"[\\/]", path.rstrip("\\/"))     # Windows paths use backslashes


def _basename(path: str) -> str:
    return _parts(path)[-1]


def _describe_file(path: str) -> str:
    parts = _parts(path)
    return f"{parts[-1]} in {parts[-2]}" if len(parts) > 1 else parts[-1]


_FILE_FILLER = {"my", "the", "a", "an", "file", "called", "named", "attach", "attachment", "document",
                "please", "it", "that", "this", "one", "from", "in", "folder", "on", "desktop", "and"}


def search_words(spoken: str) -> list[str]:
    """'my resume pdf' -> ['resume', 'pdf']: file names rarely contain the filler."""
    return [w for w in re.findall(r"[a-z0-9]+", spoken.lower()) if w not in _FILE_FILLER]
