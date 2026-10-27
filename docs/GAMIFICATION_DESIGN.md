# PragyaX Gamification Design (Phase 2 foundation)

> **Owner:** Ankush · **Status (2026-10-27):** the pure domain service exists and is unit-tested. It is **not wired** into any router, repository or database table.
> No persistent ledger, date rotation, leaderboard, route or database write exists yet. Everything marked **PROPOSED** requires Ankush's approval and the listed owners' coordination before implementation.
> Related: [INTEGRATION_BASELINE.md](INTEGRATION_BASELINE.md) (contracts, CR-08 / CR-14 / CR-15), [PHASE2_DEPENDENCIES.md](PHASE2_DEPENDENCIES.md) (Step 2c, Step 3d, Step 5).

| Artifact | Path |
|---|---|
| Domain service | `backend/app/services/gamification_service.py` |
| Unit tests | `backend/tests/test_gamification_service.py` |
| This document | `docs/GAMIFICATION_DESIGN.md` |

---

## 1. Current V1 behaviour (as found in the code)

Line numbers refer to the files as of 2026-10-27.

### 1.1 Assessment achievement ("Python Virtuoso")
| Aspect | V1 behaviour | Evidence |
|---|---|---|
| Trigger | Inside `Repository.save_assessment_attempt`, right after the attempt row is inserted | `backend/app/database/repository.py:207-251`; called from `routers/assessments.py:107-118` |
| Eligibility | `if score >= 4` (absolute score; **not** a percentage, **not** subject-aware) | `repository.py:245` |
| What is written | `user_badges` row: `badge_key='py_master'`, title `Python Virtuoso`, description `Scored 80%+ on the 5-Question Python Assessment`, icon `award`, id `bdg_<8 hex>` | `repository.py:246-249` |
| Duplicates | `INSERT OR IGNORE` + `UNIQUE(user_id, badge_key)` → at most one per user, ever | `repository.py:247`; `connection.py:176` |
| Atomicity | Same connection/transaction as the attempt insert (committed together by `get_db`) | `connection.py::get_db` |
| Points | **None.** Assessments award no points | – |

### 1.2 Daily challenge
| Aspect | V1 behaviour | Evidence |
|---|---|---|
| Which challenge | `SELECT * FROM daily_challenges LIMIT 1`: one static row, no date logic | `repository.py:372` |
| Seeded challenge | `chal_today_py`, correct option `B`, **50 points** (column default is also 50) | `connection.py:284-305`, `:145` |
| Answer visibility | `correct_option` and `explanation` set to `null` until this user has a submission | `repository.py:386-389` |
| Option validation | Router rejects anything other than A–D (case-insensitive) with 400 **before** the repository is called, so an invalid option does not use up the attempt | `routers/challenges.py:32-36` |
| Unknown challenge id | `{"error": "Challenge not found"}` → 400 | `repository.py:398-399`; `challenges.py:44-48` |
| Correctness | `selected_option.strip().upper() == correct_option.upper()`, compared against the DB answer key | `repository.py:409` |
| Reward amount | `points = chal["points"] if is_correct else 0`, taken from the DB row (never from the client) | `repository.py:410` |
| Attempts | **One submission per user per challenge, right or wrong.** A wrong answer stores `points_awarded=0` and locks the challenge | `repository.py:413-418`; `UNIQUE(user_id, challenge_id)` `connection.py:160` |
| Repeat submission | Pre-check finds the existing row → `{"error": "Challenge already completed by this user today"}` → **400**; no evaluation, no new row, no points | `repository.py:401-407` |
| Badge | On a correct answer: `INSERT OR IGNORE` `daily_striker` / `Daily Code Breaker` / `Solved today's Python code snippet challenge` / `zap` | `repository.py:420-425` |
| Response | `{challenge_id, is_correct, points_awarded, correct_option, explanation}` | `repository.py:427-433`; `schemas/challenges.py:33-38` |
| Tests | First correct submit = 50 points; repeat = 400 "already completed" | `backend/tests/test_api_flow.py:291-323` |

### 1.3 Points and badges on the dashboard
- `total_points = COALESCE(SUM(points_awarded), 0)` and `challenges_attempted = COUNT(*)` over `user_challenge_submissions` for the user (`repository.py:320-321, 355-356`). **The submissions table is the de facto points ledger.**
- Badges: `get_user_badges` lists the user's `user_badges` rows, newest first (`repository.py:435-446`).
- Frontend coupling: `frontend/src/pages/ChallengePage.tsx:73` hard-codes the text "Badge: Daily Code Breaker". `DashboardPage.tsx` maps badge icons `zap`/`award`, and anything else renders as a trophy.

