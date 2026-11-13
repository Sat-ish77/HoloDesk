from types import SimpleNamespace as NS

import pytest

import agents.brain_agent as brain_mod
from agents.brain_agent import BrainAgent
from automation import win_ui


class FakeControl:
    def __init__(self, name, control_type, value=""):
        self.element_info = NS(name=name, control_type=control_type)
        self.value = value
        self.invoked = False

    def invoke(self):
        self.invoked = True

    def set_edit_text(self, text):
        self.value = text

    @property
    def iface_value(self):
        return NS(CurrentValue=self.value)


@pytest.fixture
def window(monkeypatch):
    controls = [
        FakeControl("Seven", "Button"),
        FakeControl("Seventy", "Text"),
        FakeControl("Open:", "ComboBox", value="Open:"),
        FakeControl("Open:", "Edit"),
    ]
    monkeypatch.setattr(win_ui, "target_window", lambda: (1, "Calculator"))
    monkeypatch.setattr(win_ui, "_controls", lambda hwnd: controls)
    monkeypatch.setattr(win_ui.time, "sleep", lambda s: None)
    monkeypatch.setattr(win_ui.win32gui, "GetForegroundWindow", lambda: 1)
    monkeypatch.setattr(win_ui.win32gui, "GetWindowText", lambda h: "Calculator")
    return controls


def test_click_prefers_exact_name_and_invokes(window):
    result = win_ui.click_control("seven")
    assert result["success"] and window[0].invoked and not window[1].invoked


def test_click_unknown_name_lists_what_is_visible(window):
    result = win_ui.click_control("Banana")
    assert result["success"] is False and "Seven" in result["response"]


def test_set_text_targets_edit_not_its_combobox_and_reads_back(window):
    result = win_ui.set_text("Open", "notepad")
    assert result["success"] and result["value"] == "notepad"
    assert window[3].value == "notepad" and window[2].value == "Open:"


def test_launch_uses_installed_app_list(monkeypatch):
    monkeypatch.setattr(win_ui, "_installed_apps", lambda: {"Calculator": "Calc!App", "Google Chrome": "Chrome"})
    started = []
    monkeypatch.setattr(win_ui.os, "startfile", started.append)
    assert win_ui.launch_app("chrome")["name"] == "Google Chrome"
    assert started == ["shell:AppsFolder\\Chrome"]
    assert win_ui.launch_app("zzzz")["success"] is False


def test_brain_gates_risky_clicks(monkeypatch):
    clicked = []
    monkeypatch.setattr(brain_mod.win_ui, "click_control", lambda name, control_type=None: clicked.append(name) or {"success": True, "response": "ok"})
    from test_brain_agent import FakeTask

    task = FakeTask()
    brain = BrainAgent(task, client=object())

    assert brain._call_tool("click", {"name": "Delete account"}).get("pending_confirmation") is True
    assert clicked == []  # nothing clicked until the user says yes
    task._pending_confirm["fn"]()
    assert clicked == ["Delete account"]

    brain._call_tool("click", {"name": "Seven"})
    assert clicked[-1] == "Seven"
