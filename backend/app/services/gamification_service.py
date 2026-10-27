"""
Gamification Domain Service
Owned by: Ankush (Gamification, Challenges & Competitions)

Pure, side-effect-free reward rules for PragyaX (Phase 2 foundation).
Nothing in the application calls this module yet: wiring it into routers and the
repository is a later, approved step (see docs/GAMIFICATION_DESIGN.md).

Rules for this module:
- Standard library only. No SQL, no database connections, no FastAPI, no I/O.
- Values that decide rewards (answer keys, point values, scores) must come from
  trusted server-side data, never from a request payload.
- Assessment *scores* are computed elsewhere; this module only consumes them.
  Points (XP) and assessment scores are separate quantities.
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


# ==========================
# 1. ERRORS
# ==========================

class GamificationError(ValueError):
    """Base class for rejected gamification inputs."""


class InvalidSubmissionError(GamificationError):
    """A learner-supplied value is invalid. Maps to HTTP 400 once wired."""


class InvalidTrustedInputError(GamificationError):
    """Server-side data (answer key, reward config, score, rule) is invalid.
    Signals a bug or bad seed data. Maps to HTTP 500 once wired."""


# ==========================
# 2. CONSTANTS & VALIDATION HELPERS
# ==========================

VALID_OPTIONS = ("A", "B", "C", "D")

# database/schema.sql declares user_badges.badge_key as VARCHAR(64).
MAX_BADGE_KEY_LENGTH = 64

_SUBJECT_ID_RE = re.compile(r"[A-Za-z0-9_-]+")      # e.g. subj_python, or a UUID
_RULE_KEY_RE = re.compile(r"[a-z0-9_]+")             # e.g. high_score
_EVENT_KEY_PART_RE = re.compile(r"[A-Za-z0-9_.-]+")  # no ':' so event keys stay unambiguous
_BADGE_KEY_RE = re.compile(r"[A-Za-z0-9_.-]+")       # legacy 'py_master' and 'assessment.<subject>.<rule>'


def _normalize_option(value: object, field: str, error: type[GamificationError]) -> str:
    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized in VALID_OPTIONS:
            return normalized
    raise error(f"{field} must be one of {', '.join(VALID_OPTIONS)}; got {value!r:.40}")


def _require_int(value: object, field: str, *, minimum: int) -> None:
    # bool is a subclass of int; True must not count as 1 point or 1 correct answer.
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise InvalidTrustedInputError(f"{field} must be an integer >= {minimum}; got {value!r:.40}")


def _require_subject_id(subject_id: object) -> None:
    if not isinstance(subject_id, str) or not _SUBJECT_ID_RE.fullmatch(subject_id):
        raise InvalidTrustedInputError(f"subject_id must match [A-Za-z0-9_-]+; got {subject_id!r:.40}")


def _require_rule_key(rule_key: object) -> None:
    if not isinstance(rule_key, str) or not _RULE_KEY_RE.fullmatch(rule_key):
        raise InvalidTrustedInputError(f"rule key must match [a-z0-9_]+; got {rule_key!r:.40}")


def _require_badge_key(value: object, field: str) -> None:
    if (
        not isinstance(value, str)
        or not _BADGE_KEY_RE.fullmatch(value)
        or len(value) > MAX_BADGE_KEY_LENGTH
    ):
        raise InvalidTrustedInputError(
            f"{field} must match [A-Za-z0-9_.-]+ and be at most {MAX_BADGE_KEY_LENGTH} characters; got {value!r:.40}"
        )


def _fill(template: str, subject_title: str, min_percent: int) -> str:
    # Insert the subject title last so text inside it is never treated as a placeholder.
    return template.replace("{min_percent}", str(min_percent)).replace("{subject}", subject_title)


# ==========================
# 3. DOMAIN MODELS
# ==========================

class RewardReason(StrEnum):
    CORRECT_ANSWER = "correct_answer"
    INCORRECT_ANSWER = "incorrect_answer"
    ALREADY_COMPLETED = "already_completed"


class RewardStatus(StrEnum):
    AWARDED = "awarded"
    REVOKED = "revoked"


@dataclass(frozen=True)
class AchievementAward:
    """An achievement a learner is eligible for. Fields mirror user_badges / BadgeItem.
    Eligibility is not the award itself: the user_badges UNIQUE(user_id, badge_key)
    constraint decides whether a row is actually inserted."""
    badge_key: str
    title: str
    description: str
    icon: str


@dataclass(frozen=True)
class ChallengeConfig:
    """Trusted challenge data. Build it from the daily_challenges row, never from a request."""
    challenge_id: str
    correct_option: str
    points: int

    def __post_init__(self):
        if not isinstance(self.challenge_id, str) or not self.challenge_id.strip():
            raise InvalidTrustedInputError("challenge_id must be a non-empty string")
        _normalize_option(self.correct_option, "correct_option", InvalidTrustedInputError)
        _require_int(self.points, "points", minimum=0)


@dataclass(frozen=True)
class ChallengeRewardDecision:
    """What a challenge submission earns. Pure data: persisting it is the caller's job."""
    challenge_id: str
    is_correct: bool
    points_awarded: int
    reason: RewardReason
    achievements: tuple[AchievementAward, ...] = ()

    @property
    def is_repeat_submission(self) -> bool:
        return self.reason is RewardReason.ALREADY_COMPLETED


