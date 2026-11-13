import importlib
import sys
from pathlib import Path

log_path = Path("artifacts/startup_import_trace.txt")
log_path.parent.mkdir(parents=True, exist_ok=True)


def log(message: str) -> None:
    print(message, flush=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(message + "\n")
        f.flush()

steps = [
    "pygame",
    "dotenv",
    "groq",
    "speech_recognition",
    "pyttsx3",
    "threading",
    "faster_whisper",
    "tempfile",
    "wave",
    "audioop",
    "re",
    "cv2",
    "mediapipe",
    "pyautogui",
]

for name in steps:
    log(f"IMPORT_START {name}")
    importlib.import_module(name)
    log(f"IMPORT_OK {name}")

log("ALL_IMPORTS_OK")
sys.exit(0)
