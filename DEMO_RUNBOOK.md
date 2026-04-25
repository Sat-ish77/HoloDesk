# HoloDesk UI Grounding Demo Runbook (Windows)

## Scope
This PR adds a first version of UI grounding structure for desktop control:
- screenshot-to-UI-element parser interface (`vision/ui_parser.py`)
- safety-aware planner + executor (`agents/desktop_grounding_agent.py`)
- OpenAI API-based screen verification command helper (`VerifyWithChatGPTVision`)
- dry-run tests for planner/safety (`tests/test_desktop_grounding.py`)

This runbook is intentionally safe-by-default and does not perform risky actions automatically.

## OmniParser Install Investigation (as of April 24, 2026)
Status in this automation environment:
- Network access to GitHub/PyPI from shell is blocked.
- Python executable is unavailable in this runner shell.
- OmniParser package cannot be installed or validated here.

Implemented fallback:
- `OmniParserAdapter` reports exact dependency/import blockers.
- `MockUIParser` provides deterministic element output for dry-runs.
- The planner/executor remains testable without OmniParser.

What to do on the Windows laptop tomorrow:
1. Confirm Python is available: `python --version`
2. Install project deps: `pip install -r requirement.txt`
3. Install OmniParser per its official installation guide (CUDA/model deps if needed).
4. Replace placeholder runtime invocation inside `OmniParserAdapter.parse()` once package API is confirmed.

## Safety Rules in This Version
Blocked outright:
- login/sign-in/password actions
- payment/banking/transfer-money actions

Requires explicit confirmation before execution:
- send email
- delete file/folder
- shutdown/restart

Allowed in draft/safe flow:
- draft email content
- open app/website/folder
- click visible element by label
- type into focused field
- search inside Outlook

## Planner and Executor Behavior
Planner (`DesktopActionPlanner`):
- Converts natural command text into ordered `PlanStep` actions.
- Returns structured plan JSON (`safe`, `blocked_reason`, `steps`).

Executor (`DesktopActionExecutor`):
- Takes screenshot before each step and after each step.
- Runs parser on the pre-step screenshot.
- Resolves target element by label for click actions.
- Stops safely if parser output is unclear/unavailable.
- Supports `dry_run=True` to avoid live desktop actions.

## Verify with ChatGPT (OpenAI API, not website)
`VerifyWithChatGPTVision.run(question, screenshot_path)`:
- Reads screenshot file
- Sends screenshot + question to OpenAI vision API via `OpenAIClient`
- Returns concise verification answer

No live API calls are performed in automated tests.

## Optional Browser Experiment (Non-critical)
The planner supports website-open steps in specific browsers (`chrome`/`brave`) as an experiment. Main feature does not depend on ChatGPT website automation.

## Manual Windows Test Checklist
Use these tomorrow on the laptop:
1. Open Chrome.
2. Open Brave.
3. Open a folder.
4. Open a subfolder.
5. Open Outlook.
6. Search a person name in Outlook.
7. Draft an email in Outlook (do not send).
8. Analyze current screen using parser output.
9. Verify current screen with OpenAI vision.

## Suggested Local Smoke Commands
In a Python REPL or small script:
- Build plan: `DesktopActionPlanner().build_plan("open github in chrome")`
- Execute dry-run: `DesktopActionExecutor().execute_plan(plan, dry_run=True)`
- Verify screenshot: `VerifyWithChatGPTVision().run("What is open?", "C:/path/to/screenshot.png")`

## Known Limitations
- OmniParser runtime call is a blocker-aware placeholder until dependency install is possible.
- Element targeting relies on parser quality; low-confidence screens stop execution safely.
- No automated end-to-end desktop-action test is run in this environment.
- Windows GUI behavior must be manually validated tomorrow.
