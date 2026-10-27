"""
Unit tests for backend/app/services/gamification_integration.py (Ankush's module).

Runs the adapter against an in-memory FakeRepository that implements the PROVISIONAL
GamificationRepository protocol. Passing here proves the orchestration logic only: the
fake is single-threaded and commits by swapping dicts, so it says nothing about real
database atomicity or concurrency, which the future repository must guarantee.

No database, FastAPI app, clock or shared state; tests pass in any order. Modules are
loaded under a throwaway package (see test_points_ledger_domain.py for why).
"""

import ast
import builtins
import importlib.util
import itertools
import socket
import sqlite3
import sys
import types
from pathlib import Path

import pytest

SERVICES_DIR = Path(__file__).resolve().parents[1] / "app" / "services"
_PACKAGE = "pragyax_services_integration_under_test"


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


gi = _load("gamification_integration")
gs = sys.modules[f"{_PACKAGE}.gamification_service"]
ld = sys.modules[f"{_PACKAGE}.points_ledger_domain"]

ALICE, BOB = "usr_alice01", "usr_bob0002"
V1_ROW = {"id": "chal_today_py", "correct_option": "B", "points": 50, "explanation": "Shared references."}
PY_HIGH = "assessment.subj_python.high_score"


class FakeTransactionError(RuntimeError):
    pass


class FakeRepository:
    """In-memory stand-in for the provisional protocol. Each write stages copies and commits
    them only at the end, so an injected failure leaves no partial state."""

    def __init__(self, challenges=(V1_ROW,), badges=None, fail_on=None):
        self.challenges = {row["id"]: dict(row) for row in challenges}
        self.submissions = {}                               # (user_id, challenge_id) -> ChallengeWrite
        self.ledger = {}                                    # event_key -> LedgerEvent
        self.badges = {u: set(k) for u, k in (badges or {}).items()}
        self.fail_on = fail_on                              # None | "ledger" | "badges"
        self.stale_completion_check = False                 # simulate a racing request's stale read

    def get_challenge(self, challenge_id):
        row = self.challenges.get(challenge_id)
        return dict(row) if row is not None else None

    def has_completed_challenge(self, user_id, challenge_id):
        return False if self.stale_completion_check else (user_id, challenge_id) in self.submissions

    def get_badge_keys(self, user_id):
        return frozenset(self.badges.get(user_id, ()))

    def record_challenge_outcome(self, write):
        key = (write.user_id, write.challenge_id)
        if key in self.submissions:                         # stands in for ON CONFLICT DO NOTHING
            return gi.WriteResult.ALREADY_COMPLETED
        submissions, ledger = dict(self.submissions), dict(self.ledger)
        badges = {u: set(k) for u, k in self.badges.items()}
        submissions[key] = write
        if write.ledger_event is not None:
            ledger.setdefault(write.ledger_event.event_key, write.ledger_event)
        if self.fail_on == "ledger":
            raise FakeTransactionError("ledger insert failed")
        for badge in write.badges:
            badges.setdefault(write.user_id, set()).add(badge.badge_key)
        if self.fail_on == "badges":
            raise FakeTransactionError("badge insert failed")
        self.submissions, self.ledger, self.badges = submissions, ledger, badges   # commit
        return gi.WriteResult.INSERTED

    def insert_badges(self, user_id, awards):
        held = set(self.badges.get(user_id, ()))
        inserted = tuple(a.badge_key for a in awards if a.badge_key not in held)
        if self.fail_on == "badges":
            raise FakeTransactionError("badge insert failed")
        self.badges[user_id] = held | set(inserted)
        return inserted

    def get_reward_records(self, user_id):
        return [gs.RewardRecord(e.event_key, e.points_delta) for e in self.ledger.values() if e.user_id == user_id]

    def snapshot(self):
        return (dict(self.submissions), dict(self.ledger), {u: set(k) for u, k in self.badges.items()})


def make_adapter(repo=None, policy=ld.ZeroPointPolicy.RECORD):
    repo = repo or FakeRepository()
    counter = itertools.count(1)
    adapter = gi.GamificationIntegration(
        repo, new_event_id=lambda: f"rwd_{next(counter):032x}", zero_point_policy=policy
    )
    return adapter, repo


# ==========================
# Protocol and construction
# ==========================

def test_fake_satisfies_the_provisional_protocol():
    assert isinstance(FakeRepository(), gi.GamificationRepository)


