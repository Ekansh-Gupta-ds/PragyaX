# PragyaX Daily Challenge Rotation Engine (G-3 foundation)

> **Owner:** Ankush · **Status (2026-10-27):** a pure, unit-tested domain module exists at `backend/app/services/daily_challenge_engine.py`.
> It is **not wired** into any router, repository, schema or table. The live app still serves the single static V1 challenge.
> Everything marked **PROPOSED** requires Ankush's approval, plus the listed owners' approval for their files.
> Related: [GAMIFICATION_DESIGN.md](GAMIFICATION_DESIGN.md) §5 (rotation sketch), [GAMIFICATION_INTEGRATION_PLAN.md](GAMIFICATION_INTEGRATION_PLAN.md) (G-1 … G-6), [INTEGRATION_BASELINE.md](INTEGRATION_BASELINE.md).

| Artifact | Path |
|---|---|
| Engine | `backend/app/services/daily_challenge_engine.py` |
| Tests (64) | `backend/tests/test_daily_challenge_engine.py` |
| This document | `docs/DAILY_CHALLENGE_ENGINE.md` |

---

## 1. Current V1 behaviour and limitations (from the code)

| Aspect | V1 | Evidence |
|---|---|---|
| Which challenge is served | `SELECT * FROM daily_challenges LIMIT 1`: always the one seeded row | `repository.py:372` |
| Seed | `chal_today_py`, answer `B`, **50 points**, `question_type='multiple_choice'` | `connection.py:284-305` |
| Subject | **None.** `daily_challenges` has no `subject_id`; the response schema has none either | `connection.py:129-148`, `schemas/challenges.py:9-25` |
| Date | **None.** No date column, no "today" logic; the "already completed … today" message is not date-based | `repository.py:406-407` |
| Answer key | `correct_option` and `explanation` nulled in `GET /challenges/daily` until the user has submitted; grading compares against the DB key | `repository.py:386-389, 409` |
| Completion | One submission per user per **challenge id**, ever (`UNIQUE(user_id, challenge_id)`); a wrong answer uses up the attempt | `connection.py:160`, `repository.py:401-418` |
| Reward identity | Points live on the submission row. The proposed ledger key is `daily_challenge:<challenge_id>:<user_id>` (`reward_event_key`) | `gamification_service.py`, `points_ledger_domain.py` |

Limitations that block rotation:
1. No subject or date columns, so there's nothing to rotate between and no notion of "today's" challenge.
2. Completion and reward identity are keyed by challenge id only. If a challenge reappears on a later date, the user can never attempt or earn it again, and the two dates can't be told apart.
3. `LIMIT 1` without `ORDER BY` relies on table order.
4. The selection rule is inside the repository (data layer), not testable on its own.

---

## 2. Selection algorithm

```
pool      = all challenges of one subject, sorted by challenge_id   (canonical order)
index     = challenge_date.toordinal() % len(pool)
selection = pool[index]
```

- **Deterministic:** the same `(pool, date)` always gives the same challenge. No randomness, no clock, no hashing.
- **Order-independent input:** the pool is canonicalised by `challenge_id` at construction, so the order challenges were loaded in (for example, DB row order) doesn't matter.
- **Round-robin:** consecutive dates step through the pool in id order, and each challenge recurs every `len(pool)` days. `date.toordinal()` is a timezone-free day counter (proleptic Gregorian), so month ends, year ends and leap days are handled without gaps.
- **Per subject:** each subject has its own pool and is selected independently (`select_daily_challenges` returns one per subject, ordered by `subject_id`).
- **Single-challenge pool:** always returns that challenge. This is exactly V1's behaviour, so V1 is the degenerate case.

