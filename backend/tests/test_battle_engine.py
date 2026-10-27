"""
Unit tests for backend/app/services/battle_engine.py (Ankush's module).

Pure-function tests: no database, FastAPI app, clock, network or shared state; any order works.
Loaded under a throwaway package (see test_points_ledger_domain.py for why) so
backend/app/services/__init__.py, which imports the repository and config, never runs.
"""

import ast
import builtins
import dataclasses
import importlib.util
import random
import socket
import sqlite3
import sys
import types
from pathlib import Path

import pytest

SERVICES_DIR = Path(__file__).resolve().parents[1] / "app" / "services"
_PACKAGE = "pragyax_services_battle_under_test"


def _load(module_name):
    if _PACKAGE not in sys.modules:
        package = types.ModuleType(_PACKAGE)
        package.__path__ = [str(SERVICES_DIR)]
        sys.modules[_PACKAGE] = package
    full_name = f"{_PACKAGE}.{module_name}"
    spec = importlib.util.spec_from_file_location(full_name, SERVICES_DIR / f"{module_name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


be = _load("battle_engine")
gs = sys.modules[f"{_PACKAGE}.gamification_service"]
lb = sys.modules[f"{_PACKAGE}.leaderboard_engine"]

ASHA = be.BattleParticipant("usr_asha01", "Asha")
RAVI = be.BattleParticipant("usr_ravi02", "Ravi")
MEERA = "usr_meera03"
KEYS = {"bq_1": "B", "bq_2": "C", "bq_3": "A"}


def question(qid, correct, **overrides):
    fields = dict(question_id=qid, question_text=f"Question {qid}?", option_a="a", option_b="b",
                  option_c="c", option_d="d", correct_option=correct, explanation=f"SECRET-EXPLANATION-{qid}",
                  topic="Lists")
    fields.update(overrides)
    return be.BattleQuestion(**fields)


def config(battle_id="btl_001", require_all_answers=True, keys=KEYS):
    return be.BattleConfig(battle_id, tuple(question(q, k) for q, k in keys.items()), require_all_answers)


def active(battle_id="btl_001", **kwargs):
    return be.start_battle(be.create_battle(config(battle_id, **kwargs), ASHA, RAVI))


def sheet(options):
    """options: dict question_id -> option."""
    return [be.AnswerSubmission(q, o) for q, o in options.items()]


ALL_RIGHT = {"bq_1": "B", "bq_2": "C", "bq_3": "A"}
TWO_RIGHT = {"bq_1": "B", "bq_2": "C", "bq_3": "D"}
ONE_RIGHT = {"bq_1": "B", "bq_2": "A", "bq_3": "D"}


def finish(a_answers, r_answers, **kwargs):
    state = be.submit_answers(active(**kwargs), ASHA.user_id, sheet(a_answers))
    return be.submit_answers(state, RAVI.user_id, sheet(r_answers))


# ==========================
# Valid battles and scoring
# ==========================

def test_valid_two_player_battle_lifecycle():
    created = be.create_battle(config(), ASHA, RAVI)
    assert created.status is be.BattleStatus.CREATED
    started = be.start_battle(created)
    assert started.status is be.BattleStatus.ACTIVE
    half = be.submit_answers(started, ASHA.user_id, sheet(ALL_RIGHT))
    assert half.status is be.BattleStatus.ACTIVE and half.result is None
    done = be.submit_answers(half, RAVI.user_id, sheet(ONE_RIGHT))
    assert done.status is be.BattleStatus.COMPLETED
    assert done.result == be.BattleResult(
        "btl_001",
        (be.ParticipantScore(ASHA.user_id, 3, 3, 3), be.ParticipantScore(RAVI.user_id, 1, 3, 3)),
        be.BattleOutcome.WIN, ASHA.user_id,
    )


def test_both_players_get_the_same_questions():
    state = active()
    asha_q = be.learner_questions(state, ASHA.user_id)
    ravi_q = be.learner_questions(state, RAVI.user_id)
    assert asha_q == ravi_q
    assert [q.question_id for q in asha_q] == ["bq_1", "bq_2", "bq_3"]
    assert [q.position for q in asha_q] == [1, 2, 3]


def test_player_one_wins():
    result = finish(ALL_RIGHT, TWO_RIGHT).result
    assert (result.outcome, result.winner_user_id) == (be.BattleOutcome.WIN, ASHA.user_id)


def test_player_two_wins():
    result = finish(ONE_RIGHT, TWO_RIGHT).result
    assert (result.outcome, result.winner_user_id) == (be.BattleOutcome.WIN, RAVI.user_id)
    assert [s.correct for s in result.scores] == [1, 2]


@pytest.mark.parametrize("answers", [ALL_RIGHT, TWO_RIGHT, ONE_RIGHT, {"bq_1": "D", "bq_2": "D", "bq_3": "D"}])
def test_equal_correct_counts_tie_without_any_tiebreak(answers):
    result = finish(answers, answers).result
    assert result.outcome is be.BattleOutcome.TIE and result.winner_user_id is None


def test_tie_with_different_wrong_answers():
    a = {"bq_1": "B", "bq_2": "A", "bq_3": "B"}
    r = {"bq_1": "A", "bq_2": "C", "bq_3": "C"}
    result = finish(a, r).result
    assert result.outcome is be.BattleOutcome.TIE and [s.correct for s in result.scores] == [1, 1]


def test_correct_and_incorrect_answers_are_judged_by_server_keys():
    result = finish({"bq_1": "b", "bq_2": " c ", "bq_3": "B"}, {"bq_1": "A", "bq_2": "A", "bq_3": "A"}).result
    assert [s.correct for s in result.scores] == [2, 1]          # case/whitespace normalised like V1


def test_partial_sheets_when_allowed_count_skips_as_incorrect():
    state = be.submit_answers(active(require_all_answers=False), ASHA.user_id, sheet({"bq_1": "B"}))
    state = be.submit_answers(state, RAVI.user_id, [])
    assert [(s.correct, s.answered, s.total) for s in state.result.scores] == [(1, 1, 3), (0, 0, 3)]
    assert state.result.winner_user_id == ASHA.user_id


def test_incomplete_sheet_rejected_when_completeness_required():
    with pytest.raises(gs.InvalidSubmissionError):
        be.submit_answers(active(), ASHA.user_id, sheet({"bq_1": "B", "bq_2": "C"}))


def test_answer_order_in_the_sheet_does_not_matter():
    reordered = dict(reversed(list(ALL_RIGHT.items())))
    assert finish(reordered, ONE_RIGHT).result == finish(ALL_RIGHT, ONE_RIGHT).result


# ==========================
# Authorization and submission validation
# ==========================

def test_third_player_cannot_view_or_submit():
    state = active()
    with pytest.raises(be.UnauthorizedParticipantError):
        be.submit_answers(state, MEERA, sheet(ALL_RIGHT))
    with pytest.raises(be.UnauthorizedParticipantError):
        be.learner_questions(state, MEERA)
    with pytest.raises(be.UnauthorizedParticipantError):
        be.battle_view(state, MEERA)


def test_participants_must_be_two_distinct_valid_users():
    with pytest.raises(gs.InvalidTrustedInputError):
        be.create_battle(config(), ASHA, be.BattleParticipant("usr_asha01", "Asha again"))
    with pytest.raises(gs.InvalidTrustedInputError):
        be.create_battle(config(), ASHA, {"user_id": "usr_x"})
    for bad in ("", "usr a", None, "u" * 65):
        with pytest.raises(gs.InvalidTrustedInputError):
            be.BattleParticipant(bad, "Name")
    with pytest.raises(gs.InvalidTrustedInputError):
        be.BattleParticipant("usr_ok", " ")


def test_duplicate_submission_is_rejected():
    state = be.submit_answers(active(), ASHA.user_id, sheet(ALL_RIGHT))
    with pytest.raises(be.InvalidBattleTransitionError):
        be.submit_answers(state, ASHA.user_id, sheet(ONE_RIGHT))


def test_duplicate_answers_for_one_question_are_rejected():
    answers = sheet(ALL_RIGHT) + [be.AnswerSubmission("bq_1", "A")]
    with pytest.raises(gs.InvalidSubmissionError):
        be.submit_answers(active(), ASHA.user_id, answers)


@pytest.mark.parametrize("bad", [
    [be.AnswerSubmission("bq_999", "A")],
    [be.AnswerSubmission(None, "A")],
    [be.AnswerSubmission("bq_1", "E")],
    [be.AnswerSubmission("bq_1", "")],
    [be.AnswerSubmission("bq_1", None)],
    [{"question_id": "bq_1", "selected_option": "B"}],
    "bq_1=B",
])
def test_invalid_question_ids_and_options_are_rejected(bad):
    with pytest.raises(gs.InvalidSubmissionError):
        be.submit_answers(active(require_all_answers=False), ASHA.user_id, bad)


def test_rejected_submission_changes_nothing():
    state = active()
    with pytest.raises(gs.InvalidSubmissionError):
        be.submit_answers(state, ASHA.user_id, [be.AnswerSubmission("bq_1", "Z")])
    assert state.answer_sheets == ()
    assert be.submit_answers(state, ASHA.user_id, sheet(ALL_RIGHT)).answer_sheets[0].user_id == ASHA.user_id


# ==========================
# Lifecycle transitions
# ==========================

def test_invalid_state_transitions_are_rejected():
    created = be.create_battle(config(), ASHA, RAVI)
    with pytest.raises(be.InvalidBattleTransitionError):
        be.submit_answers(created, ASHA.user_id, sheet(ALL_RIGHT))          # not started
    started = be.start_battle(created)
    with pytest.raises(be.InvalidBattleTransitionError):
        be.start_battle(started)                                           # already active
    done = finish(ALL_RIGHT, ONE_RIGHT)
    with pytest.raises(be.InvalidBattleTransitionError):
        be.start_battle(done)
    with pytest.raises(be.InvalidBattleTransitionError):
        be.cancel_battle(done, "too late")
    cancelled = be.cancel_battle(created, "opponent left")
    for action in (be.start_battle, lambda s: be.cancel_battle(s, "again"),
                   lambda s: be.submit_answers(s, ASHA.user_id, sheet(ALL_RIGHT))):
        with pytest.raises(be.InvalidBattleTransitionError):
            action(cancelled)
    with pytest.raises(be.InvalidBattleTransitionError):
        be.score_battle(be.submit_answers(started, ASHA.user_id, sheet(ALL_RIGHT)))   # one sheet only


def test_cancelling_a_battle():
    created = be.create_battle(config(), ASHA, RAVI)
    cancelled = be.cancel_battle(created, "  matchmaking timeout  ")
    assert (cancelled.status, cancelled.cancel_reason, cancelled.result) == (be.BattleStatus.CANCELLED, "matchmaking timeout", None)
    assert be.cancel_battle(be.start_battle(created), "opponent disconnected").status is be.BattleStatus.CANCELLED
    with pytest.raises(be.InvalidBattleTransitionError):     # a participant already finished
        be.cancel_battle(be.submit_answers(be.start_battle(created), ASHA.user_id, sheet(ALL_RIGHT)), "abort")
    with pytest.raises(gs.InvalidTrustedInputError):
        be.cancel_battle(created, " ")


def test_completed_battle_is_final_and_immutable():
    done = finish(ALL_RIGHT, ONE_RIGHT)
    with pytest.raises(be.InvalidBattleTransitionError):     # replay / resubmission after completion
        be.submit_answers(done, ASHA.user_id, sheet(ONE_RIGHT))
    with pytest.raises(be.InvalidBattleTransitionError):
        be.submit_answers(done, RAVI.user_id, sheet(ALL_RIGHT))
    with pytest.raises(dataclasses.FrozenInstanceError):
        done.result = None
    with pytest.raises(dataclasses.FrozenInstanceError):
        done.result.scores[1].correct = 99
    assert isinstance(done.answer_sheets, tuple) and isinstance(done.result.scores, tuple)


def test_transitions_return_new_states_and_never_mutate_inputs():
    created = be.create_battle(config(), ASHA, RAVI)
    started = be.start_battle(created)
    submitted = be.submit_answers(started, ASHA.user_id, sheet(ALL_RIGHT))
    assert created.status is be.BattleStatus.CREATED and started.answer_sheets == ()
    assert submitted is not started
    answers = sheet(ONE_RIGHT)
    snapshot = list(answers)
    be.submit_answers(submitted, RAVI.user_id, answers)
    assert answers == snapshot


# ==========================
# Secrecy and privacy
# ==========================

def test_correct_answers_are_secret_before_completion():
    state = be.submit_answers(active(), ASHA.user_id, sheet(ALL_RIGHT))
    for viewer in (ASHA.user_id, RAVI.user_id):
        view = be.battle_view(state, viewer)
        assert view.result is None and view.review == ()
        text = repr(view) + repr(be.learner_questions(state, viewer))
        assert "SECRET-EXPLANATION" not in text and "correct_option" not in text
    assert not {"correct_option", "explanation"} & {f.name for f in dataclasses.fields(be.LearnerBattleQuestion)}


def test_opponent_answers_stay_private_until_results_are_final():
    state = be.submit_answers(active(), ASHA.user_id, sheet({"bq_1": "B", "bq_2": "C", "bq_3": "D"}))
    ravi_view = be.battle_view(state, RAVI.user_id)
    assert ravi_view.opponent_submitted is True and ravi_view.viewer_submitted is False
    assert ravi_view.viewer_answers == ()
    assert "'D'" not in repr(ravi_view)                       # Asha's answers are not visible to Ravi
    asha_view = be.battle_view(state, ASHA.user_id)
    assert asha_view.viewer_answers == (("bq_1", "B"), ("bq_2", "C"), ("bq_3", "D"))   # own answers only
    assert asha_view.opponent_submitted is False and asha_view.opponent_display_name == "Ravi"


def test_review_after_completion_shows_keys_and_both_answers():
    done = finish(ALL_RIGHT, ONE_RIGHT)
    view = be.battle_view(done, RAVI.user_id)
    assert view.result == done.result
    assert view.review[1] == be.QuestionReview(
        2, "bq_2", "C", "SECRET-EXPLANATION-bq_2", ((ASHA.user_id, "C"), (RAVI.user_id, "A")),
    )


def test_cancelled_battle_reveals_nothing():
    state = be.cancel_battle(active(), "abandoned")
    view = be.battle_view(state, ASHA.user_id)
    assert view.result is None and view.review == ()


# ==========================
# Configuration validation
# ==========================

def test_invalid_configuration_is_rejected():
    with pytest.raises(gs.InvalidTrustedInputError):
        be.BattleConfig("btl_1", ())
    with pytest.raises(gs.InvalidTrustedInputError):
        be.BattleConfig("btl_1", tuple(question(f"q{i}", "A") for i in range(be.MAX_BATTLE_QUESTIONS + 1)))
    with pytest.raises(gs.InvalidTrustedInputError):
        be.BattleConfig("btl_1", (question("q1", "A"), question("q1", "B")))
    with pytest.raises(gs.InvalidTrustedInputError):
        be.BattleConfig("btl 1", (question("q1", "A"),))
    with pytest.raises(gs.InvalidTrustedInputError):
        be.BattleConfig("btl_1", (question("q1", "A"),), require_all_answers="yes")
    for bad in ({"correct": "E"}, {"question_text": " "}, {"question_id": "q:1"}, {"explanation": None}):
        with pytest.raises(gs.InvalidTrustedInputError):
            question(bad.pop("question_id", "q1"), bad.pop("correct", "A"), **bad)


# ==========================
# Determinism, independence, purity, compatibility
# ==========================

def test_scoring_is_deterministic():
    runs = {finish(ALL_RIGHT, TWO_RIGHT).result for _ in range(5)}
    assert len(runs) == 1


def test_independent_battles_do_not_interact():
    one = be.submit_answers(active("btl_one"), ASHA.user_id, sheet(ALL_RIGHT))
    two = active("btl_two")
    assert two.answer_sheets == ()
    two = be.submit_answers(two, ASHA.user_id, sheet(ONE_RIGHT))      # same player, separate battle
    one = be.submit_answers(one, RAVI.user_id, sheet(ONE_RIGHT))
    two = be.submit_answers(two, RAVI.user_id, sheet(ALL_RIGHT))
    assert (one.result.battle_id, one.result.winner_user_id) == ("btl_one", ASHA.user_id)
    assert (two.result.battle_id, two.result.winner_user_id) == ("btl_two", RAVI.user_id)


def test_no_database_filesystem_clock_network_or_random_use(monkeypatch):
    state = random.getstate()

    def forbidden(*args, **kwargs):
        raise AssertionError("battle engine must be pure")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    done = finish(ALL_RIGHT, TWO_RIGHT)
    be.battle_view(done, ASHA.user_id)
    be.cancel_battle(be.create_battle(config(), ASHA, RAVI), "x")
    monkeypatch.undo()
    assert random.getstate() == state


def test_source_imports_only_stdlib_and_owned_modules():
    tree = ast.parse((SERVICES_DIR / "battle_engine.py").read_text(encoding="utf-8"))
    absolute, relative, attributes = set(), set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            absolute |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            (relative if node.level else absolute).add(node.module.split(".")[0])
        elif isinstance(node, ast.Attribute):
            attributes.add(node.attr)
    assert absolute <= set(sys.stdlib_module_names), absolute
    assert not absolute & {"sqlite3", "os", "io", "socket", "http", "urllib", "random", "secrets",
                           "time", "datetime", "uuid", "asyncio", "threading"}
    assert relative == {"gamification_service", "leaderboard_engine"}
    assert not attributes & {"now", "today", "utcnow", "monotonic", "execute", "connect"}


def test_battle_scores_are_not_points_and_existing_modules_are_unchanged():
    assert "points" not in {f.name for f in dataclasses.fields(be.ParticipantScore)}
    assert not {"points", "xp"} & {f.name for f in dataclasses.fields(be.BattleResult)}
    decision = gs.compute_challenge_reward(gs.ChallengeConfig("chal_today_py", "B", 50), "B", already_completed=False)
    assert decision.points_awarded == 50
    board = lb.build_leaderboard(lb.LeaderboardScope("platform"), [lb.LeaderboardMember("usr_a", "A", 5)])
    assert board.entries[0].rank == 1