### 1.4 Reward amounts (complete list)
| Event | Points | Badge |
|---|---|---|
| Daily challenge, first submission, correct | `daily_challenges.points` (seed: 50) | `daily_striker` (once per user) |
| Daily challenge, first submission, wrong | 0 | – |
| Daily challenge, repeat submission | rejected (400), 0 | – |
| Assessment attempt, score ≥ 4 | 0 | `py_master` (once per user) |
| Assessment attempt, score < 4 | 0 | – |
| Chat, subject selection, registration | 0 | – |

### 1.5 Known V1 limitations
1. **Business rules live in the data layer** (`repository.py`): the badge threshold, challenge grading, points and badge awards are mixed with SQL (SF-01 in the baseline).
2. **The assessment badge is not subject-specific.** Key `py_master` and the "Python" text are used for any subject.
3. **The threshold is absolute** (`score >= 4`). It only means "80%" when the assessment has exactly 5 questions.
4. **One static challenge.** "Today" in the repeat message is misleading; there is no date, rotation or streak.
5. **No ledger.** Points exist only as `points_awarded` on submissions: no event identity, no revocation, no audit trail, no other point sources.
6. **Race on repeat submits** (by code reading, not reproduced): the check-then-insert at `repository.py:401-418` relies on `UNIQUE(user_id, challenge_id)`. Two concurrent first submissions would make the second insert raise `sqlite3.IntegrityError`, which nothing catches → HTTP 500 instead of 400. Points cannot be double-awarded, because the constraint holds.
7. **No validation of reward config.** `daily_challenges.points` has no `CHECK (points >= 0)` in SQLite or `database/schema.sql`; a negative value would be stored and summed.
8. **Badge metadata is hard-coded in SQL strings**, and the frontend repeats one badge title.
9. **`user_submission`** in the challenge response is an untyped raw row (`is_correct` as `0/1`, includes `user_id`), as noted in INTEGRATION_BASELINE IC-08.

---

## 2. The new pure service

### 2.1 Principles
- **Standard library only** (`re`, `dataclasses`, `enum`, `collections.abc`). No SQL, no connections, no FastAPI, no I/O, no clock, no randomness. A unit test enforces this by parsing the module's imports.
- **Trusted inputs decide rewards.** Points come only from a `ChallengeConfig` built from the DB row; no function accepts a reward amount from a caller. Scores come from backend grading.
- **Score ≠ points.** The service *consumes* an assessment score to decide achievements. It never computes scores, and achievements carry no points.
- **Immutable results** (frozen dataclasses, tuples). Module constants are never mutated.
- **Two error classes** (both `ValueError` subclasses via `GamificationError`):
  - `InvalidSubmissionError`: a learner-supplied value is bad → **400** once wired.
  - `InvalidTrustedInputError`: server data (answer key, reward config, score, rule, subject id) is bad → **500** plus logging once wired.

### 2.2 Domain models
| Model | Fields | Notes |
|---|---|---|
| `ChallengeConfig` | `challenge_id: str, correct_option: str, points: int` | Validated on construction: non-empty id, answer key A–D, `points` an `int >= 0` (bools rejected). Build from `daily_challenges` only |
| `ChallengeRewardDecision` | `challenge_id, is_correct: bool, points_awarded: int, reason: RewardReason, achievements: tuple[AchievementAward, ...]` | `is_repeat_submission` property |
| `RewardReason` (StrEnum) | `correct_answer`, `incorrect_answer`, `already_completed` | |
| `AchievementAward` | `badge_key, title, description, icon` | Mirrors `user_badges` / `BadgeItem`. Eligibility only; the DB's `UNIQUE(user_id, badge_key)` decides whether a row is inserted |
| `AssessmentAchievementRule` | `key, min_percent: int (0..100), title, description, icon` | `{subject}` and `{min_percent}` placeholders. Validated on construction |
| `RewardRecord` | `event_key: str, points: int, status: str = "awarded"` | A persisted ledger row. Deliberately **not** validated on construction (see `aggregate_points`) |
| `RewardStatus` (StrEnum) | `awarded`, `revoked` | |
| `PointsSummary` | `total_points, counted_records, invalid_records, not_awarded_records, duplicate_records` | Counts make data problems visible instead of silent |

