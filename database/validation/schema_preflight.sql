-- ============================================================================
-- PragyaX PostgreSQL Integration Validation Package
-- File: schema_preflight.sql
-- Description: Read-only schema inspection queries for deployment preflight.
-- Author: Nagin (Senior Database Architect & Supabase Specialist)
-- Target: PostgreSQL 14+ / Supabase PostgreSQL
-- 
-- SAFETY GUARANTEES:
-- 1. STRICTLY READ-ONLY: Contains only SELECT queries querying information_schema
--    and system catalogs. Never executes DDL, DML, or DCL.
-- 2. ABSENT TABLE SAFETY: Queries against information_schema return empty result sets
--    rather than failing if expected tables are not yet created.
-- 3. ZERO SECRET EXPOSURE: Does not select password hashes, salts, or session tokens.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Existing Application Tables Check
-- Expected: Exactly 10 core tables in schema 'public'.
-- ----------------------------------------------------------------------------
SELECT 
    table_name,
    table_type
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN (
    'users', 'user_preferences', 'subjects', 'assessment_questions',
    'chat_messages', 'assessment_attempts', 'daily_challenges',
    'user_challenge_submissions', 'user_badges', 'active_sessions'
  )
ORDER BY table_name;

-- Summary Count (Expected: 10 when all migrations applied)
SELECT 
    COUNT(*) AS tables_found,
    CASE 
        WHEN COUNT(*) = 10 THEN 'PASS: All 10 application tables present'
        ELSE 'FAIL: Missing tables detected (check table list above)'
    END AS evaluation_status
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN (
    'users', 'user_preferences', 'subjects', 'assessment_questions',
    'chat_messages', 'assessment_attempts', 'daily_challenges',
    'user_challenge_submissions', 'user_badges', 'active_sessions'
  );


-- ----------------------------------------------------------------------------
-- 2. Primary Key & Unique Constraints Check
-- ----------------------------------------------------------------------------
SELECT 
    tc.table_name,
    tc.constraint_name,
    tc.constraint_type,
    kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu 
  ON tc.constraint_name = kcu.constraint_name 
 AND tc.table_schema = kcu.table_schema
WHERE tc.table_schema = 'public'
  AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE')
ORDER BY tc.table_name, tc.constraint_type, kcu.column_name;


-- ----------------------------------------------------------------------------
-- 3. Foreign Key Referential Integrity Check
-- ----------------------------------------------------------------------------
SELECT 
    tc.table_name AS child_table,
    kcu.column_name AS child_column,
    ccu.table_name AS parent_table,
    ccu.column_name AS parent_column,
    rc.delete_rule,
    tc.constraint_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu 
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.referential_constraints rc 
  ON tc.constraint_name = rc.constraint_name
JOIN information_schema.constraint_column_usage ccu 
  ON rc.unique_constraint_name = ccu.constraint_name
WHERE tc.table_schema = 'public'
  AND tc.constraint_type = 'FOREIGN KEY'
ORDER BY tc.table_name, kcu.column_name;


-- ----------------------------------------------------------------------------
-- 4. Check Constraints Verification
-- ----------------------------------------------------------------------------
SELECT 
    tc.table_name,
    tc.constraint_name,
    cc.check_clause
FROM information_schema.table_constraints tc
JOIN information_schema.check_constraints cc 
  ON tc.constraint_name = cc.constraint_name
WHERE tc.table_schema = 'public'
  AND tc.constraint_type = 'CHECK'
  AND tc.constraint_name NOT LIKE '%_not_null'
ORDER BY tc.table_name, tc.constraint_name;


-- ----------------------------------------------------------------------------
-- 5. Existing B-Tree Indexes Check
-- Expected: Composite indexes from 0002 (e.g. idx_assessment_attempts_user_created)
-- ----------------------------------------------------------------------------
SELECT 
    tablename,
    indexname,
    indexdef
FROM pg_indexes 
WHERE schemaname = 'public' 
  AND (indexname LIKE 'idx_%' OR indexname LIKE 'uq_%')
ORDER BY tablename, indexname;


-- ----------------------------------------------------------------------------
-- 6. Orphaned Subject Reference Preflight Check
-- Expected: 0 rows (No preferences point to non-existent subjects)
-- ----------------------------------------------------------------------------
SELECT 
    up.user_id,
    up.selected_subject_id,
    'Orphaned preference: subject does not exist in subjects table' AS issue_description
FROM user_preferences up
LEFT JOIN subjects s ON up.selected_subject_id = s.id
WHERE s.id IS NULL;


-- ----------------------------------------------------------------------------
-- 7. Assessment Question Answer Key Validity Preflight
-- Expected: 0 rows (All correct options must be A, B, C, or D)
-- ----------------------------------------------------------------------------
SELECT 
    id AS question_id,
    subject_id,
    question_number,
    correct_option,
    'Invalid MCQ answer key: must be A, B, C, or D' AS issue_description
FROM assessment_questions 
WHERE correct_option NOT IN ('A', 'B', 'C', 'D');


-- ----------------------------------------------------------------------------
-- 8. Question Slot Collision Preflight Check
-- Expected: 0 rows (Exactly one question per number within each subject)
-- ----------------------------------------------------------------------------
SELECT 
    subject_id,
    question_number,
    COUNT(*) AS occurrences,
    'Duplicate question number slot within subject' AS issue_description
FROM assessment_questions 
GROUP BY subject_id, question_number 
HAVING COUNT(*) > 1;
