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
