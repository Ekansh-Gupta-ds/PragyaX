# PragyaX Gamification Integration Plan (Phase 2, Task 02)

> **Status:** Design only. **Nothing in this document is implemented.** No router, repository, table, migration or test was changed to produce it.
> Every proposal below is **PROPOSED and requires Ankush's approval**. Every edit to a shared or teammate-owned file **also requires that owner's approval**.
> Inputs (read 2026-10-27): [GAMIFICATION_DESIGN.md](GAMIFICATION_DESIGN.md), [INTEGRATION_BASELINE.md](INTEGRATION_BASELINE.md), [PHASE2_DEPENDENCIES.md](PHASE2_DEPENDENCIES.md), `backend/app/services/gamification_service.py`, `backend/app/database/{repository,connection}.py`, `backend/app/routers/{challenges,assessments,dashboard}.py`, `backend/app/schemas/{challenges,dashboard}.py`, `backend/tests/*`.
> Environment facts used: Python 3.14.7 with SQLite 3.50.4 locally (supports `ON CONFLICT … DO NOTHING` from 3.24, `RETURNING` from 3.35, and triggers).

---

## 1. Proposals G-1 … G-6 (verbatim from GAMIFICATION_DESIGN.md §8)

Copied exactly. No proposal has been approved: no approval is recorded in any project document as of this writing.

| ID | Proposal (exact text) | Needs | Owner(s) | Approval status |
|---|---|---|---|---|
| G-1 | `points_ledger` table + idempotent V1 backfill | Schema (SQLite init + `database/schema.sql`), repository methods | Nagin, Ankush | **PROPOSED — requires Ankush's approval** |
| G-2 | Migrate `user_badges.badge_key='py_master'` → `assessment.subj_python.high_score` (valid because Python is the only active subject in V1), or keep `py_master` as an alias | Data migration, decision on old badge text | Nagin, Ankush | **PROPOSED — requires Ankush's approval** |
| G-3 | `daily_challenges.challenge_date` + `subject_id`; timezone decision | Schema, seeds, repository | Nagin, Ankush | **PROPOSED — requires Ankush's approval** |
| G-4 | `GET /api/leaderboard` | New router, schema, frontend page | Ankush, Shoeb | **PROPOSED — requires Ankush's approval** |
| G-5 | Additional assessment tiers (e.g. `perfect_score` at 100%) | Rule-table change only (no code); frontend already renders unknown icons as a trophy | Ankush | **PROPOSED — requires Ankush's approval** |
| G-6 | Wire the service into the challenges/assessments routers and the dashboard (§7) | Router + repository changes | Ankush, Arsh, Nagin | **PROPOSED — requires Ankush's approval** |

How this plan refines them (refinements are themselves proposals):
- **G-1:** this plan specifies `points_ledger` as **append-only**, with revocation recorded in a separate append-only table (§2.4). This **differs from GAMIFICATION_DESIGN.md §3**, which proposed revoking by updating a `status` column. Choose one at approval time (decision D-1, §7).
- **G-2:** this plan recommends the **alias (equivalence) option**, which needs no data migration, over rewriting `py_master` rows (§3.2, decision D-2).
- **G-3, G-4, G-5:** not needed for V1-parity integration; out of scope here beyond the dependencies noted.
- **G-6:** §5 is the detailed version.

Related baseline items: **CR-08** (typed `user_submission`), **CR-14** (subject-specific badges), **CR-15** (repository split and gamification service). G-numbers are not yet listed in INTEGRATION_BASELINE.md §9; Ankush should add them there when deciding.

---

## 2. Data model proposal: append-only reward ledger (G-1)

### 2.1 Contract

One row = one reward event that already happened. Rows are inserted once and never updated or deleted by application code.

