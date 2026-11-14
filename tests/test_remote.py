import time

from brain.llm import LLMResponse
from helpers import call, make_engine, say
from remote.telegram_bridge import TelegramBridge
from service.monitors import Monitors

OWNER, STRANGER = 111, 999


class FakeResponse:
    def __init__(self, payload=None, content=b""):
        self._payload, self.content, self.text = payload or {"ok": True, "result": {}}, content, "ok"

    def json(self):
        return self._payload


class FakeTelegram:
    """Stands in for requests.Session and records every outgoing call."""

    def __init__(self):
        self.sent = []

    def post(self, url, json=None, data=None, files=None, timeout=None):
        method = url.rsplit("/", 1)[-1]
        self.sent.append((method, json or data))
        if method == "getFile":
            return FakeResponse({"ok": True, "result": {"file_path": "voice/1.oga", "file_size": 100}})
        return FakeResponse()

    def get(self, url, timeout=None):
        return FakeResponse(content=b"OggS-fake-audio")

    def messages(self):
        return [p["text"] for m, p in self.sent if m == "sendMessage"]


class FakeSTT:
    ready = True

    def transcribe(self, audio, filename="x"):
        assert filename.endswith(".ogg") and audio.startswith(b"OggS")
        return {"text": "क्रोम खोल", "language": "ne"}


def update(text=None, user=OWNER, chat_type="private", age=0, voice=None):
    msg = {"chat": {"id": user, "type": chat_type}, "from": {"id": user}, "date": time.time() - age}
    if text is not None:
        msg["text"] = text
    if voice:
        msg["voice"] = voice
    return {"update_id": 1, "message": msg}


def make_bridge(script, stt=None):
    engine, backend, log = make_engine(script)
    http = FakeTelegram()
    bridge = TelegramBridge(engine, "TOKEN", {OWNER}, stt=stt, session=http)
    return bridge, http, log, engine


def drain(bridge):
    while not bridge._jobs.empty():
        bridge.process(bridge._jobs.get_nowait())


def test_owner_command_runs_through_the_engine():
    bridge, http, log, _ = make_bridge([call("open_app", name="chrome"), say("Chrome is open.")])
    bridge.handle_update(update("open chrome"))
    drain(bridge)
    assert log == [("open_app", {"name": "chrome"})]
    assert http.messages() == ["Chrome is open."]


def test_stranger_is_ignored_and_runs_nothing():
    bridge, http, log, _ = make_bridge([call("open_app", name="chrome")])
    bridge.handle_update(update("open chrome", user=STRANGER))
    bridge.handle_update(update("open chrome", user=STRANGER))
    drain(bridge)
    assert log == [] and bridge._jobs.empty()
    assert len(http.messages()) == 1 and "private" in http.messages()[0]   # told once, then silence


def test_empty_allowlist_obeys_nobody():
    bridge, http, log, _ = make_bridge([call("open_app", name="chrome")])
    bridge.allowed_ids = set()
    bridge.handle_update(update("open chrome"))
    drain(bridge)
    assert log == []


def test_group_chats_are_ignored():
    bridge, http, log, _ = make_bridge([call("open_app", name="chrome")])
    bridge.handle_update(update("open chrome", chat_type="group"))
    drain(bridge)
    assert log == [] and http.sent == []


def test_stale_messages_do_not_fire_after_the_laptop_was_off():
    bridge, http, log, _ = make_bridge([call("power", action="shutdown")])
    bridge.handle_update(update("shut down the laptop", age=3600))
    drain(bridge)
    assert log == [] and http.sent == []


def test_stop_works_without_the_worker_and_blocks_actions():
    bridge, http, log, engine = make_bridge([call("open_app", name="chrome")])
    bridge.handle_update(update("/stop"))            # handled inline, no drain needed
    assert engine.policy.halted and "Halted" in http.messages()[-1]
    bridge.handle_update(update("open chrome"))
    drain(bridge)
    assert log == []
    bridge.handle_update(update("/resume"))
    assert not engine.policy.halted


def test_dangerous_action_from_phone_waits_for_yes():
    bridge, http, log, _ = make_bridge([call("delete_path", path="~/a.txt")])
    bridge.handle_update(update("delete a.txt"))
    drain(bridge)
    assert log == [] and "need your OK" in http.messages()[-1]
    bridge.handle_update(update("yes"))
    drain(bridge)
    assert log == [("delete_path", {"path": "~/a.txt"})]


def test_voice_note_is_transcribed_and_echoed_back():
    bridge, http, log, _ = make_bridge([call("open_app", name="chrome"), say("क्रोम खुल्यो।")], stt=FakeSTT())
    bridge.handle_update(update(voice={"file_id": "abc"}))
    drain(bridge)
    assert log == [("open_app", {"name": "chrome"})]
    assert http.messages() == ["🎙 क्रोम खोल", "क्रोम खुल्यो।"]


def test_screenshot_photo_is_sent_back(tmp_path):
    photo = tmp_path / "s.png"
    photo.write_bytes(b"png")
    bridge, http, _, _ = make_bridge([LLMResponse(content="Here.")])
    bridge.engine.reply = lambda text, source: type("R", (), {"text": "Here.", "photos": [str(photo)]})()
    bridge.handle_update(update("/screenshot"))
    drain(bridge)
    assert any(method == "sendPhoto" for method, _ in http.sent)


def test_notify_reaches_every_allowed_user_and_long_text_is_chunked():
    bridge, http, _, engine = make_bridge([])
    assert engine.notify == bridge.notify             # tools can reach the phone
    bridge.notify("x" * 9000)
    assert len(http.messages()) == 3


# ---------------------------------------------------------------- monitors
def test_battery_alert_fires_once_then_rearms():
    alerts = Monitors(notify=lambda _: None)
    low = {"battery_percent": 15, "plugged_in": False}
    assert len(alerts.check_once(low)) == 1
    assert alerts.check_once(low) == []                                   # no spam
    assert alerts.check_once({"battery_percent": 60, "plugged_in": True}) == []
    again = alerts.check_once(low)
    assert any("Battery" in a for a in again) and any("unplugged" in a for a in again)


def test_disk_and_sustained_ram_alerts():
    m = Monitors(notify=lambda _: None)
    assert "disk" in m.check_once({"disk_free_gb": 2.0})[0]
    assert m.check_once({"ram_percent": 97}) == []
    assert m.check_once({"ram_percent": 97}) == []
    assert "Memory" in m.check_once({"ram_percent": 97})[0]              # third strike
    assert m.check_once({}) == []                                         # missing sensors are fine


def test_a_message_sent_while_a_task_runs_steers_it_instead_of_queueing():
    bridge, http, log, engine = make_bridge([])
    engine._lock.acquire()                           # a task is running
    try:
        bridge.handle_update(update("stop"))
        assert bridge._jobs.empty() and engine._steer.get_nowait() == "stop"
        assert http.messages() == ["Passed to the task that is running."]
        bridge.handle_update(update("/status"))      # commands still queue
        assert not bridge._jobs.empty()
    finally:
        engine._lock.release()
