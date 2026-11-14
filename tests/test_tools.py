import json

import pytest

from brain.policy import Risk
from brain.tools import build_default_registry
from brain.tools.files import resolve_path
from brain.tools.knowledge import get_datetime
from brain.tools.registry import ToolContext, ToolError, tokenize


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv("HOLODESK_FILE_ROOTS", raising=False)
    return tmp_path


def test_catalogue_is_valid_for_the_openai_tool_format():
    registry = build_default_registry()
    assert len(registry) >= 30
    for tool in registry.all():
        schema = tool.schema()
        json.dumps(schema)                                   # serialisable
        params = schema["function"]["parameters"]
        assert params["type"] == "object"
        for required in params.get("required", []):
            assert required in params["properties"], (tool.name, required)
        assert len(tool.description) >= 20, tool.name


def test_risk_tiers_of_the_dangerous_tools():
    r = build_default_registry()
    assert r.get("delete_path").risk_for({"path": "~/x"}) == Risk.DANGER
    assert r.get("kill_process").risk_for({"target": "chrome"}) == Risk.DANGER
    assert r.get("power").risk_for({"action": "shutdown"}) == Risk.DANGER
    assert r.get("power").risk_for({"action": "lock"}) == Risk.ACT
    assert r.get("power").risk_for({"action": "cancel_shutdown"}) == Risk.SAFE
    assert r.get("run_powershell").risk_for({"command": "Get-Process"}) == Risk.SAFE
    assert r.get("run_powershell").risk_for({"command": "Remove-Item x"}) == Risk.DANGER
    assert r.get("run_powershell").risk_for({"command": "format c:"}) == Risk.BLOCKED
    assert r.get("system_status").risk_for({}) == Risk.SAFE


def test_tokenizer_keeps_devanagari_words_whole():
    assert tokenize("मेरो ल्यापटप, कस्तो छ?") == ["मेरो", "ल्यापटप", "कस्तो", "छ"]


def test_file_tools_are_confined_to_home(home):
    assert resolve_path("~/notes.txt") == (home / "notes.txt").resolve()
    assert resolve_path("Documents/a.txt") == (home / "Documents" / "a.txt").resolve()
    with pytest.raises(ToolError):
        resolve_path("/etc/passwd")
    with pytest.raises(ToolError):
        resolve_path("~/../outside.txt")


def test_credential_files_are_off_limits(home):
    for bad in ["~/.ssh/id_rsa", "~/project/.env", "~/.aws/credentials"]:
        with pytest.raises(ToolError):
            resolve_path(bad)


def test_file_roundtrip_and_overwrite_needs_confirmation(home):
    r = build_default_registry()
    ctx = ToolContext()
    write, read = r.get("write_text_file"), r.get("read_text_file")
    args = {"path": "~/notes/todo.txt", "content": "दूध किन्ने\nbuy milk"}
    assert write.risk_for(args) == Risk.ACT                      # new file: just do it
    write.handler(args, ctx)
    assert "दूध किन्ने" in read.handler({"path": "~/notes/todo.txt"}, ctx)["content"]
    assert write.risk_for(args) == Risk.DANGER                   # now it would overwrite
    assert write.risk_for({**args, "append": True}) == Risk.ACT

    listing = r.get("list_directory").handler({"path": "~/notes"}, ctx)
    assert listing["entries"][0]["name"] == "todo.txt"
    found = r.get("find_files").handler({"query": "todo"}, ctx)
    assert found["matches"] and found["matches"][0].endswith("todo.txt")

    r.get("move_path").handler({"source": "~/notes/todo.txt", "destination": "~/notes/done.txt"}, ctx)
    r.get("delete_path").handler({"path": "~/notes/done.txt"}, ctx)
    assert not (home / "notes" / "done.txt").exists()


def test_binary_and_missing_files_fail_cleanly(home):
    r = build_default_registry()
    (home / "blob.bin").write_bytes(b"\x00\x01\x02" * 100)
    with pytest.raises(ToolError):
        r.get("read_text_file").handler({"path": "~/blob.bin"}, ToolContext())
    with pytest.raises(ToolError):
        r.get("delete_path").handler({"path": "~/nope.txt"}, ToolContext())
    with pytest.raises(ToolError):
        r.get("delete_path").handler({"path": "~"}, ToolContext())        # never the whole home


def test_datetime_gives_nepal_time_and_bs_conversion():
    out = get_datetime({"convert_ad_to_bs": "2026-11-11", "convert_bs_to_ad": "2083-01-01"}, ToolContext())
    assert "NPT" in out["nepal"]
    pytest.importorskip("nepali_datetime")
    assert out["converted_to_bs"]["bs_date"] == "2083-07-25"
    assert out["converted_to_ad"]["ad_date"] == "2026-04-14"
    assert "nepal_bs_today" in out


def test_memory_tools_roundtrip():
    from brain.memory import MemoryStore
    r = build_default_registry()
    ctx = ToolContext(memory=MemoryStore(":memory:"))
    r.get("remember").handler({"fact": "The user's favourite team is Liverpool.", "branch": "user"}, ctx)
    assert "Liverpool" in r.get("recall_memory").handler({"query": "favourite team"}, ctx)["facts"][0]["fact"]
    assert r.get("forget_memory").handler({"query": "favourite team Liverpool"}, ctx)["removed"] == 1


def test_phone_tools_explain_when_bridge_is_missing():
    r = build_default_registry()
    assert r.get("notify_phone").handler({"message": "hi"}, ToolContext())["ok"] is False
    sent = []
    assert r.get("notify_phone").handler({"message": "hi"}, ToolContext(notify=sent.append))["ok"]
    assert sent == ["hi"]


def test_the_menu_is_fixed_and_rare_tools_sit_on_the_shelf():
    r = build_default_registry()
    menu = {t.name for t in r.menu()}
    assert {"look", "click", "type", "open_app", "gmail_compose", "gmail_send", "find_files", "run_powershell"} <= menu
    assert not {"kill_process", "list_processes", "clipboard", "browser_open_result"} & menu
    assert len(menu) <= 42 and len(r) > len(menu)
    # find_tool reaches the shelf by keyword, in Nepali too.
    assert r.rank("frozen app force quit")[0][1].name == "kill_process"
    for gone in ("social_react", "social_comment", "ask_chatbot", "browser_snapshot", "browser_click_ref",
                 "browser_click_text", "click_ui_element", "mouse_click", "type_text"):
        assert r.get(gone) is None, gone
