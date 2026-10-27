# PragyaX Student 1v1 Battle Engine (domain foundation)

> **Owner:** Ankush · **Status (2026-10-27):** a pure, unit-tested domain engine exists at `backend/app/services/battle_engine.py`.
> Before this, **no battle code existed** anywhere in `backend/`, `ai/`, `database/` or `frontend/src` (battles appeared only as future work in the docs).
> **Not wired:** no route, table, matchmaking, timer, WebSocket or XP award. Everything marked **PROPOSED** requires Ankush's approval, plus the listed owners' approval for their files.

| Artifact | Path |
|---|---|
| Engine | `backend/app/services/battle_engine.py` |
| Tests (39) | `backend/tests/test_battle_engine.py` |
| This document | `docs/BATTLE_ENGINE.md` |

---

## 1. Domain model signatures

```python
class BattleStatus(StrEnum):  CREATED | ACTIVE | COMPLETED | CANCELLED
class BattleOutcome(StrEnum): WIN | TIE

BattleParticipant(user_id, display_name)                                   # authenticated server identity
BattleQuestion(question_id, question_text, option_a..option_d,
               correct_option, explanation, topic)                         # TRUSTED: holds the answer key
LearnerBattleQuestion(position, question_id, question_text, option_a..option_d, topic)   # no key, no explanation
BattleConfig(battle_id, questions: tuple[BattleQuestion, ...], require_all_answers: bool = True)
AnswerSubmission(question_id, selected_option)                             # the only learner input
AnswerSheet(user_id, answers: tuple[tuple[question_id, "A".."D"], ...])     # normalised, in question order
ParticipantScore(user_id, correct, answered, total)
BattleResult(battle_id, scores: (p1, p2), outcome, winner_user_id | None)
BattleState(config, participants: (p1, p2), status, answer_sheets, result, cancel_reason)
QuestionReview(position, question_id, correct_option, explanation, answers: ((user_id, option | None), ...))
BattleView(battle_id, status, viewer_user_id, opponent_display_name, viewer_submitted, opponent_submitted,
           questions, viewer_answers, result, review)

create_battle(config, player_one, player_two) -> BattleState               # CREATED
start_battle(state) -> BattleState                                         # CREATED -> ACTIVE
submit_answers(state, user_id, answers: Iterable[AnswerSubmission]) -> BattleState
cancel_battle(state, reason: str) -> BattleState
score_battle(state) -> BattleResult
learner_questions(state, viewer_user_id) -> tuple[LearnerBattleQuestion, ...]
battle_view(state, viewer_user_id) -> BattleView
```

**Conventions reused:**
- User ids follow the ledger/leaderboard rule (`[A-Za-z0-9_.-]+`, ≤ 64, via `leaderboard_engine`).
- Answers are normalised exactly like V1 (`strip().upper()`, A–D, via `gamification_service._normalize_option`).
- Question and battle ids match `[A-Za-z0-9_.-]+`, ≤ 64.
- Every function is pure, and every transition **returns a new immutable `BattleState`**.

**Errors** (all are `GamificationError` / `ValueError` subclasses):

| Error | When | HTTP once wired |
|---|---|---|
| `InvalidSubmissionError` | Unknown question id, invalid option, duplicate answer, incomplete sheet, malformed answers | 400 |
| `UnauthorizedParticipantError` | Acting/viewing user isn't one of the two participants | 403 |
| `InvalidBattleTransitionError` | Action not allowed in the current status, resubmission, scoring before both sheets | 409 |
| `InvalidTrustedInputError` | Bad config/question/participant data, same user twice, blank cancel reason | 500 + log (server bug) |

---

## 2. Lifecycle

```
create_battle ─▶ CREATED ──start_battle──▶ ACTIVE ──(2nd answer sheet)──▶ COMPLETED   (final)
                    │                         │
                    └──cancel_battle──▶ CANCELLED ◀──cancel_battle (only before any sheet)──┘
```

