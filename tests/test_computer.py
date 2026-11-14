from types import SimpleNamespace

from PIL import Image

from brain.tools.computer import computer_task


class _Block(dict):
    def model_dump(self, exclude_none=True):
        return dict(self)


class _Client:
    """Replays scripted responses and records every request."""

    def __init__(self, turns):
        self.turns, self.requests = list(turns), []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.requests.append({**kw, "messages": list(kw["messages"])})   # the loop keeps appending
        return SimpleNamespace(stop_reason="end_turn", content=[_Block(b) for b in self.turns.pop(0)])


class _Mouse:
    def __init__(self):
        self.calls = []

    def screenshot(self):
        return Image.new("RGB", (1920, 1080))

    def size(self):
        return (1920, 1080)

    def position(self):
        return (0, 0)

    def __getattr__(self, name):            # click, write, hotkey, keyDown, ...
        return lambda *a, **k: self.calls.append((name, a, k))


def _use(i, name, **inp):
    return {"type": "tool_use", "id": f"t{i}", "name": name, "toolset_name": "computer", "input": inp}


def test_screenshot_click_then_report():
    client, mouse = _Client([
        [_use(1, "screenshot"), _use(2, "left_click", coordinate=[683, 384])],
        [{"type": "text", "text": "The Downloads folder is open."}],
    ]), _Mouse()
    out = computer_task({"goal": "open Downloads"}, SimpleNamespace(engine=None), client=client, pyautogui=mouse)
    assert out == {"ok": True, "message": "The Downloads folder is open.", "actions": 1}
    # the 1366-wide model screenshot maps back to the 1920-wide screen
    assert ("click", (960, 540), {"clicks": 1, "interval": 0.08, "button": "left"}) in mouse.calls
    results = client.requests[1]["messages"][-1]["content"]
    assert all(r["toolset_name"] == "computer" for r in results)
    assert results[0]["content"][0]["type"] == "image"
    assert client.requests[0]["tools"] == [{"type": "computer_toolset_20260801"}]


def test_pauses_before_irreversible_steps():
    client = _Client([[{"type": "text", "text": "NEEDS OK: click Send on the email to Smarika."}]])
    out = computer_task({"goal": "send it"}, SimpleNamespace(engine=None), client=client, pyautogui=_Mouse())
    assert out["needs_ok"] == "click Send on the email to Smarika."      # the engine asks through the policy

    client = _Client([[{"type": "text", "text": "Sent; the window shows Message sent."}]])
    computer_task({"goal": "send it", "approved": out["needs_ok"]}, SimpleNamespace(engine=None),
                  client=client, pyautogui=_Mouse())
    assert "The user approved this step: click Send" in client.requests[0]["messages"][0]["content"]


def test_failed_action_skips_the_rest_of_the_batch():
    client = _Client([
        [_use(1, "teleport"), _use(2, "left_click", coordinate=[1, 1])],
        [{"type": "text", "text": "I got stuck."}],
    ])
    mouse = _Mouse()
    computer_task({"goal": "x"}, SimpleNamespace(engine=None), client=client, pyautogui=mouse)
    results = client.requests[1]["messages"][-1]["content"]
    assert results[0]["is_error"] and results[1]["content"].startswith("Not executed")
    assert not any(c[0] == "click" for c in mouse.calls)
