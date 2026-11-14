"""
Phone bridge over a Telegram bot.

Why Telegram: the laptop only makes OUTBOUND requests (long polling), so
nothing is exposed to the internet. No port forwarding, no public IP, and it
works from any network the phone is on.

    phone text / voice note  ->  ReplyEngine  ->  reply (+ screenshots)
    laptop events            ->  notify()     ->  phone

Security model:
  * Only user IDs in TELEGRAM_ALLOWED_USER_IDS are obeyed. Everyone else is
    ignored. With an empty allowlist the bot runs nothing at all and just
    tells you your ID so you can add it.
  * Only private chats. A bot added to a group obeys nobody.
  * Messages older than MAX_AGE_SEC are dropped, so commands queued while the
    laptop was off do not fire hours later.
  * /stop works even while a long request is running.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_AGE_SEC = 120
_CHUNK = 3900

HELP = (
    "HoloDesk is listening. Just tell me what to do, in English or Nepali, by text or voice note.\n\n"
    "/status      laptop health right now\n"
    "/screenshot  see the screen\n"
    "/log         last actions I ran\n"
    "/stop        kill switch: refuse every action\n"
    "/resume      turn actions back on\n"
    "/whoami      your Telegram user ID\n\n"
    "Risky actions (delete, shutdown, unknown commands) wait for your 'yes'."
)


class TelegramSender:
    """Send-only half. Safe to use from several processes at once (unlike
    polling, which Telegram allows from one process only)."""

    def __init__(self, token: str, allowed_ids: set[int], session=None):
        self.token = token
        self.allowed_ids = set(allowed_ids)
        self._session = session
        self.api = f"https://api.telegram.org/bot{token}"

    def _http(self):
        if self._session is None:
            import requests
            self._session = requests.Session()
        return self._session

    def call(self, method: str, http_timeout: int = 20, **params):
        """`params` are Telegram's own parameters (which include one named
        `timeout` for long polling, hence the different name here)."""
        resp = self._http().post(f"{self.api}/{method}", json=params, timeout=http_timeout)
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram {method} failed: {data.get('description')}")
        return data.get("result")

    def send_message(self, chat_id: int, text: str) -> None:
        text = (text or "").strip() or "(empty reply)"
        for i in range(0, len(text), _CHUNK):
            try:
                self.call("sendMessage", chat_id=chat_id, text=text[i:i + _CHUNK])
            except Exception as e:
                logger.warning("sendMessage failed: %s", e)
                return

    def send_photo(self, chat_id: int, path: str, caption: str = "") -> None:
        try:
            with open(path, "rb") as f:
                resp = self._http().post(
                    f"{self.api}/sendPhoto", data={"chat_id": chat_id, "caption": caption[:900]},
                    files={"photo": (Path(path).name, f)}, timeout=60)
            if not resp.json().get("ok"):
                logger.warning("sendPhoto failed: %s", resp.text[:200])
        except Exception as e:
            logger.warning("sendPhoto failed: %s", e)

    def notify(self, text: str) -> None:
        """Push a message to every allowed user."""
        for user_id in self.allowed_ids:
            self.send_message(user_id, text)


class TelegramBridge(TelegramSender):
    def __init__(self, engine, token: str, allowed_ids: set[int], stt=None, session=None):
        super().__init__(token, allowed_ids, session=session)
        self.engine = engine
        self.stt = stt
        self.running = False
        self._offset = 0
        self._jobs: queue.Queue = queue.Queue(maxsize=20)
        self._warned: set[int] = set()
        # Let tools and monitors reach the phone.
        engine.notify = self.notify

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        self.running = True
        threading.Thread(target=self._worker, daemon=True, name="telegram-worker").start()
        threading.Thread(target=self.poll_forever, daemon=True, name="telegram-poll").start()

    def stop(self) -> None:
        self.running = False

    def poll_forever(self) -> None:
        backoff = 2
        while self.running:
            try:
                updates = self.call("getUpdates", http_timeout=65, offset=self._offset,
                                    allowed_updates=["message"], timeout=50)
                backoff = 2
            except Exception as e:
                # 409 = another process is polling this bot. Either way: wait, retry.
                logger.warning("Telegram polling error (retry in %ss): %s", backoff, e)
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue
            for update in updates or []:
                self._offset = max(self._offset, int(update.get("update_id", 0)) + 1)
                try:
                    self.handle_update(update)
                except Exception:
                    logger.exception("failed to handle a Telegram update")

    # ------------------------------------------------------------------
    # Incoming
    # ------------------------------------------------------------------
    def handle_update(self, update: dict) -> None:
        msg = update.get("message") or {}
        chat = msg.get("chat") or {}
        user = msg.get("from") or {}
        chat_id, user_id = chat.get("id"), user.get("id")
        if chat_id is None or user_id is None or chat.get("type") != "private":
            return
        if time.time() - float(msg.get("date") or 0) > MAX_AGE_SEC:
            logger.info("dropping stale Telegram message from %s", user_id)
            return

        if user_id not in self.allowed_ids:
            # Tell a stranger nothing useful, and only once. The owner needs
            # their ID during setup, which is all this reveals.
            if user_id not in self._warned:
                self._warned.add(user_id)
                self.send_message(chat_id, (
                    f"This bot is private. Your Telegram user ID is {user_id}. "
                    "If this is your HoloDesk, add it to TELEGRAM_ALLOWED_USER_IDS in .env "
                    "and restart the daemon."))
            logger.warning("ignored Telegram message from unauthorised user %s", user_id)
            return

        text = (msg.get("text") or "").strip()
        command = text.split()[0].split("@")[0].lower() if text.startswith("/") else ""

        # Control commands run right here on the polling thread, so they work
        # even while the worker is busy with a long request.
        if command in ("/start", "/help"):
            return self.send_message(chat_id, HELP)
        if command == "/whoami":
            return self.send_message(chat_id, f"Your Telegram user ID is {user_id}.")
        if command == "/stop":
            self.engine.halt(f"telegram:{user_id}")
            return self.send_message(chat_id, "⛔ Halted. I will refuse every action until /resume.")
        if command == "/resume":
            self.engine.resume(f"telegram:{user_id}")
            return self.send_message(chat_id, "✅ Resumed.")

        if text and not command and self.engine.busy:
            # A task is running: these words are for it ("stop", "no, the other one"),
            # read between its steps. Queued, they would run as a new task afterwards.
            self.engine.steer(text)
            return self.send_message(chat_id, "Passed to the task that is running.")

        voice = msg.get("voice") or msg.get("audio")
        if not text and not voice:
            return self.send_message(chat_id, "I can read text and voice notes. Send one of those.")
        try:
            self._jobs.put_nowait({"chat_id": chat_id, "text": text, "command": command,
                                   "voice": voice})
        except queue.Full:
            self.send_message(chat_id, "I'm backed up with requests. Try again in a moment.")

    def _worker(self) -> None:
        while self.running:
            try:
                job = self._jobs.get(timeout=1)
            except queue.Empty:
                continue
            try:
                self.process(job)
            except Exception as e:
                logger.exception("Telegram job failed")
                self.send_message(job["chat_id"], f"Something broke while handling that: {e}")

    def process(self, job: dict) -> None:
        chat_id, text, command = job["chat_id"], job["text"], job["command"]
        try:
            self.call("sendChatAction", chat_id=chat_id, action="typing")
        except Exception:
            pass

        if job.get("voice"):
            text = self._transcribe_voice(job["voice"])
            if not text:
                return self.send_message(chat_id, "I couldn't make out that voice note. Try again or type it.")
            self.send_message(chat_id, f"🎙 {text}")

        if command == "/status":
            text = "Give me a short laptop status report: CPU, RAM, disk, battery, active window."
        elif command == "/screenshot":
            text = "Take a screenshot and send it to me."
        elif command == "/log":
            text = "Show the last 8 actions from the audit log."
        elif command:
            return self.send_message(chat_id, "Unknown command. /help lists what I understand.")

        reply = self.engine.reply(text, source="telegram")
        self.send_message(chat_id, reply.text)
        for photo in reply.photos:
            self.send_photo(chat_id, photo)

    def _transcribe_voice(self, voice: dict) -> str:
        if self.stt is None or not getattr(self.stt, "ready", False):
            return ""
        try:
            info = self.call("getFile", file_id=voice["file_id"])
            if int(info.get("file_size") or 0) > 20_000_000:
                return ""
            url = f"https://api.telegram.org/file/bot{self.token}/{info['file_path']}"
            audio = self._http().get(url, timeout=60).content
        except Exception as e:
            logger.warning("voice download failed: %s", e)
            return ""
        # Telegram voice notes are Opus in an Ogg container.
        return self.stt.transcribe(audio, filename="voice.ogg")["text"]
