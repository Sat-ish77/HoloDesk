# HoloDesk Demo Runbook

## Wake-word activation (optional)

Wake-word support is off by default and does not change existing V-gesture activation.

Set these variables in `.env` to enable it:

```env
HOLODESK_WAKE_WORD_ENABLED=1
HOLODESK_WAKE_WORD_PHRASE=hey desk
HOLODESK_WAKE_WORD_ENGINE=simple
```

Supported engines:

- `simple`: lightweight `speech_recognition` listener. No paid key required.
- `whisper`: local `faster-whisper` listener using `HOLODESK_WAKE_WORD_WHISPER_MODEL`.
- `porcupine`: optional Picovoice engine. Requires `pvporcupine` install and `HOLODESK_PORCUPINE_ACCESS_KEY`.

Optional wake listener knobs:

```env
HOLODESK_WAKE_WORD_LISTEN_TIMEOUT=1.0
HOLODESK_WAKE_WORD_PHRASE_LIMIT=2.0
HOLODESK_WAKE_WORD_COOLDOWN=2.0
HOLODESK_WAKE_WORD_WHISPER_MODEL=tiny
HOLODESK_PORCUPINE_ACCESS_KEY=
```

## Disable wake-word

Set:

```env
HOLODESK_WAKE_WORD_ENABLED=0
```

This keeps existing behavior only (gesture/spacebar/manual wake).

## How wake-word triggers HoloDesk

The wake-word adapter posts a synthetic `SPACE` key press into Pygame. `app/main.py` already maps spacebar to `voice_thread.request_wake()`, so the existing wake path is reused.

## Logs to look for

When active, watch for:

- `[WAKE] Wake-word listener started. engine=... phrase='...'`
- `[WAKE] Wake phrase detected: '...'`
- `[WAKE] Posted synthetic SPACE key event.`

## Limitations and fallback behavior

- Wake-word is optional and env-controlled.
- If optional dependencies are missing, wake-word falls back safely or stays inactive without blocking app startup.
- `porcupine` will not run without a valid access key; it falls back to `simple`.
- `simple` uses SpeechRecognition and may need internet for transcription.
- Existing VAD/Whisper/auto-gain tuning in `app/main.py` is unchanged.

## Manual Windows test checklist (laptop + microphone)

1. Ensure `.env` has `HOLODESK_WAKE_WORD_ENABLED=1` and desired phrase/engine.
2. Start app: `python app/main.py`.
3. Confirm startup log includes wake listener start line.
4. Say the configured phrase (example: "hey desk").
5. Confirm log: wake phrase detected + synthetic space key posted.
6. Confirm voice state transitions as normal (`WAKE` -> `LISTENING` -> `PROCESSING`).
7. Verify command handling still works after wake.
8. Verify V-gesture activation still works unchanged.
9. Set `HOLODESK_WAKE_WORD_ENABLED=0` and restart.
10. Confirm no wake listener logs and no phrase-triggered wake.
