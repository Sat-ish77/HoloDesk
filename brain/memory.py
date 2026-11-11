"""
Long-term memory for HoloDesk, in the same SQLite file as the habit logger.

Three layers, cheapest first:

  warm profile   a short block of user facts + standing instructions that is
                 injected into EVERY reply (no search, no extra LLM call)
  facts          durable things worth knowing, in three branches:
                   user        who the user is, tastes, people, routines
                   directives  how the user wants the assistant to behave
                   world       things learned along the way
  turns + diary  every conversation turn, searchable, plus daily summaries

Everything is redacted before it is written: keys, passwords and card-like
numbers never reach disk.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

from .tools.registry import tokenize

_DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "holodesk.db"

BRANCHES = ("user", "directives", "world")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS brain_turns (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    source   TEXT NOT NULL,
    role     TEXT NOT NULL,
    content  TEXT NOT NULL,
    ts       REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_brain_turns_ts ON brain_turns(ts);

CREATE TABLE IF NOT EXISTS brain_facts (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    branch    TEXT NOT NULL,
    fact      TEXT NOT NULL,
    norm      TEXT NOT NULL,
    created   REAL NOT NULL,
    last_used REAL NOT NULL,
    uses      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_brain_facts_branch ON brain_facts(branch);

CREATE TABLE IF NOT EXISTS brain_diary (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    day          TEXT NOT NULL,
    summary      TEXT NOT NULL,
    last_turn_id INTEGER NOT NULL,
    created      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS brain_audit (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        REAL NOT NULL,
    record    TEXT NOT NULL
);
"""

