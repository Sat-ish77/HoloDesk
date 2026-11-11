"""
Background monitors: the laptop tells the phone what is going on without
being asked.

Each alert fires once when a problem starts and re-arms when it clears, so a
low battery is one message, not one per minute.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)


def read_sensors() -> dict:
    """Current readings. Missing sensors are simply absent from the dict."""
    import os
    from pathlib import Path

    import psutil
    readings: dict = {"ram_percent": psutil.virtual_memory().percent}
    try:
        drive = os.path.splitdrive(str(Path.home()))[0]
        readings["disk_free_gb"] = psutil.disk_usage((drive + os.sep) if drive else "/").free / 1e9
    except Exception:
        pass
    try:
        battery = psutil.sensors_battery()
        if battery is not None:
            readings["battery_percent"] = battery.percent
            readings["plugged_in"] = bool(battery.power_plugged)
    except Exception:
        pass
    return readings


class Monitors(threading.Thread):
    def __init__(self, notify: Callable[[str], None], engine=None, interval_sec: int = 60,
                 battery_low: int = 20, disk_low_gb: float = 5.0, ram_high: float = 95.0,
                 sensors: Callable[[], dict] = read_sensors):
        super().__init__(daemon=True, name="holodesk-monitors")
        self.notify = notify
        self.engine = engine
        self.interval_sec = interval_sec
        self.battery_low = battery_low
        self.disk_low_gb = disk_low_gb
        self.ram_high = ram_high
        self.sensors = sensors
        self.running = True
        self._active: set[str] = set()     # alerts currently raised
        self._ram_strikes = 0
        self._last_plugged: bool | None = None
        self._last_diary = time.time()

    def _raise(self, key: str, condition: bool, message: str) -> str | None:
        if condition and key not in self._active:
            self._active.add(key)
            return message
        if not condition:
            self._active.discard(key)
        return None

    def check_once(self, readings: dict | None = None) -> list[str]:
        """Evaluate one set of readings. Returns the alerts to send."""
        r = readings if readings is not None else self.sensors()
        alerts: list[str] = []

        pct, plugged = r.get("battery_percent"), r.get("plugged_in")
        if pct is not None and plugged is not None:
            msg = self._raise("battery", pct <= self.battery_low and not plugged,
                              f"🔋 Battery at {pct:.0f}% and not charging. Plug the laptop in "
                              "or I'll go offline soon.")
            if msg:
                alerts.append(msg)
            if self._last_plugged is True and plugged is False:
                alerts.append(f"🔌 The laptop was unplugged (battery {pct:.0f}%).")
            self._last_plugged = plugged

        free = r.get("disk_free_gb")
        if free is not None:
            msg = self._raise("disk", free < self.disk_low_gb,
                              f"💾 Only {free:.1f} GB of disk space left.")
            if msg:
                alerts.append(msg)

        ram = r.get("ram_percent")
        if ram is not None:
            # Three checks in a row: a brief spike is not worth a message.
            self._ram_strikes = self._ram_strikes + 1 if ram >= self.ram_high else 0
            msg = self._raise("ram", self._ram_strikes >= 3,
                              f"🧠 Memory has been above {self.ram_high:.0f}% for a few minutes "
                              f"(now {ram:.0f}%).")
            if msg:
                alerts.append(msg)
        return alerts

    def run(self) -> None:
        while self.running:
            try:
                for alert in self.check_once():
                    self.notify(alert)
                # Housekeeping: turn finished conversations into diary entries.
                if self.engine is not None and time.time() - self._last_diary > 1800:
                    self._last_diary = time.time()
                    self.engine.write_diary()
            except Exception:
                logger.exception("monitor pass failed")
            time.sleep(self.interval_sec)

    def stop(self) -> None:
        self.running = False
