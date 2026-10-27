# PragyaX Database Schema Contract Proposal: Learning Roadmaps

**Author:** Arsh (Senior FastAPI Backend Engineer)  
**Target Recipient:** Nagin (Database Architect)  
**Status:** Proposal for Phase 2 Schema Migration  
**Strict Rule:** *Proposal only. No migrations or modifications have been applied to `database/schema.sql` or the production database.*

---

## 1. Overview & Objectives

In Phase 2, PragyaX introduces the **Personalized Learning Roadmap** feature. Roadmaps provide a structured skill-tree progression tailored to each student's assessment diagnostics.

To persist roadmaps, modules, and individual learner progress, we propose three normalized tables:
1. `learning_roadmaps` — Stores personalized or template roadmap metadata.
2. `roadmap_modules` — Stores the curriculum nodes, topics, prerequisites, and estimates.
3. `user_roadmap_progress` — Tracks each student's completion percentage and lock status per module.

---

## 2. Table Specifications

### 2.1 Table: `learning_roadmaps`
Defines the top-level roadmap entity associated with a learner and subject.

```sql
CREATE TABLE IF NOT EXISTS learning_roadmaps (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_id VARCHAR(64) NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    overall_progress DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_user_subject_roadmap UNIQUE (user_id, subject_id)
);
```

- **Primary Key:** `id` (e.g. `rdm_py_usr_12charhex`)
- **Foreign Keys:**
  - `user_id` -> `users(id)` (ON DELETE CASCADE)
  - `subject_id` -> `subjects(id)` (ON DELETE CASCADE)
- **Unique Constraint:** `(user_id, subject_id)` — One active personalized roadmap per subject per student.
- **Ownership:** Belongs strictly to `user_id`.

---

### 2.2 Table: `roadmap_modules`
Defines the modular learning units (nodes) belonging to a roadmap or subject catalog.

```sql
CREATE TABLE IF NOT EXISTS roadmap_modules (
    id VARCHAR(64) PRIMARY KEY,
    roadmap_id VARCHAR(64) REFERENCES learning_roadmaps(id) ON DELETE CASCADE,
    subject_id VARCHAR(64) NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    module_key VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    difficulty VARCHAR(32) NOT NULL DEFAULT 'Beginner', -- 'Beginner' | 'Intermediate' | 'Advanced'
    estimated_minutes INT NOT NULL DEFAULT 30,
    order_index INT NOT NULL DEFAULT 0,
    prerequisite_module_ids TEXT NOT NULL DEFAULT '[]', -- JSON array of module IDs
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_roadmap_module_key UNIQUE (roadmap_id, module_key)
);
```

- **Primary Key:** `id` (e.g. `mod_py_types`)
- **Foreign Keys:**
  - `roadmap_id` -> `learning_roadmaps(id)` (ON DELETE CASCADE)
  - `subject_id` -> `subjects(id)` (ON DELETE CASCADE)
- **Prerequisites:** Stored as portable JSON array string `['mod_py_types']` for flexibility across dialects.

---

### 2.3 Table: `user_roadmap_progress`
Tracks a student's granular progress, lock status, and completion state for a specific module.

```sql
CREATE TABLE IF NOT EXISTS user_roadmap_progress (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    module_id VARCHAR(64) NOT NULL REFERENCES roadmap_modules(id) ON DELETE CASCADE,
    status VARCHAR(32) NOT NULL DEFAULT 'locked', -- 'locked' | 'unlocked' | 'in_progress' | 'completed'
    completion_percentage DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_user_module_progress UNIQUE (user_id, module_id),
    CONSTRAINT chk_completion_percentage CHECK (completion_percentage >= 0.0 AND completion_percentage <= 100.0)
);
```

- **Primary Key:** `id` (e.g. `rmp_12charhex`)
- **Foreign Keys:**
  - `user_id` -> `users(id)` (ON DELETE CASCADE)
  - `module_id` -> `roadmap_modules(id)` (ON DELETE CASCADE)
- **Unique Constraint:** `(user_id, module_id)` ensures idempotent progress updates.
- **Check Constraint:** `completion_percentage` bound between `0.0` and `100.0`.

---

## 3. Index Recommendations

For optimal query performance during dashboard rendering and API calls:

