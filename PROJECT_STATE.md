# HoloDesk Project State

Last updated: 2026-07-23
Current branch: `codex/holo-chatbot-3d-overlay`

## One-Line Summary

HoloDesk is a Windows desktop AI overlay that combines voice, hand gestures, screen vision, UI grounding, memory, and safe automation into one futuristic assistant.

The project is no longer just a gesture demo. It now has the beginning of a real "desktop control brain": user command -> intent/planning -> UI perception -> safe execution -> verification.

## Current Position

HoloDesk is in a strong prototype stage.

It has several impressive working parts:

- Transparent always-on-top Pygame overlay.
- Webcam-based hand tracking using MediaPipe.
- Voice command capture with Whisper.
- Gesture wake using V-sign.
- Spacebar/manual wake path.
- Windows desktop control through PyAutoGUI and UI automation helpers.
- Screen analysis through OpenAI vision.
- Optional wake phrase support for `hey holo`.
- Optional OmniParser server integration for UI element detection, not fully validated end-to-end with HoloDesk yet.
- Safe command routing for risky actions.
- Memory/session logging.
- Expandable Holo Orb and chat panel.
- Game menu with Laser Hands and Tic Tac Toe.
- Production control brain v1 for English/romanized Nepali command routing.

But it is not fully autonomous yet.

The biggest missing piece is reliability: every desktop action needs to be done through a verified loop:

```text
hear command
understand intent
look at screen
detect UI elements
choose target
perform one action
look again
verify result
continue, retry, or ask user
```

That is the path from cool prototype to production-quality project.

## What HoloDesk Can Do Now

### 1. Overlay And Interaction

Status: working prototype

HoloDesk opens as a transparent always-on-top overlay. It can show visual UI elements without blocking the full desktop experience.

Current overlay pieces:

- Small docked Holo Orb.
- Expandable orb menu.
- Chat panel.
- Mission mode panel.
- Game menu.
- Laser Hands game.
- Tic Tac Toe game.

Recent decision:

- Flappy Holo is hidden/disabled from the demo because the gesture control was not reliable enough.
- Keeping a half-working game would hurt the project more than help it.
- Laser Hands and Tic Tac Toe are better demo choices.

### 2. Hand Tracking

Status: partially reliable

Working ideas:

- Hand landmark detection through MediaPipe.
- V-gesture starts voice listening.
- Thumbs up/down can control scrolling.
- Open palm can stop scrolling or speech.
- Pinch can interact with overlay objects.
- Two-hand payload support exists for Laser Hands.

Current limitation:

- Hand interaction is sensitive to lighting, camera angle, hand distance, and frame rate.
- Pinch-to-open-menu is not yet reliable enough to be the main control path.
- For demo, voice should be the primary input and hand gestures should be shown as a bonus interaction.

### 3. Voice Control

Status: working, but speech recognition is noisy

Working:

- V-gesture can wake voice listening.
- HoloDesk can hear commands and dispatch them through the orchestrator.
- It can respond through TTS.
- TTS echo filtering has been improved.

Known issue:

- Speech recognition can mishear phrases.
- Example: "close Facebook in Chrome" can become "close facebooking in Chrome."
- Because of this, dangerous actions must ask for confirmation.

Current best practice:

- Use short commands.
- Avoid asking it to do too many things in one sentence during demo.
- Use confirmation-first behavior for closing, sending, deleting, shutdown, restart.

### 4. Wake Word

Status: implemented but not currently recommended as the main demo path

Wake phrase:

```text
hey holo
```

Environment variables:

```env
HOLODESK_WAKE_WORD_ENABLED=0
HOLODESK_WAKE_WORD_PHRASE=hey holo
HOLODESK_WAKE_WORD_ENGINE=simple
```

Current decision:

- Wake word is disabled by default.
- This is intentional.
- The project should focus on stable core control first.

Why:

- Always-listening wake word is hard to make reliable without a dedicated wake-word engine.
- The simple listener can miss the phrase or compete with other microphone paths.
- Later, use Porcupine or a dedicated local wake model for stronger reliability.