| Column | Type (Postgres / SQLite) | Rule | Source of value |
|---|---|---|---|
| `id` | `VARCHAR(64)` / `TEXT` PK | Event ID. Live: `rwd_<32 hex>`. Backfill: deterministic `rwd_v1_<submission id>` | Server |
| `event_key` | `VARCHAR(255)` / `TEXT` **UNIQUE NOT NULL** | Idempotency key = `reward_event_key(user_id, source_type, source_id)` → `"<source_type>:<source_id>:<user_id>"` | Service function (pure, deterministic) |
| `user_id` | `VARCHAR(64)` / `TEXT` NOT NULL, FK `users(id)` | **The authenticated user** from `get_current_user`; never from the request body | Auth dependency |
| `source_type` | `VARCHAR(32)` / `TEXT` NOT NULL | `daily_challenge` now (later `achievement`, `battle`, …) | Server constant |
| `source_id` | `VARCHAR(64)` / `TEXT` NOT NULL | e.g. `chal_today_py` | Trusted DB row |
| `points_delta` | `INTEGER` NOT NULL **CHECK (points_delta >= 0)** | Trusted amount from `ChallengeRewardDecision.points_awarded`, which only ever comes from `daily_challenges.points`. Non-negative by design: corrections use revocation (§2.4), never negative rows | Service decision |
| `reason` | `VARCHAR(32)` / `TEXT` NOT NULL | `RewardReason` value (`correct_answer`) | Service decision |
| `badge_key` | `VARCHAR(64)` / `TEXT` NULL | Achievement granted with this event, if any (e.g. `daily_striker`). Informational link; `user_badges` stays the display source | Service decision |
| `origin` | `VARCHAR(16)` / `TEXT` NOT NULL, CHECK in (`live`, `backfill_v1`) | Lets migration and reconciliation tell rows apart | Writer |
| `created_at` | `TIMESTAMPTZ` / `TEXT` (ISO-8601 UTC, `…Z`) NOT NULL | Live: insert time. Backfill: the original submission's `created_at` | DB default / copied |

```sql
-- PROPOSED (G-1). Not executed. Postgres flavour; the SQLite differences are in §2.5.
CREATE TABLE points_ledger (
    id            VARCHAR(64)  PRIMARY KEY,
    event_key     VARCHAR(255) NOT NULL UNIQUE,
    user_id       VARCHAR(64)  NOT NULL REFERENCES users(id),
    source_type   VARCHAR(32)  NOT NULL,
    source_id     VARCHAR(64)  NOT NULL,
    points_delta  INTEGER      NOT NULL CHECK (points_delta >= 0),
    reason        VARCHAR(32)  NOT NULL,
    badge_key     VARCHAR(64),
    origin        VARCHAR(16)  NOT NULL DEFAULT 'live' CHECK (origin IN ('live', 'backfill_v1')),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_points_ledger_user    ON points_ledger (user_id);
CREATE INDEX idx_points_ledger_created ON points_ledger (created_at);

CREATE TABLE points_ledger_revocations (           -- append-only corrections (§2.4)
    id          VARCHAR(64)  PRIMARY KEY,           -- 'rvk_<hex>'
    ledger_id   VARCHAR(64)  NOT NULL UNIQUE REFERENCES points_ledger(id),  -- one revocation per event
    reason      VARCHAR(255) NOT NULL,
    revoked_by  VARCHAR(64)  NOT NULL,              -- admin/user id or 'system'
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
```

**What is deliberately absent:** no `ON DELETE CASCADE` from `users` (the existing tables have it; whether ledger history survives a user deletion is decision D-5), and no `status` column (see §2.4).

### 2.2 Duplicate protection
| Layer | Mechanism |
|---|---|
| Database (authoritative) | `UNIQUE(event_key)` on the ledger; the existing `UNIQUE(user_id, challenge_id)` on submissions; the existing `UNIQUE(user_id, badge_key)` on badges; `UNIQUE(ledger_id)` on revocations |
| Write SQL | `INSERT … ON CONFLICT (event_key) DO NOTHING` (both engines). Never `INSERT OR IGNORE` (SQLite-only) in new code |
| Service | `compute_challenge_reward(..., already_completed=True)` → 0 points; `aggregate_points` counts each event key at most once |
| Pre-check | Allowed only as a fast path for the response; correctness never depends on it |

