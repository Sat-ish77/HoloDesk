from speech.stt import CloudSTT
from speech.tts import clean_for_speech, is_nepali, pick_voice, wants_neural

KEY = "gsk_" + "a" * 40


class Resp:
    def __init__(self, payload, status=200):
        self._p, self.status_code, self.text = payload, status, str(payload)

    def json(self):
        return self._p


class FakeHTTP:
    def __init__(self, replies):
        self.replies, self.requests = list(replies), []

    def post(self, url, headers=None, data=None, files=None, timeout=None):
        self.requests.append(data)
        return self.replies.pop(0)


def test_transcribes_and_reports_language():
    http = FakeHTTP([Resp({"text": " open chrome ", "language": "english"})])
    out = CloudSTT(api_key=KEY, session=http).transcribe(b"wav")
    assert out == {"text": "open chrome", "language": "english"}
    assert "language" not in http.requests[0]            # auto-detect by default


def test_nepali_mistaken_for_hindi_is_retried_as_nepali():
    http = FakeHTTP([Resp({"text": "क्रोम खोलो", "language": "hindi"}),
                     Resp({"text": "क्रोम खोल", "language": "nepali"})])
    out = CloudSTT(api_key=KEY, session=http).transcribe(b"wav")
    assert out == {"text": "क्रोम खोल", "language": "ne"}
    assert http.requests[1]["language"] == "ne"


def test_forced_language_is_sent_and_not_retried():
    http = FakeHTTP([Resp({"text": "hello", "language": "hindi"})])
    CloudSTT(api_key=KEY, session=http, language="en").transcribe(b"wav")
    assert http.requests[0]["language"] == "en" and len(http.requests) == 1


def test_failures_return_empty_so_the_caller_falls_back():
    assert CloudSTT(api_key="", session=FakeHTTP([])).transcribe(b"wav")["text"] == ""
    assert CloudSTT(api_key=KEY, session=FakeHTTP([Resp({"error": "x"}, 500)])).transcribe(b"wav")["text"] == ""


def test_prompt_echo_on_silence_is_dropped_but_short_words_survive():
    from speech.stt import DEFAULT_PROMPT, _drop_prompt_echo
    assert _drop_prompt_echo(DEFAULT_PROMPT) == ""
    assert _drop_prompt_echo("YouTube") == "YouTube"


def test_nepali_detection_and_voice_choice():
    assert is_nepali("क्रोम खुल्यो।")
    assert is_nepali("Chrome खुल्यो, अरू केही चाहिन्छ?")
    assert not is_nepali("Chrome is open.")
    assert not is_nepali("12:30")
    assert wants_neural("भयो।") and not wants_neural("Done.")
    assert pick_voice("भयो।").startswith("ne-NP") and pick_voice("Done.").startswith("en-")


def test_markdown_and_urls_are_not_read_aloud():
    assert clean_for_speech("**Done** see https://x.y/z `code`") == "Done see code"


def test_noise_is_not_turned_into_words():
    silent = {"text": "Thank you.", "language": "english",
              "segments": [{"no_speech_prob": 0.92, "avg_logprob": -0.4}]}
    mumble = {"text": "the quick brown fox", "language": "english",
              "segments": [{"no_speech_prob": 0.1, "avg_logprob": -1.6}]}
    real = {"text": "धन्यवाद", "language": "nepali",
            "segments": [{"no_speech_prob": 0.02, "avg_logprob": -0.3}]}
    stt = lambda payload: CloudSTT(api_key=KEY, session=FakeHTTP([Resp(payload)])).transcribe(b"wav")
    assert stt(silent)["text"] == "" and stt(silent)["silence"]
    assert stt(mumble)["text"] == ""
    assert stt(real)["text"] == "धन्यवाद"


def test_personal_names_from_env_reach_the_bias_prompt(monkeypatch):
    monkeypatch.setenv("HOLODESK_STT_NAMES", "Kapil Sharma")
    http = FakeHTTP([Resp({"text": "search Kapil Sharma", "language": "english"})])
    CloudSTT(api_key=KEY, session=http).transcribe(b"wav")
    assert "Gmail" in http.requests[0]["prompt"] and "Kapil Sharma" in http.requests[0]["prompt"]