Constants:
- `ASSESSMENT_ACHIEVEMENT_RULES`: one rule, `high_score` at ≥ 80% (V1 parity).
- `DAILY_CHALLENGE_ACHIEVEMENT`: byte-identical to the V1 `daily_striker` badge.
- `VALID_OPTIONS = ("A","B","C","D")`.
- `MAX_BADGE_KEY_LENGTH = 64` (from `user_badges.badge_key VARCHAR(64)` in `database/schema.sql`).

### 2.3 Functions
| Function | Input → output | Raises |
|---|---|---|
| `is_challenge_answer_correct(selected_option, correct_option)` | → `bool`. Same normalisation as V1 (`strip().upper()`) | `InvalidSubmissionError` (bad learner option), `InvalidTrustedInputError` (bad key) |
| `compute_challenge_reward(challenge, selected_option, *, already_completed)` | → `ChallengeRewardDecision`. First correct = `challenge.points` + `daily_striker`; first wrong = 0; repeat = 0, `already_completed`, no achievements | `InvalidSubmissionError` (validated first, even on repeats, matching V1 router order); `InvalidTrustedInputError` (non-`ChallengeConfig` challenge, non-bool flag) |
| `eligible_assessment_achievements(score, total, subject_id, subject_title, rules=ASSESSMENT_ACHIEVEMENT_RULES)` | → `tuple[AchievementAward, ...]` in rule order; eligible iff `score*100 >= min_percent*total` (integer maths) | `InvalidTrustedInputError`: `total < 1`, `score < 0`, `score > total`, non-int or bool values, bad subject id, blank title, duplicate or foreign rules. **All inputs are validated before any rule is evaluated** |
| `assessment_badge_key(subject_id, rule_key)` | → `"assessment.<subject_id>.<rule_key>"`, ≤ 64 chars | `InvalidTrustedInputError` |
| `reward_event_key(user_id, source_type, source_id)` | → `"<source_type>:<source_id>:<user_id>"` (parts limited to `[A-Za-z0-9_.-]`, so the key is unambiguous) | `InvalidTrustedInputError` |
| `aggregate_points(records)` | → `PointsSummary`. Counts a record only if it is a `RewardRecord` with a non-blank key, `int` points ≥ 0 (no bools) and status `awarded`; **each event key counts at most once** (first valid awarded record wins). Invalid or non-awarded rows never claim a key | never raises on bad rows; reports them |

Why a badge key looks like `assessment.subj_python.high_score`:
- **Stable:** derived from the immutable `subject_id`, never the display title, so renaming a subject never duplicates badges.
- **Subject-specific.**
- **Unambiguous:** subject ids cannot contain `.`.
- **Fits the column:** `VARCHAR(64)` allows subject ids up to 42 characters (UUIDs fit).

### 2.4 Differences between the service rules and V1
| Rule | V1 | Service | Impact when wired |
|---|---|---|---|
| Assessment badge key | `py_master` for every subject | `assessment.<subject_id>.high_score` | **Persisted data:** existing `py_master` rows need a migration or alias (§8, G-2), otherwise Python users could receive a second, equivalent badge |
| Assessment threshold | `score >= 4` (absolute) | `score/total >= 80%` | Identical for the current 5-question test (4/5 and 5/5). Differs for other totals (e.g. 4/10: V1 awards, service does not) |
| Assessment badge text | "Python Virtuoso" / "Scored 80%+ on the 5-Question Python Assessment" | "`<Subject title>` Virtuoso" / "Scored 80%+ on the `<Subject title>` assessment" | New awards display different text; existing rows unchanged |
| Score/total validation | None | Rejects invalid values (500 once wired) | Surfaces grading bugs instead of awarding silently |
| Negative challenge points | Stored and summed | `ChallengeConfig` rejects them | Bad seed data fails loudly |
| Corrupt answer key (not A–D) | Every answer silently "wrong" | `InvalidTrustedInputError` | Bad seed data fails loudly |
| Repeat submission | Rejected with 400 before evaluation | Decision with `points_awarded=0`, `reason=already_completed` | **No API change if the router keeps returning the V1 400 message** (§7) |
| Points total | `SUM(points_awarded)` over submissions | `aggregate_points`: valid, awarded, unique event keys only | Equal for valid V1 data (one row per user per challenge, points ≥ 0) |
| Daily challenge badge | `daily_striker` | Unchanged (V1 parity) | None. **Not subject-specific**, because `daily_challenges` has no subject column (G-3) |
| Wrong answer uses up the attempt | Yes | Yes (`incorrect_answer`, caller records the completion) | None |

