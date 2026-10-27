"""
Student 1v1 Battle Engine (domain only)
Owned by: Ankush (Gamification, Challenges & Competitions)

Pure, deterministic rules for a two-player quiz battle. Nothing in the application calls this
module: there is no battle route, table, matchmaking, timer or real-time channel.
See docs/BATTLE_ENGINE.md.

Rules for this module:
- Standard library only; no database, FastAPI, clock, randomness, network or I/O.
- Every function takes a BattleState and returns a NEW BattleState; states are immutable.
- Participants are authenticated server identities. Learners supply only answer selections.
- Scores are counts of correct answers against server-held answer keys. They are battle
  scores, not points/XP: nothing here touches the ledger or leaderboards.
- Equal correct counts are a tie. There is deliberately no speed tiebreaker.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import StrEnum

# Same owner modules: reuse their error types, option normalisation and user-id rules.
from .gamification_service import (
    GamificationError,
    InvalidSubmissionError,
    InvalidTrustedInputError,
    _normalize_option,
)
from .leaderboard_engine import _require_user_id

MAX_BATTLE_QUESTIONS = 20
MAX_ID_LENGTH = 64
_ID_RE = re.compile(r"[A-Za-z0-9_.-]+")


class UnauthorizedParticipantError(GamificationError):
    """The acting user is not one of the battle's two participants. Maps to HTTP 403."""


class InvalidBattleTransitionError(GamificationError):
    """The action is not allowed in the battle's current status. Maps to HTTP 409."""


# ==========================
# 1. MODELS
# ==========================

class BattleStatus(StrEnum):
    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class BattleOutcome(StrEnum):
    WIN = "win"
    TIE = "tie"


@dataclass(frozen=True)
class BattleParticipant:
    user_id: str
    display_name: str

    def __post_init__(self):
        _require_user_id(self.user_id)
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise InvalidTrustedInputError("display_name must be a non-empty string")