### 5. Screen Vision

Status: working when OpenAI key is configured

HoloDesk can analyze the current screen using OpenAI vision.

Example commands:

```text
what's on my screen
analyze screen
verify current screen
```

Use cases:

- Explain error messages.
- Summarize visible content.
- Verify whether an automation step succeeded.

Limitation:

- Screen vision can describe the screen, but it is not automatically the same as precise UI control.
- For clicking buttons, OmniParser or UI automation is better.

### 6. OmniParser UI Grounding

Status: optional integration path exists; live HoloDesk + OmniParser testing is still pending

OmniParser is treated as the main UI perception layer when it is running at:

```text
http://127.0.0.1:8000
```

HoloDesk adapter:

- Captures screenshot.
- Sends screenshot to OmniParser server.
- Receives UI boxes/elements.
- Ranks targets by label, confidence, and spatial references.
- Saves artifacts under `artifacts/ui_grounding/`.

Current honest status:

- OmniParser has been installed and run separately.
- HoloDesk and OmniParser have not yet been fully validated together on real workflows.
- The next required test is running HoloDesk while OmniParser server is active, then saying `test UI parser`.
- OmniParser may feel laggy on CPU, especially when parsing full desktop screenshots.
- This latency is expected for a heavy visual parser and needs optimization before it can feel production-ready.

Test commands:

```text
test UI parser
show UI boxes
analyze screen
click Messages
click Sign in
click the first profile
```

Important understanding:

OmniParser is the eyes, not the brain.

It can help answer:

```text
Where is the Messages button?
Where is the first profile?
Where is the search box?
```

But it does not by itself understand the whole user goal:

```text
Find Satish Wagle in Gmail and draft an email saying I will be late.
```

That requires:

- language understanding
- workflow planning
- UI perception
- target ranking
- action execution
- verification
- safety confirmation

### 7. Production Control Brain

Status: v1 implemented

Files:

- `agents/production_control.py`
- `agents/production_brain.py`
- `agents/orchestrator.py`
- `agents/desktop_grounding_agent.py`
- `connectors/openai_client.py`

Purpose:

Convert messy user language into structured commands and safe workflows.

Current examples supported:

```text
facebook khola
gmail khola
game menu khola
tic tac toe khola
first row ko second box ma lagau
click the first profile
gmail ma Satish Wagle bhanne manxe khoja ta teslai malai aauna dhilo hunxa bhanera mail draft gara ta
```

What this means:

- Romanized Nepali starter commands can route into English task intents.
- Tic Tac Toe spatial voice commands can map to board positions.
- Gmail draft workflow can be planned as a safe draft-only action.
- "Click first profile" can use spatial/ordinal target selection.

Limitations:

- This is not full multilingual task execution yet.
- HoloDesk does not yet reliably carry out complex Nepali desktop workflows end-to-end.
- The deterministic Nepali support covers starter/demo phrases, not every natural Nepali sentence.
- The current improvement area is English + Nepali/romanized Nepali command understanding.
- OpenAI structured command interpretation is wired as the right future path, but live behavior depends on API key, model availability, latency, prompt quality, and verification after each action.

Important direction:

The goal is not just translation.

The goal is:

```text
User speaks Nepali or English
HoloDesk understands the task
HoloDesk plans the workflow
HoloDesk uses OmniParser/screen perception
HoloDesk performs safe steps
HoloDesk verifies progress
HoloDesk responds in the same language
```

English and Nepali should become production-ready first. Other languages should come after that foundation is stable.

### 8. Desktop Automation

Status: useful but must stay safety-first

Working/partially working actions:

- Open apps.
- Open websites.
- Close/minimize/maximize windows.
- Scroll.
- Media pause/play hotkeys.
- Draft email/message workflows in planner form.
- Click UI by visible label when parser sees the target.

Safety rules:

- Login/payment/banking/password flows are blocked or confirmation-gated.
- Send/delete/shutdown/restart require confirmation.
- Email/message flows should draft only.
- HoloDesk must not send automatically.

Known issue fixed:

