-- Reverts Education module tables (SoT Section 6) for raw sqlite3 connections.
-- Mirrors Alembic revision 20261120_01_edu downgrade. `users` is owned by the
-- core platform and is intentionally left untouched.
DROP TABLE IF EXISTS edu_explain_cache;
DROP TABLE IF EXISTS edu_sessions;
DROP TABLE IF EXISTS scenarios;
DROP TABLE IF EXISTS plans;
DROP TABLE IF EXISTS lessons;
DROP TABLE IF EXISTS attempts;
DROP TABLE IF EXISTS questions;
DROP TABLE IF EXISTS skill_scores;
DROP TABLE IF EXISTS unlocks;
