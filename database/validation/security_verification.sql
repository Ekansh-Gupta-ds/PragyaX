-- ============================================================================
-- PragyaX PostgreSQL Integration Validation Package
-- File: security_verification.sql
-- Description: Read-only security posture, RLS, and PostgREST isolation inspection.
-- Author: Nagin (Senior Database Architect & Supabase Security Specialist)
-- Target: PostgreSQL 14+ / Supabase PostgreSQL
-- 
-- SAFETY GUARANTEES:
-- 1. STRICTLY READ-ONLY: Never alters roles, grants, privileges, or policies.
-- 2. ZERO SECRET EXPOSURE: Does not select password hashes, salts, or session tokens.
-- 3. AUDIT INSPECTION: Validates PostgREST lockdown and RLS Default-Deny status.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Row-Level Security (RLS) Status Across All Application Tables
-- Expected: rowsecurity = TRUE across all 10 application tables.
-- ----------------------------------------------------------------------------
SELECT 
    tablename,
    rowsecurity,
    CASE 
        WHEN rowsecurity = TRUE THEN 'PASS: RLS Enabled (Protected)'
        ELSE 'CRITICAL ALERT: RLS Disabled (Exposed to public API)'
    END AS rls_evaluation
FROM pg_tables 
WHERE schemaname = 'public' 
  AND tablename IN (
    'users', 'user_preferences', 'subjects', 'assessment_questions',
    'chat_messages', 'assessment_attempts', 'daily_challenges',
    'user_challenge_submissions', 'user_badges', 'active_sessions'
  )
ORDER BY tablename;

-- RLS Coverage Summary (Expected: exactly 10 tables protected)
SELECT 
    COUNT(*) AS protected_tables_count,
    CASE 
        WHEN COUNT(*) = 10 THEN 'PASS: 100% of application tables have RLS enabled'
        ELSE 'FAIL: Unprotected tables detected'
    END AS rls_overall_status
FROM pg_tables 
WHERE schemaname = 'public' 
  AND rowsecurity = TRUE
  AND tablename IN (
    'users', 'user_preferences', 'subjects', 'assessment_questions',
    'chat_messages', 'assessment_attempts', 'daily_challenges',
    'user_challenge_submissions', 'user_badges', 'active_sessions'
  );


-- ----------------------------------------------------------------------------
-- 2. PostgREST Public Exposure Audit (anon & authenticated roles)
-- Expected: 0 rows returned for sensitive tables.
-- Confirms that external API callers holding SUPABASE_ANON_KEY have ZERO access.
-- ----------------------------------------------------------------------------
SELECT 
    grantee,
    table_name,
    privilege_type,
    'SECURITY RISK: PostgREST role has direct table access' AS audit_warning
FROM information_schema.table_privileges 
WHERE table_schema = 'public' 
  AND grantee IN ('anon', 'authenticated')
  AND table_name IN (
    'users', 'active_sessions', 'assessment_attempts', 
    'chat_messages', 'user_preferences', 'user_challenge_submissions', 
    'user_badges', 'assessment_questions'
  )
ORDER BY table_name, grantee, privilege_type;


-- ----------------------------------------------------------------------------
-- 3. Active RLS Policy Manifest
-- Expected: 0 policies (Default-Deny) when using backend service-role architecture.
-- Any policy referencing auth.uid() is flagged as a potential conflict with custom auth.
-- ----------------------------------------------------------------------------
SELECT 
    tablename,
    policyname,
    roles,
    cmd,
    qual,
    with_check,
    CASE 
        WHEN qual LIKE '%auth.uid()%' OR with_check LIKE '%auth.uid()%' 
        THEN 'WARNING: Policy uses auth.uid() which returns NULL for custom FastAPI tokens'
        ELSE 'INFO: Standard RLS policy'
    END AS policy_compatibility_check
FROM pg_policies 
WHERE schemaname = 'public'
ORDER BY tablename, policyname;


-- ----------------------------------------------------------------------------
-- 4. Current Connected Session Role & RLS Bypass Capabilities
-- Inspects current connection user to verify whether it operates with BYPASSRLS
-- ----------------------------------------------------------------------------
SELECT 
    CURRENT_USER AS active_database_user,
    SESSION_USER AS active_session_user,
    r.rolsuper AS is_superuser,
    r.rolbypassrls AS has_bypass_rls_capability,
    CASE 
        WHEN r.rolsuper = TRUE OR r.rolbypassrls = TRUE 
        THEN 'PASS: Role can service FastAPI queries without RLS blockage'
        ELSE 'ALERT: Standard role subject to RLS Default-Deny (queries may return 0 rows)'
    END AS role_backend_evaluation
FROM pg_roles r
WHERE r.rolname = CURRENT_USER;


-- ----------------------------------------------------------------------------
-- 5. Public Schema Privilege Inspection
-- Ensures unprivileged roles cannot create tables or hijack objects in public
-- ----------------------------------------------------------------------------
SELECT 
    grantee,
    privilege_type
FROM information_schema.usage_privileges 
WHERE object_schema = 'public'
  AND grantee IN ('anon', 'authenticated', 'PUBLIC')
ORDER BY grantee, privilege_type;