@dataclass(frozen=True)
class AssessmentAchievementRule:
    """Eligible when score / total >= min_percent. `{subject}` and `{min_percent}`
    in title/description are filled in per subject."""
    key: str
    min_percent: int
    title: str
    description: str
    icon: str

    def __post_init__(self):
        _require_rule_key(self.key)
        _require_int(self.min_percent, "min_percent", minimum=0)
        if self.min_percent > 100:
            raise InvalidTrustedInputError(f"min_percent must be at most 100; got {self.min_percent}")
        for field in ("title", "description", "icon"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise InvalidTrustedInputError(f"rule {field} must be a non-empty string")


@dataclass(frozen=True)
class RewardRecord:
    """One already-persisted reward event (a ledger row).
    Deliberately not validated on construction: aggregate_points() skips bad rows
    and reports them, instead of failing a whole dashboard on one corrupt row."""
    event_key: str
    points: int
    status: str = RewardStatus.AWARDED


@dataclass(frozen=True)
class PointsSummary:
    total_points: int
    counted_records: int
    invalid_records: int
    not_awarded_records: int
    duplicate_records: int


# V1 parity: V1 awards 'py_master' when score >= 4 (repository.py save_assessment_attempt),
# i.e. 80% of the 5-question assessment. Here the threshold is a percentage of `total` and
# the badge key is subject-specific. Adding tiers is a product change needing approval.
ASSESSMENT_ACHIEVEMENT_RULES = (
    AssessmentAchievementRule(
        key="high_score",
        min_percent=80,
        title="{subject} Virtuoso",
        description="Scored {min_percent}%+ on the {subject} assessment",
        icon="award",
    ),
)

# V1 parity: identical to the badge V1 inserts in repository.py submit_daily_challenge,
# so already-persisted 'daily_striker' badges keep deduplicating against new awards.
DAILY_CHALLENGE_ACHIEVEMENT = AchievementAward(
    badge_key="daily_striker",
    title="Daily Code Breaker",
    description="Solved today's Python code snippet challenge",
    icon="zap",
)


# ==========================
# 4. DAILY CHALLENGE RULES
# ==========================

def is_challenge_answer_correct(selected_option: str, correct_option: str) -> bool:
    """Compare a learner's option with the trusted answer key (case/whitespace-insensitive,
    same normalisation as V1). Invalid learner input -> InvalidSubmissionError;
    a corrupt answer key -> InvalidTrustedInputError."""
    selected = _normalize_option(selected_option, "selected_option", InvalidSubmissionError)
    correct = _normalize_option(correct_option, "correct_option", InvalidTrustedInputError)
    return selected == correct


def compute_challenge_reward(
    challenge: ChallengeConfig, selected_option: str, *, already_completed: bool
) -> ChallengeRewardDecision:
    """Decide the reward for one submission.

    Points always come from the trusted ChallengeConfig; there is deliberately no
    parameter through which a caller could pass a reward amount. A repeat submission
    (already_completed=True) earns zero additional points and no achievements.
    """
    if not isinstance(challenge, ChallengeConfig):
        raise InvalidTrustedInputError("challenge must be a ChallengeConfig built from trusted data")
    if not isinstance(already_completed, bool):
        raise InvalidTrustedInputError("already_completed must be a bool")

    is_correct = is_challenge_answer_correct(selected_option, challenge.correct_option)
    if already_completed:
        return ChallengeRewardDecision(challenge.challenge_id, is_correct, 0, RewardReason.ALREADY_COMPLETED)
    if not is_correct:
        return ChallengeRewardDecision(challenge.challenge_id, False, 0, RewardReason.INCORRECT_ANSWER)
    return ChallengeRewardDecision(
        challenge.challenge_id, True, challenge.points, RewardReason.CORRECT_ANSWER, (DAILY_CHALLENGE_ACHIEVEMENT,)
    )


# ==========================
# 5. ASSESSMENT ACHIEVEMENTS
# ==========================

def assessment_badge_key(subject_id: str, rule_key: str) -> str:
    """Stable, subject-specific achievement id, e.g. 'assessment.subj_python.high_score'.
    Derived from the immutable subject id (never the display title), so renaming a
    subject never changes or duplicates a learner's badges."""
    _require_subject_id(subject_id)
    _require_rule_key(rule_key)
    key = f"assessment.{subject_id}.{rule_key}"
    if len(key) > MAX_BADGE_KEY_LENGTH:
        raise InvalidTrustedInputError(f"badge key exceeds {MAX_BADGE_KEY_LENGTH} characters: {key!r}")
    return key


def eligible_assessment_achievements(
    score: int,
    total: int,
    subject_id: str,
    subject_title: str,
    rules: Sequence[AssessmentAchievementRule] = ASSESSMENT_ACHIEVEMENT_RULES,
) -> tuple[AchievementAward, ...]:
    """Achievements earned by a graded attempt, in rule order.

    `score`/`total` are the backend-computed assessment result (number correct out of
    number of questions). This function never computes a score and never awards points.
    All inputs are validated before any rule is evaluated, so invalid data fails the
    same way whatever the score.
    """
    _require_int(total, "total", minimum=1)
    _require_int(score, "score", minimum=0)
    if score > total:
        raise InvalidTrustedInputError(f"score {score} exceeds total {total}")
    _require_subject_id(subject_id)
    if not isinstance(subject_title, str) or not subject_title.strip():
        raise InvalidTrustedInputError("subject_title must be a non-empty string")

    seen_keys = set()
    keyed_rules = []
    for rule in rules:
        if not isinstance(rule, AssessmentAchievementRule):
            raise InvalidTrustedInputError("rules must contain AssessmentAchievementRule items")
        if rule.key in seen_keys:
            raise InvalidTrustedInputError(f"duplicate rule key {rule.key!r}")
        seen_keys.add(rule.key)
        keyed_rules.append((rule, assessment_badge_key(subject_id, rule.key)))

    title = subject_title.strip()
    return tuple(
        AchievementAward(
            badge_key=badge_key,
            title=_fill(rule.title, title, rule.min_percent),
            description=_fill(rule.description, title, rule.min_percent),
            icon=rule.icon,
        )
        for rule, badge_key in keyed_rules
        # Integer arithmetic: no float rounding at the threshold.
        if score * 100 >= rule.min_percent * total
    )


# ==========================
# 6. LEGACY BADGE COMPATIBILITY
# ==========================

# Current badge key -> legacy (V1) keys that represent the same achievement.
# Deliberately limited to the Python high-score badge: V1 awarded 'py_master' (score >= 4)
# only on the Python assessment, the only active subject in V1, so 'py_master' must never
# satisfy another subject's high-score badge. Read-only (MappingProxyType over tuples).
LEGACY_BADGE_EQUIVALENTS = MappingProxyType({
    assessment_badge_key("subj_python", "high_score"): ("py_master",),
})


def _equivalent_badge_keys(badge_key: str) -> frozenset[str]:
    """The key plus every key equivalent to it (itself only, for keys outside the mapping)."""
    for current, legacy in LEGACY_BADGE_EQUIVALENTS.items():
        if badge_key == current or badge_key in legacy:
            return frozenset((current, *legacy))
    return frozenset((badge_key,))


def filter_new_achievements(
    awards: Iterable[AchievementAward], held_badge_keys: Iterable[str]
) -> tuple[AchievementAward, ...]:
    """Keep only the awards the learner has not already earned, in input order.

    An award is dropped if its badge_key, or any key equivalent to it under
    LEGACY_BADGE_EQUIVALENTS, is already held, or was already kept earlier in this
    batch. Keys outside the mapping (including unknown legacy keys) match only
    themselves. Inputs are read once and never mutated. All inputs are validated
    before filtering, so malformed data fails the same way whatever is held.
    """
    for name, value in (("awards", awards), ("held_badge_keys", held_badge_keys)):
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise InvalidTrustedInputError(f"{name} must be an iterable collection, not {type(value).__name__}")

    held_keys = tuple(held_badge_keys)
    for key in held_keys:
        _require_badge_key(key, "held badge key")
    candidates = tuple(awards)
    for award in candidates:
        if not isinstance(award, AchievementAward):
            raise InvalidTrustedInputError("awards must contain AchievementAward items")
        _require_badge_key(award.badge_key, "award badge_key")

    claimed = set()  # local working set; the caller's collections are never touched
    for key in held_keys:
        claimed |= _equivalent_badge_keys(key)

    kept = []
    for award in candidates:
        group = _equivalent_badge_keys(award.badge_key)
        if group & claimed:
            continue
        claimed |= group
        kept.append(award)
    return tuple(kept)


# ==========================
# 7. POINTS (XP) AGGREGATION
# ==========================

def reward_event_key(user_id: str, source_type: str, source_id: str) -> str:
    """Idempotency key for one reward event, e.g. 'daily_challenge:chal_today_py:usr_ab12'.
    A persistent ledger should enforce UNIQUE(event_key) so retries never double-award."""
    for name, value in (("user_id", user_id), ("source_type", source_type), ("source_id", source_id)):
        if not isinstance(value, str) or not _EVENT_KEY_PART_RE.fullmatch(value):
            raise InvalidTrustedInputError(f"{name} must match [A-Za-z0-9_.-]+; got {value!r:.40}")
    return f"{source_type}:{source_id}:{user_id}"


def aggregate_points(records: Iterable[RewardRecord]) -> PointsSummary:
    """Sum already-awarded reward records safely.

    A record is counted only if it is a RewardRecord with a non-empty event_key,
    integer points >= 0 (bools rejected) and status 'awarded'. Each event_key
    contributes at most once: the first valid awarded record wins and later ones are
    reported as duplicates. Invalid or non-awarded rows never claim an event key.
    """
    total = counted = invalid = not_awarded = duplicates = 0
    counted_keys = set()
    for record in records:
        if not _is_valid_record(record):
            invalid += 1
        elif record.status != RewardStatus.AWARDED:
            not_awarded += 1
        elif record.event_key in counted_keys:
            duplicates += 1
        else:
            counted_keys.add(record.event_key)
            total += record.points
            counted += 1
    return PointsSummary(total, counted, invalid, not_awarded, duplicates)


def _is_valid_record(record: object) -> bool:
    return (
        isinstance(record, RewardRecord)
        and isinstance(record.event_key, str)
        and record.event_key.strip() != ""
        and isinstance(record.points, int)
        and not isinstance(record.points, bool)
        and record.points >= 0
    )
