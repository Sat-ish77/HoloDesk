"""File tools, confined to the user's home folder (plus HOLODESK_FILE_ROOTS)."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from ..policy import Risk
from .registry import Tool, ToolContext, ToolError

# Never read or write these, even inside the home folder: reading them would
# ship credentials to the model provider.
_SENSITIVE_PARTS = {".ssh", ".aws", ".gnupg", ".azure", ".kube", ".docker"}
_SENSITIVE_NAMES = {".env", "id_rsa", "id_ed25519", "login data", "cookies", "key4.db",
                    "logins.json", "wallet.dat", ".netrc", "credentials", ".git-credentials"}
_SKIP_DIRS = {"appdata", "node_modules", ".git", "__pycache__", ".venv", "venv",
              "$recycle.bin", ".cache", "site-packages", "library"}


def _roots(ctx: ToolContext | None) -> list[Path]:
    roots = [Path.home().resolve()]
    extra = (getattr(getattr(ctx, "cfg", None), "extra_file_roots", "")
             or os.getenv("HOLODESK_FILE_ROOTS") or "")
    for part in extra.split(os.pathsep):
        if part.strip():
            try:
                roots.append(Path(part.strip()).expanduser().resolve())
            except OSError:
                continue
    return roots


def resolve_path(raw: str, ctx: ToolContext | None = None) -> Path:
    raw = (raw or "").strip().strip('"')
    if not raw:
        raise ToolError("path is required")
    p = Path(os.path.expandvars(os.path.expanduser(raw)))
    if not p.is_absolute():
        p = Path.home() / p
    p = p.resolve()
    if not any(p == r or r in p.parents for r in _roots(ctx)):
        raise ToolError(f"'{p}' is outside the folders I am allowed to touch")
    lowered = [part.lower() for part in p.parts]
    if any(part in _SENSITIVE_PARTS for part in lowered) or p.name.lower() in _SENSITIVE_NAMES:
        raise ToolError("that file holds credentials; I don't read or change it")
    return p


def list_directory(args: dict, ctx: ToolContext) -> dict:
    p = resolve_path(args.get("path") or "~", ctx)
    if not p.is_dir():
        raise ToolError(f"'{p}' is not a folder")
    limit = max(1, min(int(args.get("limit") or 60), 200))
    entries = []
    for child in sorted(p.iterdir(), key=lambda c: (c.is_file(), c.name.lower())):
        try:
            st = child.stat()
            entries.append({"name": child.name + ("/" if child.is_dir() else ""),
                            "size_kb": None if child.is_dir() else round(st.st_size / 1024, 1),
                            "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))})
        except OSError:
            continue
    return {"ok": True, "path": str(p), "total": len(entries), "entries": entries[:limit]}


def read_text_file(args: dict, ctx: ToolContext) -> dict:
    p = resolve_path(args.get("path"), ctx)
    if not p.is_file():
        raise ToolError(f"'{p}' is not a file")
    if p.stat().st_size > 2_000_000:
        raise ToolError("file is larger than 2 MB; too big to read into the conversation")
    data = p.read_bytes()
    if b"\x00" in data[:4000]:
        raise ToolError("this looks like a binary file, not text")
    text = data.decode("utf-8", errors="replace")
    limit = max(200, min(int(args.get("max_chars") or 6000), 20000))
    return {"ok": True, "path": str(p), "chars": len(text), "truncated": len(text) > limit,
            "content": text[:limit]}


def _write_risk(args: dict) -> Risk:
    try:
        p = resolve_path(args.get("path"))
    except ToolError:
        return Risk.ACT      # the handler will raise the real error
    if p.exists() and not args.get("append"):
        return Risk.DANGER   # overwriting loses the old content
    return Risk.ACT


def write_text_file(args: dict, ctx: ToolContext) -> dict:
    p = resolve_path(args.get("path"), ctx)
    content = args.get("content")
    if not isinstance(content, str):
        raise ToolError("content must be text")
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a" if args.get("append") else "w", encoding="utf-8") as f:
        f.write(content)
    return {"ok": True, "path": str(p), "message": f"Wrote {len(content)} characters to {p.name}."}


def find_files(args: dict, ctx: ToolContext) -> dict:
    query = (args.get("query") or "").lower().strip()
    if not query:
        raise ToolError("query is required")
    root = resolve_path(args.get("folder") or "~", ctx)
    limit = max(1, min(int(args.get("limit") or 30), 100))
    words = query.split()
    deadline = time.time() + 8.0
    found, timed_out = [], False
    for dirpath, dirnames, filenames in os.walk(root):
        if time.time() > deadline:
            timed_out = True
            break
        dirnames[:] = [d for d in dirnames if d.lower() not in _SKIP_DIRS and not d.startswith(".")]
        for name in filenames + dirnames:
            low = name.lower()
            if all(w in low for w in words):
                full = Path(dirpath) / name
                try:
                    mtime = full.stat().st_mtime
                except OSError:
                    continue
                found.append((mtime, str(full)))
    found.sort(reverse=True)
    return {"ok": True, "matches": [p for _, p in found[:limit]], "total": len(found),
            **({"note": "search stopped after 8 seconds; narrow the folder for more"} if timed_out else {})}


def _move_risk(args: dict) -> Risk:
    try:
        dst = resolve_path(args.get("destination"))
    except ToolError:
        return Risk.ACT
    return Risk.DANGER if dst.is_file() else Risk.ACT


def move_path(args: dict, ctx: ToolContext) -> dict:
    src = resolve_path(args.get("source"), ctx)
    dst = resolve_path(args.get("destination"), ctx)
    if not src.exists():
        raise ToolError(f"'{src}' does not exist")
    if dst.is_dir():
        dst = dst / src.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return {"ok": True, "message": f"Moved to {dst}."}


def _trash_available() -> bool:
    try:
        import send2trash  # noqa: F401
        return True
    except ImportError:
        return False


def delete_path(args: dict, ctx: ToolContext) -> dict:
    p = resolve_path(args.get("path"), ctx)
    if not p.exists():
        raise ToolError(f"'{p}' does not exist")
    if p in _roots(ctx) or p.parent == p:
        raise ToolError("I won't delete a whole root folder")
    if _trash_available():
        import send2trash
        send2trash.send2trash(str(p))
        return {"ok": True, "message": f"Moved {p.name} to the Recycle Bin."}
    if p.is_dir():
        shutil.rmtree(p)
    else:
        p.unlink()
    return {"ok": True, "message": f"Permanently deleted {p.name}."}


def open_path(args: dict, ctx: ToolContext) -> dict:
    p = resolve_path(args.get("path"), ctx)
    if not p.exists():
        raise ToolError(f"'{p}' does not exist")
    if hasattr(os, "startfile"):
        os.startfile(str(p))  # noqa: S606 - opening the user's own file on request
        return {"ok": True, "message": f"Opened {p.name}."}
    raise ToolError("opening files only works on Windows")


def build() -> list[Tool]:
    path_param = {"type": "string", "description": "Absolute path, or relative to the home folder. '~/Downloads' works."}
    return [
        Tool(name="list_directory",
             description="List the files and folders inside a folder (default: home folder).",
             parameters={"type": "object", "properties": {"path": path_param, "limit": {"type": "integer"}}},
             handler=list_directory,
             keywords=("folder", "files", "downloads", "documents", "desktop", "what's in", "फाइल", "फोल्डर")),
        Tool(name="read_text_file",
             description="Read a text file (code, notes, logs, csv) and return its content.",
             parameters={"type": "object", "properties": {"path": path_param, "max_chars": {"type": "integer"}},
                         "required": ["path"]},
             handler=read_text_file,
             keywords=("read", "open file", "show file", "contents", "log", "पढ")),
        Tool(name="write_text_file",
             description="Create a text file, or append to / overwrite an existing one.",
             parameters={"type": "object", "properties": {
                 "path": path_param, "content": {"type": "string"},
                 "append": {"type": "boolean", "description": "Add to the end instead of replacing."}},
                 "required": ["path", "content"]},
             handler=write_text_file, risk=_write_risk,
             summarize=lambda a: f"overwrite the file {a.get('path')}",
             keywords=("write", "save", "create file", "note", "append", "लेख")),
        Tool(name="find_files",
             description="Find files or folders by name anywhere under a folder (default: home).",
             parameters={"type": "object", "properties": {
                 "query": {"type": "string", "description": "Words that must all appear in the name."},
                 "folder": path_param, "limit": {"type": "integer"}}, "required": ["query"]},
             handler=find_files,
             keywords=("find", "search file", "where is", "locate", "खोज", "kaha cha")),
        Tool(name="move_path",
             description="Move or rename a file or folder.",
             parameters={"type": "object", "properties": {"source": path_param, "destination": path_param},
                         "required": ["source", "destination"]},
             handler=move_path, risk=_move_risk,
             summarize=lambda a: f"move {a.get('source')} over the existing file {a.get('destination')}",
             keywords=("move", "rename", "organize", "सार")),
        Tool(name="delete_path",
             description="Delete a file or folder (goes to the Recycle Bin when possible).",
             parameters={"type": "object", "properties": {"path": path_param}, "required": ["path"]},
             handler=delete_path, risk=Risk.DANGER,
             summarize=lambda a: (f"delete {a.get('path')} "
                                  + ("(to the Recycle Bin)" if _trash_available() else "PERMANENTLY")),
             keywords=("delete", "remove", "trash", "erase", "मेट", "hatau", "delete gara")),
        Tool(name="open_path",
             description="Open a file or folder with its default app, as if double-clicked.",
             parameters={"type": "object", "properties": {"path": path_param}, "required": ["path"]},
             handler=open_path, risk=Risk.ACT,
             keywords=("open file", "open folder", "show me", "खोल")),
    ]
