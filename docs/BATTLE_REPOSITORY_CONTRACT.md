# PragyaX Battle Repository Contract (Phase 2, Task 12)

> **Owner:** Ankush · **Status (2026-10-27):** a **provisional** `BattleRepository` protocol and its contract tests exist in `backend/tests/battle_contract/test_battle_repository_contract.py`.
> **No real repository implements it**, no battle table exists, and nothing in the application uses it. By default only an in-memory fake runs and **no database is contacted**.
> `backend/app/services/battle_engine.py` is unchanged (scoring, lifecycle, eligibility and errors as in [BATTLE_ENGINE.md](BATTLE_ENGINE.md)).
> Related: [GAMIFICATION_REPOSITORY_CONTRACT.md](GAMIFICATION_REPOSITORY_CONTRACT.md) (same opt-in and guard pattern).

---

## 1. Proposed protocol (provisional, defined only in the test module)

```python
class TransitionResult(StrEnum): APPLIED | CONFLICT          # CONFLICT: guard failed, nothing written
class SheetResult(StrEnum):      INSERTED | ALREADY_SUBMITTED | NOT_ACTIVE

class BattleRepository(Protocol):
    def create_battle(self, state: BattleState) -> None            # CREATED only; frozen question snapshot; raises on duplicate id
    def load_battle(self, battle_id: str) -> BattleState | None    # full trusted state; sheets in seat order
    def start_battle(self, battle_id: str) -> TransitionResult     # CREATED -> ACTIVE
    def submit_answer_sheet(self, battle_id: str, sheet: AnswerSheet) -> SheetResult   # one per (battle, user), ACTIVE only
    def complete_battle(self, battle_id: str, result: BattleResult) -> TransitionResult  # ACTIVE + 2 sheets + no result, exactly once
    def cancel_battle(self, battle_id: str, reason: str) -> TransitionResult  # CREATED, or ACTIVE with no sheets
```

**Rules:**
- Every mutating method is **one transaction** with a **guarded precondition**.
- Write conflicts are **return values, never exceptions**. That's required because the merged Postgres `get_db()` turns every exception into `DatabaseConnectionError` (see GAMIFICATION_REPOSITORY_CONTRACT §4).
- An unknown `battle_id` raises `LookupError`.
- A sheet from a non-participant raises: it's a server bug, and the database enforces it with a foreign key to `battle_participants`.

### Why "submit" and "complete" are separate
The pure engine completes a battle inside `submit_answers` when it sees the second sheet. With persistence, two players can submit **at the same time**, each having loaded a state with zero sheets; neither would see two sheets, and the battle would never complete.

The protocol therefore stores sheets one at a time. After any accepted sheet, the caller reloads, and if both sheets are present it calls `complete_battle(score_battle(state))`. The guard makes completion exactly-once whichever request gets there first; a losing completer gets `CONFLICT`, which is harmless.

### Intended service algorithm (test-local `BattleFlow`)
1. **Load** the battle (`LookupError` if missing).
2. Run the **pure engine** transition on the loaded state. This performs **all** validation and raises the existing domain errors: `InvalidSubmissionError`, `UnauthorizedParticipantError`, `InvalidBattleTransitionError`.
3. Do the **guarded write**. On `CONFLICT`, `ALREADY_SUBMITTED` or `NOT_ACTIVE`: reload and re-run the engine, which raises the precise domain error for the fresh state.
4. **After an accepted sheet:** run the completion step.
5. **Views:** always `battle_view(load_battle(id), viewer)`, so answer keys and opponent answers stay hidden until COMPLETED. That's the engine's guarantee, unchanged.

`BattleFlow` is a test helper showing the intended composition. It isn't application code.

---

## 2. What is tested

**Contract tests**, run per backend. The fake runs now; SQLite and Postgres are opt-in.

