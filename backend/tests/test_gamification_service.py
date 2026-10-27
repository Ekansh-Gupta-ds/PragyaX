"""
Unit tests for backend/app/services/gamification_service.py (Ankush's module).

Pure-function tests: no database, no FastAPI app, no network, no shared mutable state.
Every test builds its own inputs, so tests pass in any order and individually.

The service is loaded straight from its file instead of `import backend.app.services...`.
Importing the package would run backend/app/services/__init__.py, which imports the
repository and backend/app/config.py; config reads .env and fixes DATABASE_PATH at import
time. If that happened before test_api_flow.py sets its temporary DATABASE_PATH, the API
tests would write to the real pragyax.db. Loading by path removes that risk.
"""

import ast
import dataclasses
import importlib.util
import inspect
import sys
from pathlib import Path

import pytest

SERVICE_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "gamification_service.py"


def _load_service():
    # Recipe from the importlib docs ("Importing a source file directly").
    spec = importlib.util.spec_from_file_location("pragyax_gamification_service_under_test", SERVICE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gs = _load_service()

PYTHON = ("subj_python", "Python Programming")
HIGH_SCORE_PY = "assessment.subj_python.high_score"


def make_challenge(challenge_id="chal_today_py", correct_option="B", points=50):
    """Defaults mirror the V1 seed row (backend/app/database/connection.py)."""
    return gs.ChallengeConfig(challenge_id=challenge_id, correct_option=correct_option, points=points)


def badge_keys(awards):
    return tuple(award.badge_key for award in awards)


def record(event_key, points, status=gs.RewardStatus.AWARDED):
    return gs.RewardRecord(event_key=event_key, points=points, status=status)


# ==========================
# Challenge answer correctness
# ==========================

@pytest.mark.parametrize("selected, key", [("B", "B"), ("b", "B"), ("  B ", "B"), ("c", "C"), ("A", " a ")])
def test_correct_answer_is_recognised(selected, key):
    assert gs.is_challenge_answer_correct(selected, key) is True


@pytest.mark.parametrize("selected", ["A", "c", " d "])
def test_incorrect_answer_is_not_correct(selected):
    assert gs.is_challenge_answer_correct(selected, "B") is False


@pytest.mark.parametrize("selected", ["", "   ", "E", "Z", "AB", "1", None, 1, ["B"]])
def test_invalid_learner_option_is_a_submission_error(selected):
    with pytest.raises(gs.InvalidSubmissionError):
        gs.is_challenge_answer_correct(selected, "B")


@pytest.mark.parametrize("key", ["", "E", "BB", None])
def test_corrupt_answer_key_is_a_trusted_input_error(key):
    with pytest.raises(gs.InvalidTrustedInputError):
        gs.is_challenge_answer_correct("B", key)


def test_error_types_are_distinguishable_but_share_a_base():
    assert issubclass(gs.InvalidSubmissionError, gs.GamificationError)
    assert issubclass(gs.InvalidTrustedInputError, gs.GamificationError)
    assert not issubclass(gs.InvalidSubmissionError, gs.InvalidTrustedInputError)
    assert issubclass(gs.GamificationError, ValueError)


# ==========================
# Challenge reward decisions
# ==========================

def test_first_correct_answer_awards_configured_points_and_badge():
    decision = gs.compute_challenge_reward(make_challenge(), "b", already_completed=False)
    assert decision == gs.ChallengeRewardDecision(
        challenge_id="chal_today_py",
        is_correct=True,
        points_awarded=50,
        reason=gs.RewardReason.CORRECT_ANSWER,
        achievements=(gs.DAILY_CHALLENGE_ACHIEVEMENT,),
    )
    assert decision.is_repeat_submission is False


def test_first_incorrect_answer_awards_nothing():
    decision = gs.compute_challenge_reward(make_challenge(), "A", already_completed=False)
    assert decision.is_correct is False
    assert decision.points_awarded == 0
    assert decision.reason is gs.RewardReason.INCORRECT_ANSWER
    assert decision.achievements == ()


@pytest.mark.parametrize("selected", ["B", "A"])
def test_already_completed_challenge_awards_zero_additional_points(selected):
    decision = gs.compute_challenge_reward(make_challenge(), selected, already_completed=True)
    assert decision.points_awarded == 0
    assert decision.reason is gs.RewardReason.ALREADY_COMPLETED
    assert decision.achievements == ()
    assert decision.is_repeat_submission is True


def test_repeat_submission_still_validates_the_option_first():
    # V1 router parity: an invalid option is a 400 before the repeat check.
    with pytest.raises(gs.InvalidSubmissionError):
        gs.compute_challenge_reward(make_challenge(), "Z", already_completed=True)


@pytest.mark.parametrize("points", [0, 1, 50, 1000])
def test_reward_equals_trusted_config_points(points):
    decision = gs.compute_challenge_reward(make_challenge(points=points), "B", already_completed=False)
    assert decision.points_awarded == points
    # A zero-point challenge still counts as solved (V1 awards the badge on any correct answer).
    assert decision.reason is gs.RewardReason.CORRECT_ANSWER
    assert decision.achievements == (gs.DAILY_CHALLENGE_ACHIEVEMENT,)


@pytest.mark.parametrize("points", [-1, -50, True, False, 1.5, "50", None])
def test_negative_or_non_integer_reward_config_is_rejected(points):
    with pytest.raises(gs.InvalidTrustedInputError):
        make_challenge(points=points)


@pytest.mark.parametrize("challenge_id", ["", "   ", None])
def test_challenge_config_requires_an_id(challenge_id):
    with pytest.raises(gs.InvalidTrustedInputError):
        make_challenge(challenge_id=challenge_id)


@pytest.mark.parametrize("key", ["", "E", None])
def test_challenge_config_rejects_corrupt_answer_key(key):
    with pytest.raises(gs.InvalidTrustedInputError):
        make_challenge(correct_option=key)


def test_reward_amount_cannot_come_from_the_caller():
    # No parameter accepts a reward amount: points can only come from ChallengeConfig.
    assert list(inspect.signature(gs.compute_challenge_reward).parameters) == [
        "challenge", "selected_option", "already_completed",
    ]
    # A request-shaped dict is refused even if it carries a points value.
    forged = {"challenge_id": "chal_today_py", "correct_option": "B", "points": 1_000_000}
    with pytest.raises(gs.InvalidTrustedInputError):
        gs.compute_challenge_reward(forged, "B", already_completed=False)


@pytest.mark.parametrize("flag", [None, 0, 1, "false"])
def test_completion_flag_must_be_a_real_bool(flag):
    with pytest.raises(gs.InvalidTrustedInputError):
        gs.compute_challenge_reward(make_challenge(), "B", already_completed=flag)


def test_daily_challenge_badge_matches_the_v1_persisted_badge():
    # Persisted-data compatibility: same key/text/icon V1 writes in submit_daily_challenge.
    assert gs.DAILY_CHALLENGE_ACHIEVEMENT == gs.AchievementAward(
        badge_key="daily_striker",
        title="Daily Code Breaker",
        description="Solved today's Python code snippet challenge",
        icon="zap",
    )


# ==========================
# Assessment achievements
# ==========================

@pytest.mark.parametrize("score, expected", [
    (0, ()), (1, ()), (2, ()), (3, ()),
    (4, (HIGH_SCORE_PY,)), (5, (HIGH_SCORE_PY,)),
])
def test_assessment_scores_zero_through_five(score, expected):
    assert badge_keys(gs.eligible_assessment_achievements(score, 5, *PYTHON)) == expected


def test_high_score_award_content():
    (award,) = gs.eligible_assessment_achievements(4, 5, *PYTHON)
    assert award == gs.AchievementAward(
        badge_key=HIGH_SCORE_PY,
        title="Python Programming Virtuoso",
        description="Scored 80%+ on the Python Programming assessment",
        icon="award",
    )


@pytest.mark.parametrize("score, total, eligible", [
    (8, 10, True), (7, 10, False), (4, 10, False),   # V1 (score >= 4) would award 4/10
    (4, 4, True), (3, 4, False), (1, 1, True), (0, 1, False),
])
def test_threshold_is_a_percentage_of_total(score, total, eligible):
    awards = gs.eligible_assessment_achievements(score, total, *PYTHON)
    assert (badge_keys(awards) == (HIGH_SCORE_PY,)) is eligible


@pytest.mark.parametrize("score, total", [
    (-1, 5), (6, 5), (0, 0), (1, 0), (3, -5),
    (True, 5), (4, True), (4.0, 5), (4, 5.0), ("4", 5), (None, 5),
])
def test_invalid_scores_or_totals_are_rejected(score, total):
    with pytest.raises(gs.InvalidTrustedInputError):
        gs.eligible_assessment_achievements(score, total, *PYTHON)


def test_achievements_are_subject_specific():
    python = gs.eligible_assessment_achievements(5, 5, "subj_python", "Python Programming")
    datasci = gs.eligible_assessment_achievements(5, 5, "subj_datasci", "Data Science & ML")
    assert badge_keys(python) == ("assessment.subj_python.high_score",)
    assert badge_keys(datasci) == ("assessment.subj_datasci.high_score",)
    assert datasci[0].title == "Data Science & ML Virtuoso"
    assert "Data Science & ML" in datasci[0].description


def test_badge_key_is_stable_and_ignores_the_display_title():
    original = gs.eligible_assessment_achievements(5, 5, "subj_python", "Python Programming")
    renamed = gs.eligible_assessment_achievements(5, 5, "subj_python", "Python (renamed)")
    assert badge_keys(original) == badge_keys(renamed) == (gs.assessment_badge_key("subj_python", "high_score"),)
    assert original[0].title != renamed[0].title
    assert gs.assessment_badge_key("subj_python", "high_score") == HIGH_SCORE_PY


def test_subject_title_text_is_never_treated_as_a_placeholder():
    (award,) = gs.eligible_assessment_achievements(5, 5, "subj_python", "{min_percent} {subject}")
    assert award.title == "{min_percent} {subject} Virtuoso"


@pytest.mark.parametrize("subject_id", [
    "", "subj python", "subj.python", "subj:python", "subj_python\n", None, 42, "x" * 43,
])
def test_invalid_subject_ids_are_rejected_whatever_the_score(subject_id):
    for score in (0, 5):  # validated even when no rule would match
        with pytest.raises(gs.InvalidTrustedInputError):
            gs.eligible_assessment_achievements(score, 5, subject_id, "Python")


@pytest.mark.parametrize("subject_title", ["", "   ", None])
def test_subject_title_is_required(subject_title):
    with pytest.raises(gs.InvalidTrustedInputError):
        gs.eligible_assessment_achievements(5, 5, "subj_python", subject_title)


def test_badge_keys_fit_the_badge_key_column():
    longest = gs.assessment_badge_key("s" * 42, "high_score")
    assert len(longest) == gs.MAX_BADGE_KEY_LENGTH == 64
    uuid_key = gs.assessment_badge_key("123e4567-e89b-12d3-a456-426614174000", "high_score")
    assert uuid_key == "assessment.123e4567-e89b-12d3-a456-426614174000.high_score"
    with pytest.raises(gs.InvalidTrustedInputError):
        gs.assessment_badge_key("s" * 43, "high_score")


def test_multiple_rules_are_evaluated_in_rule_order():
    rules = (
        gs.AssessmentAchievementRule("completed", 0, "{subject} Starter", "Finished the {subject} assessment", "trophy"),
        gs.AssessmentAchievementRule("high_score", 80, "{subject} Virtuoso", "Scored {min_percent}%+", "award"),
        gs.AssessmentAchievementRule("perfect_score", 100, "{subject} Perfectionist", "Scored {min_percent}%", "trophy"),
    )

    def earned(score):
        return [key.rsplit(".", 1)[1] for key in badge_keys(gs.eligible_assessment_achievements(score, 5, *PYTHON, rules=rules))]

    assert earned(0) == ["completed"]
    assert earned(3) == ["completed"]
    assert earned(4) == ["completed", "high_score"]
    assert earned(5) == ["completed", "high_score", "perfect_score"]


def test_empty_rule_table_awards_nothing():
    assert gs.eligible_assessment_achievements(5, 5, *PYTHON, rules=()) == ()


@pytest.mark.parametrize("kwargs", [
    dict(key="high score", min_percent=80, title="t", description="d", icon="i"),
    dict(key="High_Score", min_percent=80, title="t", description="d", icon="i"),
    dict(key="high_score", min_percent=101, title="t", description="d", icon="i"),
    dict(key="high_score", min_percent=-1, title="t", description="d", icon="i"),
    dict(key="high_score", min_percent=80.0, title="t", description="d", icon="i"),
    dict(key="high_score", min_percent=80, title=" ", description="d", icon="i"),
    dict(key="high_score", min_percent=80, title="t", description="d", icon=""),
])
def test_invalid_rules_are_rejected(kwargs):
    with pytest.raises(gs.InvalidTrustedInputError):
        gs.AssessmentAchievementRule(**kwargs)


def test_duplicate_or_foreign_rules_are_rejected():
    rule = gs.ASSESSMENT_ACHIEVEMENT_RULES[0]
    with pytest.raises(gs.InvalidTrustedInputError):
        gs.eligible_assessment_achievements(5, 5, *PYTHON, rules=(rule, rule))
    with pytest.raises(gs.InvalidTrustedInputError):
        gs.eligible_assessment_achievements(5, 5, *PYTHON, rules=({"key": "high_score"},))


def test_assessment_achievements_never_carry_points():
    # XP and assessment scores are separate: achievements have no points field.
    assert "points" not in {field.name for field in dataclasses.fields(gs.AchievementAward)}


# ==========================
# Reward event keys
# ==========================

def test_reward_event_key_format_and_stability():
    key = gs.reward_event_key("usr_1", "daily_challenge", "chal_today_py")
    assert key == "daily_challenge:chal_today_py:usr_1"
    assert key == gs.reward_event_key("usr_1", "daily_challenge", "chal_today_py")
    assert key != gs.reward_event_key("usr_2", "daily_challenge", "chal_today_py")
    assert key != gs.reward_event_key("usr_1", "daily_challenge", "chal_tomorrow_py")


@pytest.mark.parametrize("parts", [
    ("", "daily_challenge", "chal"),
    ("usr:1", "daily_challenge", "chal"),
    ("usr_1", "daily challenge", "chal"),
    ("usr_1", "daily_challenge", "chal\n"),
    (None, "daily_challenge", "chal"),
])
def test_reward_event_key_rejects_ambiguous_parts(parts):
    with pytest.raises(gs.InvalidTrustedInputError):
        gs.reward_event_key(*parts)


# ==========================
# Points aggregation
# ==========================

def test_empty_reward_history_sums_to_zero():
    assert gs.aggregate_points([]) == gs.PointsSummary(
        total_points=0, counted_records=0, invalid_records=0, not_awarded_records=0, duplicate_records=0
    )


def test_only_valid_awarded_records_are_summed():
    records = [
        record("daily_challenge:c1:usr_1", 50),
        record("daily_challenge:c2:usr_1", 0),                            # valid, worth 0
        record("daily_challenge:c3:usr_1", 10, "awarded"),                # raw DB string status
        record("daily_challenge:c4:usr_1", 30, gs.RewardStatus.REVOKED),  # not awarded
        record("daily_challenge:c5:usr_1", -20),                          # negative: invalid
        record("daily_challenge:c6:usr_1", True),                         # bool: invalid
        record("daily_challenge:c7:usr_1", 12.5),                         # float: invalid
        record("   ", 40),                                                # blank key: invalid
        "not a record",                                                   # wrong type: invalid
    ]
    assert gs.aggregate_points(records) == gs.PointsSummary(
        total_points=60, counted_records=3, invalid_records=5, not_awarded_records=1, duplicate_records=0
    )


def test_duplicate_reward_events_are_counted_once():
    key = gs.reward_event_key("usr_1", "daily_challenge", "chal_today_py")
    summary = gs.aggregate_points([record(key, 50), record(key, 50), record(key, 50)])
    assert (summary.total_points, summary.counted_records, summary.duplicate_records) == (50, 1, 2)


def test_first_valid_award_wins_for_a_duplicated_event():
    key = "daily_challenge:chal_today_py:usr_1"
    summary = gs.aggregate_points([record(key, 50), record(key, 5000)])
    assert (summary.total_points, summary.duplicate_records) == (50, 1)


def test_invalid_or_revoked_rows_do_not_claim_an_event_key():
    key = "daily_challenge:chal_today_py:usr_1"
    summary = gs.aggregate_points([record(key, -5), record(key, 7, gs.RewardStatus.REVOKED), record(key, 50)])
    assert summary == gs.PointsSummary(
        total_points=50, counted_records=1, invalid_records=1, not_awarded_records=1, duplicate_records=0
    )


# ==========================
# Determinism, immutability and purity
# ==========================

def test_outputs_are_deterministic():
    records = [record("daily_challenge:c1:usr_1", 50), record("daily_challenge:c1:usr_1", 50), record("x", -1)]
    runs = [
        (
            gs.compute_challenge_reward(make_challenge(), "B", already_completed=False),
            gs.eligible_assessment_achievements(4, 5, *PYTHON),
            gs.aggregate_points(records),
            gs.reward_event_key("usr_1", "daily_challenge", "chal_today_py"),
        )
        for _ in range(3)
    ]
    assert runs[0] == runs[1] == runs[2]


def test_aggregation_gives_the_same_result_for_any_iterable():
    records = [record("a", 1), record("b", 2), record("a", 3)]
    assert gs.aggregate_points(iter(records)) == gs.aggregate_points(records) == gs.aggregate_points(tuple(records))


def test_domain_objects_are_immutable():
    challenge = make_challenge()
    decision = gs.compute_challenge_reward(challenge, "B", already_completed=False)
    with pytest.raises(dataclasses.FrozenInstanceError):
        challenge.points = 1_000_000
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.points_awarded = 1_000_000
    with pytest.raises(dataclasses.FrozenInstanceError):
        gs.DAILY_CHALLENGE_ACHIEVEMENT.badge_key = "hacked"
    assert isinstance(gs.ASSESSMENT_ACHIEVEMENT_RULES, tuple)


def test_inputs_are_not_mutated():
    records = [record("a", 1), record("a", 1)]
    snapshot = list(records)
    rules = list(gs.ASSESSMENT_ACHIEVEMENT_RULES)
    gs.aggregate_points(records)
    gs.eligible_assessment_achievements(5, 5, *PYTHON, rules=rules)
    assert records == snapshot
    assert rules == list(gs.ASSESSMENT_ACHIEVEMENT_RULES)


def test_service_uses_only_side_effect_free_standard_library_modules():
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "no relative imports: the service must not depend on app modules"
            imported.add(node.module.split(".")[0])
    assert imported <= set(sys.stdlib_module_names), imported
    assert not imported & {"sqlite3", "os", "io", "socket", "http", "urllib", "subprocess", "random", "time", "datetime"}
