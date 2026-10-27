# PragyaX Leaderboard Ranking Engine (G-4 foundation)

> **Owner:** Ankush · **Status (2026-10-27):** a pure, unit-tested ranking engine exists at `backend/app/services/leaderboard_engine.py`.
> **No leaderboard route, query, table or UI exists**, and nothing in the application calls this module.
> Totals are not computed here; membership is not verified here. Everything marked **PROPOSED** requires Ankush's approval, plus the listed owners' approval for their files.
> Related: [GAMIFICATION_DESIGN.md](GAMIFICATION_DESIGN.md) §6 (leaderboard sketch, G-4), [GAMIFICATION_INTEGRATION_PLAN.md](GAMIFICATION_INTEGRATION_PLAN.md) (ledger, G-1), [DAILY_CHALLENGE_ENGINE.md](DAILY_CHALLENGE_ENGINE.md) §7 (scopes).

| Artifact | Path |
|---|---|
| Engine | `backend/app/services/leaderboard_engine.py` |
| Tests (62) | `backend/tests/test_leaderboard_engine.py` |
| This document | `docs/LEADERBOARD_ENGINE.md` |

---

## 1. Domain contracts and signatures

```python
class ScopeType(StrEnum): PLATFORM = "platform"; COLLEGE = "college"; COMPANY = "company"

@dataclass(frozen=True)
class LeaderboardScope:            # platform: scope_id None; college/company: scope_id required
    scope_type: ScopeType; scope_id: str | None = None
    key -> str                      # 'platform' | 'college:<id>' | 'company:<id>'

@dataclass(frozen=True)
class LeaderboardMember:           # TRUSTED input: identity from users, total from the ledger
    user_id: str; display_name: str; total_points: int

@dataclass(frozen=True)
class ScopeMembership:             # TRUSTED input from a future membership service
    scope: LeaderboardScope; user_ids: frozenset[str]

@dataclass(frozen=True)
class RankedMember:                # server-side only (keeps user_id)
    rank: int; position: int; user_id: str; display_name: str; total_points: int

@dataclass(frozen=True) class Leaderboard:      scope; entries: tuple[RankedMember, ...]; total_participants
@dataclass(frozen=True) class LeaderboardPage:  scope; offset; limit; total_participants; entries
@dataclass(frozen=True) class LeaderboardRow:   rank; display_name; total_points; is_viewer   # learner-safe

def rank_members(members: Iterable[LeaderboardMember]) -> tuple[RankedMember, ...]
def build_leaderboard(scope, members, membership: ScopeMembership | None = None) -> Leaderboard
def paginate(leaderboard, *, offset: int = 0, limit: int = 20) -> LeaderboardPage
def top_n(leaderboard, n: int) -> LeaderboardPage
def viewer_standing(leaderboard, viewer_user_id: str) -> LeaderboardRow | None
def to_learner_rows(page, viewer_user_id: str | None = None) -> tuple[LeaderboardRow, ...]
```

**Validation:**