### 2.3 Transaction and concurrency requirements
1. One request = **one transaction**: submission row + ledger row + badge row(s). All or nothing.
2. **SQLite:** start the write transaction with `BEGIN IMMEDIATE` *before* the "already completed?" read, so two requests serialise on the database write lock. Today the read happens outside a write lock, which is what allows the V1 race.
3. **Postgres:** default `READ COMMITTED` is enough. Correctness comes from the unique constraints plus `ON CONFLICT DO NOTHING RETURNING id`: "no row returned" means another transaction won.
4. **Conflict outcome:** if the submission insert returns nothing, recompute the decision with `already_completed=True` (0 points), write nothing else, and answer with the **V1 repeat response** (§3.1). No 500.
5. **Idempotent retries:** a client or network retry produces the same `event_key`, so it never creates a second ledger row.
6. **Server-only values:** `user_id` comes from the auth dependency; `points_delta` comes from `daily_challenges.points` via `ChallengeConfig`; the request carries only `challenge_id` and `selected_option`.

### 2.4 Revocation and correction (append-only)
- **Revoke an award:** insert one `points_ledger_revocations` row pointing at the ledger row. The ledger row is never edited.
- **Read model:** an event counts iff it has **no** revocation row. Repository adapters map it to `RewardRecord(event_key, points_delta, status="revoked" if revoked else "awarded")` and call `aggregate_points`. This is the exact contract the existing service and its tests implement.
- **Correct a wrong amount:** revoke the event, then append a correction event with its own key (e.g. `source_type='correction'`, `source_id='<original ledger id>'`) and the right non-negative amount. Both steps go in one transaction.
- **Enforcing append-only:** Postgres uses `REVOKE UPDATE, DELETE` from the app role, or a trigger that raises; SQLite uses `CREATE TRIGGER … BEFORE UPDATE/DELETE ON points_ledger BEGIN SELECT RAISE(ABORT, 'append-only'); END`. The single exception is the pre-cutover migration rollback (§4.5), which drops the whole table.

### 2.5 PostgreSQL ↔ SQLite portability
| Concern | Postgres | SQLite (≥ 3.35 required) | Rule for the implementation |
|---|---|---|---|
| Upsert-ignore | `ON CONFLICT (event_key) DO NOTHING` | Same syntax (≥ 3.24) | Use this form only |
| Detect insert | `RETURNING id` | `RETURNING id` (≥ 3.35) | Check the row count / returned row |
| Placeholders | `%s` (psycopg) | `?` | Hidden inside the repository implementations |
| Timestamps | `TIMESTAMPTZ` → `datetime` | `TEXT` | Serialise as ISO-8601 UTC strings in responses (relates to IC-06 / CR-05) |
| Booleans | `BOOLEAN` | `INTEGER 0/1` | Convert at the repository boundary |
| String concat (backfill) | `||` | `||` | Portable as written in §4 |
| Write lock | Row/unique locks | `BEGIN IMMEDIATE` | Each implementation handles its own locking |
| Append-only guard | Grants or trigger | Trigger | Both shipped by Nagin |

---

## 3. Preserving V1 behaviour

### 3.1 Daily challenge: observable behaviour that must not change
| Case | V1 today (evidence) | Required after integration |
|---|---|---|
| First correct submission | 200, `is_correct: true`, `points_awarded: 50` (seed value), `daily_striker` badge (`repository.py:409-425`; test `test_api_flow.py:307-315`) | Identical. Points come from `daily_challenges.points` via `ChallengeConfig` |
| First wrong submission | 200, `is_correct: false`, `points_awarded: 0`, attempt used up (`repository.py:410-418`) | Identical; no ledger row (nothing awarded) |
| Repeat submission | **400** `{"detail": "Challenge already completed by this user today"}` (`repository.py:406-407` → `challenges.py:44-48`; test `:317-323`) | **Same status and exact message**, including when it is detected through a conflict |
| Invalid option | **400** `"selected_option must be A, B, C, or D."` (`challenges.py:32-36`), attempt not used | Identical; `InvalidSubmissionError` maps to this exact message |
| Unknown challenge | **400** `"Challenge not found"` (`repository.py:398-399`) | Identical |
| `GET /challenges/daily` | Answer hidden until submitted; 404 `"No daily challenge active at this time."` if none (`challenges.py:17-22`) | Unchanged; not part of this integration |
| Response shape | `ChallengeResultResponse{challenge_id, is_correct, points_awarded, correct_option, explanation}` | Unchanged fields and types |