### 2.5 Test coverage (`backend/tests/test_gamification_service.py`)
- **Answers:** correct and incorrect answers, normalisation, invalid learner options, corrupt keys.
- **Challenge rewards:** first correct, first wrong, repeat (correct and wrong), zero and positive rewards, negative and non-integer reward config, forged dict config, non-bool completion flag, and the signature test proving no reward-amount parameter exists.
- **Assessments:** scores 0–5 on a 5-question test, percentage thresholds on other totals, invalid scores and totals, subject-specific keys and titles, key stability across title changes, invalid subject ids at every score, badge-key length limit and UUIDs, multi-tier rule ordering, invalid and duplicate rules.
- **Points:** event-key format and ambiguity rejection; aggregation of an empty history, valid-only summing, duplicates, first-wins, and invalid or revoked rows not claiming keys.
- **Determinism and purity:** deterministic results, any-iterable input, immutability, inputs not mutated, and the stdlib-only import guard.

The module is loaded by file path, so these tests never import `backend.app` (see the test isolation note in §4).

---

## 3. Proposed persistent ledger (PROPOSED, not implemented)

**Owner:** Nagin (schema and repository) with Ankush (rules). **Requires Ankush's approval** (G-1).

```sql
-- PROPOSED. Postgres syntax; SQLite equivalent uses TEXT/INTEGER and the same constraints.
CREATE TABLE points_ledger (
    id           VARCHAR(64) PRIMARY KEY,                    -- 'pts_<hex>'
    user_id      VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_key    VARCHAR(255) NOT NULL UNIQUE,               -- reward_event_key(user, source_type, source_id)
    source_type  VARCHAR(32)  NOT NULL,                      -- 'daily_challenge' (later: 'battle', 'referral', ...)
    source_id    VARCHAR(64)  NOT NULL,                      -- e.g. challenge id
    points       INTEGER      NOT NULL CHECK (points >= 0),
    status       VARCHAR(16)  NOT NULL DEFAULT 'awarded' CHECK (status IN ('awarded', 'revoked')),
    reason       VARCHAR(32)  NOT NULL,                      -- RewardReason value
    created_at   TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_points_ledger_user ON points_ledger (user_id);
CREATE INDEX idx_points_ledger_created ON points_ledger (created_at);   -- leaderboard windows
```

The database enforces the same rules `aggregate_points` checks:
- `CHECK (points >= 0)` ↔ negative records are invalid.
- `UNIQUE (event_key)` ↔ each event counts once.
- `status` ↔ only `awarded` rows count.

**Write path** for a challenge submission, in **one transaction**:
1. Load the challenge row → `ChallengeConfig` (trusted).
2. Decide with `compute_challenge_reward(config, selected, already_completed=<pre-check>)`.
3. Insert the submission with `ON CONFLICT (user_id, challenge_id) DO NOTHING`. If nothing was inserted, a concurrent request won: recompute with `already_completed=True`, write nothing else, and answer as a repeat.
4. If `points_awarded > 0`: insert a ledger row with `ON CONFLICT (event_key) DO NOTHING`.
5. For each achievement: insert into `user_badges` with `ON CONFLICT (user_id, badge_key) DO NOTHING`.
6. Commit; any error rolls back all of it.

**Read path:** `SELECT COALESCE(SUM(points),0) FROM points_ledger WHERE user_id=? AND status='awarded'`. In Python, map rows to `RewardRecord` and call `aggregate_points` when per-record diagnostics are wanted.

**Backfill from V1 (idempotent):**
- Source: every `user_challenge_submissions` row with `points_awarded > 0`.
- Ledger row: `event_key = 'daily_challenge:<challenge_id>:<user_id>'`, `points = points_awarded`, `reason = 'correct_answer'`.
- Insert with `ON CONFLICT DO NOTHING`.
- Verification: the ledger total per user must equal V1's `SUM(points_awarded)`.

**Revocation:** set `status='revoked'` on the existing row. Never insert negative "compensating" rows, because the service and the CHECK reject negative points.

---

## 4. Idempotency and concurrency requirements