- `close facebook in chrome` should not instantly kill Chrome.
- Close actions are now confirmation-first.
- Suspicious misheard words like `facebooking` should trigger clarification instead of acting blindly.

## Good Things About The Project

### 1. It Has A Strong Vision

The idea is clear and impressive:

```text
Control your computer naturally using voice, hands, screen understanding, and AI planning.
```

That is a strong capstone/futuristic project angle.

### 2. It Is Multimodal

HoloDesk is not just a chatbot.

It combines:

- voice
- gestures
- visual screen understanding
- desktop automation
- memory
- UI overlay
- games/interaction

That makes it stand out.

### 3. It Has A Real Safety Model

The project does not just blindly click and type.

It has the right philosophy:

- draft before send
- confirm risky actions
- block sensitive flows
- stop safely when UI is unclear

This is important if you want to present it as serious AI desktop control.

### 4. It Is Built In Layers

The code is moving toward a better architecture:

```text
input agent
intent agent
planner
UI perception
executor
verifier
response
```

That is much better than one giant `main.py` trying to do everything.

### 5. It Has Demo Value

Good demo paths:

- Say a command and open a website.
- Ask what is on the screen.
- Show OmniParser boxes.
- Use Holo Orb/game menu.
- Play Laser Hands.
- Play Tic Tac Toe with voice.
- Draft an email safely.

## Main Limitations

### 1. Full Autonomy Is Not Solved Yet

The project cannot yet reliably control "anything on screen."

Reason:

- Real desktop UI is messy.
- Websites change.
- Popups appear.
- Labels are inconsistent.
- Speech is noisy.
- Wrong clicks can be risky.

The solution is not one better model. The solution is a production loop with verification.

### 2. OmniParser Needs Live Validation

The server can run separately, but the HoloDesk side still needs repeated real-world testing together with the running server:

- Does it detect Chrome profile buttons?
- Does it detect Gmail Compose?
- Does it detect Facebook Messages?
- Does it return coordinates in the expected format?
- Does it work fast enough on CPU?

Until this is proven, UI control should be called "experimental."

Performance concern:

- OmniParser can be laggy, especially on CPU.
- For production, HoloDesk should not parse the entire screen more often than necessary.
- It should cache recent UI boxes, crop to active window when possible, and only re-parse after meaningful UI changes.
- Fast deterministic UI automation should be used before OmniParser when it is clearly safer and faster.

### 3. Wake Word Is Not Reliable Enough Yet

The current simple wake listener is good as a prototype, but not ideal for demo-critical use.

Best current input:

- V-gesture wake
- spacebar/manual wake
- typed chat

Future input:

- Porcupine custom wake phrase
- better local wake model
- push-to-talk fallback

### 4. Latency Can Feel Slow

Latency comes from:

- Whisper transcription
- camera/vision thread
- OpenAI calls
- OmniParser CPU inference
- TTS
- repeated screenshot/parse steps

Production version needs async step execution, caching, and fast model choices.

Specific OmniParser latency fixes to explore:

- Parse only the active window instead of the whole desktop.
- Downscale screenshots before sending to OmniParser when possible.
- Cache parser results for a short time window.
- Reuse previous UI boxes if the screen has not changed much.
- Use Windows UI Automation first for native apps when labels are available.
- Use OmniParser mainly for unknown/custom/web UI where normal automation cannot see elements.
- Keep OpenAI vision as fallback for ambiguous cases, not as the first step for every click.

### 5. Games Are Not The Core Product

Laser Hands and Tic Tac Toe are useful for demo/fun.

But the main project should not become "an overlay game app."

The core product is:

```text
safe AI desktop control
```

Games should support the story:

- prove hand tracking
- make the demo memorable
- show futuristic interaction

They should not distract from the automation story.

## Manual Test Plan

### A. Start OmniParser

In one terminal:

```bat
C:\Users\Dipendra\miniconda3\envs\omni\python.exe C:\Users\Dipendra\Desktop\OmniParser\omnitool\omniparserserver\omniparserserver.py
```

Wait for:

```text
Omniparser initialized!!!
Uvicorn running on http://127.0.0.1:8000
```

