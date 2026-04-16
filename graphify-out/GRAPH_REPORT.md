# Graph Report - .  (2026-04-14)

## Corpus Check
- 21 files · ~22,617 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 222 nodes · 354 edges · 18 communities detected
- Extraction: 81% EXTRACTED · 19% INFERRED · 0% AMBIGUOUS · INFERRED: 66 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]

## God Nodes (most connected - your core abstractions)
1. `TaskAgent` - 33 edges
2. `MemoryAgent` - 25 edges
3. `VoiceAssistantThread` - 20 edges
4. `OrchestratorAgent` - 17 edges
5. `ChatAgent` - 16 edges
6. `VisionThread` - 14 edges
7. `GroqClient` - 12 edges
8. `CameraThread` - 12 edges
9. `OpenAIClient` - 11 edges
10. `Database` - 11 edges

## Surprising Connections (you probably didn't know these)
- `VisionThread — reads camera frames, runs MediaPipe, detects gestures.  Outputs` --uses--> `GestureDetector`  [INFERRED]
  core\vision_thread.py → vision\gesture_detector.py
- `Replace stale landmark data with fresh (maxsize=1 queue).` --uses--> `GestureDetector`  [INFERRED]
  core\vision_thread.py → vision\gesture_detector.py
- `ChatResult` --uses--> `GroqClient`  [INFERRED]
  agents\chat_agent.py → connectors\groq_client.py
- `VoiceAssistantThread` --uses--> `ChatAgent`  [INFERRED]
  app\main.py → agents\chat_agent.py
- `Makes the Pygame window transparent and always-on-top.          What this does` --uses--> `ChatAgent`  [INFERRED]
  app\main.py → agents\chat_agent.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.08
Nodes (19): CameraThread, CameraThread — captures webcam frames on a dedicated daemon thread.  The main, analyze_screen(), ask_ai(), Ask the AI a question and get a response, Stop the AI from speaking immediately, Sequential state machine — the production pattern used by every working     voi, Detect if transcribed text is actually the AI's own speech (echo). (+11 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (20): _get_active_window(), _is_blocked(), MemoryAgent, MemoryAgent — Passive session logging and habit detection.  What this does:, Create a new session row and return its id.         Call this once when HoloDes, Close the current session. Call this on HoloDesk exit., Start the 60-second background logger thread.         Safe to call multiple tim, Signal the logger thread to stop gracefully. (+12 more)

### Community 2 - "Community 2"
Cohesion: 0.12
Nodes (11): _contains_blocked(), _extract_after(), _extract_email_recipient(), _extract_search_engine(), _extract_search_query(), _extract_subject(), _extract_text_payload(), _looks_like_cancel() (+3 more)

