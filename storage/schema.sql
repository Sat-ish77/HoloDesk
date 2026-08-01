-- HoloDesk v2 — SQLite Schema
-- Plain SQLite (no encryption dependency — reliable on all Windows machines)
-- WAL mode is enabled in db.py for concurrent reads/writes

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    created_at      TEXT    DEFAULT (datetime('now')),
    last_seen       TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                 INTEGER REFERENCES users(id),
    start_time              TEXT    NOT NULL,
    end_time                TEXT,
    total_duration_minutes  INTEGER
);

-- Every active window is logged here every 60 seconds.
-- This is the raw data that feeds habit detection.
CREATE TABLE IF NOT EXISTS app_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER REFERENCES sessions(id),
    app_name        TEXT    NOT NULL,
    window_title    TEXT,
    timestamp       TEXT    NOT NULL,
    day_of_week     INTEGER,   -- 0=Monday, 6=Sunday (Python weekday())
    hour_of_day     INTEGER    -- 0-23
);

CREATE TABLE IF NOT EXISTS voice_commands (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER REFERENCES sessions(id),
    command_text    TEXT    NOT NULL,
    response_summary TEXT,
    agent_used      TEXT,
    timestamp       TEXT    NOT NULL
);

-- Computed habit patterns (built from app_events via SQL queries)
CREATE TABLE IF NOT EXISTS habit_patterns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER REFERENCES users(id),
    pattern_type    TEXT,   -- e.g. "morning_app", "evening_routine"
    pattern_data    TEXT,   -- JSON string with pattern details
    confidence_score REAL,
    last_computed   TEXT,
    times_confirmed INTEGER DEFAULT 0
);

-- Tracks whether HoloDesk suggestions were accepted or dismissed.
-- This is how the system learns to surface fewer bad suggestions over time.
CREATE TABLE IF NOT EXISTS feedback_events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          INTEGER REFERENCES sessions(id),
    trigger_type        TEXT,   -- "proactive" or "reactive"
    agent_used          TEXT,
    user_accepted       INTEGER DEFAULT 0,  -- 1 = accepted
    user_dismissed      INTEGER DEFAULT 0,  -- 1 = dismissed
    response_latency_ms INTEGER,
    timestamp           TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS preferences (
    key         TEXT PRIMARY KEY,
    value       TEXT,
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reminders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    due_at          TEXT NOT NULL,
    status          TEXT DEFAULT 'pending',
    source_text     TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    completed_at    TEXT
);

-- Fast lookups for habit queries (app + time slot combinations)
CREATE INDEX IF NOT EXISTS idx_app_events_app_time
    ON app_events(app_name, hour_of_day, day_of_week);

CREATE INDEX IF NOT EXISTS idx_app_events_session
    ON app_events(session_id);

CREATE INDEX IF NOT EXISTS idx_app_events_timestamp
    ON app_events(timestamp);

CREATE INDEX IF NOT EXISTS idx_feedback_agent
    ON feedback_events(agent_used, user_accepted);

CREATE INDEX IF NOT EXISTS idx_reminders_due
    ON reminders(status, due_at);