```sql
-- Fast lookup of user's active roadmaps
CREATE INDEX IF NOT EXISTS idx_roadmaps_user_subject 
ON learning_roadmaps(user_id, subject_id);

-- Fast ordered retrieval of modules within a roadmap
CREATE INDEX IF NOT EXISTS idx_roadmap_modules_roadmap_order 
ON roadmap_modules(roadmap_id, order_index);

-- Fast lookup of all module progress states for a student
CREATE INDEX IF NOT EXISTS idx_user_progress_user_module 
ON user_roadmap_progress(user_id, module_id);
```

---

## 4. Suggested Row-Level Security (RLS) Policies

When deployed to production Supabase PostgreSQL with Supabase Auth:

```sql
-- 1. Enable RLS
ALTER TABLE learning_roadmaps ENABLE ROW LEVEL SECURITY;
ALTER TABLE roadmap_modules ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_roadmap_progress ENABLE ROW LEVEL SECURITY;

-- 2. learning_roadmaps: Users can only select and update their own roadmaps
CREATE POLICY "Users can view their own roadmap"
ON learning_roadmaps FOR SELECT
USING (auth.uid()::text = user_id);

CREATE POLICY "Users can modify their own roadmap"
ON learning_roadmaps FOR ALL
USING (auth.uid()::text = user_id);

-- 3. roadmap_modules: All authenticated users can read modules
CREATE POLICY "Authenticated users can read roadmap modules"
ON roadmap_modules FOR SELECT
TO authenticated
USING (true);

-- 4. user_roadmap_progress: Users can only read and modify their own progress
CREATE POLICY "Users can manage their own roadmap progress"
ON user_roadmap_progress FOR ALL
USING (auth.uid()::text = user_id);
```

---

## 5. Migration Considerations & Deployment Strategy

1. **Backwards Compatibility:**
   - Existing tables (`users`, `subjects`, `assessment_attempts`, `user_preferences`) remain untouched.
   - Foreign key cascading ensures that if a user deletes their account, their roadmap progress is safely expunged.
2. **Seed Data:**
   - Standard baseline modules for Python (Data Types, Collections, Functions, Comprehensions, OOP, Generators, Decorators, Async) can be pre-seeded into `roadmap_modules` with `roadmap_id IS NULL` as global templates.
3. **Execution Plan:**
   - Nagin reviews and approves this contract.
   - Nagin authors `database/migrations/002_learning_roadmaps.sql`.
   - Migration is applied to Supabase and local test database.
   - Arsh activates the persistence methods in `Repository` and updates `POST /api/roadmap/{module_id}/complete` from HTTP 501 to HTTP 200.

---

## 6. Authentication and Authorization Compatibility

1. **Current Custom Bearer-Token Authentication:**
   - PragyaX currently uses custom PBKDF2-hashed tokens stored in `active_sessions`.
   - API requests are validated via FastAPI's `get_current_user` dependency rather than Supabase GoTrue JWT tokens.

2. **Supabase `auth.uid()` Incompatibility with Custom Tokens:**
   - Policies evaluating `auth.uid()::text = user_id` will evaluate to `NULL` for custom token sessions, because the incoming HTTP requests to FastAPI do not pass Supabase-signed JWTs directly to PostgreSQL.
   - Applying `auth.uid()` RLS without migrating authentication will block legitimate backend and client operations.

3. **Privileged Database Connection Role Bypasses RLS:**
   - The FastAPI backend connects to Supabase PostgreSQL using the pooler with a role that has `rolbypassrls = True`.
   - Consequently, PostgreSQL does not enforce table-level RLS against backend pooler connections.

4. **Service-Layer Ownership Enforcement:**
   - All repository data access operations MUST explicitly filter and bind records using the authenticated `user_id` (e.g. `WHERE user_id = %s` and `WHERE id = %s AND user_id = %s`).
   - Tenant isolation is strictly guaranteed at the backend service layer.

5. **Future Supabase Auth Migration:**
   - Migrating from `active_sessions` to Supabase GoTrue Auth requires separate architectural planning, frontend token migration, and formal team approval.

6. **RLS Policy Deployment Safety:**
   - No RLS policies should be applied or enforced on `learning_roadmaps`, `roadmap_modules`, or `user_roadmap_progress` without explicit coordination and review with Nagin.

