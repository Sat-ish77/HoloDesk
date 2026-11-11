"""System tools: shell, status, processes, power, volume."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import threading
import time
from pathlib import Path

from ..policy import Risk, classify_shell
from .registry import Tool, ToolContext, ToolError

IS_WINDOWS = platform.system() == "Windows"


def _psutil():
    try:
        import psutil
        return psutil
    except ImportError:
        raise ToolError("psutil is not installed (pip install psutil)")


# ---------------------------------------------------------------- shell
def _shell_exe() -> list[str]:
    if IS_WINDOWS:
        return ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command"]
    pwsh = shutil.which("pwsh")
    if pwsh:
        return [pwsh, "-NoProfile", "-NonInteractive", "-Command"]
    raise ToolError("PowerShell is not available on this machine")


def run_powershell(args: dict, ctx: ToolContext) -> dict:
    command = (args.get("command") or "").strip()
    if not command:
        raise ToolError("command is required")
    if classify_shell(command) == Risk.BLOCKED:   # defence in depth
        raise ToolError("this command is blocked by the safety policy")
    timeout = max(1, min(int(args.get("timeout_sec") or 30), 300))
    # UTF-8 output so Nepali file names survive the trip.
    wrapped = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + command if IS_WINDOWS else command
    try:
        proc = subprocess.run(_shell_exe() + [wrapped], capture_output=True, timeout=timeout,
                              cwd=str(Path.home()), text=True, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timed out after {timeout}s (the command may still be running)"}
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    return {"ok": proc.returncode == 0, "exit_code": proc.returncode,
            "output": out[-6000:], **({"stderr": err[-1500:]} if err else {})}


# ---------------------------------------------------------------- status
def _foreground_title() -> str:
    try:
        import win32gui
        return win32gui.GetWindowText(win32gui.GetForegroundWindow()) or ""
    except Exception:
        return ""


def system_status(args: dict, ctx: ToolContext) -> dict:
    psutil = _psutil()
    vm = psutil.virtual_memory()
    home_drive = os.path.splitdrive(str(Path.home()))[0] + os.sep if IS_WINDOWS else "/"
    disk = psutil.disk_usage(home_drive)
    status = {
        "ok": True,
        "cpu_percent": psutil.cpu_percent(interval=0.4),
        "ram_percent": vm.percent,
        "ram_free_gb": round(vm.available / 1e9, 1),
        "disk_free_gb": round(disk.free / 1e9, 1),
        "disk_percent_used": disk.percent,
        "uptime_hours": round((time.time() - psutil.boot_time()) / 3600, 1),
    }
    try:
        battery = psutil.sensors_battery()
        if battery:
            status["battery_percent"] = round(battery.percent)
            status["plugged_in"] = bool(battery.power_plugged)
    except Exception:
        pass
    title = _foreground_title()
    if title:
        status["active_window"] = title[:120]
    procs = []
    for p in psutil.process_iter(["name", "memory_info"]):
        try:
            procs.append((p.info["memory_info"].rss, p.info["name"]))
        except Exception:
            continue
    procs.sort(reverse=True)
    status["top_memory"] = [f"{name} {rss / 1e6:.0f}MB" for rss, name in procs[:5]]
    return status


def list_processes(args: dict, ctx: ToolContext) -> dict:
    psutil = _psutil()
    needle = (args.get("filter") or "").lower().strip()
    limit = max(1, min(int(args.get("limit") or 25), 80))
    rows: dict[str, dict] = {}
    for p in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            name = p.info["name"] or "?"
            if needle and needle not in name.lower():
                continue
            row = rows.setdefault(name, {"name": name, "count": 0, "memory_mb": 0.0, "pids": []})
            row["count"] += 1
            row["memory_mb"] += p.info["memory_info"].rss / 1e6
            if len(row["pids"]) < 5:
                row["pids"].append(p.info["pid"])
        except Exception:
            continue
    out = sorted(rows.values(), key=lambda r: -r["memory_mb"])[:limit]
    for r in out:
        r["memory_mb"] = round(r["memory_mb"])
    return {"ok": True, "processes": out}


def _match_processes(target: str):
    psutil = _psutil()
    target = (target or "").strip()
    if not target:
        raise ToolError("process name or pid is required")
    if target.isdigit():
        try:
            return [psutil.Process(int(target))]
        except psutil.Error:
            raise ToolError(f"no process with pid {target}")
    want = target.lower().removesuffix(".exe")
    matches = []
    for p in psutil.process_iter(["name"]):
        name = (p.info.get("name") or "").lower().removesuffix(".exe")
        if name == want or (len(want) >= 3 and want in name):
            matches.append(p)
    return matches


def kill_process(args: dict, ctx: ToolContext) -> dict:
    procs = _match_processes(str(args.get("target") or ""))
    if not procs:
        return {"ok": False, "error": "no matching running process"}
    killed = 0
    for p in procs:
        try:
            p.kill()
            killed += 1
        except Exception:
            continue
    return {"ok": killed > 0, "killed": killed}


def watch_process(args: dict, ctx: ToolContext) -> dict:
    target = str(args.get("target") or "")
    if not _match_processes(target):
        return {"ok": False, "error": f"'{target}' is not running right now"}
    if not ctx.notify:
        return {"ok": False, "error": "phone notifications are not set up (no Telegram bridge running)"}
    notify = ctx.notify

    def _watch():
        deadline = time.time() + 12 * 3600
        while time.time() < deadline:
            time.sleep(5)
            try:
                if not _match_processes(target):
                    notify(f"'{target}' has finished (the process exited).")
                    return
            except Exception:
                return
    threading.Thread(target=_watch, daemon=True, name=f"watch-{target}").start()
    return {"ok": True, "message": f"I'll message your phone when '{target}' exits."}


# ---------------------------------------------------------------- power
_POWER_CMDS = {
    "shutdown": ["shutdown", "/s", "/t", "30"],
    "restart": ["shutdown", "/r", "/t", "30"],
    "cancel_shutdown": ["shutdown", "/a"],
    "sign_out": ["shutdown", "/l"],
    "sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
}


def _power_risk(args: dict) -> Risk:
    action = (args.get("action") or "").lower()
    if action == "cancel_shutdown":
        return Risk.SAFE
    if action == "lock":
        return Risk.ACT
    return Risk.DANGER


def power(args: dict, ctx: ToolContext) -> dict:
    action = (args.get("action") or "").lower()
    if not IS_WINDOWS:
        raise ToolError("power control only works on Windows")
    if action == "lock":
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return {"ok": True, "message": "Screen locked."}
    cmd = _POWER_CMDS.get(action)
    if not cmd:
        raise ToolError(f"unknown power action '{action}'")
    subprocess.Popen(cmd)
    msg = {"shutdown": "Shutting down in 30 seconds. Say 'cancel shutdown' to stop it.",
           "restart": "Restarting in 30 seconds. Say 'cancel shutdown' to stop it.",
           "cancel_shutdown": "Shutdown cancelled.", "sign_out": "Signing out.",
           "sleep": "Going to sleep. I can't hear the phone again until the laptop wakes."}[action]
    return {"ok": True, "message": msg}


def set_volume(args: dict, ctx: ToolContext) -> dict:
    action = (args.get("action") or "").lower()
    key = {"up": "volumeup", "down": "volumedown", "mute": "volumemute"}.get(action)
    if not key:
        raise ToolError("action must be up, down or mute")
    import pyautogui
    steps = 1 if action == "mute" else max(1, min(int(args.get("steps") or 5), 50))
    for _ in range(steps):
        pyautogui.press(key)
    return {"ok": True, "message": f"Volume {action}."}


def build() -> list[Tool]:
    return [
        Tool(
            name="run_powershell",
            description=("Run a PowerShell command on the laptop and return its output. The "
                         "general-purpose tool for anything without a dedicated tool: settings, "
                         "installs, network, services, scripts. Read-only commands run "
                         "immediately; anything that changes the system asks the user first."),
            parameters={"type": "object", "properties": {
                "command": {"type": "string", "description": "The PowerShell command."},
                "timeout_sec": {"type": "integer", "description": "Default 30, max 300."}},
                "required": ["command"]},
            handler=run_powershell,
            risk=lambda a: classify_shell(a.get("command") or ""),
            summarize=lambda a: f"run this command: {(a.get('command') or '')[:300]}",
            keywords=("command", "terminal", "shell", "cmd", "script", "install", "wifi",
                      "network", "ip", "service", "setting", "settings", "चलाऊ", "command chalau"),
            always=True,
        ),
        Tool(
            name="system_status",
            description=("What is the laptop doing right now: CPU, RAM, disk, battery, uptime, "
                         "active window, heaviest processes. Use for 'how is my laptop', "
                         "'what's going on', battery or storage questions."),
            handler=system_status,
            keywords=("status", "battery", "cpu", "ram", "memory", "disk", "storage", "slow",
                      "health", "charge", "ब्याट्री", "अवस्था", "के भइरहेको", "laptop kasto cha"),
            always=True,
        ),
        Tool(
            name="list_processes",
            description="List running programs with memory use, optionally filtered by name.",
            parameters={"type": "object", "properties": {
                "filter": {"type": "string"}, "limit": {"type": "integer"}}},
            handler=list_processes,
            keywords=("running", "processes", "programs", "apps open", "task manager"),
        ),
        Tool(
            name="kill_process",
            description=("Force-kill a process by name or pid. Unsaved work in it is lost. For a "
                         "normal close use close_app instead."),
            parameters={"type": "object", "properties": {
                "target": {"type": "string", "description": "Process name or pid."}},
                "required": ["target"]},
            handler=kill_process, risk=Risk.DANGER,
            summarize=lambda a: f"force-kill '{a.get('target')}' (unsaved work will be lost)",
            keywords=("kill", "force quit", "end task", "frozen", "hung", "not responding"),
        ),
        Tool(
            name="watch_process",
            description=("Message the user's phone when a running program exits. Use for 'tell "
                         "me when the download / build / training finishes'."),
            parameters={"type": "object", "properties": {
                "target": {"type": "string", "description": "Process name or pid."}},
                "required": ["target"]},
            handler=watch_process,
            keywords=("tell me when", "notify", "finishes", "done", "let me know", "सकिएपछि", "bhayepachi"),
        ),
        Tool(
            name="power",
            description="Lock, sleep, shut down, restart, sign out, or cancel a pending shutdown.",
            parameters={"type": "object", "properties": {"action": {
                "type": "string",
                "enum": ["lock", "sleep", "shutdown", "restart", "sign_out", "cancel_shutdown"]}},
                "required": ["action"]},
            handler=power, risk=_power_risk,
            summarize=lambda a: f"{(a.get('action') or '').replace('_', ' ')} the laptop",
            keywords=("lock", "sleep", "shutdown", "shut down", "restart", "reboot", "power off",
                      "sign out", "log off", "बन्द", "banda gara", "restart gara"),
        ),
        Tool(
            name="set_volume",
            description="Turn the system volume up or down, or toggle mute.",
            parameters={"type": "object", "properties": {
                "action": {"type": "string", "enum": ["up", "down", "mute"]},
                "steps": {"type": "integer", "description": "Each step is 2%. Default 5."}},
                "required": ["action"]},
            handler=set_volume, risk=Risk.ACT,
            keywords=("volume", "louder", "quieter", "mute", "unmute", "sound", "आवाज", "awaj"),
        ),
    ]