_REDACTIONS = [
    (re.compile(r"\b(gsk|sk|pk|xox[baprs]|ghp|gho|github_pat|AKIA)[-_A-Za-z0-9]{16,}\b"), "[redacted-key]"),
    (re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b"), "[redacted-bot-token]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[redacted-number]"),
    (re.compile(r"(?i)\b(password|passwd|pwd|passcode|pin|secret|token|api[_ ]?key)\b(\s*(is|=|:)\s*)(\S+)"),
     r"\1\2[redacted]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[redacted-id]"),
]


def redact(text: str) -> str:
    out = text or ""
    for pattern, repl in _REDACTIONS:
        out = pattern.sub(repl, out)
    return out


def redact_obj(obj):
    """Redact every string inside a JSON-like structure (keeps it valid JSON)."""
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        return {str(k): redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [redact_obj(v) for v in obj]
    if isinstance(obj, (int, float, bool)) or obj is None:
        return obj
    return redact(str(obj))


def _norm(text: str) -> str:
    return " ".join(tokenize(text))


def _overlap(a: str, b: str) -> float:
    ta, tb = set(tokenize(a)), set(tokenize(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


class MemoryStore:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = str(db_path) if db_path else str(_DEFAULT_DB)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            if self.db_path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # ------------------------------------------------------------------ turns
    def add_turn(self, source: str, role: str, content: str) -> int:
        content = redact((content or "").strip())
        if not content:
            return 0
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO brain_turns (source, role, content, ts) VALUES (?,?,?,?)",
                (source, role, content, time.time()))
            self._conn.commit()
            return cur.lastrowid

    def recent_turns(self, limit: int = 12, max_age_sec: float = 1800.0) -> list[dict]:
        """Recent dialogue across ALL sources: a question asked by voice can be
        followed up from the phone, because it is one conversation."""
        cutoff = time.time() - max_age_sec
        with self._lock:
            rows = self._conn.execute(
                "SELECT role, content, source, ts FROM brain_turns WHERE ts >= ? "
                "ORDER BY id DESC LIMIT ?", (cutoff, limit)).fetchall()
        return [dict(r) for r in reversed(rows)]

    def search_turns(self, query: str, limit: int = 6) -> list[dict]:
        q = set(tokenize(query))
        if not q:
            return []
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, role, content, ts FROM brain_turns ORDER BY id DESC LIMIT 3000"
            ).fetchall()
        scored = []
        for r in rows:
            hits = len(q & set(tokenize(r["content"])))
            if hits:
                scored.append((hits, r["id"], dict(r)))
        scored.sort(key=lambda x: (-x[0], -x[1]))
        out = []
        for _, _, r in scored[:limit]:
            r["when"] = datetime.fromtimestamp(r.pop("ts")).strftime("%Y-%m-%d %H:%M")
            r.pop("id", None)
            out.append(r)
        return out

    # ------------------------------------------------------------------ facts
    def add_fact(self, branch: str, fact: str) -> dict:
        branch = branch if branch in BRANCHES else "user"
        fact = redact((fact or "").strip())
        norm = _norm(fact)
        if not norm:
            return {"saved": False, "reason": "empty"}
        now = time.time()
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, fact, norm FROM brain_facts WHERE branch = ?", (branch,)).fetchall()
            for r in rows:
                if r["norm"] == norm:
                    return {"saved": False, "reason": "already known", "id": r["id"]}
                # A longer restatement of a known fact replaces it.
                if _overlap(r["norm"], norm) >= 0.85 and len(norm) >= len(r["norm"]):
                    self._conn.execute(
                        "UPDATE brain_facts SET fact=?, norm=?, last_used=? WHERE id=?",
                        (fact, norm, now, r["id"]))
                    self._conn.commit()
                    return {"saved": True, "updated": True, "id": r["id"]}
                if _overlap(r["norm"], norm) >= 0.85:
                    return {"saved": False, "reason": "already known", "id": r["id"]}
            cur = self._conn.execute(
                "INSERT INTO brain_facts (branch, fact, norm, created, last_used) VALUES (?,?,?,?,?)",
                (branch, fact, norm, now, now))
            self._conn.commit()
            return {"saved": True, "id": cur.lastrowid}

    def facts(self, branch: str | None = None) -> list[dict]:
        sql = "SELECT id, branch, fact, uses, last_used FROM brain_facts"
        params: tuple = ()
        if branch:
            sql += " WHERE branch = ?"
            params = (branch,)
        with self._lock:
            rows = self._conn.execute(sql + " ORDER BY last_used DESC", params).fetchall()
        return [dict(r) for r in rows]

    def recall(self, query: str, limit: int = 6) -> list[dict]:
        q = set(tokenize(query))
        if not q:
            return []
        scored = []
        for f in self.facts():
            hits = len(q & set(tokenize(f["fact"])))
            if hits:
                scored.append((hits, f["last_used"], f))
        scored.sort(key=lambda x: (-x[0], -x[1]))
        top = [f for _, _, f in scored[:limit]]
        if top:
            now = time.time()
            with self._lock:
                self._conn.executemany(
                    "UPDATE brain_facts SET uses = uses + 1, last_used = ? WHERE id = ?",
                    [(now, f["id"]) for f in top])
                self._conn.commit()
        return [{"branch": f["branch"], "fact": f["fact"]} for f in top]

    def forget(self, query: str) -> int:
        """Delete facts matching the query. Returns how many were removed."""
        q = set(tokenize(query))
        if not q:
            return 0
        doomed = []
        for f in self.facts():
            tokens = set(tokenize(f["fact"]))
            if tokens and len(q & tokens) / len(q) >= 0.6:
                doomed.append(f["id"])
        if doomed:
            with self._lock:
                self._conn.executemany("DELETE FROM brain_facts WHERE id = ?",
                                       [(i,) for i in doomed])
                self._conn.commit()
        return len(doomed)

    def warm_profile(self, max_chars: int = 900) -> str:
        """Query-independent block injected into every reply."""
        lines: list[str] = []
        used = 0
        for branch, title in (("directives", "Standing instructions"), ("user", "About the user")):
            facts = self.facts(branch)
            if not facts:
                continue
            block = [f"{title}:"]
            for f in facts:
                line = f"- {f['fact']}"
                if used + len(line) > max_chars:
                    break
                block.append(line)
                used += len(line)
            if len(block) > 1:
                lines.extend(block)
        return "\n".join(lines)

    # ------------------------------------------------------------------ diary
    def unsummarised_turns(self) -> tuple[list[dict], int]:
        with self._lock:
            row = self._conn.execute("SELECT MAX(last_turn_id) AS m FROM brain_diary").fetchone()
            last = row["m"] or 0
            rows = self._conn.execute(
                "SELECT id, role, content, ts FROM brain_turns WHERE id > ? ORDER BY id",
                (last,)).fetchall()
        turns = [dict(r) for r in rows]
        return turns, (turns[-1]["id"] if turns else last)

    def add_diary(self, summary: str, last_turn_id: int) -> None:
        summary = redact((summary or "").strip())
        if not summary:
            return
        with self._lock:
            self._conn.execute(
                "INSERT INTO brain_diary (day, summary, last_turn_id, created) VALUES (?,?,?,?)",
                (datetime.now().strftime("%Y-%m-%d"), summary, last_turn_id, time.time()))
            self._conn.commit()

    def diary(self, limit: int = 5) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT day, summary FROM brain_diary ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ audit
    def audit(self, record: dict) -> None:
        safe = redact_obj(record)
        with self._lock:
            self._conn.execute("INSERT INTO brain_audit (ts, record) VALUES (?,?)",
                               (time.time(), json.dumps(safe, ensure_ascii=False)))
            self._conn.commit()

    def recent_audit(self, limit: int = 10) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT ts, record FROM brain_audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for r in rows:
            rec = json.loads(r["record"])
            rec["when"] = datetime.fromtimestamp(r["ts"]).strftime("%Y-%m-%d %H:%M:%S")
            out.append(rec)
        return out

    def close(self) -> None:
        with self._lock:
            self._conn.close()