1. **Every reward has a deterministic event key** (`reward_event_key`). Retries, double clicks and replays must map to the same key.
2. **The database is the arbiter.** Uniqueness comes from `UNIQUE` constraints (`points_ledger.event_key`, `user_challenge_submissions(user_id, challenge_id)`, `user_badges(user_id, badge_key)`), never from a Python pre-check alone. Pre-checks are only a fast path.
3. **Conflicts are expected, not errors.** Use `INSERT … ON CONFLICT DO NOTHING` (SQLite ≥ 3.24 and Postgres) and map "nothing inserted" to a repeat decision: 0 points, and the V1 400 "already completed" response. This fixes the V1 race that can surface as a 500 (§1.5 item 6).
4. **One transaction** covers the submission, the ledger row and the badges; a partial award is impossible.
5. **Server-trusted values only:** points from `daily_challenges`, correctness from the stored key, dates from the server clock (UTC). The request carries only `challenge_id` and `selected_option`.
6. **No negative ledger rows.** Corrections are status changes (`revoked`), so totals are monotonic sums of non-negative values.
7. **Reads are tolerant.** Dashboards and leaderboards use `aggregate_points` semantics (skip and report anomalies) rather than failing the page.

### Test isolation note (pre-existing, not changed)
`backend/tests/test_api_flow.py` sets `DATABASE_PATH` (line 27) **before** importing the app (line 30). Any test module collected earlier that imports `backend.app.*` would fix the database path first, and the API tests would then write to the real `pragyax.db`. The new gamification tests avoid this by loading the service by file path. Making `test_api_flow.py` robust (e.g. a fixture that sets the path before any app import) is Arsh's file and needs his change.

---

## 5. Future daily-challenge rotation (PROPOSED)

**Requires Ankush's approval** (G-3) and a schema change by Nagin.
- **Schema options:**
  - **(a)** Add `challenge_date DATE UNIQUE` and `subject_id` to `daily_challenges`, one row per day. The event key stays `daily_challenge:<challenge_id>:<user_id>`.
  - **(b)** A `daily_challenge_schedule(challenge_date PRIMARY KEY, challenge_id)` table so challenges can be reused. The event key must then include the date (e.g. `source_id = "<challenge_id>@<YYYY-MM-DD>"`, already allowed by `reward_event_key`).
  - **Recommendation: (a)** for the hackathon.
- **Defining "today":** decide one timezone (UTC vs `Asia/Kolkata`); the server computes it and the client never sends a date.
- **Eligibility:** only today's challenge can be submitted. Past or future ids → 400. The pure function would gain an eligibility input (e.g. "not active today") in a later, approved change.
- **Answer reveal:** after the user's submission (as today) or after the day ends.
- **Subject-specific daily badge:** possible once `daily_challenges.subject_id` exists (e.g. `daily.<subject_id>.first_correct`). Until then, `daily_striker` stays.
- **Streaks:** consecutive dates with a correct submission, derived from the ledger or submissions (not stored as a counter).
- **No challenge for today:** keep V1's 404 "No daily challenge active at this time."

## 6. Future leaderboards (PROPOSED)

**Requires Ankush's approval** (G-4: new router `routers/leaderboard.py`, Ankush-owned).
- **Source:** `points_ledger` only (`status='awarded'`), the same rules as `aggregate_points`.
- **Windows:** all-time, and weekly (week start in the chosen timezone).
- **Deterministic ranking:** `points DESC`, then the time the total was reached (`MAX(created_at) ASC`), then `user_id ASC`. Decide between competition ranking (1, 1, 3) and dense ranking (1, 1, 2).
- **Privacy:** show `users.name` only, never emails. Add an opt-out flag later (schema change).
- **Performance:** indexes on `user_id` and `created_at`; top-N plus the caller's own rank; cache or a materialised total if needed.
- **Integrity:** only server-created ledger rows count; revocations drop out automatically.
- **Sketch:** `GET /api/leaderboard?window=weekly&limit=20` → `{entries: [{rank, name, points}], me: {rank, points}}`.

---

## 7. How the service will integrate into FastAPI (future, not done)

None of this is implemented. Each step needs the listed approval.

