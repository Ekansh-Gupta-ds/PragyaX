"""
Unit tests for legacy badge compatibility in backend/app/services/gamification_service.py
(LEGACY_BADGE_EQUIVALENTS and filter_new_achievements). Ankush's module.

Pure-function tests: no database, no FastAPI app, no shared mutable state; each test
builds its own inputs and passes in any order. The service is loaded from its file path
(not `import backend.app...`) for the same reason as test_gamification_service.py:
importing the app package fixes DATABASE_PATH before test_api_flow.py can redirect it.
"""

import importlib.util
import inspect
import sys
from pathlib import Path
from types import MappingProxyType

import pytest

SERVICE_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "gamification_service.py"


def _load_service():
    # Recipe from the importlib docs ("Importing a source file directly").
    spec = importlib.util.spec_from_file_location("pragyax_gamification_legacy_under_test", SERVICE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gs = _load_service()

PY_HIGH = "assessment.subj_python.high_score"
DS_HIGH = "assessment.subj_datasci.high_score"


def award(badge_key, title="t"):
    return gs.AchievementAward(badge_key=badge_key, title=title, description="d", icon="award")


def python_high_score():
    (high,) = gs.eligible_assessment_achievements(5, 5, "subj_python", "Python Programming")
    return high


def keys(awards):
    return tuple(a.badge_key for a in awards)


# ==========================
# The mapping
# ==========================

def test_mapping_is_exactly_python_high_score_to_py_master():
    assert dict(gs.LEGACY_BADGE_EQUIVALENTS) == {PY_HIGH: ("py_master",)}
    assert PY_HIGH == gs.assessment_badge_key("subj_python", "high_score")


def test_mapping_is_read_only():
    assert isinstance(gs.LEGACY_BADGE_EQUIVALENTS, MappingProxyType)
    with pytest.raises(TypeError):
        gs.LEGACY_BADGE_EQUIVALENTS["assessment.subj_datasci.high_score"] = ("py_master",)
    assert all(isinstance(v, tuple) for v in gs.LEGACY_BADGE_EQUIVALENTS.values())


# ==========================
# Filtering
# ==========================

def test_no_existing_badges_keeps_every_award():
    awards = (python_high_score(), gs.DAILY_CHALLENGE_ACHIEVEMENT)
    assert gs.filter_new_achievements(awards, []) == awards


def test_existing_py_master_blocks_new_python_high_score():
    assert gs.filter_new_achievements([python_high_score()], {"py_master"}) == ()


def test_existing_new_python_key_blocks_an_equivalent_legacy_award():
    assert gs.filter_new_achievements([award("py_master")], [PY_HIGH]) == ()


def test_exact_key_already_held_is_dropped():
    assert gs.filter_new_achievements([python_high_score()], [PY_HIGH]) == ()
    assert gs.filter_new_achievements([gs.DAILY_CHALLENGE_ACHIEVEMENT], ["daily_striker"]) == ()


@pytest.mark.parametrize("held", [{"py_master"}, {PY_HIGH}, {"py_master", PY_HIGH}])
def test_other_subject_high_score_stays_eligible(held):
    (ds_high,) = gs.eligible_assessment_achievements(5, 5, "subj_datasci", "Data Science & ML")
    assert keys(gs.filter_new_achievements([ds_high], held)) == (DS_HIGH,)


def test_py_master_never_equates_to_other_subjects_or_badges():
    held = {"py_master"}
    candidates = [award(DS_HIGH), award("assessment.subj_webdev.high_score"), gs.DAILY_CHALLENGE_ACHIEVEMENT]
    assert keys(gs.filter_new_achievements(candidates, held)) == keys(candidates)


def test_daily_badge_is_independent_of_python_high_score():
    candidates = [python_high_score(), gs.DAILY_CHALLENGE_ACHIEVEMENT]
    assert keys(gs.filter_new_achievements(candidates, {"py_master"})) == ("daily_striker",)
    assert keys(gs.filter_new_achievements(candidates, {"daily_striker"})) == (PY_HIGH,)


def test_duplicate_awards_in_one_batch_keep_the_first():
    first, second = award(PY_HIGH, title="first"), award(PY_HIGH, title="second")
    result = gs.filter_new_achievements([first, second, gs.DAILY_CHALLENGE_ACHIEVEMENT, gs.DAILY_CHALLENGE_ACHIEVEMENT], [])
    assert result == (first, gs.DAILY_CHALLENGE_ACHIEVEMENT)


@pytest.mark.parametrize("order", [("py_master", PY_HIGH), (PY_HIGH, "py_master")])
def test_equivalent_awards_in_one_batch_keep_only_the_first(order):
    candidates = [award(order[0]), award(order[1])]
    assert keys(gs.filter_new_achievements(candidates, [])) == (order[0],)


def test_unknown_legacy_keys_only_match_themselves():
    held = {"old_badge_2025", "beta_tester"}
    candidates = [python_high_score(), award("old_badge_2025"), award("brand_new")]
    assert keys(gs.filter_new_achievements(candidates, held)) == (PY_HIGH, "brand_new")


def test_empty_candidate_list_returns_empty_tuple():
    assert gs.filter_new_achievements([], ["py_master", "daily_striker"]) == ()
    assert gs.filter_new_achievements((), set()) == ()


def test_output_order_follows_input_order():
    candidates = [award("c_badge"), award("a_badge"), award("b_badge")]
    assert keys(gs.filter_new_achievements(candidates, [])) == ("c_badge", "a_badge", "b_badge")


def test_output_is_deterministic_and_independent_of_held_order():
    candidates = [python_high_score(), award(DS_HIGH), gs.DAILY_CHALLENGE_ACHIEVEMENT, award(PY_HIGH)]
    runs = {
        gs.filter_new_achievements(candidates, held)
        for held in (["daily_striker", "x_badge"], ("x_badge", "daily_striker"), {"daily_striker", "x_badge"})
        for _ in range(3)
    }
    assert len(runs) == 1
    assert keys(runs.pop()) == (PY_HIGH, DS_HIGH)


def test_accepts_generators_and_reads_them_once():
    candidates = [python_high_score(), award(DS_HIGH)]
    result = gs.filter_new_achievements((a for a in candidates), (k for k in ["py_master"]))
    assert keys(result) == (DS_HIGH,)


def test_inputs_are_not_mutated():
    candidates = [python_high_score(), award(PY_HIGH), award("py_master")]
    held = {"daily_striker"}
    candidates_before, held_before = list(candidates), set(held)
    gs.filter_new_achievements(candidates, held)
    assert candidates == candidates_before
    assert held == held_before
    assert dict(gs.LEGACY_BADGE_EQUIVALENTS) == {PY_HIGH: ("py_master",)}


@pytest.mark.parametrize("bad_key", ["", " ", "py master", "py:master", "py_master\n", None, 42, "k" * 65])
def test_malformed_held_keys_are_rejected(bad_key):
    with pytest.raises(gs.InvalidTrustedInputError):
        gs.filter_new_achievements([python_high_score()], ["daily_striker", bad_key])


@pytest.mark.parametrize("bad_key", ["", "py master", "py:master", "k" * 65, None])
def test_malformed_award_keys_are_rejected(bad_key):
    with pytest.raises(gs.InvalidTrustedInputError):
        gs.filter_new_achievements([award(bad_key)], [])


def test_malformed_input_is_rejected_even_when_it_would_be_filtered():
    # Validation happens before filtering, so errors don't depend on what is held.
    with pytest.raises(gs.InvalidTrustedInputError):
        gs.filter_new_achievements([award("py_master"), award("bad key")], [PY_HIGH])


@pytest.mark.parametrize("awards, held", [
    ([], "py_master"),                 # a bare string would be iterated character by character
    ([], b"py_master"),
    ([], None),
    ("daily_striker", []),
    ([{"badge_key": "py_master"}], []),
    ([None], []),
])
def test_wrong_collection_types_are_rejected(awards, held):
    with pytest.raises(gs.InvalidTrustedInputError):
        gs.filter_new_achievements(awards, held)


def test_longest_valid_key_is_accepted():
    longest = gs.assessment_badge_key("s" * 42, "high_score")
    assert keys(gs.filter_new_achievements([award(longest)], [])) == (longest,)


# ==========================
# Existing behaviour unchanged
# ==========================

def test_existing_public_signatures_are_unchanged():
    expected = {
        "is_challenge_answer_correct": ["selected_option", "correct_option"],
        "compute_challenge_reward": ["challenge", "selected_option", "already_completed"],
        "assessment_badge_key": ["subject_id", "rule_key"],
        "eligible_assessment_achievements": ["score", "total", "subject_id", "subject_title", "rules"],
        "reward_event_key": ["user_id", "source_type", "source_id"],
        "aggregate_points": ["records"],
    }
    for name, params in expected.items():
        assert list(inspect.signature(getattr(gs, name)).parameters) == params, name
    assert list(inspect.signature(gs.filter_new_achievements).parameters) == ["awards", "held_badge_keys"]


def test_existing_functions_return_the_same_values():
    challenge = gs.ChallengeConfig("chal_today_py", "B", 50)
    assert gs.compute_challenge_reward(challenge, "B", already_completed=False) == gs.ChallengeRewardDecision(
        "chal_today_py", True, 50, gs.RewardReason.CORRECT_ANSWER, (gs.DAILY_CHALLENGE_ACHIEVEMENT,)
    )
    # eligible_assessment_achievements still returns the award without consulting held badges.
    assert keys(gs.eligible_assessment_achievements(4, 5, "subj_python", "Python Programming")) == (PY_HIGH,)
    assert gs.eligible_assessment_achievements(3, 5, "subj_python", "Python Programming") == ()
    assert gs.reward_event_key("usr_1", "daily_challenge", "chal_today_py") == "daily_challenge:chal_today_py:usr_1"
    assert gs.aggregate_points([gs.RewardRecord("a", 5), gs.RewardRecord("a", 5)]).total_points == 5
    assert gs.DAILY_CHALLENGE_ACHIEVEMENT.badge_key == "daily_striker"
