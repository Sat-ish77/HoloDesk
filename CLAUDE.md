# HoloDesk (brain v3)

Current task and full context: `docs/HANDOFF_ROUND4.md`. Read it first.
Done: round 1 `docs/HANDOFF_PLAYWRIGHT.md`, round 2 `docs/HANDOFF_ROUND2.md`, round 3 `docs/HANDOFF_ROUND3.md`.

## Save tokens

- Find code with the graph, not by reading files. `graphify-out/graph.json` is a
  code map (896 nodes). Install once: `pip install graphifyy`, then
  `graphify query "<question>" --budget 800`, `graphify explain "<Symbol>"`,
  `graphify path "<A>" "<B>"`. Each answer names the file and line (`src=... loc=L..`).
  If install fails, read `graphify-out/GRAPH_REPORT.md` once as the map.
- Then read only ~40 lines around that location. Never read whole large files:
  `app/main.py`, `agents/task_agent.py`, `brain/engine.py`, `brain/tools/desktop.py`.
- Never read `graphify-out/cache/`, `node_modules`, `.venv`, `artifacts/`.
- Read old-branch code with `git show origin/<branch>:<path>`; don't check it out.
- After changing code: `graphify update .` (code only, no API cost) and commit
  `graphify-out/graph.json` + `graphify-out/GRAPH_REPORT.md` only.

## Rules

- Tests: `python -m pytest -q` must stay green (132 at handoff).
- Safety: DANGER actions go through `brain/policy.py`; no second confirm system.
  Never handle passwords.
- Minimal diffs. Comments say why, not what. No unrequested refactors or docs.
- The user runs Windows; this code is tested in the cloud with mocks only.
  Say plainly what you could not run.