| ID | Verifies |
|---|---|
| C01 | Object satisfies `BattleRepository` |
| C02 | Create stores participants and a frozen copy of the questions with keys; unknown id → `None`; duplicate id raises |
| C03 | Start → first sheet (still ACTIVE, no result) → second sheet → COMPLETED with the right winner |
| C04 | Saved result == `score_battle(loaded)` == the result of the pure engine run in memory (domain and storage agree) |
| C05 | Reload through `contract_reopen()` gives identical status, result, sheets and **both participants' views** |
| C06 | Duplicate submission → `InvalidBattleTransitionError`; repository returns `ALREADY_SUBMITTED`; the original sheet is unchanged |
| C07 | Third party: `UnauthorizedParticipantError` (flow) and a repository-level rejection; nothing stored |
| C08 | Invalid transitions (submit before start, start twice, complete without sheets, cancel after a sheet) are rejected and nothing is written; unknown id → `LookupError` |
| C09 | A cancelled battle can't start, accept sheets (`NOT_ACTIVE`) or complete (`CONFLICT`), and reveals nothing; ACTIVE-with-no-sheets can be cancelled |
| C10 ×5 | An injected failure at create, start, submit, complete or cancel leaves no partial state, and a retry succeeds |
| C11 | Result stored exactly once: a forged later `complete_battle` → `CONFLICT`; a racing completer is a no-op |
| C12 | No answer key, explanation or opponent answers in views before completion; both participants' answers in the review after |
| C13 | Separate battles and participants stay isolated (including the same player in two battles) |
| C14 | Invalid answers (unknown question, bad option, incomplete sheet) never reach storage |

**Real-database-only tests (D).** They're defined, and **skipped for the fake by design**: the fake can't honestly show these properties.

| ID | Verifies (real SQLite/Postgres only) |
|---|---|
| D01 | Both players submit simultaneously → exactly one completion; result == `score_battle` |
| D02 | 4 parallel submits by one player → 1 `INSERTED`, 3 `ALREADY_SUBMITTED` (unique sheet constraint) |
| D03 | 4 parallel `complete_battle` calls → 1 `APPLIED`, 3 `CONFLICT` (transactional result creation) |
| D04 | Concurrent cancel vs. submit → either cancelled with no sheet or active with the sheet; never both (lost-update prevention) |
| D05 | Restart (`contract_reopen`) in the middle of a battle → the second player completes it correctly (durability) |

**E01** (backend-independent): the battle engine's public API and `MAX_BATTLE_QUESTIONS` are unchanged.

---

## 3. Real vs. simulated guarantees

| Property | In-memory fake | Real SQLite/Postgres (required, not yet tested) |
|---|---|---|
| All-or-nothing writes | Stages a row copy and commits by replacement; injected failures leave nothing | Real transactions (one `with get_db()` block) |
| Guards (status, sheet count, result absent) | Python checks inside one call | `UPDATE … WHERE status = … AND …` / `INSERT … ON CONFLICT DO NOTHING`, with rowcount or `RETURNING` deciding the result |
| One sheet per player | Dict key | `PRIMARY KEY (battle_id, user_id)` on `battle_answer_sheets` |
| Exactly-once result | Python check | `PRIMARY KEY (battle_id)` on `battle_results`, plus the status guard in the same transaction |
| Concurrency / locking | **Not demonstrated** (single-threaded) | D01–D04 must pass |
| Restart durability | **Simulated** (`contract_reopen` shares a dict) | D05 with a real reconnect |

**Passing the fake proves only the contract's expected behaviour. No atomicity, locking or durability claim can be made until D01–D05 pass on a real backend.**

**Known gap (C10, `complete` stage):** if the completion transaction fails after the second sheet committed, the battle sits ACTIVE with two sheets until something retries the completion step. The service must therefore also run the completion step when loading or viewing a battle (self-healing), or run a periodic repair job. Completion is idempotent, so either is safe.

---

## 4. Schema requirements (PROPOSED, not created)

As BATTLE_ENGINE.md §5, plus the constraints this contract relies on:

| Table | Must have |
|---|---|
| `battles` | `id` PK; `status` CHECK in (`created`, `active`, `completed`, `cancelled`); `require_all_answers`; `cancel_reason`; timestamps |
| `battle_participants` | PK `(battle_id, user_id)`; `UNIQUE (battle_id, seat)`; seat ∈ {1, 2}; `display_name` snapshot |
| `battle_questions` | PK `(battle_id, position)`; `UNIQUE (battle_id, question_id)`; full snapshot incl. `correct_option` and `explanation` (server-only columns) |
| `battle_answer_sheets` | PK `(battle_id, user_id)`; FK to `battle_participants` |
| `battle_answers` | PK `(battle_id, user_id, question_id)`; FK to the sheet and to `battle_questions (battle_id, question_id)` |
| `battle_results` | PK `battle_id`; outcome, `winner_user_id` (nullable for a tie), per-seat `correct` / `answered` / `total` |

