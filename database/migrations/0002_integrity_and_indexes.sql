-- ============================================================================
-- PragyaX PostgreSQL Database Migration
-- Version: 0002
-- Description: Indexes for critical query paths and non-destructive integrity constraints.
-- Author: Nagin (Senior Database Architect & Supabase Specialist)
-- Target: PostgreSQL 14+ / Supabase PostgreSQL
-- 
-- DEPLOYMENT SAFETY NOTES:
-- 1. All index additions use CREATE INDEX IF NOT EXISTS to guarantee idempotent execution.
-- 2. All constraint additions are wrapped in idempotent DO $$ ... $$ blocks checking
--    pg_constraint to prevent syntax errors on already-migrated databases.
-- 3. Preflight data validation queries must be executed prior to running this migration
--    on a populated database (see database/migrations/README.md).
-- ============================================================================

-- ============================================================================
-- PART 1: PERFORMANCE INDEXES (NON-REDUNDANT)
-- ============================================================================

-- 1. Optimize student assessment history retrieval & dashboard metrics:
--    Used by: Repository.get_user_assessment_attempts and Repository.get_user_dashboard_metrics
--    Query pattern: WHERE user_id = ? ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_assessment_attempts_user_created 
    ON assessment_attempts (user_id, created_at DESC);

-- 2. Optimize chat history retrieval for context loading:
--    Used by: Repository.get_chat_history
--    Query pattern: WHERE user_id = ? ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_created 
    ON chat_messages (user_id, created_at DESC);

-- 3. Optimize assessment question lookup by subject:
--    Used by: Repository.get_assessment_questions and Repository.get_raw_assessment_questions_with_answers
--    Query pattern: WHERE subject_id = ? ORDER BY question_number ASC
CREATE INDEX IF NOT EXISTS idx_assessment_questions_subject 
    ON assessment_questions (subject_id);

-- 4. Optimize user badge milestone loading:
--    Used by: Repository.get_user_badges
--    Query pattern: WHERE user_id = ? ORDER BY awarded_at DESC
CREATE INDEX IF NOT EXISTS idx_user_badges_user_awarded 
    ON user_badges (user_id, awarded_at DESC);

-- 5. Optimize session token cleanup and user verification:
--    Used by: Repository.get_user_by_token
--    Query pattern: JOIN users u ON s.user_id = u.id WHERE s.token = ?
CREATE INDEX IF NOT EXISTS idx_active_sessions_user_id 
    ON active_sessions (user_id);


-- ============================================================================
-- PART 2: INTEGRITY CONSTRAINTS & REFERENTIAL GUARDS
-- ============================================================================

-- 6. Add Foreign Key on user_preferences.selected_subject_id -> subjects(id)
--    Guarantees user preferences cannot reference a non-existent subject.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_constraint 
        WHERE conname = 'fk_user_preferences_subject' 
          AND conrelid = 'user_preferences'::regclass
    ) THEN
        ALTER TABLE user_preferences
            ADD CONSTRAINT fk_user_preferences_subject
            FOREIGN KEY (selected_subject_id)
            REFERENCES subjects(id)
            ON DELETE RESTRICT;
    END IF;
END $$;

-- 7. Add Unique Constraint on (subject_id, question_number)
--    Enforces the curriculum contract of unique, numbered questions per subject.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_constraint 
        WHERE conname = 'uq_assessment_questions_subject_number' 
          AND conrelid = 'assessment_questions'::regclass
    ) THEN
        ALTER TABLE assessment_questions
            ADD CONSTRAINT uq_assessment_questions_subject_number
            UNIQUE (subject_id, question_number);
    END IF;
END $$;

-- 8. Add Check Constraint on assessment_questions.correct_option
--    Prevents insertion of invalid MCQ answer keys (only A, B, C, D accepted).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_constraint 
        WHERE conname = 'chk_assessment_questions_correct_opt' 
          AND conrelid = 'assessment_questions'::regclass
    ) THEN
        ALTER TABLE assessment_questions
            ADD CONSTRAINT chk_assessment_questions_correct_opt
            CHECK (correct_option IN ('A', 'B', 'C', 'D'));
    END IF;
END $$;

-- 9. Add Check Constraint on chat_messages.role
--    Restricts message sender role to valid conversational actors.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_constraint 
        WHERE conname = 'chk_chat_messages_role' 
          AND conrelid = 'chat_messages'::regclass
    ) THEN
        ALTER TABLE chat_messages
            ADD CONSTRAINT chk_chat_role
            CHECK (role IN ('user', 'assistant'));
    END IF;
END $$;

-- 10. Add Check Constraint on daily_challenges.correct_option
--     Prevents invalid answer keys on Ankush's daily code snippet challenge.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_constraint 
        WHERE conname = 'chk_daily_challenges_correct_opt' 
          AND conrelid = 'daily_challenges'::regclass
    ) THEN
        ALTER TABLE daily_challenges
            ADD CONSTRAINT chk_daily_challenges_correct_opt
            CHECK (correct_option IN ('A', 'B', 'C', 'D'));
    END IF;
END $$;

-- 11. Enforce NOT NULL on assessment_questions.subject_id
--     Synchronizes PostgreSQL schema with backend SQLite definition (connection.py line 80).
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
          AND table_name = 'assessment_questions' 
          AND column_name = 'subject_id' 
          AND is_nullable = 'YES'
    ) THEN
        ALTER TABLE assessment_questions 
            ALTER COLUMN subject_id SET NOT NULL;
    END IF;
END $$;