### 3.2 Badges
- **Existing `py_master` rows stay valid** and keep displaying as they do today (title "Python Virtuoso"). No rows are rewritten under the recommended option.
- **Legacy equivalence (recommended for G-2):** the canonical key `assessment.subj_python.high_score` is equivalent to the legacy key `py_master`. Before inserting an assessment award, the writer checks whether the user already holds the canonical key **or any equivalent legacy key**; if so, nothing is inserted. A user who earned `py_master` in V1 therefore never receives a second high-score badge.
- **Why no race remains:** once integration removes the V1 rule, nothing ever inserts `py_master` again. Two concurrent first high scores for the same user can only both try the canonical key, and `UNIQUE(user_id, badge_key)` keeps exactly one.
- `daily_striker` is unchanged (the service constant is identical to V1), so existing rows deduplicate naturally.

### 3.3 Points
- **Existing points stay as they are until migration is verified.** The dashboard keeps computing `total_points` from `SUM(user_challenge_submissions.points_awarded)` (`repository.py:320`) through the dual-write phase. The read source switches to the ledger only after the verification in §4.4 passes and Ankush approves the cutover.

---

## 4. Migration plan (documentation only: never executed by this plan)

### 4.1 Phases
| Phase | What happens | Read source for `total_points` | Rollback |
|---|---|---|---|
| M0 | Back up: copy `pragyax.db` (SQLite) / `pg_dump` (Postgres) | Submissions | Restore backup |
| M1 | Create `points_ledger` + revocations table + append-only triggers (Nagin) | Submissions | Drop the new tables (nothing reads them) |
| M2 | Backfill V1 history (§4.2); rerunnable | Submissions | Drop and re-create the tables |
| M3 | **Dual write:** new challenge submissions write the submission row (as today) **and** the ledger row in one transaction | Submissions | Stop dual write; ledger ignored |
| M4 | Verification and reconciliation (§4.4) green for an agreed period | Submissions | – |
| M5 | **Cutover** (Ankush approves): dashboard reads ledger totals | Ledger | Flip the read back to submissions (both stay complete thanks to dual write) |

### 4.2 Backfill of historical challenge points
- **Which rows:** every V1 submission with `is_correct = 1`. Wrong answers are not rewards and have no ledger row. Correct answers with `points_awarded = 0` (possible only if a challenge was configured with 0 points) are still recorded, for completeness.
- **Deterministic legacy keys:** `event_key = 'daily_challenge:' || challenge_id || ':' || user_id`. This is **exactly** what `reward_event_key(user_id, "daily_challenge", challenge_id)` produces. V1 ids (`usr_<hex>`, `chal_today_py`) satisfy its `[A-Za-z0-9_.-]` rule, so backfilled and live rows can never both exist for the same event.
- **Deterministic id:** `'rwd_v1_' || submission.id`.

```sql
-- PROPOSED backfill (documentation only). Same text runs on SQLite >= 3.24 and Postgres.
INSERT INTO points_ledger (id, event_key, user_id, source_type, source_id,
                           points_delta, reason, badge_key, origin, created_at)
SELECT 'rwd_v1_' || s.id,
       'daily_challenge:' || s.challenge_id || ':' || s.user_id,
       s.user_id, 'daily_challenge', s.challenge_id,
       s.points_awarded, 'correct_answer', 'daily_striker', 'backfill_v1', s.created_at
FROM user_challenge_submissions s
WHERE s.is_correct = 1            -- Postgres: s.is_correct = TRUE
ON CONFLICT (event_key) DO NOTHING;
```

**Rerun safety:** a second run inserts nothing, because of the unique `event_key` (and the deterministic primary key). If a backfilled event was already written live during dual write, the live row wins and the backfill skips it, so no double reward is possible.

Before running, check that `s.points_awarded >= 0` for all rows. The ledger's CHECK would otherwise abort the whole statement, which is the desired behaviour: investigate, don't coerce.