def test_constructor_rejects_bad_dependencies():
    with pytest.raises(gs.InvalidTrustedInputError):
        gi.GamificationIntegration(object(), new_event_id=lambda: "rwd_1", zero_point_policy="record")
    with pytest.raises(gs.InvalidTrustedInputError):
        gi.GamificationIntegration(FakeRepository(), new_event_id="rwd_1", zero_point_policy="record")
    with pytest.raises(gs.InvalidTrustedInputError):
        gi.GamificationIntegration(FakeRepository(), new_event_id=lambda: "rwd_1", zero_point_policy="maybe")
    with pytest.raises(TypeError):     # the zero-point policy has no default (D-3 undecided)
        gi.GamificationIntegration(FakeRepository(), new_event_id=lambda: "rwd_1")


# ==========================
# Challenge submissions
# ==========================

def test_correct_answer_earns_trusted_points_once():
    adapter, repo = make_adapter()
    first = adapter.submit_daily_challenge(ALICE, "chal_today_py", " b ")
    assert first.status is gi.SubmissionStatus.ACCEPTED
    assert first.to_v1_response() == {
        "challenge_id": "chal_today_py", "is_correct": True, "points_awarded": 50,
        "correct_option": "B", "explanation": "Shared references.",
    }
    assert first.badges_awarded == ("daily_striker",) and first.ledger_recorded
    assert adapter.get_points_summary(ALICE).total_points == 50

    again = adapter.submit_daily_challenge(ALICE, "chal_today_py", "B")
    assert again.status is gi.SubmissionStatus.ALREADY_COMPLETED
    assert again.v1_error_detail == "Challenge already completed by this user today"
    assert adapter.get_points_summary(ALICE).total_points == 50
    assert len(repo.ledger) == 1 and len(repo.submissions) == 1


def test_wrong_answer_earns_zero_and_uses_the_attempt():
    adapter, repo = make_adapter()
    wrong = adapter.submit_daily_challenge(ALICE, "chal_today_py", "A")
    assert (wrong.status, wrong.is_correct, wrong.points_awarded) == (gi.SubmissionStatus.ACCEPTED, False, 0)
    assert wrong.to_v1_response()["correct_option"] == "B"          # V1 reveals the key after submitting
    assert wrong.badges_awarded == () and not wrong.ledger_recorded
    assert repo.ledger == {} and repo.badges == {}
    retry = adapter.submit_daily_challenge(ALICE, "chal_today_py", "B")
    assert retry.status is gi.SubmissionStatus.ALREADY_COMPLETED      # V1: a wrong answer locks the challenge


def test_concurrent_duplicate_detected_by_the_write_returns_already_completed():
    # Both requests pass the fast-path check; only the repository's conflict rule stops the second.
    repo = FakeRepository()
    repo.stale_completion_check = True
    adapter, _ = make_adapter(repo)
    assert adapter.submit_daily_challenge(ALICE, "chal_today_py", "B").status is gi.SubmissionStatus.ACCEPTED
    second = adapter.submit_daily_challenge(ALICE, "chal_today_py", "B")
    assert second.status is gi.SubmissionStatus.ALREADY_COMPLETED and second.points_awarded == 0
    assert adapter.get_points_summary(ALICE).total_points == 50 and len(repo.ledger) == 1


@pytest.mark.parametrize("option", ["Z", "", "AB", None, 3])
def test_invalid_option_is_rejected_before_any_lookup_or_write(option):
    adapter, repo = make_adapter()
    outcome = adapter.submit_daily_challenge(ALICE, "chal_does_not_exist", option)
    assert outcome.status is gi.SubmissionStatus.INVALID_OPTION
    assert outcome.v1_error_detail == "selected_option must be A, B, C, or D."
    assert repo.submissions == {}
    assert adapter.submit_daily_challenge(ALICE, "chal_today_py", "B").status is gi.SubmissionStatus.ACCEPTED


@pytest.mark.parametrize("challenge_id", ["chal_missing", "", None])
def test_unknown_challenge_returns_not_found(challenge_id):
    adapter, repo = make_adapter()
    outcome = adapter.submit_daily_challenge(ALICE, challenge_id, "B")
    assert outcome.status is gi.SubmissionStatus.CHALLENGE_NOT_FOUND
    assert outcome.v1_error_detail == "Challenge not found"
    assert repo.submissions == {}
    with pytest.raises(ValueError):
        outcome.to_v1_response()


