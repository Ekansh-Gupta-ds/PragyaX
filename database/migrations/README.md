# PragyaX PostgreSQL Database Migrations

**Owner:** Nagin (Senior Database Architect & Supabase Specialist)  
**Target Architecture:** PostgreSQL 14+ / Supabase PostgreSQL  
**Backend Framework:** FastAPI (Python) via PragyaX Repository Pattern

---

## 1. Overview & Migration Strategy

This directory provides a **versioned, non-destructive, and idempotent** database migration framework for PragyaX.

- **Non-Destructive Guarantee:** Migrations never execute `DROP TABLE`, `DROP COLUMN`, or `TRUNCATE`.
- **Idempotent Design:** Every table, index, and constraint is guarded by `IF NOT EXISTS` or conditional `DO $$` procedural blocks that check PostgreSQL metadata dictionaries (`information_schema` and `pg_constraint`).
- **Contract Preservation:** All primary and foreign keys maintain their existing `VARCHAR(64)` format (`usr_...`, `subj_...`, `q_py_...`, `atm_...`). They are **not** altered to UUID, ensuring 100% compatibility with Arsh's FastAPI schemas and Pydantic models.
- **Supabase CLI Compatibility:** Migrations use sequential prefix numbering (`0001_...`, `0002_...`, `0003_...`). They can be executed directly in the Supabase SQL Editor or placed in a standard `supabase/migrations/` pipeline.

---

## 2. Migration Manifest & Ordering

Migrations must be executed strictly in ascending numerical order:

| Version | File | Scope & Purpose | Dependencies |
| :--- | :--- | :--- | :--- |
| **0001** | `0001_initial_schema.sql` | Baseline creation of all 10 core tables in foreign-key topological order. | None |
| **0002** | `0002_integrity_and_indexes.sql` | Composite query-path indexes, foreign keys (`user_preferences -> subjects`), check constraints, and unique constraints. | `0001_initial_schema.sql` |
| **0003** | `0003_security_hardening.sql` | PostgREST API isolation (`REVOKE` from `anon`/`authenticated`), Default-Deny RLS enablement, and redundant index cleanup. | `0001_initial_schema.sql`, `0002_integrity_and_indexes.sql` |

---

## 3. Preflight Inspection (Execute Before Applying on Live / Populated Databases)

If the Supabase database is already populated with test data, run these verification queries in the Supabase SQL Editor prior to running `0002` and `0003`:

```sql
-- Check 1: Verify whether tables already exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;

-- Check 2: Verify no orphan selected_subject_id exists in user_preferences
SELECT up.user_id, up.selected_subject_id 
FROM user_preferences up
LEFT JOIN subjects s ON up.selected_subject_id = s.id
WHERE s.id IS NULL;
-- (Must return 0 rows before adding fk_user_preferences_subject)

-- Check 3: Verify no invalid MCQ correct_option values exist
SELECT id, subject_id, correct_option 
FROM assessment_questions 
WHERE correct_option NOT IN ('A', 'B', 'C', 'D');
-- (Must return 0 rows before adding chk_assessment_questions_correct_opt)

-- Check 4: Verify no duplicate question numbers exist per subject
SELECT subject_id, question_number, COUNT(*) 
FROM assessment_questions 
GROUP BY subject_id, question_number 
HAVING COUNT(*) > 1;
-- (Must return 0 rows before adding uq_assessment_questions_subject_number)

-- Check 5: Verify no chat messages have invalid roles
SELECT id, role 
FROM chat_messages 
WHERE role NOT IN ('user', 'assistant');
-- (Must return 0 rows before adding chk_chat_messages_role)
```

---

## 4. Execution Procedures & Seed Dependencies

### Seeding Dependency Note:
`user_preferences.selected_subject_id` defaults to `'subj_python'`. Once `0002_integrity_and_indexes.sql` adds the foreign key constraint `fk_user_preferences_subject`, any new user registration will fail unless the curriculum catalog (`database/seed.sql`) has been loaded.

**Execution Sequence:**
1. Execute `0001_initial_schema.sql`
2. Execute `database/seed.sql` (populates `subjects` with `'subj_python'`)
3. Execute `0002_integrity_and_indexes.sql`
4. Execute `0003_security_hardening.sql`

