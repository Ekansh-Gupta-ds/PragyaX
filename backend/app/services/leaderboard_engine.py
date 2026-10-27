"""
Leaderboard Ranking Engine (G-4 foundation)
Owned by: Ankush (Gamification, Challenges & Competitions)

Pure, deterministic ranking of trusted point totals. Nothing in the application calls this
module; there is no leaderboard route, table or query. See docs/LEADERBOARD_ENGINE.md.

Rules for this module:
- Standard library only; no database, FastAPI, clock, randomness or I/O.
- Totals are trusted server data: eventually aggregate_points() over the verified ledger.
  Nothing here accepts client-supplied ranks or points.
- College/company membership is supplied by a future trusted service; this module does not
  verify membership, it only applies the membership it is given.
- Ranking: total_points descending, ties broken by user_id ascending (Python str ordering,
  i.e. Unicode code points). Displayed ranks use competition ranking (1, 1, 3).
- Learner-facing rows contain rank, display name, points and an is_viewer flag only:
  no user ids, emails, tokens or other database fields.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

# Same owner modules; reuse their validators and limits so identifiers stay consistent.
from .gamification_service import InvalidSubmissionError, InvalidTrustedInputError, _require_int
from .points_ledger_domain import MAX_USER_ID_LENGTH

MAX_DISPLAY_NAME_LENGTH = 100        # schemas/auth.py RegisterRequest.name max_length
MAX_SCOPE_ID_LENGTH = 64
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

_USER_ID_RE = re.compile(r"[A-Za-z0-9_.-]+")     # ledger user_id rule (reward_event_key parts)
_SCOPE_ID_RE = re.compile(r"[A-Za-z0-9_-]+")


# ==========================
# 1. MODELS
# ==========================

class ScopeType(StrEnum):
    PLATFORM = "platform"
    COLLEGE = "college"
    COMPANY = "company"


@dataclass(frozen=True)
class LeaderboardScope:
    """platform has no scope_id; college/company require one (e.g. a college id)."""
    scope_type: ScopeType
    scope_id: str | None = None

    def __post_init__(self):
        try:
            object.__setattr__(self, "scope_type", ScopeType(self.scope_type))
        except ValueError:
            raise InvalidTrustedInputError(f"unknown scope_type {self.scope_type!r:.40}") from None
        if self.scope_type is ScopeType.PLATFORM:
            if self.scope_id is not None:
                raise InvalidTrustedInputError("platform scope takes no scope_id")
        elif (
            not isinstance(self.scope_id, str)
            or not _SCOPE_ID_RE.fullmatch(self.scope_id)
            or len(self.scope_id) > MAX_SCOPE_ID_LENGTH
        ):
            raise InvalidTrustedInputError(f"{self.scope_type.value} scope needs a valid scope_id; got {self.scope_id!r:.40}")

    @property
    def key(self) -> str:
        """Stable identifier, e.g. 'platform' or 'college:clg_iitd'."""
        return self.scope_type.value if self.scope_id is None else f"{self.scope_type.value}:{self.scope_id}"


@dataclass(frozen=True)
class LeaderboardMember:
    """Trusted input: identity from the users table, total from the verified ledger."""
    user_id: str
    display_name: str
    total_points: int

    def __post_init__(self):
        _require_user_id(self.user_id)
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise InvalidTrustedInputError("display_name must be a non-empty string")
        if len(self.display_name.strip()) > MAX_DISPLAY_NAME_LENGTH:
            raise InvalidTrustedInputError(f"display_name exceeds {MAX_DISPLAY_NAME_LENGTH} characters")
        _require_int(self.total_points, "total_points", minimum=0)


@dataclass(frozen=True)
class ScopeMembership:
    """Trusted membership list for a college/company scope, supplied by a future service."""
    scope: LeaderboardScope
    user_ids: frozenset[str]

    def __post_init__(self):
        if not isinstance(self.scope, LeaderboardScope):
            raise InvalidTrustedInputError("scope must be a LeaderboardScope")
        if self.scope.scope_type is ScopeType.PLATFORM:
            raise InvalidTrustedInputError("platform scope has no membership list")
        if isinstance(self.user_ids, (str, bytes)) or not isinstance(self.user_ids, Iterable):
            raise InvalidTrustedInputError("user_ids must be a collection of user ids")
        ids = frozenset(self.user_ids)
        for user_id in ids:
            _require_user_id(user_id)
        object.__setattr__(self, "user_ids", ids)


@dataclass(frozen=True)
class RankedMember:
    """Server-side ranked row (keeps user_id for lookups; never send it to learners)."""
    rank: int
    position: int            # 1-based place in the ordering; unique even when ranks tie
    user_id: str
    display_name: str
    total_points: int


@dataclass(frozen=True)
class Leaderboard:
    scope: LeaderboardScope
    entries: tuple[RankedMember, ...]

    @property
    def total_participants(self) -> int:
        return len(self.entries)


@dataclass(frozen=True)
class LeaderboardPage:
    scope: LeaderboardScope
    offset: int
    limit: int
    total_participants: int
    entries: tuple[RankedMember, ...]


@dataclass(frozen=True)
class LeaderboardRow:
    """Learner-safe projection: no user ids, emails, tokens or database fields."""
    rank: int
    display_name: str
    total_points: int
    is_viewer: bool


# ==========================
# 2. RANKING
# ==========================

def rank_members(members: Iterable[LeaderboardMember]) -> tuple[RankedMember, ...]:
    """Order by total_points descending, then user_id ascending; competition ranks (1, 1, 3)."""
    if isinstance(members, (str, bytes)) or not isinstance(members, Iterable):
        raise InvalidTrustedInputError("members must be a collection of LeaderboardMember")
    items = tuple(members)
    seen = set()
    for member in items:
        if not isinstance(member, LeaderboardMember):
            raise InvalidTrustedInputError("members must contain LeaderboardMember items")
        if member.user_id in seen:
            raise InvalidTrustedInputError(f"duplicate user_id {member.user_id!r} in leaderboard snapshot")
        seen.add(member.user_id)

    ordered = sorted(items, key=lambda m: (-m.total_points, m.user_id))
    ranked = []
    for position, member in enumerate(ordered, start=1):
        tied_with_previous = ranked and ranked[-1].total_points == member.total_points
        rank = ranked[-1].rank if tied_with_previous else position
        ranked.append(RankedMember(rank, position, member.user_id, member.display_name.strip(), member.total_points))
    return tuple(ranked)


def build_leaderboard(
    scope: LeaderboardScope,
    members: Iterable[LeaderboardMember],
    membership: ScopeMembership | None = None,
) -> Leaderboard:
    """Rank `members` for `scope`. Platform: everyone given, membership must be None.
    College/company: membership is required and only its members are ranked; others are
    left out (not an error), because the member list may come from a global query."""
    if not isinstance(scope, LeaderboardScope):
        raise InvalidTrustedInputError("scope must be a LeaderboardScope")
    if scope.scope_type is ScopeType.PLATFORM:
        if membership is not None:
            raise InvalidTrustedInputError("platform leaderboard takes no membership")
        return Leaderboard(scope, rank_members(members))
    if not isinstance(membership, ScopeMembership) or membership.scope != scope:
        raise InvalidTrustedInputError(f"{scope.key} leaderboard needs the ScopeMembership for that scope")
    if isinstance(members, (str, bytes)) or not isinstance(members, Iterable):
        raise InvalidTrustedInputError("members must be a collection of LeaderboardMember")
    items = tuple(members)
    rank_members(items)                   # validate every member (types, duplicates) before filtering
    return Leaderboard(scope, rank_members(m for m in items if m.user_id in membership.user_ids))


# ==========================
# 3. PAGINATION AND PROJECTIONS
# ==========================

def paginate(leaderboard: Leaderboard, *, offset: int = 0, limit: int = DEFAULT_PAGE_SIZE) -> LeaderboardPage:
    """A slice of the ranking. Ranks are those of the full leaderboard, never renumbered.
    offset/limit are request values: invalid ones raise InvalidSubmissionError (HTTP 400)."""
    if not isinstance(leaderboard, Leaderboard):
        raise InvalidTrustedInputError("leaderboard must be a Leaderboard")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise InvalidSubmissionError(f"offset must be an integer >= 0; got {offset!r:.40}")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_PAGE_SIZE:
        raise InvalidSubmissionError(f"limit must be an integer from 1 to {MAX_PAGE_SIZE}; got {limit!r:.40}")
    return LeaderboardPage(
        leaderboard.scope, offset, limit, leaderboard.total_participants,
        leaderboard.entries[offset:offset + limit],
    )


def top_n(leaderboard: Leaderboard, n: int) -> LeaderboardPage:
    return paginate(leaderboard, offset=0, limit=n)


def viewer_standing(leaderboard: Leaderboard, viewer_user_id: str) -> LeaderboardRow | None:
    """The viewer's own row (e.g. for 'me' below a page), or None if not on this leaderboard."""
    _require_user_id(viewer_user_id)
    for entry in leaderboard.entries:
        if entry.user_id == viewer_user_id:
            return LeaderboardRow(entry.rank, entry.display_name, entry.total_points, True)
    return None


def to_learner_rows(page: LeaderboardPage, viewer_user_id: str | None = None) -> tuple[LeaderboardRow, ...]:
    """Learner-safe rows for a page; is_viewer marks the authenticated viewer's own row."""
    if not isinstance(page, LeaderboardPage):
        raise InvalidTrustedInputError("page must be a LeaderboardPage")
    if viewer_user_id is not None:
        _require_user_id(viewer_user_id)
    return tuple(
        LeaderboardRow(e.rank, e.display_name, e.total_points, e.user_id == viewer_user_id)
        for e in page.entries
    )


def _require_user_id(value: object) -> None:
    if not isinstance(value, str) or not _USER_ID_RE.fullmatch(value) or len(value) > MAX_USER_ID_LENGTH:
        raise InvalidTrustedInputError(
            f"user_id must match [A-Za-z0-9_.-]+ (max {MAX_USER_ID_LENGTH}); got {value!r:.40}"
        )
