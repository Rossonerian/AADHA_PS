-- Education module tables (SoT Section 6) for raw sqlite3 connections.
-- Mirrors Alembic revision 20261120_01_edu; used by
-- app.education.repository.apply_migrations for standalone SQLite databases.
-- Idempotent: safe to run on a fresh or existing database.

-- `users` is owned by the core platform (Alembic 0001_initial_platform).
-- Created here only when absent so standalone SQLite DBs can satisfy FKs.
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    current_level INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_users_current_level_range CHECK (current_level >= 1 AND current_level <= 4)
);

CREATE TABLE IF NOT EXISTS unlocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    tool TEXT NOT NULL,
    unlocked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_unlocks_user_tool UNIQUE (user_id, tool),
    CONSTRAINT ck_unlocks_tool CHECK (
        tool IN ('scenarios','red_flag_check','explain_stock','verifier','dashboard')
    )
);
CREATE INDEX IF NOT EXISTS ix_unlocks_user_id ON unlocks (user_id);

CREATE TABLE IF NOT EXISTS skill_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    skill_area TEXT NOT NULL,
    score REAL NOT NULL,
    brier REAL NOT NULL,
    measured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_skill_scores_area CHECK (
        skill_area IN ('basics','reading_stock','judging_info','risk')
    ),
    CONSTRAINT ck_skill_scores_range CHECK (score >= 0 AND score <= 100),
    CONSTRAINT ck_skill_scores_brier CHECK (brier >= 0 AND brier <= 1)
);
CREATE INDEX IF NOT EXISTS ix_skill_scores_user_measured ON skill_scores (user_id, measured_at);

CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    level INTEGER NOT NULL,
    skill_area TEXT NOT NULL,
    difficulty INTEGER NOT NULL,
    text TEXT NOT NULL,
    options TEXT NOT NULL,
    answer TEXT NOT NULL,
    explanation TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    data_origin TEXT NOT NULL DEFAULT 'synthetic',
    CONSTRAINT ck_questions_level CHECK (level BETWEEN 1 AND 4),
    CONSTRAINT ck_questions_difficulty CHECK (difficulty BETWEEN 1 AND 5),
    CONSTRAINT ck_questions_skill_area CHECK (
        skill_area IN ('basics','reading_stock','judging_info','risk')
    ),
    CONSTRAINT ck_questions_origin CHECK (data_origin IN ('real','synthetic'))
);
CREATE INDEX IF NOT EXISTS ix_questions_level_skill_diff
    ON questions (level, skill_area, difficulty);

CREATE TABLE IF NOT EXISTS attempts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    item_type TEXT NOT NULL,
    item_id TEXT NOT NULL,
    answer TEXT NOT NULL,
    confidence INTEGER NOT NULL,
    correct INTEGER NOT NULL,
    context TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_attempts_item_type CHECK (
        item_type IN ('question','scenario','verifier_guess')
    ),
    CONSTRAINT ck_attempts_confidence CHECK (confidence BETWEEN 50 AND 100),
    CONSTRAINT ck_attempts_context CHECK (
        context IN ('onboarding','lesson','assessment','practice','study_pre','study_post')
    )
);
CREATE INDEX IF NOT EXISTS ix_attempts_user_context ON attempts (user_id, context, created_at);
CREATE INDEX IF NOT EXISTS ix_attempts_user_item ON attempts (user_id, item_type, item_id);

CREATE TABLE IF NOT EXISTS lessons (
    id TEXT PRIMARY KEY,
    level INTEGER NOT NULL,
    skill_area TEXT NOT NULL,
    title TEXT NOT NULL,
    minutes INTEGER NOT NULL,
    sections TEXT NOT NULL,
    check_questions TEXT NOT NULL,
    data_origin TEXT NOT NULL DEFAULT 'synthetic',
    CONSTRAINT ck_lessons_level CHECK (level BETWEEN 1 AND 4),
    CONSTRAINT ck_lessons_skill_area CHECK (
        skill_area IN ('basics','reading_stock','judging_info','risk')
    ),
    CONSTRAINT ck_lessons_minutes CHECK (minutes BETWEEN 1 AND 60),
    CONSTRAINT ck_lessons_origin CHECK (data_origin IN ('real','synthetic'))
);

CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    level INTEGER NOT NULL DEFAULT 1,
    lesson_ids TEXT NOT NULL,
    progress TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_plans_user_id UNIQUE (user_id),
    CONSTRAINT ck_plans_level CHECK (level BETWEEN 1 AND 4)
);

CREATE TABLE IF NOT EXISTS scenarios (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    window_days INTEGER NOT NULL,
    context TEXT NOT NULL,
    outcome TEXT NOT NULL,
    explanation TEXT NOT NULL,
    key_clues TEXT NOT NULL,
    tags TEXT NOT NULL,
    difficulty INTEGER NOT NULL,
    data_origin TEXT NOT NULL,
    CONSTRAINT ck_scenarios_difficulty CHECK (difficulty BETWEEN 1 AND 5),
    CONSTRAINT ck_scenarios_window_days CHECK (window_days > 0),
    CONSTRAINT ck_scenarios_origin CHECK (data_origin IN ('real','synthetic'))
);
CREATE INDEX IF NOT EXISTS ix_scenarios_difficulty ON scenarios (difficulty);

CREATE TABLE IF NOT EXISTS edu_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    session_type TEXT NOT NULL,
    target_level INTEGER,
    state TEXT NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS edu_explain_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    year INTEGER NOT NULL,
    chart TEXT NOT NULL,
    moves TEXT NOT NULL,
    summary TEXT NOT NULL,
    data_origin TEXT NOT NULL,
    CONSTRAINT uq_explain_symbol_year UNIQUE (symbol, year),
    CONSTRAINT ck_explain_origin CHECK (data_origin IN ('real','synthetic'))
);