### Option A: Via Supabase Web Dashboard (Recommended for Hackathon Demo)
1. Log in to [supabase.com](https://supabase.com) and open your project.
2. Navigate to the **SQL Editor** tab.
3. Paste and execute each file sequentially according to the sequence above.

### Option B: Via PostgreSQL CLI (`psql`)
```bash
psql "$DATABASE_URL" -f database/migrations/0001_initial_schema.sql
psql "$DATABASE_URL" -f database/seed.sql
psql "$DATABASE_URL" -f database/migrations/0002_integrity_and_indexes.sql
psql "$DATABASE_URL" -f database/migrations/0003_security_hardening.sql
```

---

## 5. Security & Verification Queries

### Verify All 10 Tables Exist:
```sql
SELECT count(*) = 10 AS all_tables_active 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN (
    'users', 'user_preferences', 'subjects', 'assessment_questions',
    'chat_messages', 'assessment_attempts', 'daily_challenges',
    'user_challenge_submissions', 'user_badges', 'active_sessions'
  );
```

### Verify PostgREST Permissions Revocation:
```sql
-- Must return 0 rows. Confirms that anon and authenticated cannot access sensitive student data:
SELECT grantee, table_name, privilege_type 
FROM information_schema.table_privileges 
WHERE table_schema = 'public' 
  AND grantee IN ('anon', 'authenticated')
  AND table_name IN ('users', 'active_sessions', 'assessment_attempts', 'chat_messages');
```

### Verify Row Level Security (RLS) is Enabled on All Tables:
```sql
SELECT tablename, rowsecurity 
FROM pg_tables 
WHERE schemaname = 'public' 
ORDER BY tablename;
-- All rows must show rowsecurity = TRUE
```

### Verify Active Performance Indexes:
```sql
SELECT indexname, tablename 
FROM pg_indexes 
WHERE schemaname = 'public' 
  AND (indexname LIKE 'idx_%' OR indexname LIKE 'uq_%')
ORDER BY tablename, indexname;
```

---

## 6. Architecture: Custom Authentication vs Supabase PostgREST RLS

> [!IMPORTANT]
> **Why we use RLS Default-Deny instead of standard `auth.uid()` policies:**
> 
> PragyaX currently uses custom FastAPI authentication (`backend/app/services/auth_service.py`), generating bearer tokens (`pragya_<token>`) stored in `active_sessions`. User IDs are strings (`usr_<hex12>`).
> 
> In Supabase, `auth.uid()` evaluates against the JWT issued by Supabase Auth (`gotrue`). Since FastAPI connects to PostgreSQL via a direct backend connection string (`DATABASE_URL`), `auth.uid()` is `NULL`.
> 
> **Security Implementation:**
> 1. In `0003_security_hardening.sql`, we **revoke all privileges from `anon` and `authenticated`** and enable **Row Level Security (RLS) in Default-Deny mode**.
> 2. This completely seals the public Supabase PostgREST API: no student passwords, attempts, or chat messages can be queried from the internet using public API keys.
> 3. The FastAPI backend connects using `DATABASE_URL` as a privileged role (with `BYPASSRLS`), allowing all internal queries in `repository.py` to function with zero disruption.
> 4. Application-level data isolation is enforced by Arsh's `get_current_user` FastAPI dependency, ensuring students can only access their own records.

---

## 7. Least-Privileged Backend Role Template (Production Best Practice)

In production, avoid running FastAPI as the database superuser (`postgres`). Create a dedicated backend application role:

```sql
-- Execute in Supabase SQL Editor:
CREATE ROLE pragyax_backend WITH LOGIN PASSWORD 'YOUR_STRONG_BACKEND_PASSWORD';

-- Grant connection and schema usage
GRANT CONNECT ON DATABASE postgres TO pragyax_backend;
GRANT USAGE ON SCHEMA public TO pragyax_backend;

-- Grant standard DML (no DDL/DROP permissions)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO pragyax_backend;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO pragyax_backend;

-- Grant RLS bypass so backend can manage all user records
ALTER ROLE pragyax_backend BYPASSRLS;
```

---

## 8. Local Disposable PostgreSQL Testing (Offline Verification)

To test the complete migration and seed sequence locally without touching remote databases:

```bash
# 1. Start a disposable PostgreSQL container in Docker:
docker run --name pragyax-test-db -e POSTGRES_PASSWORD=testpass -p 5439:5432 -d postgres:16

# 2. Set test connection string:
export TEST_DB_URL="postgresql://postgres:testpass@localhost:5439/postgres"

# 3. Run all migrations and seeds in order:
psql "$TEST_DB_URL" -f database/migrations/0001_initial_schema.sql
psql "$TEST_DB_URL" -f database/seed.sql
psql "$TEST_DB_URL" -f database/migrations/0002_integrity_and_indexes.sql
psql "$TEST_DB_URL" -f database/migrations/0003_security_hardening.sql

# 4. Cleanup when finished:
docker stop pragyax-test-db && docker rm pragyax-test-db
```

---

## 9. Rollback & Disaster Recovery Strategy

- **No Destructive Down Migrations:** We do not provide automated down migrations that execute `DROP TABLE` or `DROP COLUMN`, as they carry extreme risk of accidental data destruction.
- **Rollback Protocol:** If a constraint or policy needs adjustment, author a subsequent forward migration (e.g. `0004_adjust_policy.sql`) using `ALTER TABLE ... DROP CONSTRAINT IF EXISTS ...`.
- **Database Backup (Prior to Production Application):**
  ```bash
  pg_dump "$DATABASE_URL" --schema=public --format=custom --file="pragyax_backup_$(date +%Y%m%d_%H%M%S).dump"
  ```

---

## 10. Outstanding Team Decisions Requiring Approval

1. **Database Client Library (Arsh):**
   - Confirm using direct PostgreSQL connection pooling via `psycopg[binary]` over `DATABASE_URL` (recommended).
2. **Dual-Mode Persistence (Ankush):**
   - Confirm `repository.py` fallback to SQLite if `DATABASE_URL` is omitted, preserving zero-config offline tests.
3. **Identity Provider Roadmap (Arsh & Ankush):**
   - Confirm retaining custom PBKDF2 bearer tokens for the hackathon MVP, deferring Supabase Auth (`auth.users`) to a future milestone.
