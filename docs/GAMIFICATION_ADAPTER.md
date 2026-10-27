# PragyaX Gamification Integration Adapter (G-6 foundation)

> **Owner:** Ankush · **Status (2026-10-27):** `backend/app/services/gamification_integration.py` exists and is unit-tested against an **in-memory fake** only.
> It is **not wired** into any router, and **no real repository implements its protocol**. `backend/app/database/repository.py` today has only `get_daily_challenge`, the all-in-one `submit_daily_challenge` and `get_user_badges`.
> The protocol below is **PROPOSED**. It has not been agreed with Nagin (database) or Arsh (backend), and every item needing approval is listed in §8.

| Artifact | Path |
|---|---|
| Adapter + provisional protocol | `backend/app/services/gamification_integration.py` |
| Tests (38, in-memory fake) | `backend/tests/test_gamification_integration.py` |
| This document | `docs/GAMIFICATION_ADAPTER.md` |

---

## 1. Proposed repository protocol (`GamificationRepository`, a `typing.Protocol`)

| Kind | Method | Contract |
|---|---|---|
| Pure read | `get_challenge(challenge_id: str) -> Mapping[str, object] \| None` | Trusted `daily_challenges` row with keys `id`, `correct_option`, `points`, `explanation`; `None` if unknown |
| Pure read (fast path only) | `has_completed_challenge(user_id: str, challenge_id: str) -> bool` | Optimisation only; correctness must never depend on it |
| Pure read | `get_badge_keys(user_id: str) -> frozenset[str]` | Every `badge_key` the user holds, legacy keys (`py_master`) included |
| **Transactional write + idempotent inserts** | `record_challenge_outcome(write: ChallengeWrite) -> WriteResult` | One transaction:<ol><li>Insert the submission with `ON CONFLICT (user_id, challenge_id) DO NOTHING`. On conflict, write nothing else and return `ALREADY_COMPLETED`.</li><li>Otherwise, insert the ledger event if present, with `ON CONFLICT (event_key) DO NOTHING`.</li><li>Insert each badge with `ON CONFLICT (user_id, badge_key) DO NOTHING`.</li><li>Return `INSERTED`.</li></ol>All or nothing |
| **Badge award** (transactional, idempotent) | `insert_badges(user_id: str, awards: tuple[AchievementAward, ...]) -> tuple[str, ...]` | One transaction; `ON CONFLICT (user_id, badge_key) DO NOTHING`; returns the keys actually inserted |
| Points total query | `get_reward_records(user_id: str) -> Iterable[RewardRecord]` | The user's ledger rows as `RewardRecord`. Revocation marking waits for D-1 |

Supporting types (in the same module):
- **`ChallengeWrite`** (frozen): `user_id, challenge_id, selected_option` (normalised A–D), `is_correct, points_awarded, ledger_event: LedgerEvent | None, badges: tuple[AchievementAward, ...]` (already filtered).
- **`WriteResult`**: `INSERTED` or `ALREADY_COMPLETED`.

The protocol is `@runtime_checkable`, so the adapter rejects objects that lack these methods. That only checks method names, not behaviour.

## 2. Adapter entry points (`GamificationIntegration`)

```python
GamificationIntegration(repository, *, new_event_id: Callable[[], str], zero_point_policy: ZeroPointPolicy)

submit_daily_challenge(user_id, challenge_id, selected_option) -> ChallengeSubmissionOutcome
award_assessment_badges(user_id, score, total, subject_id, subject_title) -> tuple[str, ...]
get_points_summary(user_id) -> PointsSummary
```
- **Dependency injection:** the repository, and the event-ID generator (live IDs `rwd_<hex>` need randomness, so the generator is supplied by the caller). The adapter itself uses no clock, randomness, SQL or I/O; tests enforce this.
- **`zero_point_policy` is required**, with no default, because D-3 is undecided.
- **Trust boundary:**
  - `user_id` must come from authentication; it is validated with the ledger's ID rules (≤ 64 characters) before any repository call.
  - The learner supplies only `selected_option`.
  - Points come only from the stored challenge row, via `ChallengeConfig`; badges only from `compute_challenge_reward` / `eligible_assessment_achievements`, filtered by `filter_new_achievements`. No entry point accepts points or badge keys.
- **Existing functions are reused unchanged:** `ChallengeConfig`, `compute_challenge_reward`, `decide_challenge_ledger_award`, `filter_new_achievements`, `eligible_assessment_achievements`, `aggregate_points`.