*Trusted data* (errors raise `InvalidTrustedInputError`, mapping to 500 once wired):
- `user_id` follows the ledger's user-id rule (`[A-Za-z0-9_.-]+`, ≤ 64);
- `display_name` must be non-blank, ≤ 100 characters (the `RegisterRequest.name` limit) and trimmed;
- `total_points` must be an `int ≥ 0` (bools rejected, via the gamification service's validator);
- a scope type must be one of the three; `scope_id` must match `[A-Za-z0-9_-]+` (≤ 64), be present for college/company and absent for platform;
- duplicate user ids in one snapshot are rejected;
- every member is validated, including members outside a college/company scope.

*Request data:* `offset` and `limit` raise `InvalidSubmissionError` (mapping to **400**):
- `offset` must be an `int ≥ 0`;
- `limit` must be an `int` from 1 to `MAX_PAGE_SIZE = 100`;
- bools are rejected for both.

---

## 2. Ranking and tie-break policies

1. **Order:** `total_points` descending, then `user_id` ascending in plain Python string order (Unicode code points). For example, `USR_Z < usr_10 < usr_9 < usr_b`. This tie-break is arbitrary but **stable and documented**: the input order never matters (tested with 20 shuffles).
2. **Displayed rank:** **competition ranking (1, 1, 3)**. Equal totals share a rank, and the next rank skips by the number tied. There is no project requirement for dense ranking.
3. **`position`:** a unique 1-based place in the ordering, for stable pagination and UI keys. It is not shown as a rank.
4. **Pagination never renumbers:** a page's rows keep their full-leaderboard ranks, and pages concatenate back to the whole board. An offset past the end returns an empty page (not an error), and `total_participants` is always the full count.

Tied learners with the same points therefore share a rank but always appear in the same order, so the result is deterministic for a given snapshot.

---

## 3. Scope and membership assumptions

- **Platform:** ranks every member supplied. A membership list is not allowed.
- **College / company:** a `ScopeMembership` **for that exact scope** is required. Only its members are ranked; listed users with no points row are simply absent, and supplied members outside the scope are left out (not an error).
- **Membership is not verified here.** No college or company membership data or service exists in PragyaX today. A future trusted service (owner to be decided) must supply `ScopeMembership` from server-side records, never from client claims.
- Scope keys (`college:<id>`) align with the scope idea in DAILY_CHALLENGE_ENGINE §7. Ids must be globally unique within a scope type.

---

## 4. Future ledger integration (PROPOSED)

- **Source of `total_points`:** the verified ledger only (G-1 `points_ledger`):
  - each user's total = `aggregate_points(records).total_points`, or the equivalent SQL: `SUM(points_delta)` over awarded, non-revoked rows;
  - **never** client values;
  - until G-1 exists, the only points source is `SUM(user_challenge_submissions.points_awarded)` (the V1 dashboard total).
- **Snapshot construction (repository side):** one read that returns `(user_id, users.name, total)` for every user with points. Optionally add zero-point users if the product wants them listed. Users with no rows are absent, not ranked at 0, unless they're included explicitly.
- **Windows** (weekly or monthly) need ledger `created_at` filtering and a timezone decision (G-3). Not implemented.
- **Consistency:** a leaderboard is a point-in-time snapshot. Cache it per scope and window, and rebuild when the ledger changes or on a timer.

## 5. Future FastAPI endpoint requirements (PROPOSED, G-4)

- **Route:** `GET /api/leaderboard?scope=platform|college|company&scope_id=…&offset=0&limit=20`, protected by `get_current_user`.
- **Response sketch:**

  ```json
  {"scope": "platform", "total_participants": 128, "offset": 0, "limit": 20,
   "entries": [{"rank": 1, "display_name": "Asha", "total_points": 450, "is_viewer": false}],
   "me": {"rank": 17, "display_name": "Ravi", "total_points": 120, "is_viewer": true}}
  ```
  `me` comes from `viewer_standing` and is `null` when the viewer isn't ranked.
- **Errors:**
  - `InvalidSubmissionError` → 400 (bad `offset` or `limit`);
  - an unknown scope or a scope the viewer may not see → 403 or 404 (an authorisation rule, to be decided);
  - `InvalidTrustedInputError` → 500 + log.
- **Ownership:** a new `routers/leaderboard.py` and `schemas/leaderboard.py` (Ankush); a repository snapshot query (Nagin/Arsh, shared `repository.py`, after CR-15); a frontend page (Shoeb); registration in `main.py` (shared, Arsh).
- **Rate limiting and caching** are recommended once real traffic exists.

## 6. Privacy considerations

- **What learners see:** `LeaderboardRow` has **only** `rank`, `display_name`, `total_points` and `is_viewer`. There are no user ids, emails, tokens or other database fields (tested), and `is_viewer` is computed on the server.
- **Display names are shown to other learners.** That is a product decision to confirm, and should eventually be backed by an opt-out or alias setting (a schema change, not implemented). Make sure `display_name` is the public name and never an email.
- **Scoped boards** (college or company) reveal membership to other members of the same scope. Viewing rules must be enforced by the router.
- `RankedMember` keeps `user_id` for server-side lookups only and must never be serialised to clients.

---

## 7. Remaining approvals and known limitations

| Item | Needs | Approval |
|---|---|---|
| G-4 leaderboard endpoint + schema + UI | Router, schema, `main.py` registration, frontend | ⚠️ Ankush; Arsh (`main.py`); Shoeb (UI) |
| G-1 ledger as the points source | Table + dual write + backfill | ⚠️ Ankush + Nagin |
| Snapshot query | Shared `repository.py` (after CR-15) | ⚠️ Nagin + Arsh |
| College/company membership source | New service and data model | ⚠️ Ankush + owners to be decided |
| Ranking policy (competition, `user_id` tie-break) | Product confirmation | ⚠️ Ankush |
| Public display names / opt-out | Product + schema | ⚠️ Ankush + Nagin |
| Weekly/monthly windows | Ledger timestamps + timezone (G-3) | ⚠️ Ankush |

**Known limitations:**
- The tie-break by `user_id` is fair but arbitrary; "earliest to reach the total" would need ledger timestamps.
- Snapshots are computed in memory. Fine for hackathon scale; large boards would need SQL ranking (`RANK() OVER (ORDER BY points DESC, user_id)`) with identical semantics.
- No windows, no caching, no membership verification, no anti-abuse beyond trusting only ledger totals.
- Not connected to any route, repository, ledger or frontend.