**What it does not do.** Rotation is a predictable schedule, not a security control:
- **No prediction resistance:** anyone who knows the pool can compute any date's challenge. There's deliberately no "random" selection, and no claim of unpredictability.
- **Doesn't prevent replay:** challenges recur, and revealed answers can be shared.
- **Limited uniqueness:** consecutive dates differ only while the pool has ≥ 2 challenges **and stays unchanged**. With one challenge, every day is the same; after a pool edit, the sequence shifts and a challenge can repeat on back-to-back days.
- **Pool edits recompute the past:** adding or removing a challenge changes the computed schedule for *every* date, past ones included. Integration must therefore **persist the selected challenge per date** (§6) instead of recomputing history.

---

## 3. Models and function signatures

```python
@dataclass(frozen=True)
class ChallengeDefinition:                  # trusted, server-side; holds the answer key
    challenge_id: str; subject_id: str
    title: str; topic: str; difficulty: str; description: str; code_snippet: str
    option_a: str; option_b: str; option_c: str; option_d: str
    correct_option: str; explanation: str; points: int
    question_type: str = "multiple_choice"

@dataclass(frozen=True)
class ChallengePool:                        # one subject; challenges canonicalised (sorted by id)
    subject_id: str
    challenges: tuple[ChallengeDefinition, ...]

@dataclass(frozen=True)
class LearnerChallengeView:                 # learner-facing: NO correct_option / explanation fields
    challenge_id: str; subject_id: str; challenge_date: str   # 'YYYY-MM-DD'
    title: str; topic: str; difficulty: str; description: str; code_snippet: str
    question_type: str; option_a: str; option_b: str; option_c: str; option_d: str; points: int

def parse_challenge_date(value: str) -> date
def challenge_date_for(instant: datetime, platform_tz: tzinfo) -> date
def select_daily_challenge(pool: ChallengePool, challenge_date: date) -> ChallengeDefinition
def select_daily_challenges(pools: Iterable[ChallengePool], challenge_date: date) -> tuple[ChallengeDefinition, ...]
def to_learner_view(challenge: ChallengeDefinition, challenge_date: date) -> LearnerChallengeView
```

**Validation** raises the service-wide `InvalidTrustedInputError` for each of these:
- **Challenge ids:** must match `[A-Za-z0-9_.-]+` (the same characters as `reward_event_key` parts, so every challenge id is a valid ledger `source_id`), with at most 64 characters.
- **Subject ids:** the gamification service's existing `[A-Za-z0-9_-]+` rule.
- **Answer key, points and question type:** the answer key must be A–D and points an `int >= 0` (both via the existing service validators); `question_type` must be `multiple_choice`.
- **Text fields:** required and non-blank.
- **Pools:** an empty pool, duplicate challenge ids, a challenge from another subject, or a non-collection is rejected.
- **Subjects:** two pools for the same subject are rejected.
- **Dates:** a malformed or non-existent date (`2027-02-29`, `20261027`, timestamps) is rejected, and so is a `datetime` passed where a `date` is required (it would carry an unconverted time and timezone).

**Answer-key safety:**
- `LearnerChallengeView` *structurally* lacks the answer and explanation fields, so they can't leak through it.
- `to_learner_view` never mutates the trusted `ChallengeDefinition`, which keeps the key available for server-side grading via `gamification_service.ChallengeConfig(challenge_id, correct_option, points)`.

---

## 4. Dates and timezone assumptions

- A **challenge date** is an ISO calendar date (`YYYY-MM-DD`) in the **platform timezone**. The day changes at local midnight in that zone.
- **The engine never reads the clock.** The server computes `challenge_date_for(datetime.now(timezone.utc), PLATFORM_TZ)` at the edge (router/adapter) and passes a `date` in. Tests therefore use fixed dates.
- **`PLATFORM_TZ` is undecided (part of G-3):** UTC or `Asia/Kolkata` (UTC+05:30, no DST). Example: `2026-10-27T20:00Z` is challenge date 2026-10-27 in UTC but 2026-10-28 in IST. Any `tzinfo` works, including DST zones, because the conversion uses `astimezone`.
- **Clients never supply the date** for eligibility. The server decides "today"; a client-sent date may at most be validated against it.

