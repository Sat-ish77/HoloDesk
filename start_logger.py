"""
HoloDesk Memory Logger — Run this NOW to start collecting habit data.

This is a standalone script that runs the background session/app logger
WITHOUT launching the full Pygame overlay. Run it in the background
while you work normally. Every 60 seconds it silently records which
app is in focus.

After 14 days of data, the morning briefing becomes genuinely personalized.
Start collecting today — every day counts.

Usage:
    python start_logger.py

Press Ctrl+C to stop (session is saved cleanly on exit).
"""

import sys
import time
import signal
import logging
from pathlib import Path

# Allow imports from project root regardless of working directory
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/holodesk.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("start_logger")


def main():
    from agents.memory_agent import memory_agent
    from storage.db import db

    print("=" * 55)
    print("  HoloDesk Memory Logger")
    print("  Logging active window every 60 seconds.")
    print("  Data stored in: data/holodesk.db")
    print("  Press Ctrl+C to stop cleanly.")
    print("=" * 55)

    # Start a session
    session_id = memory_agent.start_session(user_id=1)
    print(f"\n[OK] Session #{session_id} started at {__import__('datetime').datetime.now().strftime('%H:%M:%S')}")

    # Start the background 60-second logger
    memory_agent.start_background_logging()

    # Log first event immediately so we have something right away
    memory_agent.log_app_event()
    print("[OK] First window logged. Now running silently...")
    print("     (Check data/holodesk.db with DB Browser for SQLite to verify)\n")

    def _shutdown(sig, frame):
        print("\n\nCtrl+C received — shutting down cleanly...")
        memory_agent.stop_background_logging()
        memory_agent.end_session()

        # Print a quick summary
        days = memory_agent.get_days_active()
        habits = memory_agent.detect_habits()
        apps = memory_agent.get_todays_app_summary()

        print(f"\n--- Session Summary ---")
        print(f"Total days active:  {days}")
        print(f"Habits detected:    {len(habits)}")
        print(f"Apps used today:")
        for a in apps:
            print(f"  {a['app_name']:30s} ~{a['minutes_approx']} min")
        if habits:
            print("\nTop habits so far:")
            for h in habits[:3]:
                days_names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
                d = days_names[h['day_of_week']] if 0 <= h['day_of_week'] <= 6 else "?"
                print(f"  {h['app_name']:25s} {h['hour_of_day']:02d}:00 on {d} (x{h['frequency']})")
        print("\nData saved. Run again tomorrow to keep building your habit model.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)

    # Keep the main thread alive — the logger runs on a daemon thread
    while True:
        time.sleep(60)
        # Print a heartbeat every 5 minutes so you know it's still running
        from datetime import datetime
        now = datetime.now()
        if now.minute % 5 == 0:
            apps = memory_agent.get_todays_app_summary()
            top = apps[0]["app_name"] if apps else "nothing yet"
            print(f"  [{now.strftime('%H:%M')}] Still logging. Top app today: {top}")


if __name__ == "__main__":
    main()