### 4.3 Badge handling during migration
Under the recommended alias option, **no badge rows are migrated**. If Ankush instead chooses the rewrite option for G-2, that migration is a separate, reviewed script:
- Rewrite `py_master` to `assessment.subj_python.high_score`, but only for users without the canonical key.
- Keep the old title or update it (decision D-2).
- Take a backup first.

### 4.4 Verification queries (documentation only)
Written for SQLite (≥ 3.39 for `FULL OUTER JOIN`). On Postgres, read every `is_correct = 1` as `is_correct = TRUE`.
```sql
-- V1. Per-user totals must match exactly (expect zero rows).
SELECT COALESCE(v.user_id, l.user_id) AS user_id, v.v1_points, l.ledger_points
FROM (SELECT user_id, SUM(points_awarded) AS v1_points
      FROM user_challenge_submissions GROUP BY user_id) v
FULL OUTER JOIN                    -- SQLite >= 3.39 supports FULL OUTER JOIN
     (SELECT p.user_id, SUM(p.points_delta) AS ledger_points
      FROM points_ledger p
      LEFT JOIN points_ledger_revocations r ON r.ledger_id = p.id
      WHERE p.source_type = 'daily_challenge' AND r.id IS NULL
      GROUP BY p.user_id) l
  ON l.user_id = v.user_id
WHERE COALESCE(v.v1_points, 0) <> COALESCE(l.ledger_points, 0);

-- V2. Every correct V1 submission has exactly one ledger event (expect zero rows).
SELECT s.id FROM user_challenge_submissions s
LEFT JOIN points_ledger p ON p.event_key = 'daily_challenge:' || s.challenge_id || ':' || s.user_id
WHERE s.is_correct = 1 AND p.id IS NULL;

-- V3. No ledger event without a matching correct submission (expect zero rows).
SELECT p.id FROM points_ledger p
LEFT JOIN user_challenge_submissions s
       ON s.user_id = p.user_id AND s.challenge_id = p.source_id AND s.is_correct = 1
WHERE p.source_type = 'daily_challenge' AND s.id IS NULL;

-- V4. Grand totals agree (one row, the two numbers equal).
SELECT (SELECT COALESCE(SUM(points_awarded),0) FROM user_challenge_submissions) AS v1_total,
       (SELECT COALESCE(SUM(points_delta),0) FROM points_ledger p
         WHERE source_type = 'daily_challenge'
           AND NOT EXISTS (SELECT 1 FROM points_ledger_revocations r WHERE r.ledger_id = p.id)) AS ledger_total;

-- V5. No negative amounts (expect 0) - also guaranteed by the CHECK constraint.
SELECT COUNT(*) FROM points_ledger WHERE points_delta < 0;
```

### 4.5 Rollback and reconciliation
- **Before cutover (M1–M4):** users see nothing from the ledger, so rollback = stop dual write and `DROP TABLE points_ledger_revocations; DROP TABLE points_ledger;`. This is the only sanctioned deletion of ledger data, and it requires Ankush's sign-off plus the M0 backup.
- **After cutover (M5):** rollback = switch the dashboard read back to the submissions sum. Dual write must therefore continue after cutover until Ankush retires it.
- **Reconciliation (recurring, read-only):** run V1–V4. Fix any mismatch only by **appending**: re-run the idempotent backfill to add missing events, or revoke wrong events (§2.4). Never edit or delete rows. Record each run's results.

---

## 5. Integration adapter design (G-6)

### 5.1 Exact methods the routers call today
| Router (owner) | Call site | Method | Gamification side effects today |
|---|---|---|---|
| `routers/challenges.py` (**Ankush**) | line 17 | `Repository.get_daily_challenge(user_id)` | none (read; hides the answer) |
| | lines 32-36 | inline A–D check | – |
| | lines 38-42 | `Repository.submit_daily_challenge(user_id, challenge_id, selected_option)` | **grading, points, submission row, `daily_striker` badge, repeat check**, all inside the repository |
| `routers/assessments.py` (**Arsh**) | line 66 | `Repository.get_raw_assessment_questions_with_answers(subject_id)` | – |
| | line 96 | `Repository.get_subject_by_id(...)` | – |
| | lines 99-104 | `get_ai_provider().evaluate_assessment(...)` | – |
| | lines 107-118 | `Repository.save_assessment_attempt(...)` | **`py_master` badge when score ≥ 4** (`repository.py:244-249`) |
| `routers/dashboard.py` (**Arsh**) | line 21 | `Repository.get_user_dashboard_metrics(user_id)` | **`total_points` = SUM over submissions** (`repository.py:320`); badges list |