---

## 5. Challenge identity vs reward identity

| Concept | Identity | Example |
|---|---|---|
| Challenge content | `challenge_id` | `py_lists_007` |
| Scheduled occurrence | `(subject_id, challenge_date)` → `challenge_id` | `subj_python`, `2026-10-27` → `py_lists_007` |
| Reward event (ledger idempotency) | `reward_event_key(user_id, source_type, source_id)` | V1: `daily_challenge:chal_today_py:usr_ab12` |

**Unchanged in this task:** `reward_event_key()`, the ledger event identity in `points_ledger_domain.py`, the V1 50-point rule, and the V1 completion rule.

**Why the key must evolve once rotation is live:** with round-robin, a challenge id recurs every `len(pool)` days. Under the V1 identity (`daily_challenge:<challenge_id>:<user>` and `UNIQUE(user_id, challenge_id)`), a user who solved `py_lists_007` once could never earn it on its next scheduled date. Both occurrences would also share one event key, making the ledger unable to tell them apart.

**PROPOSED versioned key (G-7, not implemented, requires Ankush's approval):**
- Keep `reward_event_key()` exactly as it is, and change only its **inputs** for dated challenges: `source_type = "daily_challenge_v2"`, `source_id = "<YYYY-MM-DD>.<challenge_id>"`.
  - Example key: `daily_challenge_v2:2026-10-27.py_lists_007:usr_ab12`.
  - Every character is already allowed by `reward_event_key`, and `.` cannot appear in a date, so the split is unambiguous.
  - `source_id` must fit 64 characters, so dated challenge ids are limited to 53 characters.
- V1 rows keep `source_type = "daily_challenge"`. The different `source_type` means legacy and v2 keys can never collide, and existing backfill identity (`rwd_v1_…`, `daily_challenge:<id>:<user>`) is unaffected.
- The matching completion rule becomes one submission per user per **(challenge_id, challenge_date)**. That is a schema change (§6) and needs approval; V1's completion rule is unchanged until then.

---

## 6. Future schema and interface requirements (PROPOSED)

| Change | Purpose | Owner | Approval |
|---|---|---|---|
| `daily_challenges.subject_id` (FK `subjects.id`) + `is_active` | Build per-subject pools; retire content without deleting it | Nagin | Ankush (G-3) |
| `daily_challenge_schedule(challenge_date, subject_id, challenge_id, created_at)` with **PK (challenge_date, subject_id)** | Freeze the selection the first time a date is served, so pool edits never rewrite history; written with `INSERT … ON CONFLICT DO NOTHING` | Nagin | Ankush (G-3) |
| `user_challenge_submissions.challenge_date` + `UNIQUE(user_id, challenge_id, challenge_date)` | One attempt per occurrence instead of per challenge forever | Nagin | Ankush (G-3, G-7) |
| Ledger keys `daily_challenge_v2` (§5) | Distinct reward per occurrence | Ankush (rules), Nagin (rows) | Ankush (G-7) |
| Platform timezone constant (`PLATFORM_TZ`) | Defines the day boundary | Ankush | Ankush (G-3) |
| `GET /api/challenges/daily`: optional `subject_id` query parameter, additive `subject_id` and `challenge_date` fields | Serve the selected subject's challenge | Ankush (router), Shoeb (UI) | Ankush; CR in INTEGRATION_BASELINE §9 (additive, so existing fields stay) |
| `POST /api/challenges/submit`: the server derives today's challenge; submits for a non-current challenge are rejected with 400 | Prevents answering stale or future challenges | Ankush | Ankush (behaviour change) |
| Repository: `get_challenge_pool(subject_id)`, `get_or_create_schedule(date, subject_id, challenge_id)` | Data access only, no selection logic | Nagin/Arsh (shared `repository.py`, after CR-15) | Owners + Ankush |

---

## 7. Future platform, college and company challenges

The engine selects from *a pool* for *a date*. Scoping is the caller's choice of pool, so these can come later without changing the algorithm:
- **Pool scope:** a pool key becomes `(scope, subject_id)`, where `scope` is `platform`, `college:<college_id>` or `company:<company_id>`. Each scope keeps its own pools and schedule rows (add `scope` to the schedule PK).
- **Identity:** challenge ids must stay **globally unique** across scopes. Reward keys would use a scope-specific `source_type` (e.g. `college_challenge_v1`) so scopes never share a ledger key.
- **Eligibility** (membership of a college or company) is an authorisation check in the router or adapter, not part of selection.
- **Competitions and battles** (time-boxed, multi-user) are a different product: they would reuse `ChallengeDefinition` and `LearnerChallengeView`, but not daily rotation.

None of this is implemented.

---

## 8. Integration ownership and approvals

| Step | Files | Owner | Approval |
|---|---|---|---|
| Decide `PLATFORM_TZ`, G-3, G-7 | docs | Ankush | Ankush |
| Schema: subject, schedule, dated submissions | `database/`, `connection.py` (shared SF-02) | Nagin | ⚠️ Nagin + Ankush |
| Repository methods | `repository.py` (shared SF-01, after CR-15) | Nagin + Arsh | ⚠️ Nagin, Arsh + Ankush |
| Router: select pool → schedule → `to_learner_view`; grade via `ChallengeConfig` | `routers/challenges.py`, `schemas/challenges.py` | Ankush | Ankush; additive response CR |
| Ledger v2 keys | `points_ledger_domain.py` (inputs only) | Ankush | Ankush (G-7) |
| UI: subject picker, date display | `frontend/` | Shoeb | ⚠️ Shoeb + Ankush |
| AI | – | Ekansh | No dependency |

Until then: **no production or demo rotation.** The V1 challenge, its 50 points and its completion rule stay as they are.

---

## 9. Acceptance criteria

**Pure engine (met now; 64 unit tests):**
- the same date gives the same challenge;
- consecutive dates follow round-robin in id order, crossing month, year and leap-day boundaries;
- per-subject pools, and input-order independence;
- empty pools, duplicate ids, malformed ids, malformed dates and wrong types are all rejected;
- a single-challenge pool behaves like V1;
- leap days are valid; timezone boundaries behave as documented;
- the learner view has no answer fields, and the trusted model is not mutated;
- immutable models; no use of random state, clock, files, network or database;
- existing gamification and ledger behaviour is unchanged.

**Integration (future, for approval):**
1. With rotation disabled, `GET/POST /api/challenges/*` responses and status codes are byte-for-byte unchanged (OpenAPI snapshot plus the existing API tests).
2. A date served twice returns the stored schedule row even after the pool changes.
3. A learner never receives `correct_option` or `explanation` before submitting, for any subject.
4. One reward per user per `(challenge_id, challenge_date)`; concurrent submits give exactly one award (DB constraint), and repeats get the V1 400 message.
5. A recurring challenge can be earned again on its new date (v2 key), while V1 legacy keys and totals are unchanged.
6. Day boundaries follow `PLATFORM_TZ` (tests at 23:59:59 and 00:00:00 local time).
7. Multi-user isolation and restart persistence hold, on SQLite and Postgres.

---

## 10. Known limitations
- Predictable by design; not a fairness or anti-cheat mechanism.
- No guaranteed uniqueness on consecutive dates for one-item pools, or after pool edits.
- Authors control the order only through challenge ids (sorted order); there's no difficulty balancing, weighting or spaced repetition.
- Pool edits change computed history; a persisted schedule (§6) is required before production use.
- No content versioning: editing a challenge's text or answer under the same id affects every date it appears on.
- Only `multiple_choice` with options A–D is supported.
- Not connected to routes, storage, the ledger or the frontend.