### Community 3 - "Community 3"
Cohesion: 0.11
Nodes (12): ChatAgent, ChatResult, General conversation agent.     - Keeps short rolling history (MAX_HISTORY turn, Returns: {success: bool, response: str}, GroqClient, GroqClient — wrapper around the Groq Python SDK.  Used by morning_briefing.py, Initialize the Groq client on first use. Raises clearly if key is missing., Send a prompt to Groq and return the response text.          Args: (+4 more)

### Community 4 - "Community 4"
Cohesion: 0.14
Nodes (10): OpenAIClient, OpenAI client for GPT-4o Vision.  Only used for screen analysis — triggered ex, Lazy-load the OpenAI client. Raises clear error if key is missing., Send a base64-encoded image to GPT-4o Vision and return the response., _error(), ScreenAgent — Takes a screenshot and asks GPT-4o Vision to explain it.  Trigge, Take a full screenshot and resize to TARGET_WIDTH., Convert a PIL Image to a base64 PNG string. (+2 more)

### Community 5 - "Community 5"
Cohesion: 0.14
Nodes (10): conn(), Database, Thread-safe SQLite database wrapper for HoloDesk.  Key design decisions: - Ea, Return the first matching row as a dict, or None., Close the current thread's connection (call at thread exit)., Run schema.sql once to create all tables and indexes if missing., Insert a row and return the new row id., Update rows matching the WHERE clause. (+2 more)

### Community 6 - "Community 6"
Cohesion: 0.18
Nodes (11): _extract_after_any(), _extract_number(), _extract_urlish(), _format_habits(), _looks_like_site_name_or_url(), _looks_like_web_intent(), _looks_parallel(), _merge_results() (+3 more)

### Community 7 - "Community 7"
Cohesion: 0.27
Nodes (5): _finger_up(), GestureDetector, GestureDetector — debounced V_GESTURE and OPEN_PALM detection.  ONLY these two, Analyze one frame of hand landmarks.         Returns "V_GESTURE", "OPEN_PALM",, Classify the current hand pose into a gesture name or None.         Uses tip-vs

### Community 8 - "Community 8"
Cohesion: 0.4
Nodes (5): _insert_demo_data(), on_startup(), Startup module — runs once before the Pygame overlay initialises.  Responsibil, Called once before pygame.init().      Generates a morning briefing and stores, Insert fake app_events and a completed session if the DB looks empty.     Guard

### Community 9 - "Community 9"
Cohesion: 0.67
Nodes (1): HoloDesk Memory Logger — Run this NOW to start collecting habit data.  This is

### Community 10 - "Community 10"
Cohesion: 1.0
Nodes (1): Shared queues — the only communication channel between threads.  Rules:   - T

### Community 11 - "Community 11"
Cohesion: 1.0
Nodes (0): 

### Community 12 - "Community 12"
Cohesion: 1.0
Nodes (0): 

### Community 13 - "Community 13"
Cohesion: 1.0
Nodes (0): 

### Community 14 - "Community 14"
Cohesion: 1.0
Nodes (1): Return this thread's dedicated SQLite connection, creating if needed.

### Community 15 - "Community 15"
Cohesion: 1.0
Nodes (0): 

### Community 16 - "Community 16"
Cohesion: 1.0
Nodes (1): Return True if the fingertip is above its base joint.         In MediaPipe's no

### Community 17 - "Community 17"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **45 isolated node(s):** `HoloDesk Memory Logger — Run this NOW to start collecting habit data.  This is`, `MemoryAgent — Passive session logging and habit detection.  What this does:`, `Return (app_name, window_title) for the currently focused window.     Returns (`, `Passive logger + habit detector.     One instance is shared across the applicat`, `Create a new session row and return its id.         Call this once when HoloDes` (+40 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 10`** (2 nodes): `queues.py`, `Shared queues — the only communication channel between threads.  Rules:   - T`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 11`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 12`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 13`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 14`** (1 nodes): `Return this thread's dedicated SQLite connection, creating if needed.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 15`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 16`** (1 nodes): `Return True if the fingertip is above its base joint.         In MediaPipe's no`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 17`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskAgent` connect `Community 2` to `Community 0`, `Community 3`, `Community 4`?**
  _High betweenness centrality (0.344) - this node is a cross-community bridge._
- **Why does `MemoryAgent` connect `Community 1` to `Community 0`?**
  _High betweenness centrality (0.234) - this node is a cross-community bridge._
- **Why does `VoiceAssistantThread` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 6`?**
  _High betweenness centrality (0.140) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `TaskAgent` (e.g. with `GroqClient` and `OpenAIClient`) actually correct?**
  _`TaskAgent` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `MemoryAgent` (e.g. with `VoiceAssistantThread` and `Makes the Pygame window transparent and always-on-top.          What this does`) actually correct?**
  _`MemoryAgent` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `VoiceAssistantThread` (e.g. with `CameraThread` and `VisionThread`) actually correct?**
  _`VoiceAssistantThread` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `OrchestratorAgent` (e.g. with `VoiceAssistantThread` and `Makes the Pygame window transparent and always-on-top.          What this does`) actually correct?**
  _`OrchestratorAgent` has 8 INFERRED edges - model-reasoned connections that need verification._