### 5.2 Target flow (minimal changes)

```
challenges router (Ankush)
  └─ gamification_integration.submit_challenge(user_id, challenge_id, selected_option)   [new, Ankush-owned]
       ├─ repo.get_challenge_config(challenge_id)          -> ChallengeConfig | None   [new repo method]
       ├─ gamification_service.compute_challenge_reward(...)                           [exists, pure]
       └─ repo.record_challenge_submission(user_id, decision, selected_option)         [new repo method:
            one transaction; ON CONFLICT; returns "inserted" or "conflict"]
       └─ on "conflict": recompute with already_completed=True -> V1 repeat response
assessments router (Arsh)
  └─ after save_assessment_attempt: awards = eligible_assessment_achievements(score, total, subject_id, title)
       └─ repo.award_badges(user_id, filtered_awards)                                   [new repo method]
dashboard (Arsh)
  └─ total_points: unchanged until cutover (§4.1 M5); then from ledger via aggregate_points semantics
```

**New Ankush-owned module (proposed): `backend/app/services/gamification_integration.py`.**
- Orchestrates only. No SQL; it receives a repository object.
- Maps errors so the router keeps V1 responses:
  - `InvalidSubmissionError` → 400 `"selected_option must be A, B, C, or D."`
  - missing challenge → 400 `"Challenge not found"`
  - repeat / conflict → 400 `"Challenge already completed by this user today"`
  - `InvalidTrustedInputError` → logged, then 500
- Builds the existing `ChallengeResultResponse` dict, unchanged.

**New repository methods (Nagin implements; signatures agreed with Arsh under CR-15):**

| Method | Contract |
|---|---|
| `get_challenge_config(challenge_id) -> dict \| None` | Returns `{id, correct_option, points, explanation}` from `daily_challenges` |
| `record_challenge_submission(user_id, challenge_id, selected_option, decision) -> "inserted" \| "conflict"` | Single transaction:<ul><li>Insert the submission with `ON CONFLICT DO NOTHING`.</li><li>If inserted and `decision.reason == correct_answer`, insert the ledger row (when G-1 is live) and the badges with `ON CONFLICT DO NOTHING`.</li></ul> |
| `award_badges(user_id, awards, equivalents) -> list[str]` | Inserts each award not already held under its key **or an equivalent legacy key** (§3.2); returns the inserted keys |
| `get_reward_records(user_id) -> list[RewardRecord-shaped dicts]` | Used for the read model after cutover |

**Removed from the repository at integration time (shared file, owner approval):**
- the `score >= 4` / `py_master` insert in `save_assessment_attempt`;
- the grading, points and badge logic in `submit_daily_challenge`, which is replaced by `record_challenge_submission`.

### 5.3 Public contract preservation
| Endpoint | Fields | Status codes / messages |
|---|---|---|
| `POST /api/challenges/submit` | `challenge_id, is_correct, points_awarded, correct_option, explanation`: unchanged | 200; 400 ×3 messages exactly as in §3.1; 401 unchanged |
| `GET /api/challenges/daily` | unchanged (not touched) | unchanged |
| `POST /api/assessments/submit` | unchanged | unchanged |
| `GET /api/dashboard` | `metrics.total_points`, `metrics.challenges_attempted`, `badges[]`: same names and types | unchanged |

**Visible change that needs approval:** new high-score badges for users *without* `py_master` show the service's subject-specific text ("Python Programming Virtuoso" / "Scored 80%+ on the Python Programming assessment") under key `assessment.subj_python.high_score`.

---

## 6. File ownership boundaries for this integration

