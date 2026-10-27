# PragyaX Database Integration Validation Package

**Owner:** Nagin (Senior Database Architect & Supabase Specialist)  
**Target:** PostgreSQL 14+ / Supabase PostgreSQL & SQLite Parity  
**Status:** Verification Artifacts & Deployment Runbook (Zero Migration Edits)

---

## 1. Overview & Directory Structure

This validation package contains **strictly read-only SQL inspection scripts** and operator runbooks to verify schema integrity, curriculum completeness, and security posture across PragyaX persistence targets.

```
database/validation/
├── schema_preflight.sql          <-- Read-only structural, index, and FK inspection
├── curriculum_verification.sql   <-- Read-only 4-subject & 20-question audit
├── security_verification.sql     <-- Read-only RLS, PostgREST grant, and role audit
└── README.md                     <-- Complete validation runbook and operator guide
```

---

## 2. Migration Order & Deployment Prerequisites

When provisioning a disposable local test database or staging Supabase project, migrations must be executed sequentially:

1. **`0001_initial_schema.sql`**: Creates the 10 core tables in foreign-key topological order.
2. **`database/seed.sql`**: Seeds the baseline curriculum (`subj_python` and initial daily challenge).
3. **`0002_integrity_and_indexes.sql`**: Applies composite performance indexes and check/foreign-key constraints.
4. **`0003_security_hardening.sql`**: Revokes public PostgREST API access and enables RLS Default-Deny.
5. **`0004_four_subject_curriculum_seed.sql`**: Seeds Biology, Business, and AI/ML with conflict guards (`is_active = FALSE`).

---

## 3. Verification Procedure on a Disposable Database

Run the validation suite using `psql` against an approved disposable test instance:

```bash
# 1. Run Schema Preflight (Structural Integrity)
psql "$TEST_DB_URL" -f database/validation/schema_preflight.sql

# 2. Run Curriculum Verification (Subject and Question Parity)
psql "$TEST_DB_URL" -f database/validation/curriculum_verification.sql

# 3. Run Security Verification (RLS & Grant Lockdown)
psql "$TEST_DB_URL" -f database/validation/security_verification.sql
```

---

## 4. Interpretation of Expected Results

| Script | Check Section | Expected Output / Evaluation |
| :--- | :--- | :--- |
| **`schema_preflight.sql`** | Section 1 (Tables Found) | `tables_found = 10` $\rightarrow$ `PASS: All 10 application tables present` |
| **`schema_preflight.sql`** | Section 6 (Orphan Preferences) | `0 rows returned` (No invalid foreign keys). |
| **`schema_preflight.sql`** | Section 7 (Answer Key Validity) | `0 rows returned` (All correct options $\in \{A, B, C, D\}$). |
| **`schema_preflight.sql`** | Section 8 (Slot Collisions) | `0 rows returned` (Zero duplicate question numbers). |
| **`curriculum_verification.sql`** | Section 1 (Activation States) | `subj_python` $\rightarrow$ `TRUE`; `subj_biology`, `subj_business`, `subj_aiml`, `subj_webdev`, `subj_datasci`, `subj_cloud` $\rightarrow$ `FALSE`. |
| **`curriculum_verification.sql`** | Section 2 (Question Counts) | Exactly 5 questions each for Python, Biology, Business, and AI/ML. |
| **`curriculum_verification.sql`** | Section 3 (Slot Sequencing) | Each subject displays contiguous `1, 2, 3, 4, 5`. |
| **`security_verification.sql`** | Section 1 (RLS Status) | `100% of application tables have RLS enabled` (`rowsecurity = TRUE`). |
| **`security_verification.sql`** | Section 2 (PostgREST Grants) | `0 rows returned` for roles `anon` and `authenticated` on sensitive tables. |
| **`security_verification.sql`** | Section 4 (Backend Capabilities) | Current backend role has `rolsuper = TRUE` or `rolbypassrls = TRUE`. |

---

## 5. Architectural Differences: SQLite vs PostgreSQL

