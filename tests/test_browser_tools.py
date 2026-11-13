import threading

from browser import playwright_controller as pw


def test_browser_call_runs_every_caller_on_one_thread():
    seen = []

    def record():
        seen.append(threading.current_thread().name)
        return threading.current_thread().ident

    callers = [threading.Thread(target=lambda: pw.browser_call(record)) for _ in range(3)]
    for t in callers:
        t.start()
    for t in callers:
        t.join()
    pw.browser_call(record)

    assert seen == ["BrowserWorker"] * 4


def test_browser_call_turns_exceptions_into_results():
    def boom():
        raise RuntimeError("tab crashed")

    result = pw.browser_call(boom)
    assert result["success"] is False and "tab crashed" in result["response"]


class FakeField:
    def __init__(self, type_="text"):
        self.type = type_
        self.value = ""

    def count(self):
        return 1

    @property
    def first(self):
        return self

    def is_visible(self):
        return True

    def get_attribute(self, name):
        return self.type if name == "type" else None

    def fill(self, value, timeout=None):
        self.value = value

    def input_value(self):
        return self.value


class FakePage:
    def __init__(self, field):
        self.field = field

    def get_by_label(self, label):
        return self.field

    get_by_placeholder = get_by_role = lambda self, *a, **k: self.field


def test_fill_field_refuses_password_fields():
    field = FakeField("password")
    result = pw.fill_field(FakePage(field), "Password", "hunter2")
    assert result["success"] is False and field.value == ""


def test_fill_field_reads_value_back():
    result = pw.fill_field(FakePage(FakeField()), "Full name", "Satish")
    assert result["success"] and result["value"] == "Satish"


def test_worker_rebuilds_the_driver_after_a_broken_pipe(monkeypatch):
    """Seen live: the Playwright node driver died with EPIPE and every later
    browser command failed until HoloDesk was restarted."""
    resets = []
    monkeypatch.setattr(pw.controller, "reset", lambda: resets.append(True))
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("Error: EPIPE: broken pipe, write")
        return {"success": True, "response": "recovered"}

    assert pw.browser_call(flaky) == {"success": True, "response": "recovered"}
    assert resets == [True] and len(calls) == 2


def test_other_errors_are_not_retried(monkeypatch):
    monkeypatch.setattr(pw.controller, "reset", lambda: None)
    calls = []

    def boom():
        calls.append(1)
        raise ValueError("no such element")

    assert pw.browser_call(boom)["success"] is False
    assert len(calls) == 1