- **`start_battle`:** CREATED → ACTIVE only.
- **`submit_answers`:** ACTIVE only, exactly once per participant. The second sheet completes the battle automatically and computes the result. That's the single completion condition.
- **`cancel_battle`:** CREATED → CANCELLED at any time. ACTIVE → CANCELLED **only before any participant has submitted**, so a finished player's work is never discarded. COMPLETED and CANCELLED are terminal.
- **Everything else is rejected:** restarting, submitting before start, submitting twice, any action on a terminal battle, and scoring with fewer than two sheets.
- **A rejected call leaves the state unchanged** (the caller still holds the previous immutable state).

---

## 3. Scoring and tie rules

- **Score** = the number of answers equal to the server-held `correct_option`. When `require_all_answers=False`, skipped questions count as incorrect. `answered` and `total` are reported alongside.
- **Higher score wins.** **Equal scores are a tie** (`winner_user_id = None`). There is **no speed or time tiebreaker**, by design, since there are no timers in this phase.
- **Scores are battle scores, not points.** `ParticipantScore` and `BattleResult` have no `points` or `xp` fields. Nothing here writes the ledger or affects leaderboards.
- Results are deterministic, and the order of answers within a sheet doesn't matter.

---

## 4. Security and fairness

| Requirement | How it's met |
|---|---|
| Exactly two distinct authenticated participants | `create_battle` rejects the same user twice and anything that isn't a `BattleParticipant` |
| One shared question set | A single `BattleConfig` per battle; both participants see identical `learner_questions` (tested) |
| Fixed question count | The config holds 1–`MAX_BATTLE_QUESTIONS` (20) unique questions; completeness is enforced when `require_all_answers=True` |
| Trusted answer keys only | Keys live in `BattleQuestion`; learners send only `AnswerSubmission(question_id, selected_option)` |
| No client scores, points, winners or keys | No function accepts them; the result is computed by `score_battle` |
| Unauthorized users rejected | Non-participants get `UnauthorizedParticipantError` for submit, questions and view |
| No duplicate responses, no replay | Duplicate question in a sheet → 400; second sheet or post-completion submit → 409 |
| Answer keys secret until completion | `LearnerBattleQuestion` has no key or explanation fields; `BattleView.review` and `.result` stay empty until COMPLETED (and remain empty for CANCELLED) |
| Opponent answers private until final | Before completion a viewer sees only their own answers plus an `opponent_submitted` flag |

**Known fairness gaps (out of scope for this phase):**
- **Answers can be shared out of band:** the first player can tell the second the questions or their answers. Mitigations (timers, simultaneous reveal windows, per-player question order) need real-time infrastructure.
- **No time limits:** a participant can stall an ACTIVE battle indefinitely. A future server timer would need either `cancel_battle` (before any sheet) or a new "forfeit/expire" transition (**PROPOSED**, not implemented).

---

## 5. Persistence requirements (PROPOSED)

The engine is stateless; a future repository must store `BattleState` faithfully.

| Table (proposed) | Key columns | Constraints |
|---|---|---|
| `battles` | `id`, `status`, `require_all_answers`, `created_at`, `started_at`, `completed_at`, `cancel_reason` | `CHECK (status IN (...))` |
| `battle_participants` | `battle_id`, `user_id`, `seat` (1/2), `display_name` snapshot | `PRIMARY KEY (battle_id, user_id)`, `UNIQUE (battle_id, seat)`, exactly two rows |
| `battle_questions` | `battle_id`, `position`, `question_id`, full question incl. `correct_option` and `explanation` snapshot | `PRIMARY KEY (battle_id, position)`, `UNIQUE (battle_id, question_id)` |
| `battle_answer_sheets` | `battle_id`, `user_id`, `submitted_at` | `PRIMARY KEY (battle_id, user_id)`; this is what blocks resubmission in the DB |
| `battle_answers` | `battle_id`, `user_id`, `question_id`, `selected_option` | `PRIMARY KEY (battle_id, user_id, question_id)` |
| `battle_results` | `battle_id`, `outcome`, `winner_user_id`, per-seat `correct` / `answered` / `total` | `PRIMARY KEY (battle_id)`, written once |

