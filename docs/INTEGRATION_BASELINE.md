# PragyaX Integration Baseline (Phase 2)

> **Status:** Baseline of the V1 code as it exists locally on **2026-10-27**. Documentation only. No application code was changed to produce it.
> **Authority:** This file describes the **current** contract. Anything under [§9 Proposed contract changes](#9-proposed-contract-changes) is **PROPOSED, not implemented, and requires Ankush's approval** before anyone codes it.
> Related docs (unchanged): [API.md](API.md) (short route summary), [ARCHITECTURE.md](ARCHITECTURE.md), [PHASE2_DEPENDENCIES.md](PHASE2_DEPENDENCIES.md).

## How this was verified

| Check | Method | Result |
|---|---|---|
| Route inventory | `app.openapi()` generated in-process | 17 operations (16 under `/api` + `GET /`) |
| Request/response models | Read `backend/app/schemas/*.py` and `backend/app/routers/*.py` | Recorded below with line references |
| Actual payloads | FastAPI `TestClient` against a throwaway SQLite file outside the repo | Shapes in §4 and §6 are observed, not inferred |
| Frontend types | Read `frontend/src/api/types.ts` and `frontend/src/api/client.ts` | Mapping in §5 |
| Backend tests | `pytest backend/tests` (no cache, no bytecode written) | 19 passed |
| Frontend types | `tsc -p frontend` (`noEmit`) | 0 errors |

---

## 1. Global conventions (current behaviour)

| Topic | Current contract | Source |
|---|---|---|
| Base path | Every API route is under `/api` (`settings.API_PREFIX`). Frontend calls `${VITE_API_URL ?? ""}/api${path}`; Vite proxies `/api` to `VITE_BACKEND_URL` (default `http://127.0.0.1:8000`). | `config.py`, `client.ts`, `vite.config.ts` |
| Auth | `Authorization: Bearer <token>`; token format `pragya_<urlsafe-32>`. All routes except `GET /api/health`, `POST /api/auth/register`, `POST /api/auth/login`, `GET /` require it. | `services/auth_service.py:45-74` |
| 401 | Missing header, wrong scheme, unknown or expired token → `401 {"detail": "<message>"}` with `WWW-Authenticate: Bearer`. Expiry = `ACCESS_TOKEN_EXPIRE_MINUTES` (default 1440) from session creation. | `auth_service.py`, `repository.py:59-71` |
| Errors (handled) | `{"detail": "<string>"}` with 400 / 401 / 404. | routers |
| Errors (validation) | Pydantic → `422 {"detail": [{"type","loc","msg","input"}, ...]}`. The frontend handles both shapes (`client.ts::errorMessage`). | observed |
| IDs | Prefixed strings: `usr_`, `msg_`, `atm_`, `bdg_`, `csub_`; seeded IDs `subj_python`, `q_py_1..5`, `chal_today_py`. | `repository.py`, `connection.py` |
| Subject identifier | `subjects/select`, `assessments/questions` and `assessments/submit` accept **either** the subject `id` (`subj_python`) **or** its `slug` (`python`). Responses always return the canonical `id`. Chat uses the subject **title** instead (see IC-03). | `repository.py:91-97,177-205` |
| Timestamps | SQLite `CURRENT_TIMESTAMP` → string `"YYYY-MM-DD HH:MM:SS"`, **UTC without a zone marker** (observed `"2026-10-27 08:56:49"`). The frontend appends `Z` before parsing (`States.tsx::formatDate`). | observed |
| Booleans | Typed schema fields are real JSON booleans. Untyped pass-through fields leak SQLite integers (see IC-08). | observed |
| Options | Assessment and challenge answers are `"A"`–`"D"`, case-insensitive on input, stored upper-case. | `assessments.py`, `challenges.py` |

---

## 2. Endpoint inventory

Generated from `app.openapi()`. "Model" is the declared `response_model`.

| # | Method | Path | Auth | Success | Model | Router file |
|---|---|---|---|---|---|---|
| 1 | GET | `/api/health` | – | 200 | **none (untyped dict)** | `routers/health.py` |
| 2 | POST | `/api/auth/register` | – | **201** | `AuthResponse` | `routers/auth.py` |
| 3 | POST | `/api/auth/login` | – | 200 | `AuthResponse` | `routers/auth.py` |
| 4 | GET | `/api/auth/me` | ✓ | 200 | `UserProfileResponse` | `routers/auth.py` |
| 5 | POST | `/api/auth/logout` | ✓ | 200 | **none (untyped dict)** | `routers/auth.py` |
| 6 | GET | `/api/subjects` | ✓ | 200 | `SubjectListResponse` | `routers/subjects.py` |
| 7 | POST | `/api/subjects/select` | ✓ | 200 | `SubjectItemResponse` | `routers/subjects.py` |
| 8 | POST | `/api/chat/message` | ✓ | 200 | `ChatMessageResponse` | `routers/chat.py` |
| 9 | GET | `/api/chat/history` | ✓ | 200 | `ChatHistoryResponse` | `routers/chat.py` |
| 10 | GET | `/api/assessments/questions` | ✓ | 200 | `List[AssessmentQuestionPublic]` | `routers/assessments.py` |
| 11 | POST | `/api/assessments/submit` | ✓ | 200 | `AssessmentResultResponse` | `routers/assessments.py` |
| 12 | GET | `/api/assessments/history` | ✓ | 200 | `AssessmentHistoryResponse` | `routers/assessments.py` |
| 13 | GET | `/api/assessments/{attempt_id}` | ✓ | 200 | `AssessmentResultResponse` | `routers/assessments.py` |
| 14 | GET | `/api/dashboard` | ✓ | 200 | `DashboardResponse` | `routers/dashboard.py` |
| 15 | GET | `/api/challenges/daily` | ✓ | 200 | `DailyChallengeResponse` | `routers/challenges.py` |
| 16 | POST | `/api/challenges/submit` | ✓ | 200 | `ChallengeResultResponse` | `routers/challenges.py` |
| 17 | GET | `/` | – | 200 | none | `main.py` |

Frontend coverage: `client.ts` calls endpoints 1–16. Endpoint 17 is unused.

---

## 3. Endpoint contracts

Field types are Pydantic types. `?` = optional/nullable.

### 3.1 Health: `GET /api/health`
Untyped response. Observed keys: `status, service, version, uptime_seconds, python_version, database, persistence_active, ai_provider, ai_is_mock`.
`database` is a hard-coded string (`"SQLite Demo Persistence (File-backed)"`). The frontend reads only `ai_is_mock` (`App.tsx`) to show the "Demo AI mode" badge.

### 3.2 Auth
| Endpoint | Request | Response | Errors |
|---|---|---|---|
| `POST /auth/register` | `RegisterRequest{name: str(2..100), email: str(5..255), password: str(6..128)}` | `201 AuthResponse` | 400: invalid email format, name blank after trim, duplicate email. 422: length violations. |
| `POST /auth/login` | `LoginRequest{email: str(5..255), password: str(1..)}` | `200 AuthResponse` | 401 invalid credentials; 422 |
| `GET /auth/me` | – | `UserProfileResponse` | 401 |
| `POST /auth/logout` | – | `{"message": "Logged out successfully"}` (untyped) | 401 |

- `AuthResponse{token: str, token_type: str="Bearer", user: UserProfileResponse, demo_notice: str}`
- `UserProfileResponse{id, name, email: str, created_at?: str}`
- Emails are stored lower-cased; lookup is case-insensitive.

### 3.3 Subjects
| Endpoint | Request | Response | Errors |
|---|---|---|---|
| `GET /subjects` | – | `SubjectListResponse{subjects: SubjectItemResponse[], selected_subject_id: str}` | 401 |
| `POST /subjects/select` | `SelectSubjectRequest{subject_id: str}` (id or slug) | `SubjectItemResponse` | 404 unknown, 400 inactive ("Coming Soon"), 422 |

- `SubjectItemResponse{id, slug, title, description, icon: str, is_active: bool, question_count: int, difficulty: str}`
- Ordering: active subjects first, then by title.
- If the user never selected a subject, `selected_subject_id` is still `"subj_python"` (default, observed). Whether the user actually chose is exposed only on the dashboard (`has_selected_subject`).

### 3.4 Learning chat
| Endpoint | Request | Response | Errors |
|---|---|---|---|
| `POST /chat/message` | `ChatInputRequest{message: str(1..2000), subject?: str = "Python Programming"}` | `ChatMessageResponse` (the assistant reply) | 400 whitespace-only message; 422; **500 if `subject` is JSON `null`** (IC-02) |
| `GET /chat/history` | – | `ChatHistoryResponse{messages: ChatMessageResponse[], active_provider: str, is_mock: bool}` | 401 |

- `ChatMessageResponse{id, user_id, subject: str, role: str, content: str, suggested_followups: str[] = [], is_mock: bool = True, provider: str, created_at?: str}`
- Side effects of `POST`: persists the user message, then the assistant message.
- History returns the latest 50 messages of the caller, oldest first, all subjects mixed.

### 3.5 Assessments
| Endpoint | Request | Response | Errors |
|---|---|---|---|
| `GET /assessments/questions?subject_id=` (default `subj_python`) | – | `AssessmentQuestionPublic[]` | 404 no questions for subject |
| `POST /assessments/submit` | `AssessmentSubmitRequest{subject_id: str, answers: {question_id: "A".."D"}}` | `AssessmentResultResponse` | 400: subject does not have exactly 5 questions, unknown question id, missing answer, invalid option. 422 |
| `GET /assessments/history` | – | `AssessmentHistoryResponse{attempts: AssessmentHistoryItem[]}` (max 20, newest first) | 401 |
| `GET /assessments/{attempt_id}` | – | `AssessmentResultResponse` | 404 if missing **or owned by another user** |

- `AssessmentQuestionPublic{id, subject_id: str, question_number: int, question_text, option_a, option_b, option_c, option_d, topic, difficulty: str}`. **Contains no `correct_option` or `explanation`.** The response model filters them out even if the data layer returned them.
- `AssessmentResultResponse{id, user_id, subject_id: str, subject_title?: str = "Python Programming", score: int, total: int, percentage: float, proficiency_level: str, summary_feedback: str, recommended_topics: str[], breakdown: QuestionBreakdownItem[], is_mock: bool, provider: str, created_at?: str}`
- `QuestionBreakdownItem{question_id, question_text, selected_option, correct_option: str, is_correct: bool, explanation, topic: str}`
- `AssessmentHistoryItem{id, subject_id, subject_title: str, score, total: int, percentage: float, proficiency_level: str, created_at: str}`
- Grading: the server-side answer key from the DB, via `get_ai_provider().evaluate_assessment(...)`. Levels: 0–2 Beginner, 3–4 Intermediate, 5 Advanced (`ai/mock_provider.py::proficiency_for`).
- Side effects of `submit`: inserts an `assessment_attempts` row. If `score >= 4`, inserts the `py_master` badge (once per user).
- Retakes are unlimited; every submission is a new attempt.

### 3.6 Dashboard: `GET /api/dashboard`
`DashboardResponse`:
```
user: UserProfileResponse
selected_subject: SubjectItemResponse          # defaults to Python if never chosen
has_selected_subject: bool = False
metrics: MetricsData {
  total_assessments_completed: int
  latest_score?: int            latest_total: int = 5
  latest_percentage?: float     latest_proficiency: str = "Not Assessed"
  average_percentage: float     highest_score: int
  best_percentage: float        chat_questions_asked: int
  challenges_attempted: int     total_points: int
}
recommended_next_topics: str[]
recommendations_source: str = "starter"        # observed values: "starter" | "latest_assessment"
recent_attempts: List[Any] = []                # untyped, see IC-01
badges: BadgeItem[] {id, badge_key, title, description, icon, awarded_at: str}
```
Every metric is computed from stored rows (`repository.py::get_user_dashboard_metrics`).

### 3.7 Daily challenge
| Endpoint | Request | Response | Errors |
|---|---|---|---|
| `GET /challenges/daily` | – | `DailyChallengeResponse` | 404 if no challenge row |
| `POST /challenges/submit` | `ChallengeSubmitRequest{challenge_id: str, selected_option: str}` | `ChallengeResultResponse{challenge_id: str, is_correct: bool, points_awarded: int, correct_option: str, explanation: str}` | 400: option not A–D, unknown challenge, already submitted. 422 |

- `DailyChallengeResponse{id, title, topic, difficulty, description, code_snippet, question_type, option_a..d: str, points: int, has_completed: bool, correct_option?: str, explanation?: str, user_submission?: Any}`
- `correct_option` and `explanation` are `null` until this user has submitted.
- "Daily" is currently the first row of `daily_challenges` (`LIMIT 1`), not date-based.
- One submission per user per challenge (DB `UNIQUE(user_id, challenge_id)`). Correct → `points` and the `daily_striker` badge.

---

## 4. Internal (Python) contracts used across modules

These are not HTTP contracts, but two owners depend on each one, so they are treated the same way.

### 4.1 AI provider (`ai/base.py`): Ekansh ⇄ Arsh
```
provider_name -> str            is_mock -> bool
generate_chat_response(prompt, subject="Python Programming", history=[{role, content}])
  -> {reply: str, provider: str, is_mock: bool, suggested_followups: str[]}
evaluate_assessment(subject: str, questions: [row incl. correct_option, explanation, topic], user_answers: {qid: "A".."D"})
  -> {score, total: int, percentage: float, proficiency_level: str, breakdown: [...],
      recommended_topics: str[], summary_feedback: str, is_mock: bool, provider: str}
```
Selection: `ai/factory.py` reads `os.getenv("AI_PROVIDER")` directly (`mock` default; `openai|gemini|real` → `RealAIProvider`, which today delegates to the mock and always reports `is_mock=True`).

### 4.2 Repository (`backend/app/database/repository.py`): Nagin ⇄ Arsh ⇄ Ankush
21 static methods. Callers, taken from the router source:

| Method | Called by |
|---|---|
| `create_user`, `get_user_by_email`, `create_session`, `delete_session` | `routers/auth.py` |
| `get_user_by_token` | `services/auth_service.py` |
| `get_all_subjects`, `get_user_selected_subject`, `get_subject_by_id`, `set_user_selected_subject` | `routers/subjects.py` (`get_subject_by_id` also `assessments.py`) |
| `save_chat_message`, `get_chat_history` | `routers/chat.py` |
| `get_assessment_questions`, `get_raw_assessment_questions_with_answers`, `save_assessment_attempt`, `get_user_assessment_attempts`, `get_assessment_attempt_by_id` | `routers/assessments.py` |
| `get_user_dashboard_metrics` | `routers/dashboard.py` |
| `get_daily_challenge`, `submit_daily_challenge` | `routers/challenges.py` |
| `get_user_by_id`, `get_user_badges` | internal (used by `create_user` and the dashboard) |

Returns plain `dict`s. The SQL is SQLite-specific (`?` placeholders, `datetime('now', ?)`, `INSERT OR REPLACE/IGNORE`, `rowid`).

---

## 5. Backend ⇄ frontend type mapping

| Backend schema | Frontend type (`types.ts`) | Match |
|---|---|---|
| `UserProfileResponse` | `User` | ✅ |
| `AuthResponse` | `AuthResponse` | ✅ |
| health (untyped) | `Health` (4 of 9 keys) | ⚠️ subset of an untyped payload |
| `SubjectItemResponse` / `SubjectListResponse` | `Subject` / `SubjectList` | ✅ |
| `ChatMessageResponse` | `ChatMessage` | ⚠️ `role: str` vs `"user" \| "assistant"` |
| `ChatHistoryResponse` | `ChatHistory` | ✅ |
| `AssessmentQuestionPublic` | `Question` | ✅ |
| `QuestionBreakdownItem` | `BreakdownItem` | ✅ |
| `AssessmentResultResponse` | `AssessmentResult` | ✅ (`subject_title` optional on both) |
| `AssessmentHistoryItem` | `AttemptSummary` | ✅ |
| `AssessmentHistoryResponse` | inline `{attempts: AttemptSummary[]}` | ✅ |
| `DashboardResponse` | `Dashboard` | ⚠️ `recent_attempts: List[Any]` vs `AttemptSummary[]`; `recommendations_source: str` vs literal union |
| `BadgeItem` | `Badge` | ✅ |
| `DailyChallengeResponse` | `DailyChallenge` | ⚠️ frontend omits `question_type`; `user_submission: Any` vs a typed subset |
| `ChallengeResultResponse` | `ChallengeResult` | ✅ |
| `AssessmentSubmitRequest.answers: Dict[str,str]` | `Record<string, Option>` | ✅ (frontend stricter) |

The frontend types are **hand-maintained** (`types.ts` line 1: "Keep in sync when the API changes"). Nothing checks automatically that they match.

---

## 6. Contract inconsistencies

Severity: **H** = can cause a runtime failure or wrong data · **M** = drift or migration risk · **L** = cosmetic or documentation. "Evidence" means the behaviour was observed with `TestClient` or read directly from the cited lines.

| ID | Sev | Inconsistency | Evidence |
|---|---|---|---|
| IC-01 | M | `DashboardResponse.recent_attempts` is `List[Any]`. The payload carries undocumented fields (`user_id`, `summary_feedback`, `recommended_topics`) that are absent from OpenAPI. The frontend assumes `AttemptSummary[]`. | `schemas/dashboard.py:41`. Observed keys: `created_at, id, percentage, proficiency_level, recommended_topics, score, subject_id, subject_title, summary_feedback, total, user_id` |
| IC-02 | **H** | `ChatInputRequest.subject` is `Optional[str]`, so an explicit `null` is accepted, then the `NOT NULL` insert fails → **HTTP 500**. | `schemas/chat.py:11`; observed `500` for `{"message":"loops","subject":null}` |
| IC-03 | M | Chat identifies the subject by its **title** (`"Python Programming"`), unvalidated. Every other endpoint uses the subject **id or slug**. Any string is stored (observed `"Underwater Basket Weaving"` → 200). | `schemas/chat.py:11`, `ChatPage.tsx:30,35` hard-code the title |
| IC-04 | M | `created_at` is inconsistent for the same resource: `POST /chat/message` always returns `null`; `GET /chat/history` returns the stored string. | `routers/chat.py:70` vs `:91` |
| IC-05 | M | `is_mock` and `provider` on **historical** chat messages and on `GET /assessments/{id}` come from the **currently configured** provider, not from the provider that produced them. `POST /assessments/submit` returns the evaluator's own values. The same resource can therefore change label after a provider switch. | `routers/chat.py:89-90`, `routers/assessments.py:185-186` vs `:132-133` |
| IC-06 | M | The timestamp format is SQLite-specific (`"YYYY-MM-DD HH:MM:SS"`, implicit UTC). `created_at`/`awarded_at` are typed `str`. A Postgres driver returning `datetime` makes `UserProfileResponse` and `BadgeItem` **fail validation** ("Input should be a valid string"). The untyped `recent_attempts` would silently switch to ISO-8601 with an offset. | Verified with Pydantic in-process |
| IC-07 | L | `str(None)` pattern: `created_at=str(attempt.get("created_at"))` would emit the literal string `"None"` if the column were ever null. | `routers/assessments.py:134,152,187`, `chat.py:91` |
| IC-08 | M | `DailyChallengeResponse.user_submission` is `Optional[Any]`: it returns the raw DB row, including the caller's `user_id` and `is_correct` as an **integer** (`1`). `ChallengeResultResponse.is_correct` is a **boolean**. | Observed `{'id','user_id','challenge_id','submitted_answer','is_correct': 1,'points_awarded','created_at'}` |
| IC-09 | L | Enumerations typed as plain `str` on the backend but as literal unions on the frontend: `role`, `recommendations_source`, `proficiency_level`, answer options. | `schemas/*.py` vs `types.ts` |
| IC-10 | M | The proficiency thresholds are defined in `ai/mock_provider.py` but repeated as UI text in `ResultPage.tsx:36` ("0–2 correct = Beginner…") and in `docs/API.md`. A real provider or a threshold change would silently desync them. | cited lines |
| IC-11 | L | `AssessmentResultResponse.subject_title` is optional with a hard-coded default `"Python Programming"`; `AssessmentHistoryItem.subject_title` is required. Same field, two contracts. The routers repeat the default. | `schemas/assessments.py:41,57`, `routers/assessments.py:124,177` |
| IC-12 | L | `GET /api/health`, `POST /api/auth/logout` and `GET /` have no `response_model` and appear untyped in OpenAPI. `health.database` is hard-coded and will be wrong after a DB switch. | `app.openapi()`, `routers/health.py:28` |
| IC-13 | L | Two validation layers return different status codes for similar input. A password shorter than 6 is caught by Pydantic (422), so the router's 400 branch (`auth.py:36-40`) is unreachable. Name and email format errors return 400. Duplicate email and "already submitted" return 400 rather than 409. | `schemas/auth.py:10-12` vs `routers/auth.py` |
| IC-14 | L | `MetricsData.latest_total` defaults to the literal `5`; `highest_score` (raw) and `best_percentage` duplicate the same signal. | `schemas/dashboard.py:14,18-19` |
| IC-15 | M | `selected_subject_id` (subjects) and `selected_subject` (dashboard) return `subj_python` even when the user never chose. Only the dashboard exposes `has_selected_subject`. | observed |
| IC-16 | M | **Scoring belongs to the AI contract.** `evaluate_assessment` returns `score`/`percentage`/`proficiency_level`, so a future LLM provider would own deterministic grading. | `ai/base.py`, `routers/assessments.py:99-104` |
| IC-17 | L | The "Python Virtuoso" badge is awarded for score ≥ 4 regardless of subject. | `repository.py:244-249` |
| IC-18 | M | `database/supabase_guide.md` proposes RLS policies on `auth.uid()::text = user_id`. Today's users are backend-issued `usr_…` IDs, not Supabase Auth UIDs, so those policies would not match any row. | `database/supabase_guide.md:37,41` |

---

## 7. Shared-file ownership conflicts

Files that more than one owner must edit for their Phase 2 work. Each is a merge-conflict or contract-drift risk.

| ID | File | Who needs it | Risk | Mitigation (proposed) |
|---|---|---|---|---|
| SF-01 | `backend/app/database/repository.py` (447 lines, 21 methods, all domains) | Nagin (Postgres), Arsh (services), Ankush (challenges, points, badges) | **High:** concurrent edits to one class; business rules (badges, challenge grading) live in the data layer | CR-15: split per domain behind an interface. Until then, **one editor at a time**, coordinated by Ankush |
| SF-02 | `backend/app/database/connection.py` (DDL + seeds for every table) | Nagin, Ankush (challenge tables), Ekansh/content (questions) | High: table definitions duplicated in `database/schema.sql` and `seed.sql` (already drifted once in V1) | Single source of truth in `database/` (Phase 2, Nagin) |
| SF-03 | `backend/app/main.py`, `routers/__init__.py`, `schemas/__init__.py` | Arsh, Ankush (new routers) | Medium: each new router edits all three | Append-only edits; Ankush reviews |
| SF-04 | `ai/base.py` | Ekansh (implements), Arsh (calls) | High: any signature change breaks `routers/chat.py` and `routers/assessments.py` | Two-person review: Ekansh + Arsh, Ankush approves |
| SF-05 | `routers/assessments.py`, `routers/chat.py` | Arsh (HTTP) and Ekansh (AI call) | Medium: header says "Ekansh & Arsh" | Arsh owns the routers; Ekansh changes only `ai/` |
| SF-06 | `routers/dashboard.py` + `get_user_dashboard_metrics` + `schemas/dashboard.py` | Arsh (learning metrics), Ankush (points, badges) | Medium: one aggregate response mixes two domains | Arsh owns; Ankush supplies gamification data through a function, not by editing the query |
| SF-07 | `frontend/src/api/types.ts`, `client.ts` | Shoeb (consumer), Arsh (schema author) | **High:** hand-mirrored, no automatic drift check | CR-19: generate from `/openapi.json` or add a snapshot check |
| SF-08 | `backend/tests/test_api_flow.py` (one module, one shared DB, order-dependent) | Everyone | High: line 382 (`total_points == 50`) only passes because the challenge test (line 291) ran first; most tests reuse the user registered at line 45 | New tests go in **new per-domain files** with their own fixtures; existing file untouched |
| SF-09 | `backend/app/config.py`, `.env.example` | Arsh, Nagin (DB vars), Ekansh (AI vars) | Medium: `ai/factory.py` bypasses `settings` and reads env directly; `SECRET_KEY`, `ENVIRONMENT`, `settings.AI_PROVIDER` are unused | Add variables append-only; document each in `.env.example` |
| SF-10 | `backend/requirements.txt`, `frontend/package.json` | Ekansh (LLM SDK), Nagin (Postgres driver), Shoeb (test tooling) | Medium: version conflicts | Every new dependency requires Ankush's approval (CR-16) |
| SF-11 | `docs/API.md` vs this file | Ankush, Arsh | Low: two descriptions of one API | `API.md` = summary; this file = detailed baseline. Update both in the same change |

---

## 8. Module ownership boundaries

"Owns" = may edit freely within the current contract. "Shared" = needs the owner plus one other reviewer, and **Ankush's approval for any contract change**.

| Person | Owns (exclusive) | Must not edit | Interfaces they provide | Interfaces they consume |
|---|---|---|---|---|
| **Ankush**: architecture, integration, challenges, competitions, referrals, certificates | `docs/`, `backend/app/routers/challenges.py`, `backend/app/schemas/challenges.py`, future `routers/{leaderboard,battles,referrals,certificates}.py` and their schemas/services | Other owners' files without their review | Contract approvals (§9), challenge and gamification API | Repository interface, auth dependency |
| **Arsh**: FastAPI backend | `backend/app/{main.py, config.py}`, `routers/{auth,subjects,chat,assessments,dashboard,health}.py`, `schemas/{auth,subjects,chat,assessments,dashboard}.py`, `services/` (except future gamification service), `backend/tests/` (new files) | `ai/*`, `database/*`, `frontend/*` | HTTP contract (§3), `get_current_user` | `ai/base.py`, Repository |
| **Ekansh**: AI/ML evaluation | `ai/mock_provider.py`, `ai/real_provider.py`, `ai/factory.py`, new `ai/*` modules and AI tests | `ai/base.py` without Arsh plus Ankush approval; any `backend/` file | `BaseAIProvider` implementations | Question rows (incl. explanations) passed in by the backend |
| **Nagin**: Supabase PostgreSQL | `database/` (schema, seed, guide, migrations), new repository implementations under `backend/app/database/` | Router or schema files; the Repository **method signatures** (shared) | Repository implementation(s), DDL, seeds | Repository interface defined with Arsh |
| **Shoeb**: React frontend | `frontend/` except `src/api/types.ts` and `src/api/client.ts` (shared with Arsh) | `backend/*`, `ai/*`, `database/*` | UI | HTTP contract (§3), via `client.ts` only |

**Rules of engagement**
1. All HTTP calls go through `frontend/src/api/client.ts`; all SQL goes through the repository layer; all model calls go through `ai/`.
2. No one changes a request/response field, status code, route, table/column, or `ai/base.py` signature without an approved CR (§9).
3. New behaviour comes with new tests in a new test file; do not edit the shared order-dependent `test_api_flow.py` except to fix it.
4. Additive, backward-compatible changes (new optional response field, new route) still need a CR, but can be fast-tracked.

---

## 9. Proposed contract changes

> **Every item in this table is PROPOSED. None is implemented. Each requires Ankush's approval before work starts.**
> "Breaking" = an existing client or test would need changes.

| CR | Change | Fixes | Owner | Breaking? | Approval |
|---|---|---|---|---|---|
| CR-01 | Type `DashboardResponse.recent_attempts` as `List[AssessmentHistoryItem]` | IC-01 | Arsh | No for the frontend (drops unused fields) | **Requires Ankush's approval** |
| CR-02 | Make `ChatInputRequest.subject` non-nullable (or coerce `null` → default) | IC-02 | Arsh | No | **Requires Ankush's approval** |
| CR-03 | Chat identifies the subject by `subject_id` validated against `subjects`; accept the title temporarily | IC-03 | Arsh + Shoeb | Yes (request field) | **Requires Ankush's approval** |
| CR-04 | `POST /chat/message` returns the stored `created_at` | IC-04 | Arsh | No | **Requires Ankush's approval** |
| CR-05 | All timestamps serialized as ISO-8601 UTC with `Z`; schemas use `datetime` | IC-06, IC-07 | Arsh (+ Shoeb verifies `formatDate`) | Format change | **Requires Ankush's approval** |
| CR-06 | Persist `provider` and `is_mock` per assistant message and per attempt; return stored values | IC-05 | Nagin (columns) + Arsh | Additive DB columns | **Requires Ankush's approval** |
| CR-07 | Literal types for `role`, `recommendations_source`, `proficiency_level`, options | IC-09 | Arsh | No | **Requires Ankush's approval** |
| CR-08 | Typed `UserSubmission{submitted_answer, is_correct: bool, points_awarded, created_at}`; drop `user_id`; add `question_type` to frontend or remove it | IC-08 | Ankush + Shoeb | Minor | **Requires Ankush's approval** |
| CR-09 | `HealthResponse` and `LogoutResponse` models; `health.database` reflects the active backend | IC-12 | Arsh | No | **Requires Ankush's approval** |
| CR-10 | Remove the hard-coded `"Python Programming"` default; `subject_title` required everywhere | IC-11 | Arsh | No | **Requires Ankush's approval** |
| CR-11 | Status codes: 409 for duplicate email and repeat challenge submit; remove the unreachable password branch | IC-13 | Arsh | Yes (status code) | **Requires Ankush's approval** |
| CR-12 | Move scoring and thresholds to `backend/app/services/assessment_service.py`; replace `evaluate_assessment` in `ai/base.py` with a feedback-only method | IC-16 | Arsh + Ekansh | Yes (internal AI contract) | **Requires Ankush's approval** |
| CR-13 | Expose proficiency thresholds via the API (e.g. a `level_thresholds` field on the result); frontend stops hard-coding them | IC-10 | Arsh + Shoeb | Additive | **Requires Ankush's approval** |
| CR-14 | Subject-specific badge keys/titles | IC-17 | Ankush | Additive | **Requires Ankush's approval** |
| CR-15 | Define a `Repository` interface (Protocol) and split the implementation per domain; move badge/points rules into a gamification service | SF-01, SF-02 | Arsh + Nagin + Ankush | Internal only, no HTTP change | **Requires Ankush's approval** |
| CR-16 | New dependencies: Postgres driver / Supabase client, LLM SDK, `@playwright/test` | – | Nagin, Ekansh, Shoeb | Additive | **Requires Ankush's approval** |
| CR-17 | Initial (baseline) assessment: `is_baseline` on attempts, a learner level on the profile, flow order after registration | Product decision | Arsh + Nagin + Shoeb | Additive | **Requires Ankush's approval** |
| CR-18 | Choose a canonical subject identifier (`id` vs `slug`) and decide whether both stay accepted | §1 | Arsh | Possibly | **Requires Ankush's approval** |
| CR-19 | Generate `types.ts` from `/openapi.json`, or add a CI snapshot check of `openapi.json` | SF-07 | Shoeb + Arsh | No | **Requires Ankush's approval** |
| CR-20 | Fix `supabase_guide.md` RLS guidance to match the chosen auth model | IC-18 | Nagin | Docs/DB policy | **Requires Ankush's approval** |

### Change-control process
1. The proposer adds or updates a CR row here with status `PROPOSED`.
2. Ankush marks it `APPROVED` (with date) or `REJECTED`.
3. The implementer updates backend schemas, `types.ts`, `docs/API.md` and this file in the **same change**, plus tests.
4. Verification: `pytest backend/tests`, `tsc -p frontend`, and a diff of `app.openapi()` against the previous snapshot.