@dataclass(frozen=True)
class BattleQuestion:
    """Trusted, server-side question with its answer key. Never send to a learner as-is."""
    question_id: str
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str
    explanation: str
    topic: str

    def __post_init__(self):
        _require_id(self.question_id, "question_id")
        for field in ("question_text", "option_a", "option_b", "option_c", "option_d", "explanation", "topic"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise InvalidTrustedInputError(f"{field} must be a non-empty string")
        object.__setattr__(
            self, "correct_option", _normalize_option(self.correct_option, "correct_option", InvalidTrustedInputError)
        )


@dataclass(frozen=True)
class LearnerBattleQuestion:
    """What a participant sees while the battle is open: no answer key, no explanation."""
    position: int
    question_id: str
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    topic: str


@dataclass(frozen=True)
class BattleConfig:
    """One shared, fixed question set. require_all_answers=False lets a participant skip
    questions (skipped = incorrect); True rejects incomplete answer sheets."""
    battle_id: str
    questions: tuple[BattleQuestion, ...]
    require_all_answers: bool = True

    def __post_init__(self):
        _require_id(self.battle_id, "battle_id")
        if isinstance(self.questions, (str, bytes)) or not isinstance(self.questions, Iterable):
            raise InvalidTrustedInputError("questions must be a collection of BattleQuestion")
        questions = tuple(self.questions)
        if not 1 <= len(questions) <= MAX_BATTLE_QUESTIONS:
            raise InvalidTrustedInputError(f"a battle needs 1 to {MAX_BATTLE_QUESTIONS} questions")
        seen = set()
        for q in questions:
            if not isinstance(q, BattleQuestion):
                raise InvalidTrustedInputError("questions must contain BattleQuestion items")
            if q.question_id in seen:
                raise InvalidTrustedInputError(f"duplicate question_id {q.question_id!r}")
            seen.add(q.question_id)
        if not isinstance(self.require_all_answers, bool):
            raise InvalidTrustedInputError("require_all_answers must be a bool")
        object.__setattr__(self, "questions", questions)


@dataclass(frozen=True)
class AnswerSubmission:
    """One learner-supplied answer. Validated by submit_answers, not on construction."""
    question_id: str
    selected_option: str


@dataclass(frozen=True)
class AnswerSheet:
    """A participant's recorded answers, normalised and in question order."""
    user_id: str
    answers: tuple[tuple[str, str], ...]     # (question_id, "A".."D")


@dataclass(frozen=True)
class ParticipantScore:
    user_id: str
    correct: int
    answered: int
    total: int


@dataclass(frozen=True)
class BattleResult:
    battle_id: str
    scores: tuple[ParticipantScore, ParticipantScore]   # participant order
    outcome: BattleOutcome
    winner_user_id: str | None                           # None on a tie


@dataclass(frozen=True)
class BattleState:
    config: BattleConfig
    participants: tuple[BattleParticipant, BattleParticipant]
    status: BattleStatus = BattleStatus.CREATED
    answer_sheets: tuple[AnswerSheet, ...] = ()
    result: BattleResult | None = None
    cancel_reason: str | None = None


@dataclass(frozen=True)
class QuestionReview:
    """Post-completion review row: correct answer plus both participants' answers."""
    position: int
    question_id: str
    correct_option: str
    explanation: str
    answers: tuple[tuple[str, str | None], ...]          # (user_id, option or None if skipped)


@dataclass(frozen=True)
class BattleView:
    """Participant-safe snapshot. Opponent answers, answer keys and results appear only
    once the battle is COMPLETED; before that only an 'opponent has submitted' flag."""
    battle_id: str
    status: BattleStatus
    viewer_user_id: str
    opponent_display_name: str
    viewer_submitted: bool
    opponent_submitted: bool
    questions: tuple[LearnerBattleQuestion, ...]
    viewer_answers: tuple[tuple[str, str], ...]
    result: BattleResult | None
    review: tuple[QuestionReview, ...]


# ==========================
# 2. LIFECYCLE
# ==========================

def create_battle(config: BattleConfig, player_one: BattleParticipant, player_two: BattleParticipant) -> BattleState:
    """CREATED battle between exactly two distinct participants sharing one question set."""
    if not isinstance(config, BattleConfig):
        raise InvalidTrustedInputError("config must be a BattleConfig")
    if not isinstance(player_one, BattleParticipant) or not isinstance(player_two, BattleParticipant):
        raise InvalidTrustedInputError("participants must be BattleParticipant objects")
    if player_one.user_id == player_two.user_id:
        raise InvalidTrustedInputError("a battle needs two distinct participants")
    return BattleState(config, (player_one, player_two))


def start_battle(state: BattleState) -> BattleState:
    """CREATED -> ACTIVE."""
    _require_state(state)
    _require_status(state, BattleStatus.CREATED, "start")
    return replace(state, status=BattleStatus.ACTIVE)


def cancel_battle(state: BattleState, reason: str) -> BattleState:
    """CREATED -> CANCELLED always; ACTIVE -> CANCELLED only before any answer sheet is
    submitted (afterwards a cancellation would discard a finished player's work)."""
    _require_state(state)
    if not isinstance(reason, str) or not reason.strip():
        raise InvalidTrustedInputError("a cancellation reason is required")
    if state.status is BattleStatus.ACTIVE and state.answer_sheets:
        raise InvalidBattleTransitionError("an active battle cannot be cancelled after a participant has submitted")
    if state.status not in (BattleStatus.CREATED, BattleStatus.ACTIVE):
        raise InvalidBattleTransitionError(f"cannot cancel a {state.status.value} battle")
    return replace(state, status=BattleStatus.CANCELLED, cancel_reason=reason.strip())


def submit_answers(state: BattleState, user_id: str, answers: Iterable[AnswerSubmission]) -> BattleState:
    """Record one participant's answer sheet (exactly once). When both participants have
    submitted, the battle becomes COMPLETED and its result is final."""
    _require_state(state)
    _require_user_id(user_id)
    _require_participant(state, user_id)
    _require_status(state, BattleStatus.ACTIVE, "submit answers to")
    if any(sheet.user_id == user_id for sheet in state.answer_sheets):
        raise InvalidBattleTransitionError("answers already submitted for this battle")
    if isinstance(answers, (str, bytes)) or not isinstance(answers, Iterable):
        raise InvalidSubmissionError("answers must be a collection of AnswerSubmission")

    known = {q.question_id for q in state.config.questions}
    chosen = {}
    for item in answers:
        if not isinstance(item, AnswerSubmission):
            raise InvalidSubmissionError("answers must contain AnswerSubmission items")
        if not isinstance(item.question_id, str) or item.question_id not in known:
            raise InvalidSubmissionError(f"unknown question_id {item.question_id!r:.40}")
        if item.question_id in chosen:
            raise InvalidSubmissionError(f"duplicate answer for question {item.question_id!r}")
        chosen[item.question_id] = _normalize_option(item.selected_option, "selected_option", InvalidSubmissionError)
    if state.config.require_all_answers and len(chosen) != len(known):
        raise InvalidSubmissionError(f"all {len(known)} questions must be answered")

    sheet = AnswerSheet(user_id, tuple(
        (q.question_id, chosen[q.question_id]) for q in state.config.questions if q.question_id in chosen
    ))
    sheets = state.answer_sheets + (sheet,)
    if len(sheets) < 2:
        return replace(state, answer_sheets=sheets)
    completed = replace(state, answer_sheets=sheets, status=BattleStatus.COMPLETED)
    return replace(completed, result=score_battle(completed))


# ==========================
# 3. SCORING
# ==========================

def score_battle(state: BattleState) -> BattleResult:
    """Correct-answer count per participant against the server-held keys. Higher count wins;
    equal counts tie. Requires both answer sheets."""
    _require_state(state)
    if len(state.answer_sheets) != 2:
        raise InvalidBattleTransitionError("both participants must submit before scoring")
    keys = {q.question_id: q.correct_option for q in state.config.questions}
    total = len(keys)
    scores = []
    for participant in state.participants:
        sheet = _sheet_for(state, participant.user_id)
        correct = sum(1 for qid, option in sheet.answers if keys[qid] == option)
        scores.append(ParticipantScore(participant.user_id, correct, len(sheet.answers), total))
    first, second = scores
    if first.correct == second.correct:
        return BattleResult(state.config.battle_id, (first, second), BattleOutcome.TIE, None)
    winner = first if first.correct > second.correct else second
    return BattleResult(state.config.battle_id, (first, second), BattleOutcome.WIN, winner.user_id)


# ==========================
# 4. PARTICIPANT VIEWS
# ==========================

def learner_questions(state: BattleState, viewer_user_id: str) -> tuple[LearnerBattleQuestion, ...]:
    """The shared question set without answer keys. Participants only."""
    _require_state(state)
    _require_user_id(viewer_user_id)
    _require_participant(state, viewer_user_id)
    return tuple(
        LearnerBattleQuestion(i, q.question_id, q.question_text, q.option_a, q.option_b, q.option_c, q.option_d, q.topic)
        for i, q in enumerate(state.config.questions, start=1)
    )


def battle_view(state: BattleState, viewer_user_id: str) -> BattleView:
    """Participant-safe snapshot (see BattleView)."""
    questions = learner_questions(state, viewer_user_id)      # validates state + participant
    opponent = next(p for p in state.participants if p.user_id != viewer_user_id)
    own = _sheet_for(state, viewer_user_id, required=False)
    completed = state.status is BattleStatus.COMPLETED
    review = ()
    if completed:
        sheets = {s.user_id: dict(s.answers) for s in state.answer_sheets}
        review = tuple(
            QuestionReview(i, q.question_id, q.correct_option, q.explanation,
                           tuple((p.user_id, sheets[p.user_id].get(q.question_id)) for p in state.participants))
            for i, q in enumerate(state.config.questions, start=1)
        )
    return BattleView(
        battle_id=state.config.battle_id,
        status=state.status,
        viewer_user_id=viewer_user_id,
        opponent_display_name=opponent.display_name,
        viewer_submitted=own is not None,
        opponent_submitted=_sheet_for(state, opponent.user_id, required=False) is not None,
        questions=questions,
        viewer_answers=own.answers if own else (),
        result=state.result if completed else None,
        review=review,
    )


# ==========================
# 5. HELPERS
# ==========================

def _require_id(value: object, field: str) -> None:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value) or len(value) > MAX_ID_LENGTH:
        raise InvalidTrustedInputError(f"{field} must match [A-Za-z0-9_.-]+ (max {MAX_ID_LENGTH}); got {value!r:.40}")


def _require_state(state: object) -> None:
    if not isinstance(state, BattleState):
        raise InvalidTrustedInputError("state must be a BattleState")


def _require_status(state: BattleState, expected: BattleStatus, action: str) -> None:
    if state.status is not expected:
        raise InvalidBattleTransitionError(f"cannot {action} a {state.status.value} battle")


def _require_participant(state: BattleState, user_id: str) -> None:
    if all(p.user_id != user_id for p in state.participants):
        raise UnauthorizedParticipantError("user is not a participant in this battle")


def _sheet_for(state: BattleState, user_id: str, *, required: bool = True) -> AnswerSheet | None:
    for sheet in state.answer_sheets:
        if sheet.user_id == user_id:
            return sheet
    if required:
        raise InvalidBattleTransitionError("answer sheet missing")
    return None