| Path | Owner | Change needed for G-6 | Approval |
|---|---|---|---|
| `backend/app/services/gamification_service.py` | **Ankush** | Small additions (§8) | Ankush |
| `backend/app/services/gamification_integration.py` (new) | **Ankush** | Orchestration + error mapping | Ankush |
| `backend/app/routers/challenges.py`, `schemas/challenges.py` | **Ankush** | Call the integration module; response unchanged | Ankush |
| `backend/tests/test_gamification_*.py` (new files) | **Ankush** | Tests in §7 | Ankush |
| `backend/app/database/repository.py` | **Shared: Nagin + Arsh + Ankush (SF-01)** | New methods; remove V1 reward logic | ⚠️ **Nagin and Arsh, after CR-15** |
| `backend/app/database/connection.py` | **Shared (SF-02)** | Ledger DDL + append-only triggers | ⚠️ **Nagin** |
| `database/schema.sql`, `database/seed.sql`, migration scripts | **Nagin** | Ledger DDL, backfill script | ⚠️ **Nagin** |
| `backend/app/routers/assessments.py` | **Arsh** | Call `eligible_assessment_achievements` + `award_badges` | ⚠️ **Arsh** |
| `backend/app/routers/dashboard.py`, `schemas/dashboard.py` | **Arsh** | Cutover read (M5) only | ⚠️ **Arsh** |
| `backend/tests/test_api_flow.py` | **Arsh** | None required; import-order hazard noted in GAMIFICATION_DESIGN §4 | ⚠️ **Arsh** if touched |
| `backend/app/main.py`, `routers/__init__.py` | **Shared (SF-03)** | None (no new routes for G-6) | – |
| `frontend/**` | **Shoeb** | None for parity. `ChallengePage.tsx:73` already shows "Daily Code Breaker" | – |
| `ai/**` | **Ekansh** | None | – |

---

## 7. Test plan (acceptance criteria)

All integration tests go in **new** files with their own temporary database fixture (`tmp_path` / `TMPDIR`), so they never depend on `test_api_flow.py` order or on the real `pragyax.db`. Modules are loaded so that `DATABASE_PATH` is set before any app import.

| # | Scenario | Acceptance criteria | Level | Engines |
|---|---|---|---|---|
| T1 | Valid first submission | 200; `is_correct=true`; `points_awarded=50`; 1 submission row; 1 ledger row with `event_key='daily_challenge:chal_today_py:<user>'`, `points_delta=50`; `daily_striker` held once; dashboard `total_points=50` | API | SQLite, PG |
| T2 | Wrong first submission | 200; `is_correct=false`; `points_awarded=0`; 1 submission row; **0** ledger rows; no badge; later correct retry → 400 repeat | API | SQLite, PG |
| T3 | Duplicate (sequential) | Second submit → 400 with the exact V1 message; still 1 submission row and ≤ 1 ledger row; points unchanged | API | SQLite, PG |
| T4 | Concurrent first submissions | N parallel submits by one user (threads, each with its own connection): exactly one 200, all others 400 repeat; **no 500**; 1 submission row; ≤ 1 ledger row; total = 50 | Integration | SQLite (`BEGIN IMMEDIATE`), PG |
| T5 | Invalid option | 400 `"selected_option must be A, B, C, or D."`; no rows written; a later valid submit is still accepted | API | both |
| T6 | Badge equivalence | User seeded with `py_master` scores 5/5 → **no** new high-score badge; user without it → exactly one `assessment.subj_python.high_score`; two concurrent high scores → one badge | Integration | both |
| T7 | Ledger idempotency | Writing the same event twice (same `event_key`) → one row; `aggregate_points` total unchanged; the append-only trigger rejects UPDATE/DELETE | Repository | both |
| T8 | Historical migration totals | Seed V1 rows (mixed users, correct, wrong) → run the backfill twice → V1–V5 all pass; per-user and grand totals equal pre-migration `SUM(points_awarded)`; row count unchanged after the second run | Migration | both |
| T9 | Restart persistence | After T1, open a fresh app/client on the same DB file → dashboard total, badges and the repeat-400 behaviour are unchanged | API | SQLite (file), PG |
| T10 | Multi-user isolation | Users A and B submit; each total counts only their own events; A's events never appear in B's records; event keys differ by `user_id` | API | both |
| T11 | Revocation | Revoke A's event → A's total drops by that amount; ledger row still present; double revocation rejected by `UNIQUE(ledger_id)` | Repository | both |
| T12 | Contract snapshot | `app.openapi()` for challenges, assessments and dashboard is identical before and after integration | API | – |
| T13 | Regression | Existing 136 tests still pass unchanged | Suite | SQLite |
| T14 | Pure-service parity | Existing `test_gamification_service.py` (117) still passes | Unit | – |

