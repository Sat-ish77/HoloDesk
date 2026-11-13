# HoloDesk Demo Runbook

## Wake-word activation

Wake-word support is off by default and does not change gesture or spacebar activation.

Set these variables in `.env` to enable it:

```env
HOLODESK_WAKE_WORD_ENABLED=1
HOLODESK_WAKE_WORD_PHRASE=hey holo
HOLODESK_WAKE_WORD_ENGINE=simple
```

When enabled, HoloDesk listens continuously while the app is running. The listener uses short repeated capture windows, not one long recording:

```env
HOLODESK_WAKE_WORD_LISTEN_TIMEOUT=1.0
HOLODESK_WAKE_WORD_PHRASE_LIMIT=2.0
HOLODESK_WAKE_WORD_COOLDOWN=2.0
HOLODESK_WAKE_WORD_WHISPER_MODEL=tiny
HOLODESK_PORCUPINE_ACCESS_KEY=
```

Supported engines:

- `simple`: lightweight `speech_recognition` listener. No paid key required.
- `whisper`: local `faster-whisper` listener using `HOLODESK_WAKE_WORD_WHISPER_MODEL`.
- `porcupine`: optional Picovoice engine. Requires `pvporcupine` and `HOLODESK_PORCUPINE_ACCESS_KEY`.

To disable wake-word listening:

```env
HOLODESK_WAKE_WORD_ENABLED=0
```

This keeps existing behavior only: gesture, spacebar, and manual wake.

## UI grounding

UI grounding adds a safe desktop-control layer:

- screenshot-to-UI-element parser interface in `vision/ui_parser.py`
- safety-aware planner and executor in `agents/desktop_grounding_agent.py`
- OpenAI API-based screen verification helper
- dry-run tests for planner and safety behavior

Safety rules:

- Block login, sign-in, password, payment, banking, and transfer-money flows.
- Require explicit confirmation for send email, delete file/folder, shutdown, and restart.
- Allow safe draft flows such as drafting email content without sending.

Planner behavior:

- Converts natural commands into ordered `PlanStep` actions.
- Returns structured plan JSON with `safe`, `blocked_reason`, and `steps`.

Executor behavior:

- Takes screenshots before and after each step.
- Parses pre-step screenshots.
- Resolves target elements by visible label.
- Stops safely if parser output is unclear or unavailable.
- Supports `dry_run=True` to avoid live desktop actions.

## OmniParser

OmniParser is optional in this version. The repo includes a blocker-aware adapter and a mock parser so tests and dry-runs still work before OmniParser is installed.

Recommended Windows setup:

1. Confirm Python is available: `python --version`
2. Install project deps: `pip install -r requirement.txt`
3. Install OmniParser using its official setup instructions.
4. Confirm the installed Python import/API shape.
5. Wire the real runtime call inside `OmniParserAdapter.parse()` if the package API differs from the adapter placeholder.

## Verify with OpenAI vision

`VerifyWithChatGPTVision.run(question, screenshot_path)`:

- reads a screenshot file
- sends the image and question to OpenAI vision through `OpenAIClient`
- returns a concise verification answer

This uses the OpenAI API directly, not ChatGPT website automation.

## Logs to look for

When wake-word is active, watch for:

- `[WAKE] Wake-word listener started. engine=... phrase='hey holo'`
- `[WAKE] Wake phrase detected: '...'`
- `[WAKE] Posted synthetic SPACE key event.`

## Manual Windows test checklist

1. Set `HOLODESK_WAKE_WORD_ENABLED=1`.
2. Start app: `python app/main.py`.
3. Confirm startup log includes wake listener start line.
4. Say `hey holo`.
5. Confirm voice transitions as normal: `WAKE` -> `LISTENING` -> `PROCESSING`.
6. Verify spacebar wake still works.
7. Verify gesture wake still works.
8. Open Chrome.
9. Open Brave.
10. Open Outlook.
11. Search a name in Outlook.
12. Draft an email in Outlook without sending.
13. Click a visible UI element by label.
14. Analyze current screen.
15. Verify current screen with OpenAI vision.
16. Try risky commands and confirm they are blocked or ask for confirmation.
17. Set `HOLODESK_WAKE_WORD_ENABLED=0`, restart, and confirm phrase-triggered wake is inactive.

## Suggested local smoke commands

- Build plan: `DesktopActionPlanner().build_plan("open github in chrome")`
- Execute dry-run: `DesktopActionExecutor().execute_plan(plan, dry_run=True)`
- Verify screenshot: `VerifyWithChatGPTVision().run("What is open?", "C:/path/to/screenshot.png")`

## Known limitations

- Python is not currently available in this shell, so automated tests cannot run here until Python is fixed on PATH.
- OmniParser runtime invocation remains a guarded adapter boundary until the local install/API is confirmed.
- Live desktop actions require manual Windows validation.