### B. Start HoloDesk

In another terminal:

```bat
cd C:\Users\Dipendra\Desktop\holodesk
python app/main.py
```

### C. Test Core Startup

Expected:

- Pygame starts.
- Transparent overlay appears.
- Camera starts.
- Vision thread starts.
- Whisper model loads.
- Voice thread starts.
- Wake word says disabled unless enabled.

### D. Test Orb And Games

Commands:

```text
game menu khola
laser hands
tic tac toe
first row ko second box ma lagau
```

Expected:

- Game menu opens by voice.
- Laser Hands starts.
- Tic Tac Toe starts.
- Tic Tac Toe accepts spatial voice command.

### E. Test OmniParser

Commands:

```text
test UI parser
show UI boxes
analyze screen
```

Expected:

- HoloDesk captures screenshot.
- HoloDesk sends it to OmniParser if `OMNIPARSER_SERVER_URL` is set.
- Results are saved under `artifacts/ui_grounding/`.
- It reports how many UI elements were detected.

### F. Test UI Clicks

Open Chrome or Facebook manually first, then try:

```text
click Messages
click the first profile
click Search
```

Expected:

- HoloDesk should parse visible UI.
- It should pick a matching target.
- If parser is unclear, it should stop safely.

### G. Test Gmail Workflow

Command:

```text
gmail ma Satish Wagle bhanne manxe khoja ta teslai malai aauna dhilo hunxa bhanera mail draft gara ta
```

Expected ideal behavior:

- Open Gmail.
- Search/contact target.
- Start draft.
- Type draft text.
- Stop before send.
- Ask for confirmation before sending.

Current honest status:

- The planning/routing exists.
- Live end-to-end reliability depends on OmniParser detecting Gmail correctly and the workflow matching the actual Gmail UI state.

## What To Build Next

### Phase 1: Make One Workflow Excellent

Goal:

Make Gmail draft workflow reliable enough for demo.

Tasks:

1. Start OmniParser server.
2. Open Gmail.
3. Run `test UI parser`.
4. Inspect saved JSON in `artifacts/ui_grounding/`.
5. Confirm labels for:
   - Search mail
   - Compose
   - To
   - Subject
   - Message body
   - Send
6. Improve target synonyms in `DesktopActionPlanner`.
7. Add verification after each step.
8. Stop before Send and ask confirmation.

Definition of done:

```text
User says Gmail draft command.
HoloDesk drafts the email.
HoloDesk does not send.
HoloDesk says: "Draft is ready. Want me to send it?"
```

### Phase 2: Facebook/Messenger Workflow

Goal:

Make a safe message draft workflow.

Example:

```text
open Facebook, click Messages, search Srijana Wagle, draft: I will call you tomorrow
```

Safety:

- Draft only.
- Never send without confirmation.

Definition of done:

```text
HoloDesk opens Messenger/Facebook messages, finds visible person/chat, types message, asks before send.
```

### Phase 3: Better Multilingual Control

Goal:

Support direct Nepali/romanized Nepali commands more naturally and make them execute real desktop tasks safely.

Current:

- Deterministic starter support exists.
- Some simple romanized Nepali commands route correctly.
- Complex Nepali workflows are not yet production-ready.

Next:

- Use OpenAI structured output for language/intent.
- Preserve original transcript.
- Normalize to canonical JSON.
- Respond in same language.
- Add tests for English and Nepali versions of the same command.
- Build English/Nepali workflow examples before expanding to more languages.
- Keep multilingual execution safety-first: draft, verify, ask before sending.

Example schema:

```json
{
  "language": "ne",
  "reply_language": "ne",
  "intent": "draft_email",
  "app": "gmail",
  "recipient_name": "Satish Wagle",
  "message_body": "I will be late",
  "requires_confirmation": false,
  "user_feedback_text": "ठिक छ, Gmail मा draft तयार गर्दैछु।"
}
```

### Phase 4: Wake Word Reliability

Goal:

Make `hey holo` reliable.

Recommended path:

- Keep simple listener for dev.
- Add Porcupine for production wake word.
- Keep V-gesture and spacebar as fallback.
- Make wake acknowledgement short:

```text
Mm-hmm?
```

### Phase 5: UI Polish

Goal:

Make it feel like a premium futuristic desktop assistant.

Polish tasks:

- Cleaner orb visual.
- Better side docking.
- Smooth expand/collapse animation.
- Game menu with fewer, stronger choices.
- Chat panel scroll and drag polish.
- Mission mode with visible progress.
- Debug panel for OmniParser output.

## What Makes This A Wonderful Project

The project becomes wonderful when it stops being "a bunch of features" and becomes one coherent experience:

```text
HoloDesk watches with permission,
listens when invited,
understands what you mean,
uses the screen as context,
acts carefully,
verifies its work,
and asks before risky actions.
```

The strongest story is:

> HoloDesk is not another chatbot. It is an AI control layer for the desktop.

To make that story believable, focus on:

- one excellent automation workflow
- visible screen understanding
- strong safety behavior
- smooth overlay UX
- same-language interaction
- a short polished demo

## Recommended Demo Script

### 1. Open

Show HoloDesk overlay.

Say:

```text
game menu khola
```

Show that it understands romanized Nepali.

### 2. Fun Interaction

Start:

```text
laser hands
```

Show two-hand visual interaction briefly.

### 3. Productivity

Say:

```text
test UI parser
```

Show OmniParser/UI detection.

### 4. Real Automation

Say:

```text
gmail ma Satish Wagle bhanne manxe khoja ta teslai malai aauna dhilo hunxa bhanera mail draft gara ta
```

Show draft-only safety.

### 5. Safety

Say:

```text
send it
```

Expected:

HoloDesk should ask for confirmation or refuse to auto-send until confirmation is explicit.

## Time Estimate

### For submission-ready demo

Estimated: 2 to 4 focused days

Focus only on:

- HoloDesk starts reliably.
- OmniParser test works.
- One Gmail draft workflow works.
- Game menu is clean.
- Laser Hands or Tic Tac Toe works.
- Safety confirmation works.
- README/demo docs are updated.
- English/Nepali examples are chosen carefully and tested.

### For strong prototype

Estimated: 2 to 4 weeks

Adds:

- Gmail, Outlook, Facebook/Messenger workflow packs.
- Better English/Nepali OpenAI command interpretation.
- Better verification loop.
- More reliable wake word.
- Better overlay polish.
- OmniParser latency optimizations.

### For real production-quality assistant

Estimated: 2 to 3+ months

Adds:

- Installer.
- permissions model.
- robust local wake word.
- app-specific adapters.
- UI state recovery.
- multi-monitor support.
- persistent user preferences.
- safe automation audit log.
- non-technical user onboarding.
- broader multilingual support after English/Nepali is stable.

## Architecture Map

```text
app/main.py
  starts overlay, camera, vision, voice, orchestrator

core/camera_thread.py
  webcam capture

core/vision_thread.py
  MediaPipe hand tracking and gesture payloads

agents/orchestrator.py
  routes commands to the right agent

agents/production_control.py
  multilingual command understanding and workflow intent

agents/task_agent.py
  app/browser/media/system actions with safety

agents/desktop_grounding_agent.py
  plans and executes UI-grounded desktop actions

vision/ui_parser.py
  OmniParser/OpenAI/mock parser adapters

connectors/openai_client.py
  OpenAI vision, text, and JSON helpers

app/holo_overlay.py
  orb, chat panel, mission UI, games

agents/memory_agent.py
  session/app usage logging and summaries
```

## Immediate Next Step

Do this next:

1. Start OmniParser.
2. Start HoloDesk.
3. Run:

```text
test UI parser
```

4. Send the result/logs.

That tells us whether HoloDesk can actually see UI elements on your machine.

After that, the next coding tasks should be:

```text
Make Gmail draft workflow reliable using the real OmniParser output from my screen.
Make English and Nepali versions of the same Gmail command produce the same safe workflow.
Reduce OmniParser lag with caching/cropping/active-window parsing.
```

That is the most important next milestone before expanding to more languages or more apps.
