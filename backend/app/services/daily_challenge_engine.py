"""
Daily Challenge Rotation Engine (G-3 foundation)
Owned by: Ankush (Gamification, Challenges & Competitions)

Pure, deterministic selection of one challenge per subject per calendar date.
Nothing in the application calls this module: V1 still serves its single static
challenge (`SELECT ... LIMIT 1`), and no schema supports rotation yet.
See docs/DAILY_CHALLENGE_ENGINE.md.

Rules for this module:
- Standard library only; no database, FastAPI, clock, randomness or I/O.
  "Today" is always passed in by the caller (see challenge_date_for).
- Rotation is round-robin over the pool sorted by challenge_id:
  index = date.toordinal() % len(pool). It is predictable by design. It is not a
  security control and does not prevent replay; persist the chosen challenge per
  date once integrated, because changing a pool changes the computed schedule.
- Answer keys stay on ChallengeDefinition (server side). Learner-facing output is
  LearnerChallengeView, which has no answer or explanation fields at all.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, tzinfo

# Same owner module; reusing its validators keeps ids, options and points consistent.
from .gamification_service import (
    InvalidTrustedInputError,
    _normalize_option,
    _require_int,
    _require_subject_id,
)

MAX_CHALLENGE_ID_LENGTH = 64            # daily_challenges.id / points_ledger.source_id width
SUPPORTED_QUESTION_TYPES = ("multiple_choice",)

# Same character set as reward_event_key parts, so a challenge id is always a valid ledger source_id.
_CHALLENGE_ID_RE = re.compile(r"[A-Za-z0-9_.-]+")
_ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


# ==========================
# 1. MODELS
# ==========================

@dataclass(frozen=True)
class ChallengeDefinition:
    """Trusted, server-side challenge (mirrors daily_challenges plus a subject_id).
    Holds the answer key; never send this object to a learner."""
    challenge_id: str
    subject_id: str
    title: str
    topic: str
    difficulty: str
    description: str
    code_snippet: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str
    explanation: str
    points: int
    question_type: str = "multiple_choice"

    def __post_init__(self):
        _require_challenge_id(self.challenge_id)
        _require_subject_id(self.subject_id)
        for field in ("title", "topic", "difficulty", "description", "code_snippet",
                      "option_a", "option_b", "option_c", "option_d", "explanation"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise InvalidTrustedInputError(f"{field} must be a non-empty string")
        _normalize_option(self.correct_option, "correct_option", InvalidTrustedInputError)
        _require_int(self.points, "points", minimum=0)
        if self.question_type not in SUPPORTED_QUESTION_TYPES:
            raise InvalidTrustedInputError(f"question_type must be one of {SUPPORTED_QUESTION_TYPES}")


@dataclass(frozen=True)
class ChallengePool:
    """A subject's challenges in canonical order (sorted by challenge_id), so the
    order challenges were supplied in never affects selection."""
    subject_id: str
    challenges: tuple[ChallengeDefinition, ...]

    def __post_init__(self):
        _require_subject_id(self.subject_id)
        if isinstance(self.challenges, (str, bytes)) or not isinstance(self.challenges, Iterable):
            raise InvalidTrustedInputError("challenges must be a collection of ChallengeDefinition")
        items = tuple(self.challenges)
        if not items:
            raise InvalidTrustedInputError(f"challenge pool for {self.subject_id!r} is empty")
        seen = set()
        for challenge in items:
            if not isinstance(challenge, ChallengeDefinition):
                raise InvalidTrustedInputError("challenges must contain ChallengeDefinition items")
            if challenge.subject_id != self.subject_id:
                raise InvalidTrustedInputError(
                    f"challenge {challenge.challenge_id!r} belongs to {challenge.subject_id!r}, not {self.subject_id!r}"
                )
            if challenge.challenge_id in seen:
                raise InvalidTrustedInputError(f"duplicate challenge_id {challenge.challenge_id!r}")
            seen.add(challenge.challenge_id)
        # Frozen dataclass: canonicalise once, at construction.
        object.__setattr__(self, "challenges", tuple(sorted(items, key=lambda c: c.challenge_id)))


@dataclass(frozen=True)
class LearnerChallengeView:
    """What a learner may see before submitting. Has no answer or explanation fields."""
    challenge_id: str
    subject_id: str
    challenge_date: str          # ISO 'YYYY-MM-DD' in the platform timezone
    title: str
    topic: str
    difficulty: str
    description: str
    code_snippet: str
    question_type: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    points: int


# ==========================
# 2. DATES
# ==========================

def parse_challenge_date(value: str) -> date:
    """Strict ISO calendar date 'YYYY-MM-DD' (rejects '20261027', times, invalid days)."""
    if not isinstance(value, str) or not _ISO_DATE_RE.fullmatch(value):
        raise InvalidTrustedInputError(f"challenge date must be 'YYYY-MM-DD'; got {value!r:.40}")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise InvalidTrustedInputError(f"not a real calendar date: {value!r}") from None


def challenge_date_for(instant: datetime, platform_tz: tzinfo) -> date:
    """The challenge date of an instant: its calendar date in the platform timezone.
    The caller supplies both the instant (server clock) and the timezone (decision G-3);
    naive datetimes are rejected because their timezone is unknown."""
    if not isinstance(instant, datetime) or instant.tzinfo is None or instant.utcoffset() is None:
        raise InvalidTrustedInputError("instant must be a timezone-aware datetime")
    if not isinstance(platform_tz, tzinfo):
        raise InvalidTrustedInputError("platform_tz must be a tzinfo")
    return instant.astimezone(platform_tz).date()


# ==========================
# 3. SELECTION
# ==========================

def select_daily_challenge(pool: ChallengePool, challenge_date: date) -> ChallengeDefinition:
    """Deterministic round-robin: the same pool and date always give the same challenge;
    consecutive dates step through the pool in challenge_id order."""
    if not isinstance(pool, ChallengePool):
        raise InvalidTrustedInputError("pool must be a ChallengePool")
    _require_date(challenge_date)
    return pool.challenges[challenge_date.toordinal() % len(pool.challenges)]


def select_daily_challenges(
    pools: Iterable[ChallengePool], challenge_date: date
) -> tuple[ChallengeDefinition, ...]:
    """One challenge per subject for the date, ordered by subject_id. Each subject is
    selected from its own pool only; two pools for one subject are rejected."""
    if isinstance(pools, (str, bytes)) or not isinstance(pools, Iterable):
        raise InvalidTrustedInputError("pools must be a collection of ChallengePool")
    _require_date(challenge_date)
    by_subject = {}
    for pool in pools:
        if not isinstance(pool, ChallengePool):
            raise InvalidTrustedInputError("pools must contain ChallengePool items")
        if pool.subject_id in by_subject:
            raise InvalidTrustedInputError(f"more than one pool for subject {pool.subject_id!r}")
        by_subject[pool.subject_id] = pool
    return tuple(select_daily_challenge(by_subject[s], challenge_date) for s in sorted(by_subject))


def to_learner_view(challenge: ChallengeDefinition, challenge_date: date) -> LearnerChallengeView:
    """Learner-facing projection. Leaves `challenge` untouched and drops the answer key and explanation."""
    if not isinstance(challenge, ChallengeDefinition):
        raise InvalidTrustedInputError("challenge must be a ChallengeDefinition")
    _require_date(challenge_date)
    return LearnerChallengeView(
        challenge_id=challenge.challenge_id,
        subject_id=challenge.subject_id,
        challenge_date=challenge_date.isoformat(),
        title=challenge.title,
        topic=challenge.topic,
        difficulty=challenge.difficulty,
        description=challenge.description,
        code_snippet=challenge.code_snippet,
        question_type=challenge.question_type,
        option_a=challenge.option_a,
        option_b=challenge.option_b,
        option_c=challenge.option_c,
        option_d=challenge.option_d,
        points=challenge.points,
    )


# ==========================
# 4. HELPERS
# ==========================

def _require_challenge_id(value: object) -> None:
    if (
        not isinstance(value, str)
        or not _CHALLENGE_ID_RE.fullmatch(value)
        or len(value) > MAX_CHALLENGE_ID_LENGTH
    ):
        raise InvalidTrustedInputError(
            f"challenge_id must match [A-Za-z0-9_.-]+ (max {MAX_CHALLENGE_ID_LENGTH}); got {value!r:.40}"
        )


def _require_date(value: object) -> None:
    # datetime is a subclass of date; reject it so a time/timezone can't sneak in unconverted.
    if not isinstance(value, date) or isinstance(value, datetime):
        raise InvalidTrustedInputError("challenge_date must be a datetime.date (use parse_challenge_date / challenge_date_for)")
