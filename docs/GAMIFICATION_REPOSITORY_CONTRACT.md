# PragyaX Gamification Repository Contract (Phase 2, Task 09)

> **Owner:** Ankush · **Status (2026-10-27):** a reusable contract test suite exists at `backend/tests/gamification_contract/test_repository_contract.py`.
> **No real repository implements the protocol yet.** By default the suite runs only against an in-memory reference fake and **never contacts a database**.
> The protocol is still **PROPOSED**; signatures need agreement from Nagin (database) and Arsh (backend). Related: [GAMIFICATION_ADAPTER.md](GAMIFICATION_ADAPTER.md), [GAMIFICATION_INTEGRATION_PLAN.md](GAMIFICATION_INTEGRATION_PLAN.md).

---

## 1. Protocol under test (exact, from `backend/app/services/gamification_integration.py`)

```python
class WriteResult(StrEnum): INSERTED = "inserted"; ALREADY_COMPLETED = "already_completed"

@dataclass(frozen=True)
class ChallengeWrite:
    user_id: str; challenge_id: str; selected_option: str; is_correct: bool; points_awarded: int
    ledger_event: LedgerEvent | None; badges: tuple[AchievementAward, ...]

@runtime_checkable
class GamificationRepository(Protocol):
    def get_challenge(self, challenge_id: str) -> Mapping[str, object] | None            # pure read
    def has_completed_challenge(self, user_id: str, challenge_id: str) -> bool           # pure read (fast path)
    def get_badge_keys(self, user_id: str) -> frozenset[str]                             # pure read
    def record_challenge_outcome(self, write: ChallengeWrite) -> WriteResult             # one transaction
    def insert_badges(self, user_id: str, awards: tuple[AchievementAward, ...]) -> tuple[str, ...]  # one transaction
    def get_reward_records(self, user_id: str) -> Iterable[RewardRecord]                 # points query
```