### `submit_daily_challenge` flow
1. Validate `user_id` (`InvalidTrustedInputError` if malformed).
2. Validate the option **before** any lookup, as V1's router does → `INVALID_OPTION`.
3. `get_challenge`; unknown or non-string id → `CHALLENGE_NOT_FOUND`.
4. Build `ChallengeConfig` from the row. A malformed row (negative or boolean points, a bad key, missing fields, a non-string explanation) raises `InvalidTrustedInputError` and nothing is written.
5. Fast-path `has_completed_challenge`, then `compute_challenge_reward`. A repeat → `ALREADY_COMPLETED`.
6. `decide_challenge_ledger_award` (live origin, injected event ID, configured policy) and `filter_new_achievements` against `get_badge_keys`.
7. `record_challenge_outcome`. If it reports `ALREADY_COMPLETED` (a concurrent request won), return `ALREADY_COMPLETED` with 0 points.
8. Return `ACCEPTED` with `is_correct`, `points_awarded`, `correct_option`, `explanation`, `badges_awarded` and `ledger_recorded`.

## 3. Transaction boundaries and atomicity requirements (for the real repository)

| Requirement | Who guarantees it |
|---|---|
| Submission + ledger + badges commit together or not at all | Repository (`record_challenge_outcome` = one DB transaction) |
| One submission per user per challenge, even under concurrency | DB `UNIQUE(user_id, challenge_id)` + `ON CONFLICT DO NOTHING`; SQLite should use `BEGIN IMMEDIATE` (GAMIFICATION_INTEGRATION_PLAN §2.3) |
| One ledger row per event | DB `UNIQUE(event_key)` |
| One badge per key per user | DB `UNIQUE(user_id, badge_key)` |
| Legacy equivalence (`py_master` ≡ Python high score) | Adapter, via `filter_new_achievements` on a read taken **before** the write (see §6 for the residual race) |
| Errors roll back | Repository; the adapter does not catch repository exceptions |
| Which values are written | Adapter (pure decisions from trusted inputs) |

The adapter holds **no locks** and makes **no exactly-once claim** on its own.

## 4. Data ownership boundaries

| Data | Written by | Read by adapter | Owner of the code |
|---|---|---|---|
| `daily_challenges` | Seeds/admin (Nagin) | `get_challenge` | Nagin |
| `user_challenge_submissions` | `record_challenge_outcome` | `has_completed_challenge` | Nagin (impl), Ankush (rules) |
| `points_ledger` (G-1, not yet created) | `record_challenge_outcome` | `get_reward_records` | Nagin (impl), Ankush (rules) |
| `user_badges` | `record_challenge_outcome`, `insert_badges` | `get_badge_keys` | Nagin (impl), Ankush (rules) |
| Decision logic | – | – | Ankush (`gamification_service`, `points_ledger_domain`, this adapter) |
| HTTP mapping | – | – | Ankush (`routers/challenges.py`); Arsh (`routers/assessments.py`, `routers/dashboard.py`) |

## 5. Expected errors and duplicate behaviour

| Situation | Adapter result | V1-compatible HTTP mapping (future router) |
|---|---|---|
| Option not A–D (any challenge id) | `INVALID_OPTION`, nothing written | 400 `"selected_option must be A, B, C, or D."` |
| Unknown challenge id | `CHALLENGE_NOT_FOUND`, nothing written | 400 `"Challenge not found"` |
| Repeat, detected by the fast path or by a write conflict | `ALREADY_COMPLETED`, 0 points, nothing written | 400 `"Challenge already completed by this user today"` |
| First correct answer | `ACCEPTED`, trusted points, `daily_striker` unless already held | 200 `ChallengeResultResponse` (`to_v1_response()`) |
| First wrong answer | `ACCEPTED`, `is_correct=False`, 0 points, no ledger row, attempt used | 200 |
| Correct, 0-point challenge | `RECORD`: ledger row with 0 points; `SKIP`: no ledger row. The badge is awarded either way (V1 parity) | 200 |
| Corrupt stored challenge / bad `user_id` / bad policy | `InvalidTrustedInputError` | 500 + log |
| Repository failure | Exception propagates unchanged | 500 (repository rolled back) |
| `py_master` held, Python ≥ 80% | No new badge | n/a (assessments response unchanged) |

