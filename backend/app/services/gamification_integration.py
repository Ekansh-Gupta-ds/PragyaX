"""
Gamification Integration Adapter (G-6 foundation)
Owned by: Ankush (Gamification, Challenges & Competitions)

Orchestrates the pure gamification modules against a PROVISIONAL repository
protocol. Nothing in the application uses this module, and no real repository
implements the protocol yet: its method signatures have not been agreed with the
database/backend owners (Nagin, Arsh) and must not be read as existing DB functions.
See docs/GAMIFICATION_ADAPTER.md.

Guarantees split:
- This adapter decides *what* to write, from trusted server data only (the stored
  challenge row, the authenticated user id). Learners supply only selected_option.
- Atomicity, duplicate protection and concurrency safety are the repository's job
  (single transaction, UNIQUE constraints, INSERT ... ON CONFLICT DO NOTHING).
  The adapter holds no locks and does not claim exactly-once awards by itself.
- No clock, randomness, SQL or I/O here: event ids come from an injected callable.
"""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from .gamification_service import (
    AchievementAward,
    ChallengeConfig,
    InvalidSubmissionError,
    InvalidTrustedInputError,
    PointsSummary,
    RewardRecord,
    _normalize_option,
    aggregate_points,
    compute_challenge_reward,
    eligible_assessment_achievements,
    filter_new_achievements,
    reward_event_key,
)
from .points_ledger_domain import (
    DAILY_CHALLENGE_SOURCE,
    MAX_USER_ID_LENGTH,
    LedgerEvent,
    LedgerOrigin,
    ZeroPointPolicy,
    decide_challenge_ledger_award,
)

# Exact V1 error texts (routers/challenges.py and repository.py) so a future router keeps its contract.
V1_INVALID_OPTION_DETAIL = "selected_option must be A, B, C, or D."
V1_NOT_FOUND_DETAIL = "Challenge not found"
V1_ALREADY_COMPLETED_DETAIL = "Challenge already completed by this user today"


# ==========================
# 1. PROVISIONAL REPOSITORY PROTOCOL
# ==========================

class WriteResult(StrEnum):
    INSERTED = "inserted"
    ALREADY_COMPLETED = "already_completed"   # submission UNIQUE(user_id, challenge_id) conflict


@dataclass(frozen=True)
class ChallengeWrite:
    """Everything one challenge submission persists, decided before the transaction starts."""
    user_id: str
    challenge_id: str
    selected_option: str                      # normalised A-D
    is_correct: bool
    points_awarded: int
    ledger_event: LedgerEvent | None          # None: not a reward, or zero points skipped by policy
    badges: tuple[AchievementAward, ...]      # already filtered against held/equivalent badges


@runtime_checkable
class GamificationRepository(Protocol):
    """PROPOSED interface only. Not implemented by backend/app/database/repository.py."""

    # Pure reads
    def get_challenge(self, challenge_id: str) -> Mapping[str, object] | None:
        """Trusted daily_challenges row: keys 'id', 'correct_option', 'points', 'explanation'."""

    def has_completed_challenge(self, user_id: str, challenge_id: str) -> bool:
        """Fast-path check only; correctness must not depend on it."""

    def get_badge_keys(self, user_id: str) -> frozenset[str]:
        """All badge_key values the user holds (legacy keys included)."""

    # Transactional write (one transaction: submission + ledger + badges, all or nothing)
    def record_challenge_outcome(self, write: ChallengeWrite) -> WriteResult:
        """Insert the submission with ON CONFLICT DO NOTHING; on conflict write nothing else and
        return ALREADY_COMPLETED. Otherwise insert the ledger event (idempotent on event_key) and
        each badge (idempotent on (user_id, badge_key)) in the same transaction."""

    # Badge award (one transaction, idempotent per (user_id, badge_key))
    def insert_badges(self, user_id: str, awards: tuple[AchievementAward, ...]) -> tuple[str, ...]:
        """Insert each award with ON CONFLICT DO NOTHING; return the badge_keys actually inserted."""

    # Points total query
    def get_reward_records(self, user_id: str) -> Iterable[RewardRecord]:
        """The user's ledger rows as RewardRecords (revoked rows marked, once D-1 is decided)."""


# ==========================
# 2. OUTCOMES
# ==========================

class SubmissionStatus(StrEnum):
    ACCEPTED = "accepted"
    ALREADY_COMPLETED = "already_completed"
    INVALID_OPTION = "invalid_option"
    CHALLENGE_NOT_FOUND = "challenge_not_found"


_V1_ERROR_DETAIL = {
    SubmissionStatus.ALREADY_COMPLETED: V1_ALREADY_COMPLETED_DETAIL,
    SubmissionStatus.INVALID_OPTION: V1_INVALID_OPTION_DETAIL,
    SubmissionStatus.CHALLENGE_NOT_FOUND: V1_NOT_FOUND_DETAIL,
}


@dataclass(frozen=True)
class ChallengeSubmissionOutcome:
    status: SubmissionStatus
    challenge_id: str
    is_correct: bool = False
    points_awarded: int = 0
    correct_option: str | None = None
    explanation: str | None = None
    badges_awarded: tuple[str, ...] = ()
    ledger_recorded: bool = False

    @property
    def v1_error_detail(self) -> str | None:
        """The exact V1 400 'detail' for a rejected submission; None when accepted."""
        return _V1_ERROR_DETAIL.get(self.status)

    def to_v1_response(self) -> dict:
        """ChallengeResultResponse-shaped dict (same fields as V1) for an accepted submission."""
        if self.status is not SubmissionStatus.ACCEPTED:
            raise ValueError(f"no V1 response body for status {self.status.value!r}; use v1_error_detail")
        return {
            "challenge_id": self.challenge_id,
            "is_correct": self.is_correct,
            "points_awarded": self.points_awarded,
            "correct_option": self.correct_option,
            "explanation": self.explanation,
        }