def test_learner_cannot_supply_points_or_badges():
    params = list(gi.GamificationIntegration.submit_daily_challenge.__code__.co_varnames[1:4])
    assert params == ["user_id", "challenge_id", "selected_option"]
    adapter, repo = make_adapter()
    outcome = adapter.submit_daily_challenge(ALICE, "chal_today_py", "B")
    assert outcome.points_awarded == V1_ROW["points"]                # only from the stored row
    assert next(iter(repo.ledger.values())).points_delta == 50


def test_multiple_users_are_isolated():
    adapter, repo = make_adapter()
    adapter.submit_daily_challenge(ALICE, "chal_today_py", "B")
    bob = adapter.submit_daily_challenge(BOB, "chal_today_py", "C")
    assert bob.status is gi.SubmissionStatus.ACCEPTED and bob.points_awarded == 0
    assert adapter.get_points_summary(ALICE).total_points == 50
    assert adapter.get_points_summary(BOB).total_points == 0
    assert repo.badges == {ALICE: {"daily_striker"}}
    assert {e.user_id for e in repo.ledger.values()} == {ALICE}


def test_identical_ledger_event_keys_do_not_duplicate_entries():
    adapter, repo = make_adapter()
    adapter.submit_daily_challenge(ALICE, "chal_today_py", "B")
    (event,) = repo.ledger.values()
    # A second write carrying the same ledger event (e.g. a replayed message) for another row.
    replay = gi.ChallengeWrite(ALICE, "chal_other", "B", True, 50, event, ())
    assert repo.record_challenge_outcome(replay) is gi.WriteResult.INSERTED
    assert len(repo.ledger) == 1
    assert adapter.get_points_summary(ALICE).total_points == 50


def test_existing_daily_badge_is_not_written_again():
    repo = FakeRepository(badges={ALICE: {"daily_striker"}})
    adapter, _ = make_adapter(repo)
    outcome = adapter.submit_daily_challenge(ALICE, "chal_today_py", "B")
    assert outcome.points_awarded == 50 and outcome.badges_awarded == ()


# ==========================
# Zero-point policy
# ==========================

def zero_point_repo():
    return FakeRepository(challenges=[{**V1_ROW, "points": 0}])


def test_zero_point_policy_record_writes_a_zero_ledger_row():
    adapter, repo = make_adapter(zero_point_repo(), ld.ZeroPointPolicy.RECORD)
    outcome = adapter.submit_daily_challenge(ALICE, "chal_today_py", "B")
    assert (outcome.points_awarded, outcome.ledger_recorded, outcome.badges_awarded) == (0, True, ("daily_striker",))
    assert [e.points_delta for e in repo.ledger.values()] == [0]


def test_zero_point_policy_skip_writes_no_ledger_row_but_keeps_v1_badge():
    adapter, repo = make_adapter(zero_point_repo(), ld.ZeroPointPolicy.SKIP)
    outcome = adapter.submit_daily_challenge(ALICE, "chal_today_py", "B")
    assert (outcome.points_awarded, outcome.ledger_recorded, outcome.badges_awarded) == (0, False, ("daily_striker",))
    assert repo.ledger == {} and (ALICE, "chal_today_py") in repo.submissions


# ==========================
# Trusted configuration and failures
# ==========================

@pytest.mark.parametrize("bad_row", [
    {**V1_ROW, "points": -5},
    {**V1_ROW, "points": True},
    {**V1_ROW, "correct_option": "E"},
    {**V1_ROW, "explanation": None},
    {"id": "chal_today_py", "correct_option": "B"},            # missing fields
])
def test_invalid_trusted_configuration_is_rejected_without_writes(bad_row):
    adapter, repo = make_adapter(FakeRepository(challenges=[bad_row]))
    with pytest.raises(gs.InvalidTrustedInputError):
        adapter.submit_daily_challenge(ALICE, "chal_today_py", "B")
    assert repo.submissions == {} and repo.ledger == {}


@pytest.mark.parametrize("user_id", ["", "usr 1", "usr:1", None, "u" * 65])
def test_malformed_authenticated_user_ids_are_rejected(user_id):
    adapter, repo = make_adapter()
    with pytest.raises(gs.InvalidTrustedInputError):
        adapter.submit_daily_challenge(user_id, "chal_today_py", "B")
    with pytest.raises(gs.InvalidTrustedInputError):
        adapter.award_assessment_badges(user_id, 5, 5, "subj_python", "Python Programming")
    assert repo.submissions == {}


