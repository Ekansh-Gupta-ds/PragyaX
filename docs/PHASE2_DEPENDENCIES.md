# PragyaX Phase 2: Safe Implementation Order & Migration Paths

> **Status:** Plan only. Nothing in this document is implemented.
> Every step that changes an API field, status code, route, DB table/column, `ai/base.py` signature, or dependency references a CR in [INTEGRATION_BASELINE.md §9](INTEGRATION_BASELINE.md#9-proposed-contract-changes) and **requires Ankush's approval before work starts**.
> Baseline at the time of writing: 19 backend tests passing, frontend `tsc` clean, SQLite + Mock AI.

---

## 1. Ground rules

1. **Green baseline is the gate.** Every step ends with `pytest backend/tests` passing and `tsc -p frontend` clean, plus the new tests for that step.
2. **Default behaviour never changes silently.** SQLite and the Mock AI stay the defaults until Ankush approves a switch. New backends sit behind environment flags.
3. **No contract change without an approved CR.** That covers HTTP fields, status codes, routes, tables/columns, `ai/base.py` and dependencies.
4. **Additive first.** Add the new path next to the old one, prove it, then retire the old one in a separate approved step.
5. **One editor per shared file at a time** (see [INTEGRATION_BASELINE.md §7](INTEGRATION_BASELINE.md#7-shared-file-ownership-conflicts)) until the repository split (Step 2) lands.
6. **Secrets stay in the backend environment.** No keys in the frontend, repo, docs or tests.

---

## 2. Dependency graph

```
Step 0  Contract freeze (Ankush)  ──────────────────────────────┐
   │                                                            │
Step 1  Contract hardening, backward-compatible (Arsh)          │ Shoeb: UI-only work
   │      CR-01 CR-02 CR-04 CR-07 CR-09 CR-10                   │ (no type changes)
   │                                                            │
Step 2  Seams (no behaviour change)                             │ Ekansh: real-provider
   │   2a Repository interface + split (Arsh + Nagin)   CR-15   │ prototype for chat only,
   │   2b Scoring moved out of AI (Arsh + Ekansh)       CR-12   │ behind AI_PROVIDER, using
   │   2c Gamification service (Ankush)                 CR-15   │ the existing ai/base.py
   │                                                            │
Step 3  Parallel feature tracks ◀───────────────────────────────┘
   │   3a Postgres implementation (Nagin)          CR-05 CR-06 CR-16 CR-20
   │   3b Real AI provider (Ekansh)                CR-16
   │   3c Baseline assessment + typed client (Shoeb + Arsh)   CR-13 CR-17 CR-19
   │   3d Date-based challenges (Ankush)           CR-08 CR-14
   │
Step 4  Integration on a non-production Supabase project + live AI key (all)
   │
Step 5  Ankush modules: leaderboard → battles / referrals / certificates
```

**Why this order**
- Step 0 before everything: without a frozen contract, the parallel tracks drift (SF-07 and the hand-mirrored `types.ts`).
- Step 2a before 3a: Postgres needs an interface to implement; today it would mean rewriting a 447-line shared file (SF-01).
- Step 2b before 3b: otherwise a real LLM would own the score (IC-16).
- Step 2c before 5: points and badges must leave the data layer before the leaderboard reads them.
- Step 1 before 3a: the timestamp/typing fixes (IC-06) prevent 500s once Postgres returns `datetime`.

---

## 3. Steps in detail

### Step 0: Contract freeze (Ankush) · no code
| Item | Detail |
|---|---|
| Deliverable | Approve or reject CR-01…CR-20; save an `openapi.json` snapshot next to the docs as the reference |
| Prerequisite | This document and INTEGRATION_BASELINE.md reviewed |
| Gate | Every CR has a status |
| Unblocks | Everything |

### Step 1: Backward-compatible contract hardening (Arsh)
| Item | Detail |
|---|---|
| Scope | CR-01 (type `recent_attempts`), CR-02 (chat `subject: null` 500), CR-04 (chat `created_at`), CR-07 (literal types), CR-09 (health/logout models), CR-10 (`subject_title`) |
| Files | `backend/app/schemas/*.py`, `routers/{chat,dashboard,health,auth,assessments}.py` |
| Approval | **Requires Ankush's approval** (each CR) |
| Gate | Existing 19 tests pass unchanged; new test proves `subject: null` no longer returns 500; OpenAPI diff shows only the approved changes; `tsc` clean without editing `types.ts` |
| Parallel | Shoeb: UI-only work that does not touch `types.ts` (layout, accessibility, copy) |

### Step 2a: Repository seam (Arsh + Nagin)
| Item | Detail |
|---|---|
| Scope | CR-15: define a `Repository` Protocol from the 21 current methods ([baseline §4.2](INTEGRATION_BASELINE.md#42-repository-backendappdatabaserepositorypy-nagin--arsh--ankush)); move the SQLite code into per-domain modules implementing it; routers depend on the interface |
| Rule | **Pure refactor.** No HTTP or SQL behaviour change |
| Approval | **Requires Ankush's approval** (CR-15) |
| Gate | 19 tests pass; `app.openapi()` identical to the Step 1 snapshot |

### Step 2b: Scoring out of the AI layer (Arsh + Ekansh)
| Item | Detail |
|---|---|
| Scope | CR-12: `backend/app/services/assessment_service.py` owns validation, scoring and level thresholds; `ai/base.py` gains a feedback-only method (e.g. `generate_assessment_feedback(subject, graded_breakdown) -> {summary_feedback, recommended_topics}`); mock provider adapted |
| Approval | **Requires Ankush's approval** (internal contract change to `ai/base.py`) |
| Gate | Same scores and levels for the existing test cases; HTTP payload unchanged |

### Step 2c: Gamification service (Ankush)
| Item | Detail |
|---|---|
| Scope | Move the badge award (`repository.py:244-249`) and challenge grading/points (`:392-433`) into `backend/app/services/gamification_service.py`; the repository only persists |
| Approval | **Requires Ankush's approval** (CR-15) |
| Gate | Tests pass; the challenge awards points exactly once (existing test) |

### Step 3a: Postgres implementation (Nagin): see §4
### Step 3b: Real AI provider (Ekansh): see §5

### Step 3c: Baseline assessment and typed client (Shoeb + Arsh)
| Item | Detail |
|---|---|
| Scope | CR-17 (`is_baseline`, learner level, post-registration flow), CR-13 (thresholds from the API), CR-19 (generated or checked `types.ts`), CR-03 (chat by `subject_id`) |
| Approval | **Requires Ankush's approval** (product decision + contract) |
| Gate | Browser E2E of the full flow passes; `ResultPage` no longer hard-codes thresholds |

### Step 3d: Date-based challenges (Ankush)
| Item | Detail |
|---|---|
| Scope | Challenge rotation by date (`challenge_date` column), one submission per user per date, CR-08 typed `user_submission`, CR-14 subject-specific badges |
| Approval | **Requires Ankush's approval** (schema + contract) |

### Step 4: Integration
Run the full suite with `DB_BACKEND=postgres` against a **non-production** Supabase project, and with `AI_PROVIDER=<live>` using a test key. Compare against the SQLite + mock run. Flip any defaults only after Ankush signs off.

### Step 5: Ankush's competition modules
Leaderboard (reads the points ledger from 2c/3d) → 1v1 battles → referrals → certificates. Each is a new router/schema/service with its own CR. Nothing here starts before Step 2c.

---

## 4. Migration path: SQLite → Supabase PostgreSQL (not implemented)

### 4.1 Current coupling (what makes the switch non-trivial)
| Area | Current state | Evidence |
|---|---|---|
| SQL dialect | `?` placeholders, `datetime('now', ?)`, `INSERT OR REPLACE`, `INSERT OR IGNORE`, `rowid` ordering | `repository.py:55,68,160,247,284,423` |
| Table definitions | Created in Python at startup (`init_db`) **and** separately in `database/schema.sql` | `connection.py`, `database/schema.sql` |
| Seeds | Inserted by `init_db` **and** in `database/seed.sql` (answer keys currently identical: B, C, C, B, A; challenge B) | both files |
| Types | Booleans stored as `0/1`; JSON stored as `TEXT` (`recommended_topics`, `user_answers`, `breakdown`, `suggested_followups`); timestamps returned as strings | `connection.py` |
| Response coupling | `created_at`/`awarded_at` typed `str`; Postgres drivers return `datetime` → `/auth/me` and `/dashboard` would **fail response validation (500)** | Verified with Pydantic (IC-06) |
| Untyped pass-through | `recent_attempts` and `user_submission` would change shape silently (ISO timestamps, real booleans) | IC-01, IC-08 |
| Auth model | Backend-issued tokens in `active_sessions`; user IDs are `usr_…`, not Supabase Auth UIDs | `auth_service.py` |
| Health | Reports SQLite unconditionally | IC-12 |

### 4.2 Steps
| # | Step | Owner | Approval |
|---|---|---|---|
| 1 | Land Step 1 (typed timestamps, CR-05) and Step 2a (Repository Protocol) | Arsh, Nagin | **Ankush (CR-05, CR-15)** |
| 2 | Make `database/schema.sql` + `seed.sql` the single source; SQLite init derives from them or from shared constants | Nagin | **Ankush (schema ownership change)** |
| 3 | Decide the JSON columns: keep `TEXT` (zero-change) or `JSONB`; add the `assessment_answers` table (one row per answer) and indexes on `user_id` | Nagin | **Ankush (schema change)** |
| 4 | Add a driver dependency (e.g. `psycopg`) | Nagin | **Ankush (CR-16)** |
| 5 | Implement `PostgresRepository` in a **new file** satisfying the same Protocol; select via a new env var (e.g. `DB_BACKEND=sqlite\|postgres`, default `sqlite`) | Nagin | **Ankush (new config var)** |
| 6 | Apply `schema.sql`/`seed.sql` to a **non-production** Supabase project or branch only. No remote migrations from local scripts without Ankush present | Nagin | **Ankush** |
| 7 | Run the full test suite against Postgres via env vars; add Postgres-specific tests in a new test file | Nagin, Arsh | – |
| 8 | Auth decision: (a) keep backend tokens: the backend connects with server credentials and isolation stays in backend queries, so the RLS guidance in `supabase_guide.md` must be revised (IC-18); or (b) adopt Supabase Auth: a major contract change for `/auth/*` and the frontend | Ankush | **Ankush (CR-20; option b is a breaking CR)** |
| 9 | Make `health.database` reflect the active backend (CR-09) | Arsh | **Ankush** |
| 10 | Switch the default only after a full green run on Postgres | Ankush | **Ankush** |

### 4.3 Data and rollback
- Demo data in `pragyax.db` is disposable (git-ignored, re-seeded at startup). No data migration script is required for the hackathon. If needed later, export per table to CSV and import in FK order: `users → subjects → assessment_questions → user_preferences → chat_messages → assessment_attempts → daily_challenges → user_challenge_submissions → user_badges → active_sessions`.
- **Rollback:** set `DB_BACKEND=sqlite` (once that flag exists) and restart. The SQLite implementation stays in the codebase until Ankush approves removing it.

### 4.4 Supabase configuration (placeholders only)
Already listed in `.env.example`: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`. A direct Postgres connection string variable would be new and **requires Ankush's approval**. The service-role key must never reach the frontend.

---

## 5. Migration path: Mock AI → Real AI (not implemented)

### 5.1 Current state
| Area | Current state | Evidence |
|---|---|---|
| Selection | `ai/factory.py` reads `AI_PROVIDER` from the environment directly (not `settings`); `openai\|gemini\|real` → `RealAIProvider` | `ai/factory.py` |
| Real provider | Placeholder: delegates both methods to `MockAIProvider`; `is_mock` hard-coded `True` | `ai/real_provider.py` |
| Chat contract | `generate_chat_response(prompt, subject, history) -> {reply, provider, is_mock, suggested_followups}` | `ai/base.py` |
| Evaluation contract | `evaluate_assessment` returns the **score and level** as well as the feedback | `ai/base.py`, IC-16 |
| History passed to AI | Last 10 messages, **including the prompt just saved**, so a real LLM would see it twice | `routers/chat.py:33-42` |
| Failure handling | None: a provider exception after the user message is saved → 500 and an orphan user message | `routers/chat.py` |
| Labelling | `is_mock`/`provider` for history and past attempts reflect the current provider, not the stored one | IC-05 |
| Dependencies | No LLM SDK in `backend/requirements.txt` | file |

### 5.2 Steps
| # | Step | Owner | Approval |
|---|---|---|---|
| 1 | Land Step 2b: scoring in `assessment_service`; AI does feedback only. **An LLM never decides correctness or score** | Arsh + Ekansh | **Ankush (CR-12)** |
| 2 | Persist `provider`/`is_mock` per message and attempt (CR-06) so labels stay truthful after the switch | Nagin + Arsh | **Ankush (CR-06)** |
| 3 | Add an SDK dependency (or plain HTTPS via the stdlib) | Ekansh | **Ankush (CR-16)** |
| 4 | Implement `RealAIProvider.generate_chat_response` and the feedback method in `ai/` only: timeout (e.g. ~10 s), bounded tokens, **fall back to the mock on any error** and report `is_mock=True` and the fallback provider name on that response | Ekansh | Within the existing contract after steps 1–2 |
| 5 | Prompt safety: the chat prompt must never include assessment answer keys; feedback prompts receive only already-graded data | Ekansh | – |
| 6 | Backend fixes in the chat router: exclude the current prompt from `history`; on provider failure return a clear error without orphaning the user message | Arsh | **Ankush (behaviour/status change)** |
| 7 | Tests: keep `AI_PROVIDER=mock` for the deterministic suite (as today); add contract tests that run every provider through the `BaseAIProvider` checks; live-key tests are opt-in and never run in CI by default | Ekansh | – |
| 8 | Keys: `OPENAI_API_KEY` / `GEMINI_API_KEY` in the backend `.env` only (placeholders already in `.env.example`) | Ekansh | – |
| 9 | Only once real output exists: flip `RealAIProvider.is_mock` to `not self._has_valid_credentials()` so the UI drops the "Demo AI" / "Mock Evaluation" labels truthfully | Ekansh | **Ankush** |

### 5.3 Rollback
`AI_PROVIDER=mock` and restart. Because scores are computed by the backend after Step 2b, switching providers never changes a learner's score, only the feedback wording.

---

## 6. Work that can start now without any contract change

| Person | Safe now (no CR needed) |
|---|---|
| Ankush | Review and approve CRs; draft designs for the leaderboard, battles, referrals and certificates (docs only) |
| Arsh | Draft new per-domain test files with isolated fixtures (no production code changes) |
| Ekansh | Prototype real chat responses inside `ai/real_provider.py` **behind `AI_PROVIDER`**, using the existing `ai/base.py` contract, with no new dependency (stdlib HTTP) and `is_mock` left as `True` until Step 5.2-9 |
| Nagin | Draft `PostgresRepository` in a new, unwired file; revise the DDL proposals as documents |
| Shoeb | UI polish, accessibility, empty/error states, provided `types.ts` and `client.ts` are untouched |

---

## 7. Open decisions for Ankush

1. Approve, reject or defer each CR-01…CR-20.
2. Is the first assessment a mandatory baseline (CR-17)? Are retakes capped?
3. Auth model for Supabase: keep backend tokens or adopt Supabase Auth (§4.2 step 8)?
4. JSON columns as `TEXT` or `JSONB` (§4.2 step 3)?
5. Which LLM provider, and whether an SDK dependency is acceptable (CR-16)?
6. Canonical subject identifier: `id` or `slug` (CR-18)?
