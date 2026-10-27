-- ============================================================================
-- PragyaX PostgreSQL Integration Validation Package
-- File: curriculum_verification.sql
-- Description: Read-only curriculum parity and integrity validation queries.
-- Author: Nagin (Senior Database Architect & Supabase Specialist)
-- Target: PostgreSQL 14+ / Supabase PostgreSQL
-- 
-- SAFETY & PRIVACY GUARANTEES:
-- 1. STRICTLY READ-ONLY: Never updates, deletes, or inserts records.
-- 2. ZERO PII EXPOSURE: Does NOT query users, passwords, sessions, or personal data.
-- 3. CURRICULUM VERIFICATION: Validates the 4 core subjects and preserved catalog.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Subject Activation State Verification
-- Expected:
--   - subj_python: is_active = TRUE (Available in demo)
--   - subj_biology: is_active = FALSE (Deployment-blocked pending team approval)
--   - subj_business: is_active = FALSE (Deployment-blocked pending team approval)
--   - subj_aiml: is_active = FALSE (Deployment-blocked pending team approval)
--   - subj_webdev, subj_datasci, subj_cloud: is_active = FALSE (Coming Soon)
-- ----------------------------------------------------------------------------
SELECT 
    id AS subject_id,
    slug,
    title,
    icon,
    is_active,
    question_count,
    difficulty,
    CASE 
        WHEN id = 'subj_python' AND is_active = TRUE THEN 'PASS: Python is active'
        WHEN id IN ('subj_biology', 'subj_business', 'subj_aiml') AND is_active = FALSE THEN 'PASS: Staged inactive (deployment-blocked)'
        WHEN id IN ('subj_webdev', 'subj_datasci', 'subj_cloud') AND is_active = FALSE THEN 'PASS: Preserved Coming Soon'
        ELSE 'FAIL / UNEXPECTED: Check activation state'
    END AS activation_verification
FROM subjects 
ORDER BY is_active DESC, id ASC;


-- ----------------------------------------------------------------------------
-- 2. Question Count Per Assessment Track
-- Expected: Exactly 5 questions for Python, Biology, Business, and AI/ML.
-- ----------------------------------------------------------------------------
SELECT 
    s.id AS subject_id,
    s.title AS subject_title,
    COUNT(q.id) AS actual_questions_in_db,
    s.question_count AS expected_question_count,
    CASE 
        WHEN COUNT(q.id) = 5 THEN 'PASS: Exactly 5 assessment questions'
        WHEN COUNT(q.id) = 0 AND s.is_active = FALSE THEN 'INFO: Inactive Coming Soon subject (no questions expected)'
        ELSE 'FAIL: Question count mismatch'
    END AS count_evaluation
FROM subjects s
LEFT JOIN assessment_questions q ON s.id = q.subject_id
WHERE s.id IN ('subj_python', 'subj_biology', 'subj_business', 'subj_aiml', 'subj_webdev')
GROUP BY s.id, s.title, s.question_count, s.is_active
ORDER BY s.id;


-- ----------------------------------------------------------------------------
-- 3. Question Slot Sequencing (1 through 5 per subject)
-- Expected: Each active subject must have questions numbered 1, 2, 3, 4, 5.
-- ----------------------------------------------------------------------------
SELECT 
    subject_id,
    STRING_AGG(question_number::text, ', ' ORDER BY question_number) AS sequenced_slots,
    CASE 
        WHEN STRING_AGG(question_number::text, ', ' ORDER BY question_number) = '1, 2, 3, 4, 5' 
        THEN 'PASS: Slots 1 through 5 contiguous and complete'
        ELSE 'FAIL: Broken sequencing or missing slots'
    END AS slot_sequencing_status
FROM assessment_questions
WHERE subject_id IN ('subj_python', 'subj_biology', 'subj_business', 'subj_aiml')
GROUP BY subject_id
ORDER BY subject_id;


-- ----------------------------------------------------------------------------
-- 4. Question Text & Option Completeness Check
-- Expected: 0 rows (All options A-D, text, and explanations must be non-empty)
-- ----------------------------------------------------------------------------
SELECT 
    id AS question_id,
    subject_id,
    question_number,
    'Missing required question text or option content' AS issue_description
FROM assessment_questions
WHERE LENGTH(TRIM(question_text)) = 0
   OR LENGTH(TRIM(option_a)) = 0
   OR LENGTH(TRIM(option_b)) = 0
   OR LENGTH(TRIM(option_c)) = 0
   OR LENGTH(TRIM(option_d)) = 0
   OR LENGTH(TRIM(explanation)) = 0
   OR LENGTH(TRIM(topic)) = 0;


-- ----------------------------------------------------------------------------
-- 5. Global Question ID Uniqueness Verification
-- Expected: 0 rows (Every question ID must be globally unique across all tracks)
-- ----------------------------------------------------------------------------
SELECT 
    id AS duplicate_question_id,
    COUNT(*) AS occurrences,
    STRING_AGG(subject_id, ', ') AS conflicting_subjects
FROM assessment_questions
GROUP BY id
HAVING COUNT(*) > 1;


-- ----------------------------------------------------------------------------
-- 6. Topic String Manifest for AI Recommendation Mapping
-- Expected: Exactly 20 distinct curriculum topics (5 Python + 15 New Tracks)
-- ----------------------------------------------------------------------------
SELECT 
    q.subject_id,
    s.title AS subject_title,
    q.question_number,
    q.id AS question_id,
    q.topic AS topic_label
FROM assessment_questions q
JOIN subjects s ON q.subject_id = s.id
ORDER BY q.subject_id, q.question_number;