# ==========================
# 3. ADAPTER
# ==========================

class GamificationIntegration:
    """Dependency-injected orchestrator. The zero-point policy is explicit (D-3 undecided)."""

    def __init__(
        self,
        repository: GamificationRepository,
        *,
        new_event_id: Callable[[], str],
        zero_point_policy: ZeroPointPolicy,
    ):
        if not isinstance(repository, GamificationRepository):
            raise InvalidTrustedInputError("repository must implement GamificationRepository")
        if not callable(new_event_id):
            raise InvalidTrustedInputError("new_event_id must be callable")
        try:
            self._zero_point_policy = ZeroPointPolicy(zero_point_policy)
        except ValueError:
            raise InvalidTrustedInputError(f"unknown zero_point_policy {zero_point_policy!r:.40}") from None
        self._repo = repository
        self._new_event_id = new_event_id

    def submit_daily_challenge(
        self, user_id: str, challenge_id: str, selected_option: object
    ) -> ChallengeSubmissionOutcome:
        """V1-equivalent flow. `user_id` must come from authentication; only
        `selected_option` is learner input. Raises InvalidTrustedInputError for corrupt
        stored data; repository errors propagate unchanged (nothing is swallowed)."""
        _require_user_id(user_id)
        # V1 order: the option is validated before the challenge is looked up.
        try:
            option = _normalize_option(selected_option, "selected_option", InvalidSubmissionError)
        except InvalidSubmissionError:
            return ChallengeSubmissionOutcome(SubmissionStatus.INVALID_OPTION, str(challenge_id))

        row = self._repo.get_challenge(challenge_id) if isinstance(challenge_id, str) else None
        if row is None:
            return ChallengeSubmissionOutcome(SubmissionStatus.CHALLENGE_NOT_FOUND, str(challenge_id))
        try:
            config = ChallengeConfig(row["id"], row["correct_option"], row["points"])   # validates trusted row
            explanation = row["explanation"]
        except (KeyError, TypeError):
            raise InvalidTrustedInputError("stored challenge row is missing required fields") from None
        if not isinstance(explanation, str):
            raise InvalidTrustedInputError("stored explanation must be a string")

        already = self._repo.has_completed_challenge(user_id, config.challenge_id)
        decision = compute_challenge_reward(config, option, already_completed=already)
        if decision.is_repeat_submission:
            return ChallengeSubmissionOutcome(SubmissionStatus.ALREADY_COMPLETED, config.challenge_id)

        ledger = decide_challenge_ledger_award(
            user_id, decision,
            event_id=self._new_event_id(), origin=LedgerOrigin.LIVE, zero_point_policy=self._zero_point_policy,
        )
        badges = filter_new_achievements(decision.achievements, self._repo.get_badge_keys(user_id))
        write = ChallengeWrite(
            user_id=user_id,
            challenge_id=config.challenge_id,
            selected_option=option,
            is_correct=decision.is_correct,
            points_awarded=decision.points_awarded,
            ledger_event=ledger.event,
            badges=badges,
        )
        if self._repo.record_challenge_outcome(write) is WriteResult.ALREADY_COMPLETED:
            # A concurrent request won the submission insert; this one earned nothing.
            return ChallengeSubmissionOutcome(SubmissionStatus.ALREADY_COMPLETED, config.challenge_id)

        return ChallengeSubmissionOutcome(
            status=SubmissionStatus.ACCEPTED,
            challenge_id=config.challenge_id,
            is_correct=decision.is_correct,
            points_awarded=decision.points_awarded,
            correct_option=config.correct_option.strip().upper(),
            explanation=explanation,
            badges_awarded=tuple(b.badge_key for b in badges),
            ledger_recorded=ledger.should_record,
        )

    def award_assessment_badges(
        self, user_id: str, score: int, total: int, subject_id: str, subject_title: str
    ) -> tuple[str, ...]:
        """After a graded attempt is saved: eligible badges minus held/equivalent ones
        (py_master counts as the Python high-score badge). Returns badge_keys inserted."""
        _require_user_id(user_id)
        awards = eligible_assessment_achievements(score, total, subject_id, subject_title)
        new_awards = filter_new_achievements(awards, self._repo.get_badge_keys(user_id))
        if not new_awards:
            return ()
        return tuple(self._repo.insert_badges(user_id, new_awards))

    def get_points_summary(self, user_id: str) -> PointsSummary:
        """Points total from ledger records, with anomalies counted rather than summed."""
        _require_user_id(user_id)
        return aggregate_points(self._repo.get_reward_records(user_id))


def _require_user_id(user_id: object) -> None:
    # Same rules (and 64-char width) as ledger user ids, checked before any repository call.
    reward_event_key(user_id, DAILY_CHALLENGE_SOURCE, DAILY_CHALLENGE_SOURCE)
    if len(user_id) > MAX_USER_ID_LENGTH:
        raise InvalidTrustedInputError(f"user_id exceeds {MAX_USER_ID_LENGTH} characters")