`ChallengeSubmissionOutcome.v1_error_detail` returns the exact V1 messages. These constants are copied in the adapter so a future router can keep its contract **without** importing V1 code.

## 6. Fake guarantees vs. real database guarantees

| Property | In-memory fake (tests) | Real repository (required later) |
|---|---|---|
| All-or-nothing writes | Stages copies, then swaps dicts; injected failures leave no state | Real DB transaction |
| Duplicate submission | Python `in` check inside a single-threaded call | `UNIQUE` + `ON CONFLICT`; safe across processes |
| Duplicate ledger event | `dict.setdefault` by `event_key` | `UNIQUE(event_key)` |
| Concurrency | **Not tested and not representative.** No threads, no processes | Must be proven with concurrent tests on SQLite and Postgres (plan T4) |
| Persistence across restarts | None | Required (plan T9) |

**Passing these 38 tests proves the orchestration logic only. It does not prove atomicity, exactly-once awards or concurrency safety.**

Residual races the real implementation must handle:
- **Badge snapshot:** `get_badge_keys` is read before the write transaction, so the equivalence filter uses a possibly stale snapshot. This is safe only because, once integrated, nothing inserts `py_master` any more (the V1 rule is removed). The only remaining race is two inserts of the same key, which `UNIQUE(user_id, badge_key)` resolves. If new legacy equivalents are ever added, the equivalence check must move inside the transaction.
- **Unused event IDs:** the event ID is generated before the write. A conflicting request discards its generated ID (harmless; IDs needn't be contiguous).
- **Stale fast path:** `has_completed_challenge` may be stale; the write's conflict result is authoritative. A test covers this.

## 7. V1 API compatibility notes
- Response body fields and status codes map 1:1 to V1 (`to_v1_response()` and `v1_error_detail`); a future router needs no schema change.
- V1 order is preserved: option validation before the challenge lookup; a wrong answer uses up the attempt; the answer key is revealed in the response after a submission.
- `daily_striker` text and key are unchanged (V1 parity constant).
- The adapter does **not** change `GET /api/challenges/daily`, the dashboard or the assessment responses. Dashboard `total_points` keeps using V1 submissions until the G-1 cutover (plan §4.1 M5).

## 8. Dependencies and approvals required before integration

| Item | Dependency | Approval |
|---|---|---|
| Agree the six protocol method signatures (§1) | Nagin, Arsh | ⚠️ **Nagin + Arsh + Ankush** |
| CR-15: split `repository.py` behind an interface | Shared file SF-01 | ⚠️ Nagin + Arsh + Ankush |
| G-1: `points_ledger` table, dual write, backfill | Schema + migration | ⚠️ Ankush (plus Nagin for the implementation) |
| G-2 / D-2: `py_master` alias | **Approved by Ankush** (recorded in `points_ledger_domain.py`) | – |
| D-6: equivalents live in the service | **Approved by Ankush** | – |
| G-6: wire `routers/challenges.py` (Ankush), `routers/assessments.py` and `routers/dashboard.py` (Arsh) | This adapter + a real repository | ⚠️ Ankush; Arsh for his routers |
| G-7: dated reward keys for rotating challenges | Only needed once the rotation engine is wired | ⚠️ Ankush |
| D-1 revocation, D-3 zero-point rows, D-5 retention | Undecided | ⚠️ Ankush (D-5 with Nagin) |

Integration steps, in order, each needing the approvals above:
1. Agree the protocol.
2. Land CR-15.
3. Nagin implements a `SqliteGamificationRepository` (and later a Postgres one) satisfying it, with concurrency tests.
4. Approve G-1 and create the ledger with dual write.
5. Wire `routers/challenges.py` to the adapter, with an OpenAPI snapshot unchanged.
6. Arsh wires `award_assessment_badges` after `save_assessment_attempt` and removes the V1 `py_master` rule.
7. Do the dashboard cutover after reconciliation.

## 9. What remains unimplemented
- Any real repository implementation; any SQL, table or migration.
- Router, dashboard or frontend wiring; the live app still uses V1 logic in `repository.py`.
- Real concurrency, restart and Postgres tests (they require a real repository).
- Revocation (D-1), retention (D-5), the ledger cutover (D-4).
- Daily rotation in the submit flow (`daily_challenge_engine` is not used here) and dated v2 reward keys (G-7).
- Leaderboards (G-4) and additional tiers (G-5).
