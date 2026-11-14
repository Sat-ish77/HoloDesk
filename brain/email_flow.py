"""State of one email being written by voice.

The conversation itself is run by a strong model (ReplyEngine._email_brain):
live tests showed a fixed question script with regex rules fighting the user
(rejecting "Sati Swagli. It should be a new email.", restarting on "just
press send"). This module only holds the draft and a few helpers.
"""
from __future__ import annotations

import re
import time

_START = re.compile(r"\b(draft|write|compose)\b(\s+\S+){0,3}?\s+(e-?mail|mail)\b"
                    r"|\bsend\s+(an?|new)\s+(e-?mail|mail)\b|\b(e-?mail|mail)\s+to\b|इमेल", re.I)
_ASKING_ABOUT = re.compile(r"^\s*(did|have|has|was|were|is|are|can you check)\b", re.I)
_ORDINALS = {"first": 0, "one": 0, "1": 0, "second": 1, "two": 1, "2": 1, "third": 2, "three": 2,
             "3": 2, "fourth": 3, "four": 3, "4": 3, "fifth": 4, "five": 4, "5": 4, "last": -1}
_FILE_FILLER = {"my", "the", "a", "an", "file", "called", "named", "attach", "attachment", "document",
                "please", "it", "that", "this", "one", "from", "in", "folder", "on", "desktop", "and"}
TIMEOUT_SEC = 600


def wants_email(text: str) -> bool:
    return bool(_START.search(text)) and not _ASKING_ABOUT.search(text)


class EmailFlow:
    def __init__(self):
        self.to = self.mode = self.subject = self.body = None
        self.attachment = None          # file name as the user said it; "" = none
        self.attachment_path = None
        self.choices: list[str] = []    # several files matched: the user picks one
        self.attached = None            # file name Gmail showed as attached
        self.drafted = False            # written into Gmail and read back
        self.started = time.time()

    def expired(self) -> bool:
        return time.time() - self.started > TIMEOUT_SEC

    def pick(self, answer: str) -> str | None:
        """'the first one' / 'the PDF' -> the chosen path, or None."""
        words = re.findall(r"[a-z0-9]+", (answer or "").lower())
        pos = next((_ORDINALS[w] for w in words if w in _ORDINALS), None)
        if pos is None:
            hits = [p for p in self.choices if any(w in basename(p).lower() for w in words if len(w) > 2)]
            pos = self.choices.index(hits[0]) if len(hits) == 1 else None
        if pos is None:
            return None
        self.attachment_path = self.choices[pos]
        return self.attachment_path


def _parts(path: str) -> list[str]:
    return re.split(r"[\\/]", path.rstrip("\\/"))     # Windows paths use backslashes


def basename(path: str) -> str:
    return _parts(path)[-1]


def describe_file(path: str) -> str:
    parts = _parts(path)
    return f"{parts[-1]} in {parts[-2]}" if len(parts) > 1 else parts[-1]


def search_words(spoken: str) -> list[str]:
    """'my resume pdf' -> ['resume', 'pdf']: file names rarely contain the filler."""
    return [w for w in re.findall(r"[a-z0-9]+", spoken.lower()) if w not in _FILE_FILLER]