@pytest.mark.parametrize("stage", ["ledger", "badges"])
def test_transaction_failure_leaves_no_partial_state(stage):
    repo = FakeRepository(fail_on=stage)
    adapter, _ = make_adapter(repo)
    before = repo.snapshot()
    with pytest.raises(FakeTransactionError):                  # errors propagate, not swallowed
        adapter.submit_daily_challenge(ALICE, "chal_today_py", "B")
    assert repo.snapshot() == before
    repo.fail_on = None
    assert adapter.submit_daily_challenge(ALICE, "chal_today_py", "B").points_awarded == 50   # retry is clean


# ==========================
# Assessment badges and legacy equivalence
# ==========================

def test_existing_py_master_suppresses_the_equivalent_high_score_badge():
    repo = FakeRepository(badges={ALICE: {"py_master"}})
    adapter, _ = make_adapter(repo)
    assert adapter.award_assessment_badges(ALICE, 5, 5, "subj_python", "Python Programming") == ()
    assert repo.badges[ALICE] == {"py_master"}


def test_new_high_score_badge_is_awarded_once():
    adapter, repo = make_adapter()
    assert adapter.award_assessment_badges(ALICE, 4, 5, "subj_python", "Python Programming") == (PY_HIGH,)
    assert adapter.award_assessment_badges(ALICE, 5, 5, "subj_python", "Python Programming") == ()
    assert repo.badges[ALICE] == {PY_HIGH}


def test_py_master_does_not_block_other_subjects_or_low_scores():
    repo = FakeRepository(badges={ALICE: {"py_master"}})
    adapter, _ = make_adapter(repo)
    assert adapter.award_assessment_badges(ALICE, 5, 5, "subj_datasci", "Data Science & ML") == (
        "assessment.subj_datasci.high_score",
    )
    assert adapter.award_assessment_badges(BOB, 3, 5, "subj_python", "Python Programming") == ()


def test_badge_transaction_failure_leaves_no_partial_state():
    repo = FakeRepository(fail_on="badges")
    adapter, _ = make_adapter(repo)
    with pytest.raises(FakeTransactionError):
        adapter.award_assessment_badges(ALICE, 5, 5, "subj_python", "Python Programming")
    assert repo.badges == {}


# ==========================
# Purity and unchanged domain behaviour
# ==========================

def test_adapter_does_no_sql_network_clock_or_file_access(monkeypatch):
    adapter, _ = make_adapter()

    def forbidden(*args, **kwargs):
        raise AssertionError("adapter must not touch I/O directly")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    adapter.submit_daily_challenge(ALICE, "chal_today_py", "B")
    adapter.submit_daily_challenge(BOB, "chal_today_py", "A")
    adapter.award_assessment_badges(ALICE, 5, 5, "subj_python", "Python Programming")
    adapter.get_points_summary(ALICE)


def test_adapter_source_imports_only_stdlib_and_owned_domain_modules():
    tree = ast.parse((SERVICES_DIR / "gamification_integration.py").read_text(encoding="utf-8"))
    absolute, relative, attributes = set(), set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            absolute |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            (relative if node.level else absolute).add(node.module.split(".")[0])
        elif isinstance(node, ast.Attribute):
            attributes.add(node.attr)
    assert absolute <= set(sys.stdlib_module_names), absolute
    assert not absolute & {"sqlite3", "os", "io", "socket", "http", "urllib", "random", "secrets", "time", "datetime", "uuid", "threading"}
    assert relative == {"gamification_service", "points_ledger_domain"}
    assert not attributes & {"now", "today", "utcnow", "execute", "connect"}


def test_existing_domain_functions_keep_their_behaviour():
    decision = gs.compute_challenge_reward(gs.ChallengeConfig("chal_today_py", "B", 50), "B", already_completed=False)
    assert (decision.points_awarded, decision.reason) == (50, gs.RewardReason.CORRECT_ANSWER)
    assert gs.reward_event_key(ALICE, "daily_challenge", "chal_today_py") == f"daily_challenge:chal_today_py:{ALICE}"
    assert gs.filter_new_achievements(gs.eligible_assessment_achievements(5, 5, "subj_python", "P"), {"py_master"}) == ()
    assert ld.decide_challenge_ledger_award(
        ALICE, decision, event_id="rwd_1", origin=ld.LedgerOrigin.LIVE, zero_point_policy=ld.ZeroPointPolicy.SKIP
    ).event.points_delta == 50
