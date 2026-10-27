-- ============================================================================
-- PragyaX PostgreSQL Database Migration
-- Version: 0003
-- Description: Security hardening, PostgREST API isolation, and index optimization.
-- Author: Nagin (Senior Database Architect & Supabase Security Specialist)
-- Target: PostgreSQL 14+ / Supabase PostgreSQL
-- 
-- SECURITY OBJECTIVES:
-- 1. Eliminate public PostgREST API exposure of sensitive learner data to anon / authenticated.
-- 2. Enable Row-Level Security (RLS) in Default-Deny mode across public tables.
-- 3. Preserve FastAPI backend operations connecting via privileged service role / DATABASE_URL.
-- 4. Eliminate redundant index on assessment_questions(subject_id).
-- 5. Use defensive to_regclass checks to guarantee safe execution on any deployment state.
-- ============================================================================

-- ============================================================================
-- PART 1: MIGRATION PREREQUISITE & ORDERING DEFENSE
-- ============================================================================
DO $$
BEGIN
    -- Verify that migration 0001 baseline tables exist before applying hardening
    IF to_regclass('public.users') IS NULL THEN
        RAISE EXCEPTION 'Migration order violation: public.users does not exist. Please apply 0001_initial_schema.sql first.';
    END IF;
END $$;


-- ============================================================================
-- PART 2: INDEX OPTIMIZATION (CORRECTIVE CLEANUP)
-- ============================================================================

-- If the composite unique constraint uq_assessment_questions_subject_number exists
-- on (subject_id, question_number), the standalone single-column index on (subject_id)
-- is redundant because subject_id is the leading column of the unique index.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM pg_constraint 
        WHERE conname = 'uq_assessment_questions_subject_number'
          AND conrelid = to_regclass('public.assessment_questions')
    ) THEN
        DROP INDEX IF EXISTS idx_assessment_questions_subject;
    END IF;
END $$;


-- ============================================================================
-- PART 3: PERMISSION REVOCATION (SEAL POSTGREST PUBLIC API)
-- ============================================================================
-- In Supabase, all tables in schema public are exposed via PostgREST by default.
-- Because PragyaX uses backend-mediated architecture (React -> FastAPI -> Postgres),
-- direct client access via anon or authenticated roles MUST be revoked.

-- 1. Revoke all privileges on student identity and credentials
REVOKE ALL ON TABLE users FROM anon, authenticated;
REVOKE ALL ON TABLE active_sessions FROM anon, authenticated;

-- 2. Revoke all privileges on private student activity and evaluation records
REVOKE ALL ON TABLE assessment_attempts FROM anon, authenticated;
REVOKE ALL ON TABLE chat_messages FROM anon, authenticated;
REVOKE ALL ON TABLE user_preferences FROM anon, authenticated;
REVOKE ALL ON TABLE user_challenge_submissions FROM anon, authenticated;
REVOKE ALL ON TABLE user_badges FROM anon, authenticated;

-- 3. Revoke all privileges on curriculum questions (protects correct_option and explanations)
REVOKE ALL ON TABLE assessment_questions FROM anon, authenticated;

-- 4. Curriculum catalog and challenges:
-- Revoke all write/modification permissions. Only the backend manages these records.
REVOKE ALL ON TABLE subjects FROM anon, authenticated;
REVOKE ALL ON TABLE daily_challenges FROM anon, authenticated;


-- ============================================================================
-- PART 4: DEFENSE-IN-DEPTH ROW LEVEL SECURITY (RLS)
-- ============================================================================
-- Enabling RLS on tables without defining permissive policies enforces an automatic
-- "DEFAULT DENY" for unprivileged client roles (anon, authenticated).
-- The FastAPI backend connecting with DATABASE_URL (superuser or BYPASSRLS role)
-- bypasses RLS cleanly, preventing any disruption to the application flow.

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE subjects ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessment_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessment_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_challenges ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_challenge_submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_badges ENABLE ROW LEVEL SECURITY;
ALTER TABLE active_sessions ENABLE ROW LEVEL SECURITY;
