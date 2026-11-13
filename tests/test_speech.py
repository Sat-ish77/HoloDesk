from core.speech import is_nepali


def test_devanagari_routes_to_the_nepali_voice():
    assert is_nepali("नोटप्याड खोलें") is True
    assert is_nepali("अहिले Claude अगाडि छ।") is True  # mixed script still counts


def test_english_and_romanised_nepali_use_the_windows_voice():
    # Romanised Nepali reads as Latin text, which is why the Brain is told to
    # answer Nepali in Devanagari.
    assert is_nepali("open notepad") is False
    assert is_nepali("notepad kholnus") is False
    assert is_nepali("") is False


def test_tool_summary_clips_long_output():
    """A page read returns thousands of characters; speaking them all is what made
    HoloDesk read Gmail aloud until the user gave up."""
    from agents.brain_agent import BrainAgent

    log = [{"tool": "browser_page_text", "success": True, "response": "Gemini " * 500}]
    summary = BrainAgent._summarize(log)
    assert len(summary) < 150 and summary.endswith("...")


def test_summary_of_several_tools_stays_short():
    from agents.brain_agent import BrainAgent

    log = [{"tool": f"t{i}", "success": True, "response": "x" * 400} for i in range(5)]
    assert len(BrainAgent._summarize(log)) < 600