| Where | Change | Owner | Contract impact |
|---|---|---|---|
| `routers/challenges.py` `submit_challenge` | Build `ChallengeConfig` from the DB row, call `compute_challenge_reward`, persist via the repository. Map `InvalidSubmissionError`→400 and `InvalidTrustedInputError`→500 (logged). On a repeat, return the **existing** 400 "Challenge already completed by this user today" | Ankush (router), Nagin/Arsh (repository) | None if the messages and shape are kept |
| `repository.py` `submit_daily_challenge` | Becomes persistence only: insert the submission/ledger/badge rows given a decision, using `ON CONFLICT`. Grading and badge rules removed | Nagin + Arsh (shared file SF-01; after the CR-15 split) | None |
| `routers/assessments.py` after `save_assessment_attempt` | Call `eligible_assessment_achievements(score, total, subject_id, subject_title)` and insert each award idempotently | Arsh | New badge keys and text (§2.4); **requires G-2 first** |
| `repository.py` `save_assessment_attempt` | Remove the hard-coded `score >= 4` / `py_master` insert | Nagin + Arsh | Same as above |
| `routers/dashboard.py` / `get_user_dashboard_metrics` | `total_points` from the ledger (after G-1); `challenges_attempted` stays from submissions | Arsh | None (same field) |
| Imports | Routers import `backend.app.services.gamification_service` directly; pure functions need no dependency injection | – | – |
| Tests | Integration tests in **new** files with isolated temporary-database fixtures | Owner of each step | – |

Ordering:
1. INTEGRATION_BASELINE CR-15 (repository split) lands first.
2. Then G-1 (ledger) and G-2 (badge key migration).
3. Then the router wiring.

CR-12 (moving scoring out of `ai/`) is independent: achievements only need the final `score`/`total`, wherever they are computed.

---

## 8. Coordination and approvals

The baseline already holds related CRs: **CR-08** (typed `user_submission`), **CR-14** (subject-specific badges) and **CR-15** (repository split and gamification service). The gamification-specific proposals below should be added to [INTEGRATION_BASELINE.md §9](INTEGRATION_BASELINE.md#9-proposed-contract-changes) when Ankush reviews them. They are numbered G-n here to avoid colliding with existing CR numbers.

| ID | Proposal | Needs | Owner(s) | Status |
|---|---|---|---|---|
| G-1 | `points_ledger` table + idempotent V1 backfill | Schema (SQLite init + `database/schema.sql`), repository methods | Nagin, Ankush | **PROPOSED — requires Ankush's approval** |
| G-2 | Migrate `user_badges.badge_key='py_master'` → `assessment.subj_python.high_score` (valid because Python is the only active subject in V1), or keep `py_master` as an alias | Data migration, decision on old badge text | Nagin, Ankush | **PROPOSED — requires Ankush's approval** |
| G-3 | `daily_challenges.challenge_date` + `subject_id`; timezone decision | Schema, seeds, repository | Nagin, Ankush | **PROPOSED — requires Ankush's approval** |
| G-4 | `GET /api/leaderboard` | New router, schema, frontend page | Ankush, Shoeb | **PROPOSED — requires Ankush's approval** |
| G-5 | Additional assessment tiers (e.g. `perfect_score` at 100%) | Rule-table change only (no code); frontend already renders unknown icons as a trophy | Ankush | **PROPOSED — requires Ankush's approval** |
| G-6 | Wire the service into the challenges/assessments routers and the dashboard (§7) | Router + repository changes | Ankush, Arsh, Nagin | **PROPOSED — requires Ankush's approval** |

What each person needs to know:
- **Nagin:** G-1, G-2 and G-3 are schema or data changes; nothing in this phase touched the schema.
- **Arsh:** `assessments.py`/`dashboard.py` wiring (G-6); `test_api_flow.py` import-order robustness (test isolation note in §4).
- **Shoeb:** `ChallengePage.tsx` hard-codes the "Daily Code Breaker" text (unchanged by the service); leaderboard UI (G-4).
- **Ekansh:** no dependency. The AI never awards points, and gamification never calls the AI.

---

## 9. Intentionally unimplemented in this phase
- Any wiring of the service into routers, the repository or the dashboard: the running app still uses the V1 logic in `repository.py`.
- The persistent ledger, any table or column, any migration or backfill, any database write.
- Date-based rotation, streaks, leaderboards, new routes or response fields.
- New badges or tiers in the live app (the rule table holds only the V1-parity rule).
- Migration of existing `py_master` badges.
- Points for assessments, chat or any source other than daily challenges.
- 1v1 battles, referrals, certificates, competitions.
- Frontend changes.