### Protocol gaps and inconsistencies (to settle with Nagin and Arsh)
| # | Gap | Effect | Proposed resolution |
|---|---|---|---|
| P-1 | `record_challenge_outcome` must store `ledger_event`, but **no `points_ledger` table exists** (G-1 not approved; not in the SQLite table setup in `connection.py` or in `database/schema.sql`) | A pre-G-1 implementation can't persist ledger rows | Until G-1: derive `get_reward_records` from `user_challenge_submissions` (rows with `points_awarded > 0`) using the same key `daily_challenge:<challenge_id>:<user_id>`. The contract tests accept either approach, because they check only totals and keys |
| P-2 | `ChallengeWrite.points_awarded` and `ledger_event.points_delta` duplicate one value | They could disagree | The implementation should reject a write where they differ (both come from the same decision in the adapter) |
| P-3 | `WriteResult` can't express "submission inserted but ledger event already existed" | Invisible to callers | Acceptable: ledger idempotency is silent by design (contract test R06) |
| P-4 | `insert_badges` receives no equivalence data; legacy equivalence is applied by the adapter **before** the transaction | Stale-snapshot window (GAMIFICATION_ADAPTER §6) | Safe while nothing inserts `py_master` any more; move the check inside the transaction if more equivalents are added |
| P-5 | No seeding or failure-injection methods (correctly, since they're not production concerns) | Contract tests need them | The **factory** seeds; the optional `contract_fail_next_write(stage)` hook enables rollback tests (§3) |
| P-6 | Unknown user or challenge in a write is unspecified | Real databases fail on foreign keys; a fake might not | Contract: must raise and write nothing (R14) |
| P-7 | `get_challenge` returns the whole row, but the adapter needs only 4 keys | Timestamps may come back as engine-specific strings | Contract: values must be JSON-serialisable (R02); the adapter never reads timestamps |

---

## 2. What the suite checks

Tests marked "backend" run once per backend (`fake`, `sqlite`, `postgres`). **A05** is backend-independent.

| ID | Verifies | Requirement covered |
|---|---|---|
| R01 | Object satisfies `GamificationRepository` | conformance |
| R02 | `get_challenge` returns the trusted row with the required keys, JSON-serialisable; unknown id → `None` | trusted config, serialisation |
| R03 | First correct write → `INSERTED`; completion visible; `daily_striker` held; total 50 | successful first submission |
| R04 | Wrong-answer write → completion stored, no reward, no badge | wrong answer |
| R05 | Second write for the same user and challenge → `ALREADY_COMPLETED`, and **none** of its badges or ledger events are written | duplicate submission |
| R06 | The same ledger `event_key` on a different submission → stored once; total unchanged | duplicate reward event |
| R07 ×2 | Injected failure at the ledger / badge stage → nothing persisted; retry → `INSERTED`, total 50 | atomic rollback, retry after failure |
| R08 | `insert_badges` twice → second returns `()` | badge idempotency |
| R09 | `insert_badges` returns only newly inserted keys | badge idempotency |
| R10 | Injected failure in `insert_badges` → nothing persisted | atomic rollback |
| R11 | Seeded `py_master` is returned by `get_badge_keys` | legacy badge visibility |
| R12 | Completion, badges and records never leak between users | multi-user isolation |
| R13 | Two distinct events → total 80, 2 counted, 0 invalid | correct points totals |
| R14 | Non-`ChallengeWrite`, forged badge dict, unknown user → raise, nothing written | invalid input |
| R15 | 4 threads submit simultaneously → exactly 1 `INSERTED`, 3 `ALREADY_COMPLETED`, **no exceptions**, total 50 | concurrency (**real backends only**) |
| A01 | Adapter: first correct submission → exact V1 response body | V1 compatibility |
| A02 | Adapter: wrong answer → 0, retry → V1 "already completed" | V1 compatibility |
| A03 | Adapter: duplicate / invalid option / unknown challenge → exact V1 messages; points unchanged | V1 compatibility |
| A04 | Adapter: `py_master` blocks the Python high score; others get it once | legacy badge equivalence |
| A05 | `to_v1_response()` field order equals `ChallengeResultResponse` (parsed from `schemas/challenges.py`), and all three V1 error strings appear verbatim in `routers/challenges.py` / `repository.py` | V1 compatibility against the **actual** sources |

---

## 3. Backends: simulated vs real

| Backend | Runs when | What a pass means |
|---|---|---|
| `fake` (`ContractFakeRepository`, in the test file) | Always | The contract's **expected behaviour** is self-consistent and the adapter honours it. **Says nothing about database atomicity, isolation, persistence or concurrency**: the fake is single-threaded, in-memory, and commits by swapping dicts. R15 is **skipped** for the fake on purpose |
| `sqlite` | `PRAGYAX_CONTRACT_SQLITE_FACTORY="module:callable"` is set | The real SQLite implementation behaves per contract on a **fresh temp file outside the repository** (the fixture refuses paths inside it) |
| `postgres` | `PRAGYAX_CONTRACT_POSTGRES_FACTORY` **and** `TEST_DATABASE_URL` are set | Real Postgres behaviour on the guarded local test database |

**Factory contract for future implementations:**
```python
def factory(seed: ContractSeed, *, database: str) -> GamificationRepository: ...
# seed.users, seed.challenges (full daily_challenges rows), seed.badges {user_id: badge keys}
# database: temp SQLite file path, or the guarded TEST_DATABASE_URL
# optional: repo.contract_fail_next_write(stage)   # "ledger" | "badges"; otherwise R07/R10 skip
```

The factory must create the seeded users, challenges and badges itself, because the protocol has no seeding methods. It should start from an empty schema each time.

**Postgres guard:** the same rules as `test_postgres_student_journey.py`. The fixture **fails** (it does not skip) unless all of these hold:
- the host is `127.0.0.1`, `localhost` or `::1`;
- the database is `pragyax_test`;
- the host doesn't contain `supabase`;
- the URL and host differ from `DATABASE_URL`.

`DATABASE_URL` is never used to connect.

**Verified wiring (no database involved):** pointing both factory variables at the fake factory runs the sqlite and postgres variants. A Supabase host, a non-`pragyax_test` database, or `TEST_DATABASE_URL == DATABASE_URL` each make the fixture fail. These checks prove the opt-in and guard logic only; **no SQLite or Postgres implementation was exercised.**

---

## 4. Backend-specific requirements for the real implementations

Each of these comes from the merged code (`backend/app/database/connection.py`, `repository.py`):

1. **One transaction per write.** Implement `record_challenge_outcome` and `insert_badges` each inside a single `with get_db() as conn:` block. Today that block commits on success and rolls back on any exception, on both engines.
2. **Detect conflicts from the insert's result, never from exceptions.** In Postgres mode, `get_db()` re-raises **every** exception from inside the block as `DatabaseConnectionError` (`connection.py:192-195`), unique violations included. A duplicate is then indistinguishable from an outage. So:
   - insert the submission with `INSERT … ON CONFLICT (user_id, challenge_id) DO NOTHING`;
   - decide `INSERTED` vs `ALREADY_COMPLETED` from `cursor.rowcount` (both engines) or `RETURNING id` (SQLite ≥ 3.35, local 3.50.4);
   - only on `INSERTED`, write the ledger and badge rows with `ON CONFLICT … DO NOTHING`.
   R15 asserts that conflicts never surface as exceptions.
3. **Placeholders.** Write SQL with `?` only. The Postgres wrapper swaps **every** `?` for `%s`, so SQL text must not contain a literal `?` or `%` (e.g. `LIKE '%x'`, or text such as `"80%+"`); pass such values as parameters, as the merged repository already does for badge text.
4. **Timestamps.** Postgres rows are normalised to ISO strings by the wrapper (`2026-10-27T08:56:49.123456+00:00`); SQLite returns `2026-10-27 08:56:49`. Any value returned by `get_challenge` must be JSON-serialisable (R02). Never compare timestamps as strings across engines.
5. **Booleans.** Store `is_correct` as a real boolean (Postgres) or 0/1 (SQLite). The protocol never returns it, so there's no cross-engine leak.
6. **SQLite write lock.** `get_db()` gives no way to start with `BEGIN IMMEDIATE`. Correctness must therefore rest on `UNIQUE` + `ON CONFLICT`, not on a read-then-write check. The fast-path `has_completed_challenge` remains an optimisation only.
7. **Ordering.** Don't rely on `created_at` for ordering among same-second rows on SQLite (seconds resolution); `get_reward_records` order is not part of the contract.
8. **Foreign keys.** Unknown users or challenges must raise and write nothing (R14). Postgres enforces this; SQLite only does if `PRAGMA foreign_keys=ON`, which the current `get_db()` does **not** set, so an SQLite implementation must check explicitly.

---

## 5. Implementation steps for the real repository (each needs approval)

1. Agree the six signatures plus gaps P-1 … P-7 (Nagin, Arsh, Ankush).
2. Decide where the implementation lives. CR-15 (repository split) is **not** done; `repository.py` is still one shared class.
3. Implement a SQLite version (pre-G-1: rewards derived from submissions, P-1) and run:
   `PRAGYAX_CONTRACT_SQLITE_FACTORY=<module>:<factory> pytest backend/tests/gamification_contract`
4. Implement a Postgres version against the local `pragyax_test` cluster and run with `PRAGYAX_CONTRACT_POSTGRES_FACTORY` and `TEST_DATABASE_URL`. **R15 must pass here** before any concurrency claim is made.
5. After G-1: add the `points_ledger` table (SQLite setup + `schema.sql` + a Supabase migration by Nagin) and switch `get_reward_records` to the ledger. The contract tests stay the same.
6. Only then: G-6 router wiring (Ankush's challenges router; Arsh's assessments and dashboard).

---

## 6. Running safely

```bash
env -u DATABASE_URL -u TEST_DATABASE_URL PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python -m pytest backend/tests/gamification_contract -p no:cacheprovider -rs
```

By default: the fake variants run, the sqlite and postgres variants skip with a reason, and R15 skips for the fake. No database connection is attempted.