## 5. Transaction rules for implementers

1. **start:** `UPDATE battles SET status='active' WHERE id=? AND status='created'`. One row → `APPLIED`, zero → `CONFLICT`.
2. **submit:** in one transaction:
   - check the battle is active (`SELECT … FOR UPDATE` on `battles` in Postgres);
   - `INSERT` the sheet `ON CONFLICT DO NOTHING`;
   - if a row was inserted, insert its answers;
   - otherwise return `ALREADY_SUBMITTED` (or `NOT_ACTIVE`).
3. **complete:** in one transaction:
   - lock the battle row;
   - require `status='active'`, 2 sheets and no result;
   - insert `battle_results` and update the status.
   A competing completer then sees a non-active status → `CONFLICT`.
4. **cancel:** `UPDATE battles SET status='cancelled', cancel_reason=? WHERE id=? AND (status='created' OR (status='active' AND NOT EXISTS (SELECT 1 FROM battle_answer_sheets WHERE battle_id=?)))`. On Postgres this needs the same row lock as submit so the two can't interleave (D04).
5. **SQLite:** `get_db()` can't start with `BEGIN IMMEDIATE`, so rely on primary keys and `ON CONFLICT` for uniqueness. Guarded `UPDATE`s with a rowcount check are atomic in SQLite, because a writer holds the database lock for the whole statement. SQLite doesn't enforce foreign keys unless `PRAGMA foreign_keys=ON`, which the current `get_db()` doesn't set, so the implementation must check participants explicitly.
6. **Placeholders and serialisation:**
   - write SQL with `?` only, and no literal `?` or `%` in SQL text;
   - convert stored timestamps to strings before returning them;
   - rebuild `BattleState` from rows exactly (sheets in seat order, answers in question order) so that C05 holds.

---

## 6. Opt-in execution (real backends)

```bash
# SQLite (temp file outside the repository is provided by the fixture)
PRAGYAX_BATTLE_CONTRACT_SQLITE_FACTORY=<module>:<factory> pytest backend/tests/battle_contract
# PostgreSQL (local dedicated test database only)
PRAGYAX_BATTLE_CONTRACT_POSTGRES_FACTORY=<module>:<factory> TEST_DATABASE_URL=postgresql://…@127.0.0.1:5433/pragyax_test \
  pytest backend/tests/battle_contract
```

- **Factory:** `factory(*, database: str) -> BattleRepository` over empty battle tables.
- **Optional hooks:**
  - `contract_fail_next_write(stage)` enables C10;
  - `contract_reopen()` (a new instance over the same storage, ideally a new connection) enables C05 and D05.
- **Postgres guard:** the same as the other contract suites and `test_postgres_student_journey.py`. The URL must be a local host with database `pragyax_test`, not Supabase, and must differ from `DATABASE_URL`; otherwise the fixture **fails**. `DATABASE_URL` is never used to connect.
- **Wiring verified without any database:** pointing both factory variables at the fake runs the variants, and a Supabase host or `TEST_DATABASE_URL == DATABASE_URL` makes the fixture fail. No real implementation was exercised.

## 7. Ownership and integration blockers

| Blocker | Owner | Status |
|---|---|---|
| Agree the protocol and the submit/complete split | Ankush + Nagin + Arsh | Not agreed |
| Battle tables (§4) in the SQLite setup, `database/schema.sql` and a Supabase migration | Nagin | Not started; needs approval |
| Repository implementation location (CR-15 split not done; `repository.py` is shared) | Nagin + Arsh | Blocked on CR-15 |
| Battle service (production version of `BattleFlow`, with self-healing completion) | Ankush (new service file) | Not started |
| `routers/battles.py`, `schemas/battles.py`, registration in `main.py` | Ankush; Arsh (`main.py`) | Not started |
| Question source for battles | Arsh/Nagin (assessment bank) or Ankush (challenge pools) | Only 5 assessment questions exist |
| Matchmaking, timers, real-time updates | Ankush + team | Not designed beyond BATTLE_ENGINE §6 |
| XP for battles (ledger G-1) | Ankush + Nagin | Not approved |

**Known limitations:** `BattleFlow` is test-only. The fake can't demonstrate concurrency or durability. D01–D05 are written but have never run against a real database.