PostgreSQL tests run only against a **non-production** database supplied by Nagin, opt-in via an environment variable, and are skipped otherwise (reported as skipped, never as passed).

---

## 8. Risks and unresolved decisions

| ID | Decision / risk | Options | Recommendation | Decides |
|---|---|---|---|---|
| D-1 | Revocation model | (a) append-only + revocations table (this plan); (b) mutable `status` column (GAMIFICATION_DESIGN §3) | (a): satisfies append-only, keeps deltas non-negative | Ankush |
| D-2 | `py_master` handling (G-2) | Alias/equivalence (no data change) vs. rewrite rows | Alias | Ankush |
| D-3 | Ledger rows for zero-point correct answers | Record or skip | Record (`is_correct = 1` rows): completeness, total unaffected | Ankush |
| D-4 | Cutover timing | After N clean reconciliation runs | At least one full demo cycle green on V1–V4 | Ankush |
| D-5 | User deletion vs. append-only history | `ON DELETE CASCADE` like the other tables, or keep and anonymise | Decide before Supabase (privacy); undecided | Ankush + Nagin |
| D-6 | Where equivalence data lives | Service constant vs. DB table | Service constant (pure, versioned with the rules) | Ankush |
| R-1 | **CR-15 not landed:** `repository.py` is a shared 447-line file | – | Do not start G-6 repository work before the split | – |
| R-2 | SQLite on teammates' machines older than 3.35 / 3.39 | – | Implementation must check `sqlite3.sqlite_version` at startup; local version is 3.50.4 | Nagin |
| R-3 | Postgres timestamp typing (IC-06) breaks responses that carry `created_at` | – | Land CR-05 before running on Postgres | Arsh |
| R-4 | `test_api_flow.py` import-order hazard | – | New tests set `DATABASE_PATH` before app import; Arsh to harden the old file | Arsh |
| R-5 | Concurrency tests are timing-sensitive | – | Use a barrier so threads start together; assert invariants (row counts), not timings | Ankush |
| R-6 | Badge text change for new high scorers | – | Approve the subject-specific text, or keep "Python Virtuoso" for `subj_python` via a rule override | Ankush |
| R-7 | G-numbers absent from INTEGRATION_BASELINE §9 | – | Ankush adds them when deciding | Ankush |

---

## 9. Recommended next task (single, safest, Ankush-owned only)

**Add legacy badge equivalence to the pure service, with unit tests. No wiring.**

| Item | Detail |
|---|---|
| Files | `backend/app/services/gamification_service.py` (edit, Ankush-owned) and a **new** test file `backend/tests/test_gamification_equivalence.py`, so the existing 117 tests stay untouched |
| Add | `LEGACY_BADGE_EQUIVALENTS = {"assessment.subj_python.high_score": ("py_master",)}`; pure `filter_new_achievements(awards, held_badge_keys) -> tuple[AchievementAward, ...]` that drops awards whose key **or any equivalent legacy key** is already held, preserving order and deduplicating within `awards` |
| Tests | user holding `py_master` → high-score award filtered; holding the canonical key → filtered; holding neither → kept; unrelated badges (`daily_striker`) don't interfere; empty inputs; input order preserved; no mutation of inputs; deterministic |
| Why this one | It is the only G-6 prerequisite that touches **no** teammate-owned or shared file, needs **no** schema change or migration, and directly implements the V1-preservation guarantee in §3.2 that every later step relies on |
| Approval | D-2 (alias option) and D-6 must be accepted first; still requires Ankush's approval to start |
| Done when | New tests pass; existing 136 tests pass unchanged; no other file modified |
