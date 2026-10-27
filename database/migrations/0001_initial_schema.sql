-- ============================================================================
-- PragyaX PostgreSQL Database Migration
-- Version: 0001
-- Description: Baseline schema definition for all 10 core application tables.
-- Author: Nagin (Senior Database Architect & Supabase Specialist)
-- Target: PostgreSQL 14+ / Supabase PostgreSQL
-- 
-- NOTES & DESIGN DECISIONS:
-- 1. Preserves existing VARCHAR string primary and foreign keys (e.g. 'usr_...', 'subj_...').
--    Does NOT alter IDs to UUIDs to maintain complete compatibility with FastAPI schemas.
-- 2. Preserves table and column contracts established in database/schema.sql.
-- 3. Topological table ordering respects foreign key dependency chains.
-- 4. Uses CREATE TABLE IF NOT EXISTS. On an existing populated database, existing
--    tables will remain untouched. Column extensions are handled in subsequent migrations.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Users Table (Core Learner Identity)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    salt VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- 2. Subjects Table (Curriculum Directory)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS subjects (
    id VARCHAR(64) PRIMARY KEY,
    slug VARCHAR(64) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    icon VARCHAR(64) NOT NULL DEFAULT 'code',
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    question_count INT NOT NULL DEFAULT 5,
    difficulty VARCHAR(32) NOT NULL DEFAULT 'Beginner to Intermediate'
);

-- ----------------------------------------------------------------------------
-- 3. User Preferences (Selected Subject & Learning Profile)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id VARCHAR(64) PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    selected_subject_id VARCHAR(64) NOT NULL DEFAULT 'subj_python',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- 4. Assessment Questions (Deterministic Curriculum Questions)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS assessment_questions (
    id VARCHAR(64) PRIMARY KEY,
    subject_id VARCHAR(64) REFERENCES subjects(id) ON DELETE CASCADE,
    question_number INT NOT NULL,
    question_text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_option VARCHAR(4) NOT NULL,
    explanation TEXT NOT NULL,
    topic VARCHAR(128) NOT NULL,
    difficulty VARCHAR(32) NOT NULL DEFAULT 'Intermediate'
);

-- ----------------------------------------------------------------------------
-- 5. Learning Chat Messages (Persistent Discussion Threads)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_messages (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject VARCHAR(64) NOT NULL DEFAULT 'Python Programming',
    role VARCHAR(16) NOT NULL,
    content TEXT NOT NULL,
    suggested_followups TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- 6. Assessment Attempts (Persisted Evaluation Outcomes & AI Feedback)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS assessment_attempts (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_id VARCHAR(64) NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    score INT NOT NULL,
    total INT NOT NULL,
    percentage DOUBLE PRECISION NOT NULL,
    proficiency_level VARCHAR(32) NOT NULL,
    summary_feedback TEXT NOT NULL,
    recommended_topics TEXT NOT NULL,
    user_answers TEXT NOT NULL,
    breakdown TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- 7. Daily Challenges (Gamified Code Snippet Challenges)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS daily_challenges (
    id VARCHAR(64) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    topic VARCHAR(128) NOT NULL,
    difficulty VARCHAR(32) NOT NULL DEFAULT 'Medium',
    description TEXT NOT NULL,
    code_snippet TEXT NOT NULL,
    question_type VARCHAR(32) NOT NULL DEFAULT 'multiple_choice',
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_option VARCHAR(4) NOT NULL,
    explanation TEXT NOT NULL,
    points INT NOT NULL DEFAULT 50,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- 8. User Challenge Submissions (Daily Challenge Completion Tracking)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_challenge_submissions (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    challenge_id VARCHAR(64) NOT NULL REFERENCES daily_challenges(id) ON DELETE CASCADE,
    submitted_answer VARCHAR(32) NOT NULL,
    is_correct BOOLEAN NOT NULL,
    points_awarded INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_user_challenge UNIQUE (user_id, challenge_id)
);

-- ----------------------------------------------------------------------------
-- 9. User Badges & Achievements (Learner Milestones & Accolades)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_badges (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    badge_key VARCHAR(64) NOT NULL,
    title VARCHAR(128) NOT NULL,
    description TEXT NOT NULL,
    icon VARCHAR(64) NOT NULL,
    awarded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_user_badge UNIQUE (user_id, badge_key)
);

-- ----------------------------------------------------------------------------
-- 10. Active Sessions (Backend Bearer Session Store)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS active_sessions (
    token VARCHAR(128) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
