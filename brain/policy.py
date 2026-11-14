"""
Safety policy for a brain that can touch the whole laptop.

Three tiers decide what happens to every tool call:

    SAFE    read-only, runs immediately            (list files, system status)
    ACT     changes UI state, easy to undo, runs   (open app, type, click)
    DANGER  destructive or hard to undo, the user  (delete, kill, shutdown,
            must say yes first                      write file, arbitrary shell)
    BLOCKED never runs, no confirmation possible   (format disk, wipe system)

Plus a kill switch (`halt()`): once set, every tool call is refused until
`resume()`. Every decision is written to an audit log.
"""

from __future__ import annotations

import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class Risk(str, Enum):
    SAFE = "safe"
    ACT = "act"
    DANGER = "danger"
    BLOCKED = "blocked"


class Decision(str, Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"


# ---------------------------------------------------------------------------
# Shell command classification
# ---------------------------------------------------------------------------

# Never run, whatever the user says. These are the "one typo destroys the
# machine" and "classic malware move" families.
_BLOCKED_SHELL_PATTERNS = [
    r"\bformat(-volume)?\b\s+[a-z]:",              # format c:
    r"\bformat-volume\b",
    r"\bdiskpart\b",
    r"\bclear-disk\b|\binitialize-disk\b|\bremove-partition\b",
    r"\bbcdedit\b",
    r"\bcipher\b\s+/w",
    r"\bvssadmin\b.*\bdelete\b",
    r"\bwbadmin\b.*\bdelete\b",
    r"\b(rm|del|erase|rd|rmdir|remove-item)\b[^|;&]*\b[a-z]:\\?(\s|$|\*)",          # whole drive
    r"\b(rm|del|erase|rd|rmdir|remove-item)\b[^|;&]*(\\windows\b|system32|\\program files|\\users\\?(\s|$|\*))",
    r"\brm\s+-[a-z]*r[a-z]*f?\s+(/|~|\$home|\$env:userprofile)(\s|$)",
    r"\breg(\.exe)?\s+delete\s+hk(lm|cr|u\b|ey_local_machine|ey_classes_root)",
    r"\bremove-item\b[^|;&]*\bhk(lm|cr):",
    r"\bset-mppreference\b|\bdisablerealtimemonitoring\b",
    r"\bset-executionpolicy\b",
    r"-e(nc|ncodedcommand)?\s+[a-z0-9+/=]{20,}",    # encoded payloads
    r"\b(iwr|irm|invoke-webrequest|invoke-restmethod|curl|wget)\b[^|;&]*\|\s*(iex|invoke-expression)\b",
    r"\b(iex|invoke-expression)\b\s*\(?\s*\(?\s*new-object\s+net\.webclient",
    r"\bnet\s+(user|localgroup)\b.*(/add|/delete)",
    r"\bnetsh\b.*\bfirewall\b.*\b(off|disable)\b",
    r"\btakeown\b|\bicacls\b.*\bgrant\b.*everyone",
    r"\bmimikatz\b|\bsekurlsa\b|\blsass\b",
]

# A command made only of these verbs is read-only and runs without asking.
_SAFE_SHELL_VERBS = {
    "get-childitem", "dir", "ls", "gci", "get-content", "cat", "type", "gc",
    "get-process", "ps", "gps", "tasklist", "get-service", "gsv",
    "get-date", "date", "get-location", "pwd", "gl", "hostname", "whoami",
    "ipconfig", "systeminfo", "ver", "echo", "write-output", "write-host",
    "get-item", "gi", "get-itemproperty", "test-path", "resolve-path",
    "get-volume", "get-psdrive", "get-disk", "get-computerinfo",
    "get-ciminstance", "get-wmiobject", "get-netadapter", "get-netipaddress",
    "get-nettcpconnection", "test-connection", "ping", "nslookup", "tracert",
    "get-command", "get-help", "get-module", "get-history", "get-clipboard",
    "get-filehash", "get-acl", "get-eventlog", "get-winevent", "get-hotfix",
    "get-scheduledtask", "get-printer", "get-pnpdevice", "get-startapps",
    "where", "where.exe", "tree", "findstr", "select-string", "sls",
    "powercfg",  # only with query flags, checked below
    "nvidia-smi", "python", "pip", "git", "node", "npm",  # only with query flags, checked below
}

# Pipeline stages that only reshape output.
_SAFE_PIPE_VERBS = {
    "select-object", "select", "where-object", "?", "sort-object", "sort",
    "measure-object", "measure", "format-table", "ft", "format-list", "fl",
    "group-object", "group", "foreach-object", "%", "out-string", "convertto-json",
    "select-string", "sls", "findstr", "more", "tee-object", "convertto-csv",
}

# Verbs in the safe list that are only safe with read-only arguments.
_QUERY_ONLY = {
    "powercfg": re.compile(r"^\s*powercfg(\.exe)?\s+/(q|query|l|list|a|batteryreport|getactivescheme)\b", re.I),
    "python": re.compile(r"^\s*python\d?(\.exe)?\s+(--version|-V)\s*$", re.I),
    "pip": re.compile(r"^\s*pip\d?(\.exe)?\s+(list|show\b.*|--version|freeze)\s*$", re.I),
    "git": re.compile(r"^\s*git(\.exe)?\s+(status|log|diff|branch|remote\s+-v|show|--version)\b", re.I),
    "node": re.compile(r"^\s*node(\.exe)?\s+(--version|-v)\s*$", re.I),
    "npm": re.compile(r"^\s*npm(\.cmd)?\s+(ls|list|--version|-v|outdated)\b", re.I),
}

# Anything that can write, even inside an otherwise read-only command.
_WRITE_HINTS = re.compile(
    r"(>{1,2})|\bout-file\b|\bset-content\b|\badd-content\b|\bnew-item\b|"
    r"\bremove-item\b|\bmove-item\b|\bcopy-item\b|\brename-item\b|"
    r"\bstart-process\b|\bstop-process\b|\binvoke-expression\b|\biex\b|"
    r"\binvoke-webrequest\b|\binvoke-restmethod\b|\bstart-bitstransfer\b|"
    r"\bset-\w+|\bnew-\w+|\bremove-\w+|\bstop-\w+|\brestart-\w+|\bclear-\w+|"
    r"\binstall-\w+|\buninstall-\w+|\bregister-\w+|\bunregister-\w+|"
    r"\$\(|`|&\s*\{|\.invoke\(",
    re.I,
)


def _first_word(segment: str) -> str:
    seg = segment.strip().lstrip("(&").strip()
    m = re.match(r"[\w\.\-\?%]+", seg)
    return (m.group(0) if m else "").lower()


def classify_shell(command: str) -> Risk:
    """Classify a PowerShell / cmd command. Unknown means DANGER (ask first):
    the allowlist is for skipping the question, never for skipping safety."""
    cmd = (command or "").strip()
    if not cmd:
        return Risk.BLOCKED
    low = cmd.lower()
    for pat in _BLOCKED_SHELL_PATTERNS:
        if re.search(pat, low):
            return Risk.BLOCKED
    if _WRITE_HINTS.search(cmd):
        return Risk.DANGER

    statements = [s for s in re.split(r";|&&|\|\||\n", cmd) if s.strip()]
    for stmt in statements:
        stages = [s for s in stmt.split("|") if s.strip()]
        for i, stage in enumerate(stages):
            verb = _first_word(stage)
            if verb.endswith(".exe"):
                verb = verb[:-4]
            if i == 0:
                if verb not in _SAFE_SHELL_VERBS:
                    return Risk.DANGER
                checker = _QUERY_ONLY.get(verb)
                if checker and not checker.match(stage):
                    return Risk.DANGER
            elif verb not in _SAFE_PIPE_VERBS and verb not in _SAFE_SHELL_VERBS:
                return Risk.DANGER
    return Risk.SAFE


# ---------------------------------------------------------------------------
# Confirmation + kill switch
# ---------------------------------------------------------------------------

_YES = {
    "yes", "y", "yep", "yeah", "yup", "ok", "okay", "sure", "confirm", "do it",
    "go ahead", "go", "proceed", "please do", "yes please",
    # Nepali / Romanized Nepali
    "ho", "hunchha", "huncha", "hunxa", "has", "hajur", "gara", "garnus", "thik cha", "thik chha",
    "हो", "हुन्छ", "हस्", "हस", "हजुर", "गर", "गर्नुस्", "गर्नुस", "ठिक छ", "ठीक छ",
}
_NO = {
    "no", "n", "nope", "nah", "cancel", "stop", "don't", "dont", "abort",
    "never mind", "nevermind", "no thanks",
    "hoina", "haina", "nai", "nagara", "pardaina", "bhayo", "chhadideu",
    "होइन", "हैन", "नाइँ", "नाई", "नगर", "नगर्नुस्", "पर्दैन", "रद्द", "रद्द गर",
}


def _norm_reply(text: str) -> str:
    return re.sub(r"[\s\.\!\?,।]+$", "", (text or "").strip().lower())


# Exact-match only turned "Yes, please send it" and "go ahead, it's good to
# send" into new requests, and the confirmation was asked again and again.
_YES_HINT = re.compile(r"\b(yes|yeah|yep|yup|ok|okay|sure|confirm|go ahead|proceed|do it|send it|"
                       r"looks good|it'?s good|good to (go|send)|ho|huncha|hunchha|thik cha|हो|हुन्छ|ठीक छ)\b", re.I)
_NO_HINT = re.compile(r"\b(no|nope|nah|cancel|stop|don'?t|do not|abort|wait|hold on|not yet|never ?mind|"
                      r"hoina|haina|nagara|होइन|नगर|रद्द)\b", re.I)
# "okay, what's the weather?" must not approve a pending send.
_QUESTION = re.compile(r"\?|\b(what|who|where|when|why|how|which)\b", re.I)


# A yes may carry only confirmation words: "yes, delete everything else too"
# must not approve anything, it adds a new instruction.
_CONFIRM_WORDS = {
    "yes", "yeah", "yep", "yup", "ok", "okay", "sure", "confirm", "confirmed", "go", "ahead", "proceed",
    "do", "it", "its", "it's", "is", "send", "please", "pls", "this", "that", "the", "email", "mail",
    "good", "looks", "fine", "great", "perfect", "to", "now", "right", "just", "all", "set", "thanks",
    "thank", "you", "alright", "correct", "hajur", "ho", "huncha", "hunchha", "thik", "cha", "chha",
}


def is_yes(text: str) -> bool:
    t = _norm_reply(text)
    if t in _YES:
        return True
    words = re.findall(r"[a-z']+", t)
    return (bool(words) and bool(_YES_HINT.search(t)) and not _NO_HINT.search(t)
            and not _QUESTION.search(t) and all(w in _CONFIRM_WORDS for w in words))


def is_no(text: str) -> bool:
    t = _norm_reply(text)
    if t in _NO:
        return True
    # Mixed ("don't send it", "yes, no wait") counts as no: the safe side before a send.
    return len(t.split()) <= 8 and bool(_NO_HINT.search(t))


@dataclass
class PendingAction:
    id: str
    tool: str
    arguments: dict[str, Any]
    summary: str
    source: str
    created: float = field(default_factory=time.time)


class Policy:
    def __init__(self, confirm_timeout_sec: int = 120,
                 audit: Callable[[dict], None] | None = None):
        self.confirm_timeout_sec = confirm_timeout_sec
        self._audit = audit
        self._lock = threading.Lock()
        self._halted = False
        self._pending: dict[str, PendingAction] = {}  # keyed by source

    # --- kill switch ---
    @property
    def halted(self) -> bool:
        return self._halted

    def halt(self, who: str = "user") -> None:
        with self._lock:
            self._halted = True
            self._pending.clear()
        self.audit({"event": "halt", "source": who})

    def resume(self, who: str = "user") -> None:
        with self._lock:
            self._halted = False
        self.audit({"event": "resume", "source": who})

    # --- decisions ---
    def decide(self, risk: Risk) -> Decision:
        if self._halted or risk == Risk.BLOCKED:
            return Decision.DENY
        if risk == Risk.DANGER:
            return Decision.CONFIRM
        return Decision.ALLOW

    # --- pending confirmations (one per source) ---
    def set_pending(self, tool: str, arguments: dict, summary: str,
                    source: str) -> PendingAction:
        action = PendingAction(id=uuid.uuid4().hex[:8], tool=tool,
                               arguments=dict(arguments), summary=summary,
                               source=source)
        with self._lock:
            self._pending[source] = action
        return action

    def get_pending(self, source: str) -> PendingAction | None:
        with self._lock:
            action = self._pending.get(source)
            if action and time.time() - action.created > self.confirm_timeout_sec:
                self._pending.pop(source, None)
                return None
            return action

    def pop_pending(self, source: str) -> PendingAction | None:
        action = self.get_pending(source)
        if action:
            with self._lock:
                self._pending.pop(source, None)
        return action

    # --- audit ---
    def audit(self, record: dict) -> None:
        if self._audit:
            try:
                self._audit(record)
            except Exception:
                pass  # logging must never break a tool call