- **Snapshot the questions** into the battle, so later edits to a question bank can't change a battle's keys.
- **One transaction per transition.** Concurrent submits must rely on the `battle_answer_sheets` primary key with `INSERT … ON CONFLICT DO NOTHING` plus a rowcount check (same pattern as GAMIFICATION_REPOSITORY_CONTRACT §4). Completion must be computed under a row lock on `battles` (Postgres `SELECT … FOR UPDATE`) so exactly one request writes the result.
- **Engine portability:** placeholders and timestamp handling must follow the merged connection layer's rules (no literal `?` or `%`, serialisable timestamps).

---

## 6. Planned matchmaking and real-time integration (PROPOSED, not implemented)

- **Matchmaking:** a server-side queue pairs two users (e.g. same subject, similar level) and calls `create_battle`. Invites/challenges are an alternative flow. Neither exists.
- **Question selection:** from the assessment or challenge bank for the agreed subject, chosen server-side, then snapshotted.
- **Real time:** polling (`GET /api/battles/{id}` → `battle_view`) is enough for the first version. WebSockets/SSE would push `opponent_submitted` and completion events, but **never answers before completion**. The current FastAPI stack has no WebSocket code.
- **Timers:** server-side deadlines, never client clocks, driving cancel/expire transitions.

## 7. Future XP and leaderboard integration (PROPOSED)

- **XP/points:** an outcome-to-points rule (e.g. win/tie/participation) is a **product decision not made yet**. It would be applied by `gamification_service`, recorded as a ledger event with key `reward_event_key(user_id, "battle", battle_id)` (one per user per battle, idempotent), and gated by the ledger (G-1).
- **Leaderboards:** battle points reach `leaderboard_engine` only through ledger totals. A separate battle-rating leaderboard (Elo or win counts) would need its own design.
- **Anti-farming:** limit rewarded battles per pair and per day before any XP is enabled.

## 8. Dependencies on backend/database contracts

| Dependency | Owner | Status |
|---|---|---|
| Battle tables (§5) in the SQLite setup + `database/schema.sql` + a Supabase migration | Nagin | Not started; needs approval |
| Battle repository methods (create, load, transition, submit atomically) | Nagin + Arsh (shared repository; CR-15 not done) | Not started |
| `routers/battles.py` + `schemas/battles.py`, registered in `main.py` | Ankush (router), Arsh (`main.py`) | Not started |
| Question bank to draw battle questions from | Arsh/Nagin (assessment questions) or Ankush (challenge pools) | Only the 5 Python assessment questions and 1 challenge exist |
| Battle UI | Shoeb | Not started |
| Ledger for XP (G-1) | Ankush + Nagin | Not approved |

## 9. Known limitations

- **Only** `multiple_choice` A–D questions; one fixed set per battle.
- No timers, expiry, forfeit or reconnect handling; ACTIVE battles can stall.
- No anti-collusion beyond hiding answers in the API.
- No speed scoring, no partial credit, no question weighting.
- In-memory and stateless: concurrency safety depends entirely on the future repository (§5).
- Display names are snapshotted at creation; renames aren't reflected.

## 10. Future integration acceptance criteria

1. Battle routes return only `battle_view` / `learner_questions` projections. An OpenAPI and response test proves no `correct_option` or `explanation` appears before COMPLETED.
2. A non-participant gets 403 on every battle route; an invalid transition gets 409; invalid answers get 400.
3. Two concurrent submissions by the same user → exactly one accepted (DB constraint). Two players finishing simultaneously → exactly one result row.
4. Restart persistence: a battle reloaded from storage yields the same `BattleState`, view and result.
5. SQLite and Postgres both pass the same battle repository contract suite (opt-in Postgres via the guarded `TEST_DATABASE_URL`).
6. If XP is enabled: one ledger event per user per battle, no award for cancelled battles, and totals visible on the leaderboard only via the ledger.