| Dimension | SQLite (Local Demo / Test Suite) | PostgreSQL / Supabase (Cloud Production) |
| :--- | :--- | :--- |
| **Foreign Keys** | Disabled by default; requires `PRAGMA foreign_keys = ON;` on every connection. | Enforced by default across all transactions. |
| **Data Types** | Dynamic type affinity (`TEXT`, `INTEGER`, `REAL`). Booleans stored as `0`/`1`. | Strict static types (`VARCHAR(n)`, `TIMESTAMPTZ`, `DOUBLE PRECISION`, `BOOLEAN`). |
| **SQL Dialect Syntax** | Uses positional `?` placeholders; internal `rowid` column; `datetime('now', ?)`. | Uses `$1`/`%s` placeholders; no `rowid`; `NOW() - INTERVAL '...'`. |
| **Conflict Handling** | Supports `INSERT OR REPLACE` and `INSERT OR IGNORE`. | Requires ANSI `ON CONFLICT (id) DO UPDATE / DO NOTHING`. |
| **API Exposure** | Standalone file (`pragyax.db`); zero network exposure. | Network accessible via PostgREST; requires explicit RLS lockdown. |

---

## 6. SQLite Synchronization Requirements (For Arsh)

1. **Foreign Key Enforcement:**
   - In [`backend/app/database/connection.py`](file:///C:/Users/nagin/Downloads/PragyaX/backend/app/database/connection.py), execute `conn.execute("PRAGMA foreign_keys = ON;")` inside `get_db()`.
2. **Idempotent Seeding Guard:**
   - Replace the fragile `if count == 0` check with `INSERT INTO subjects ... ON CONFLICT(id) DO UPDATE ...` and `INSERT INTO assessment_questions ... ON CONFLICT(id) DO NOTHING;`.
   - This ensures existing `pragyax.db` files receive the 3 new subjects and 15 questions without dropping student accounts or assessment attempts.

---

## 7. Four-Subject Topic Dependency (For Ekansh)

In [`ai/mock_provider.py`](file:///C:/Users/nagin/Downloads/PragyaX/ai/mock_provider.py), the assessment evaluation algorithm dynamically matches missed questions to `q["topic"]` and looks up `TOPIC_RECOMMENDATIONS`. 

Ensure the 15 exact topic strings authored in `curriculum_verification.sql` (Section 6) are added to Ekansh's topic dictionary. If not explicitly mapped, the mock AI gracefully falls back to `f"Review: {t}"` without raising runtime errors.

---

## 8. Frontend Subject Dependencies (For Shoeb)

In [`frontend/src/pages/SubjectsPage.tsx`](file:///C:/Users/nagin/Downloads/PragyaX/frontend/src/pages/SubjectsPage.tsx):
- Register the new Lucide icon bindings in `ICONS`:
  - `activity: Activity` (Biology)
  - `briefcase: Briefcase` (Business)
  - `cpu: Cpu` (AI/ML)
- When activation is approved by Ankush, update header text to reflect the four tracks.

---

## 9. Supabase Deployment & Team Approvals (For Ankush)

Before deploying migrations `0001` through `0004` to a shared Supabase database:
- [ ] **Arsh Sign-Off:** Backend connection pooling configured and SQLite seeding updated.
- [ ] **Ekansh Sign-Off:** AI recommendation topics mapped.
- [ ] **Shoeb Sign-Off:** Frontend icon mapping verified in React.
- [ ] **Ankush Sign-Off:** Official decision on whether to activate all 4 subjects (`is_active = TRUE`) for the live hackathon demonstration.

---

## 10. Assessment-Result Persistence Verification

To verify that evaluation outcomes survive backend reboots and browser refreshes:
1. Complete a 5-question assessment via `POST /api/assessments/submit`.
2. Note the generated `attempt_id` (`atm_<hex12>`).
3. Terminate and restart the FastAPI server process (`uvicorn`).
4. Re-authenticate and issue `GET /api/assessments/history`.
5. Issue `GET /api/dashboard`.
6. Confirm that the exact score, percentage, proficiency level, breakdown, and recommended topics are loaded directly from the database without data loss.

---

## 11. Security Testing Using Restricted Database Roles

To verify that unprivileged actors cannot bypass security:
```sql
-- Simulate PostgREST anon role:
SET ROLE anon;
-- Attempt to select student accounts (MUST FAIL with permission denied):
SELECT * FROM users;
-- Attempt to select assessment results (MUST FAIL with permission denied):
SELECT * FROM assessment_attempts;
-- Reset session:
RESET ROLE;
```

---

## 12. Backup, Recovery & Rollback Precautions

- **Production Snapshot:** Before applying migrations to a cloud database:
  ```bash
  pg_dump "$DATABASE_URL" --schema=public --format=custom --file="pragyax_prod_backup.dump"
  ```
- **Forward-Only Rollbacks:** If a constraint or index requires removal, author a forward migration (e.g. `0005_revert_object.sql`) using `DROP CONSTRAINT IF EXISTS` or `DROP INDEX IF EXISTS`. Never execute destructive `DROP TABLE` down migrations on populated databases.
