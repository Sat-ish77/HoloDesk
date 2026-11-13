# Graph Report - .  (2026-04-21)

## Corpus Check
- 21 files · ~27,305 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 251 nodes · 422 edges · 18 communities detected
- Extraction: 80% EXTRACTED · 20% INFERRED · 0% AMBIGUOUS · INFERRED: 84 edges (avg confidence: 0.5)
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
1. `TaskAgent` - 46 edges
2. `MemoryAgent` - 26 edges
3. `VoiceAssistantThread` - 21 edges
4. `OrchestratorAgent` - 19 edges
5. `GroqClient` - 18 edges
6. `ChatAgent` - 17 edges
7. `OpenAIClient` - 17 edges
8. `VisionThread` - 15 edges
9. `CameraThread` - 13 edges
10. `Database` - 11 edges

## Surprising Connections (you probably didn't know these)
- `General conversation agent.     - Keeps short rolling history (MAX_HISTORY turn` --uses--> `GroqClient`  [INFERRED]
  agents\chat_agent.py → connectors\groq_client.py
- `Returns: {success: bool, response: str}` --uses--> `GroqClient`  [INFERRED]
  agents\chat_agent.py → connectors\groq_client.py
- `Replace stale landmark data with fresh (maxsize=1 queue).` --uses--> `GestureDetector`  [INFERRED]
  core\vision_thread.py → vision\gesture_detector.py
- `ChatResult` --uses--> `GroqClient`  [INFERRED]
  agents\chat_agent.py → connectors\groq_client.py
- `ChatAgent` --uses--> `GroqClient`  [INFERRED]
  agents\chat_agent.py → connectors\groq_client.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.08
Nodes (15): _build_url_from_site_name(), _contains_blocked(), _extract_after(), _extract_email_recipient(), _extract_search_engine(), _extract_search_query(), _extract_subject(), _extract_text_payload() (+7 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (25): ChatResult, GroqClient, GroqClient — wrapper around the Groq Python SDK.  Used by morning_briefing.py, Initialize the Groq client on first use. Raises clearly if key is missing., Send a prompt to Groq and return the response text.          Args:, generate_briefing(), MorningBriefingAgent — generates a personalized spoken briefing on startup.  R, Generate a morning briefing string.      Args:         demo_mode: If True, sk (+17 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (20): _get_active_window(), _is_blocked(), MemoryAgent, MemoryAgent — Passive session logging and habit detection.  What this does:, Create a new session row and return its id.         Call this once when HoloDes, Close the current session. Call this on HoloDesk exit., Start the 60-second background logger thread.         Safe to call multiple tim, Signal the logger thread to stop gracefully. (+12 more)

### Community 3 - "Community 3"
Cohesion: 0.09
Nodes (20): CameraThread, CameraThread — captures webcam frames on a dedicated daemon thread.  The main, ChatAgent, General conversation agent.     - Keeps short rolling history (MAX_HISTORY turn, Returns: {success: bool, response: str}, analyze_screen(), ask_ai(), _normalize_transcript() (+12 more)

### Community 4 - "Community 4"
Cohesion: 0.16
Nodes (12): Moonshine fallback transcription.         Requires:           ENABLE_MOONSHINE, _extract_after_any(), _extract_number(), _extract_urlish(), _format_habits(), _looks_like_site_name_or_url(), _looks_like_web_intent(), _looks_parallel() (+4 more)

### Community 5 - "Community 5"
Cohesion: 0.14
Nodes (10): conn(), Database, Thread-safe SQLite database wrapper for HoloDesk.  Key design decisions: - Ea, Return the first matching row as a dict, or None., Close the current thread's connection (call at thread exit)., Run schema.sql once to create all tables and indexes if missing., Insert a row and return the new row id., Update rows matching the WHERE clause. (+2 more)

### Community 6 - "Community 6"
Cohesion: 0.25
Nodes (2): speak(), VoiceAssistantThread

### Community 7 - "Community 7"
Cohesion: 0.21
Nodes (6): _finger_up(), GestureDetector, GestureDetector — debounced V_GESTURE and OPEN_PALM detection.  ONLY these two, Analyze one frame of hand landmarks.         Returns "V_GESTURE", "OPEN_PALM",, Classify the current hand pose into a gesture name or None.         Uses tip-vs, VisionThread — reads camera frames, runs MediaPipe, detects gestures.  Outputs

### Community 8 - "Community 8"
Cohesion: 0.4
Nodes (5): _insert_demo_data(), on_startup(), Startup module — runs once before the Pygame overlay initialises.  Responsibil, Called once before pygame.init().      Generates a morning briefing and stores, Insert fake app_events and a completed session if the DB looks empty.     Guard

### Community 9 - "Community 9"
Cohesion: 0.4
Nodes (3): Shared queues + small shared state — the only communication channel between thre, Called by speak() after a TTS utterance completes., record_tts_finished()

### Community 10 - "Community 10"
Cohesion: 0.67
Nodes (1): HoloDesk Memory Logger — Run this NOW to start collecting habit data.  This is

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
- **47 isolated node(s):** `HoloDesk Memory Logger — Run this NOW to start collecting habit data.  This is`, `MemoryAgent — Passive session logging and habit detection.  What this does:`, `Return (app_name, window_title) for the currently focused window.     Returns (`, `Passive logger + habit detector.     One instance is shared across the applicat`, `Create a new session row and return its id.         Call this once when HoloDes` (+42 more)
  These have ≤1 connection - possible missing edges or undocumented components.
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

- **Why does `TaskAgent` connect `Community 0` to `Community 1`, `Community 3`, `Community 4`, `Community 6`?**
  _High betweenness centrality (0.384) - this node is a cross-community bridge._
- **Why does `MemoryAgent` connect `Community 2` to `Community 3`, `Community 4`, `Community 6`?**
  _High betweenness centrality (0.212) - this node is a cross-community bridge._
- **Why does `OpenAIClient` connect `Community 1` to `Community 0`?**
  _High betweenness centrality (0.134) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `TaskAgent` (e.g. with `GroqClient` and `OpenAIClient`) actually correct?**
  _`TaskAgent` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `MemoryAgent` (e.g. with `VoiceAssistantThread` and `Makes the Pygame window transparent and always-on-top.          What this does`) actually correct?**
  _`MemoryAgent` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `VoiceAssistantThread` (e.g. with `CameraThread` and `VisionThread`) actually correct?**
  _`VoiceAssistantThread` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `OrchestratorAgent` (e.g. with `VoiceAssistantThread` and `Makes the Pygame window transparent and always-on-top.          What this does`) actually correct?**
  _`OrchestratorAgent` has 9 INFERRED edges - model-reasoned connections that need verification._