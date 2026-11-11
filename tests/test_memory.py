from brain.memory import MemoryStore, redact


def test_facts_dedupe_and_update():
    m = MemoryStore(":memory:")
    assert m.add_fact("user", "The user lives in Texas.")["saved"]
    assert not m.add_fact("user", "the user lives in texas")["saved"]          # same fact
    updated = m.add_fact("user", "The user lives in Denton, Texas.")           # richer restatement
    assert updated.get("updated") and len(m.facts("user")) == 1
    assert "Denton" in m.facts("user")[0]["fact"]


def test_unknown_branch_defaults_to_user():
    m = MemoryStore(":memory:")
    m.add_fact("nonsense", "The user likes momo.")
    assert m.facts("user")[0]["fact"] == "The user likes momo."


def test_recall_ranks_by_overlap_and_handles_nepali():
    m = MemoryStore(":memory:")
    m.add_fact("user", "The user's sister Asha lives in Kathmandu.")
    m.add_fact("user", "The user drinks coffee every morning.")
    m.add_fact("user", "प्रयोगकर्तालाई मःमः मन पर्छ।")
    assert "Asha" in m.recall("where does asha live")[0]["fact"]
    assert "मःमः" in m.recall("मःमः कस्तो लाग्छ")[0]["fact"]
    assert m.recall("quantum physics") == []


def test_forget_removes_matching_facts_only():
    m = MemoryStore(":memory:")
    m.add_fact("user", "The user drinks coffee every morning.")
    m.add_fact("user", "The user's sister is Asha.")
    assert m.forget("coffee morning") == 1
    assert [f["fact"] for f in m.facts()] == ["The user's sister is Asha."]


def test_warm_profile_puts_directives_first_and_respects_budget():
    m = MemoryStore(":memory:")
    m.add_fact("user", "The user is a CS student.")
    m.add_fact("directives", "Reply in Nepali when spoken to in Nepali.")
    profile = m.warm_profile()
    assert profile.index("Standing instructions") < profile.index("About the user")
    assert len(m.warm_profile(max_chars=10)) < len(profile)


def test_secrets_are_redacted_before_storage():
    m = MemoryStore(":memory:")
    m.add_turn("voice", "user", "my password is hunter2 and key gsk_abcdefghijklmnopqrstuvwxyz123456")
    stored = m.recent_turns()[0]["content"]
    assert "hunter2" not in stored and "gsk_abc" not in stored
    assert "4111 1111 1111 1111" not in redact("card 4111 1111 1111 1111 ok")


def test_audit_keeps_structure_and_redacts_values():
    m = MemoryStore(":memory:")
    m.audit({"event": "tool", "tool": "run_powershell",
             "arguments": {"command": 'setx TOKEN "password = hunter2"'}, "ok": True})
    rec = m.recent_audit()[0]
    assert rec["tool"] == "run_powershell" and "hunter2" not in str(rec)


def test_turn_search_and_diary_bookkeeping():
    m = MemoryStore(":memory:")
    m.add_turn("voice", "user", "remind me about the dentist on friday")
    m.add_turn("voice", "assistant", "Okay, dentist on Friday.")
    assert "dentist" in m.search_turns("dentist appointment")[0]["content"]
    turns, last_id = m.unsummarised_turns()
    assert len(turns) == 2
    m.add_diary("- asked about a dentist reminder", last_id)
    assert m.unsummarised_turns()[0] == [] and m.diary()[0]["summary"].startswith("- asked")
