"""Memory, date/time (with Bikram Sambat), phone notification and audit tools."""

from __future__ import annotations

import datetime as dt

from ..policy import Risk
from .registry import Tool, ToolContext, ToolError

NPT = dt.timezone(dt.timedelta(hours=5, minutes=45), name="NPT")
_BS_MONTHS = ["Baishakh", "Jestha", "Ashadh", "Shrawan", "Bhadra", "Ashwin",
              "Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chaitra"]
_BS_MONTHS_NE = ["वैशाख", "जेठ", "असार", "साउन", "भदौ", "असोज",
                 "कात्तिक", "मंसिर", "पुस", "माघ", "फागुन", "चैत"]
_WEEKDAYS_NE = ["सोमबार", "मंगलबार", "बुधबार", "बिहीबार", "शुक्रबार", "शनिबार", "आइतबार"]


def _need_memory(ctx: ToolContext):
    if ctx.memory is None:
        raise ToolError("memory is turned off")
    return ctx.memory


def remember(args: dict, ctx: ToolContext) -> dict:
    fact = (args.get("fact") or "").strip()
    if not fact:
        raise ToolError("fact is required")
    result = _need_memory(ctx).add_fact(args.get("branch") or "user", fact)
    return {"ok": True, **result}


def recall_memory(args: dict, ctx: ToolContext) -> dict:
    memory = _need_memory(ctx)
    query = (args.get("query") or "").strip()
    if not query:
        return {"ok": True, "facts": [{"branch": f["branch"], "fact": f["fact"]}
                                      for f in memory.facts()[:25]]}
    return {"ok": True, "facts": memory.recall(query),
            "past_conversation": memory.search_turns(query, limit=4)}


def forget_memory(args: dict, ctx: ToolContext) -> dict:
    query = (args.get("query") or "").strip()
    if not query:
        raise ToolError("query is required")
    removed = _need_memory(ctx).forget(query)
    return {"ok": True, "removed": removed}


def _bs(date: dt.date) -> dict | None:
    try:
        import nepali_datetime
    except ImportError:
        return None
    bs = nepali_datetime.date.from_datetime_date(date)
    return {"bs_date": f"{bs.year}-{bs.month:02d}-{bs.day:02d}",
            "bs_text": f"{bs.day} {_BS_MONTHS[bs.month - 1]} {bs.year}",
            "bs_text_nepali": f"{bs.year} {_BS_MONTHS_NE[bs.month - 1]} {bs.day} गते, "
                              f"{_WEEKDAYS_NE[date.weekday()]}"}


def get_datetime(args: dict, ctx: ToolContext) -> dict:
    now_local = dt.datetime.now().astimezone()
    now_nepal = now_local.astimezone(NPT)
    out = {"ok": True,
           "local": now_local.strftime("%A, %d %B %Y, %H:%M (%Z)"),
           "nepal": now_nepal.strftime("%A, %d %B %Y, %H:%M (NPT, UTC+5:45)")}
    bs_today = _bs(now_nepal.date())
    if bs_today:
        out["nepal_bs_today"] = bs_today
    else:
        out["bs_note"] = ("Bikram Sambat conversion is unavailable (pip install nepali-datetime). "
                          "Do not guess BS dates; say you cannot convert right now.")

    ad = (args.get("convert_ad_to_bs") or "").strip()
    if ad:
        try:
            date = dt.date.fromisoformat(ad)
        except ValueError:
            raise ToolError("convert_ad_to_bs must look like 2026-11-11")
        converted = _bs(date)
        if converted:
            out["converted_to_bs"] = {"ad_date": ad, **converted}
    bs = (args.get("convert_bs_to_ad") or "").strip()
    if bs:
        try:
            import nepali_datetime
            y, m, d = (int(x) for x in bs.split("-"))
            ad_date = nepali_datetime.date(y, m, d).to_datetime_date()
            out["converted_to_ad"] = {"bs_date": bs, "ad_date": ad_date.isoformat(),
                                      "weekday": ad_date.strftime("%A")}
        except ImportError:
            pass
        except Exception:
            raise ToolError("convert_bs_to_ad must be a real BS date like 2083-07-25")
    return out


def notify_phone(args: dict, ctx: ToolContext) -> dict:
    message = (args.get("message") or "").strip()
    if not message:
        raise ToolError("message is required")
    if not ctx.notify:
        return {"ok": False, "error": "the phone bridge is not running (set TELEGRAM_BOT_TOKEN "
                                      "and start run_daemon.py)"}
    ctx.notify(message[:3500])
    return {"ok": True, "message": "Sent to the phone."}


def recent_actions(args: dict, ctx: ToolContext) -> dict:
    limit = max(1, min(int(args.get("limit") or 10), 40))
    rows = []
    for rec in _need_memory(ctx).recent_audit(limit * 2):
        if rec.get("event") != "tool":
            continue
        rows.append({"when": rec.get("when"), "tool": rec.get("tool"), "from": rec.get("source"),
                     "decision": rec.get("decision"), "ok": rec.get("ok"),
                     "arguments": str(rec.get("arguments"))[:120]})
        if len(rows) >= limit:
            break
    return {"ok": True, "actions": rows}


def build() -> list[Tool]:
    return [
        Tool(name="remember",
             description=("Save a durable fact for future conversations. branch 'user' for facts "
                          "about the user, 'directives' for how they want you to behave, 'world' "
                          "for other knowledge. Write the fact in English."),
             parameters={"type": "object", "properties": {
                 "fact": {"type": "string"},
                 "branch": {"type": "string", "enum": ["user", "directives", "world"]}},
                 "required": ["fact"]},
             handler=remember,
             keywords=("remember", "note that", "don't forget", "from now on", "always", "सम्झ", "samjha", "yaad rakha")),
        Tool(name="recall_memory",
             description=("Search what you know about the user and past conversations. Use for "
                          "'what did I tell you about X', 'do you remember', or when a request "
                          "depends on something said earlier."),
             parameters={"type": "object", "properties": {"query": {"type": "string"}}},
             handler=recall_memory,
             keywords=("remember", "recall", "what did i", "last time", "earlier", "yesterday",
                       "know about me", "थाहा छ", "hijo", "pahila")),
        Tool(name="forget_memory", description="Delete saved facts matching a description.",
             parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
             handler=forget_memory, risk=Risk.ACT, keywords=("forget", "delete memory", "बिर्स", "birsa")),
        Tool(name="get_datetime",
             description=("Current date and time locally and in Nepal, today's Bikram Sambat (BS) "
                          "date, and BS/AD date conversion. Always use this for Nepali dates."),
             parameters={"type": "object", "properties": {
                 "convert_ad_to_bs": {"type": "string", "description": "AD date YYYY-MM-DD"},
                 "convert_bs_to_ad": {"type": "string", "description": "BS date YYYY-MM-DD"}}},
             handler=get_datetime,
             keywords=("time", "date", "today", "day", "nepal", "bs", "bikram sambat", "gate", "tithi",
                       "समय", "मिति", "गते", "आज", "कति बज्यो", "kati bajyo", "aaja", "miti", "bar"),
             always=True),
        Tool(name="notify_phone", description="Send a message to the user's phone.",
             parameters={"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]},
             handler=notify_phone, keywords=("phone", "text me", "message me", "notify", "send me", "पठाऊ", "pathau")),
        Tool(name="recent_actions",
             description="The audit log: which actions were run recently, from where, and whether they worked.",
             parameters={"type": "object", "properties": {"limit": {"type": "integer"}}},
             handler=recent_actions, keywords=("what did you do", "history", "log", "audit", "actions")),
    ]
