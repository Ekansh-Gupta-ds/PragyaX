"""
Unit tests for backend/app/services/points_ledger_domain.py (Ankush's module).

Pure-function tests: no database, no FastAPI app, no shared mutable state; any order works.
The module uses a relative import of gamification_service, so it is loaded under a
throwaway package whose __path__ is the services folder. That runs only the two service
files, never backend/app/services/__init__.py, which imports the repository and config
(see test_gamification_service.py for why that matters to test_api_flow.py).
"""

import ast
import builtins
import dataclasses
import importlib.util
import sqlite3
import sys
import types
from pathlib import Path

import pytest

SERVICES_DIR = Path(__file__).resolve().parents[1] / "app" / "services"
_PACKAGE = "pragyax_services_ledger_under_test"


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


ld = _load("points_ledger_domain")
gs = sys.modules[f"{_PACKAGE}.gamification_service"]  # the exact module ld imported

USER = "usr_ab12cd34ef56"
LIVE_ID = "rwd_0123456789abcdef0123456789abcdef"


def live_event(**overrides):
    kwargs = dict(
        event_id=LIVE_ID, user_id=USER, source_type="daily_challenge", source_id="chal_today_py",
        points=50, reason=gs.RewardReason.CORRECT_ANSWER, origin=ld.LedgerOrigin.LIVE, badge_key="daily_striker",
    )
    kwargs.update(overrides)
    return ld.prepare_ledger_event(**kwargs)


def challenge_decision(selected="B", points=50, already_completed=False):
    config = gs.ChallengeConfig("chal_today_py", "B", points)
    return gs.compute_challenge_reward(config, selected, already_completed=already_completed)


def decide(decision, policy=ld.ZeroPointPolicy.RECORD, **kwargs):
    kwargs.setdefault("event_id", LIVE_ID)
    kwargs.setdefault("origin", ld.LedgerOrigin.LIVE)
    return ld.decide_challenge_ledger_award(USER, decision, zero_point_policy=policy, **kwargs)


# ==========================
# Building events
# ==========================

def test_valid_positive_points_event():
    event = live_event()
    assert event == ld.LedgerEvent(
        event_id=LIVE_ID,
        event_key="daily_challenge:chal_today_py:usr_ab12cd34ef56",
        user_id=USER,
        source_type="daily_challenge",
        source_id="chal_today_py",
        points_delta=50,
        reason=gs.RewardReason.CORRECT_ANSWER,
        origin=ld.LedgerOrigin.LIVE,
        badge_key="daily_striker",
    )


def test_zero_point_event_is_valid():
    assert live_event(points=0).points_delta == 0


def test_badge_reference_is_optional():
    assert live_event(badge_key=None).badge_key is None


def test_string_enum_values_are_accepted_and_normalised():
    event = live_event(reason="correct_answer", origin="live")
    assert event.reason is gs.RewardReason.CORRECT_ANSWER
    assert event.origin is ld.LedgerOrigin.LIVE


@pytest.mark.parametrize("points", [-1, -50, True, False, 1.5, "50", None])
def test_negative_or_non_integer_points_are_rejected(points):
    with pytest.raises(gs.InvalidTrustedInputError):
        live_event(points=points)


@pytest.mark.parametrize("field, value", [
    ("user_id", ""), ("user_id", "usr 1"), ("user_id", "usr:1"), ("user_id", None), ("user_id", "u" * 65),
    ("source_type", ""), ("source_type", "daily:challenge"), ("source_type", "s" * 33),
    ("source_id", ""), ("source_id", "chal today"), ("source_id", "chal_today_py\n"), ("source_id", "c" * 65),
])
def test_malformed_user_and_source_identifiers_are_rejected(field, value):
    with pytest.raises(gs.InvalidTrustedInputError):
        live_event(**{field: value})


@pytest.mark.parametrize("event_id", ["", "evt_123", "rwd_", "rwd_12 34", "rwd_12-34", None, "rwd_" + "a" * 61])
def test_malformed_event_ids_are_rejected(event_id):
    with pytest.raises(gs.InvalidTrustedInputError):
        live_event(event_id=event_id)


@pytest.mark.parametrize("reason", [gs.RewardReason.INCORRECT_ANSWER, gs.RewardReason.ALREADY_COMPLETED, "bonus", None])
def test_non_reward_or_unknown_reasons_are_rejected(reason):
    with pytest.raises(gs.InvalidTrustedInputError):
        live_event(reason=reason)


@pytest.mark.parametrize("origin", ["manual", "", None, "LIVE"])
def test_unknown_origins_are_rejected(origin):
    with pytest.raises(gs.InvalidTrustedInputError):
        live_event(origin=origin)


@pytest.mark.parametrize("badge_key", ["", "bad key", "py:master", "b" * 65, 7])
def test_malformed_badge_references_are_rejected(badge_key):
    with pytest.raises(gs.InvalidTrustedInputError):
        live_event(badge_key=badge_key)


def test_backfill_prefix_is_reserved_for_backfill_origin():
    with pytest.raises(gs.InvalidTrustedInputError):
        live_event(event_id="rwd_v1_csub_1a2b3c4d5e")                      # live origin, backfill id
    with pytest.raises(gs.InvalidTrustedInputError):
        live_event(origin=ld.LedgerOrigin.BACKFILL_V1)                     # backfill origin, live id


# ==========================
# Idempotency keys and backfill compatibility
# ==========================

def test_event_key_is_exactly_the_existing_reward_event_key():
    event = live_event()
    assert event.event_key == gs.reward_event_key(USER, "daily_challenge", "chal_today_py")


def test_event_key_is_stable_and_independent_of_event_id_points_and_origin():
    a = live_event()
    b = live_event(event_id="rwd_ffffffffffffffffffffffffffffffff", points=0, badge_key=None)
    c = live_event(event_id=ld.backfill_event_id("csub_1a2b3c4d5e"), origin=ld.LedgerOrigin.BACKFILL_V1)
    assert a.event_key == b.event_key == c.event_key


def test_event_keys_differ_per_user_and_per_challenge():
    keys = {
        live_event().event_key,
        live_event(user_id="usr_other").event_key,
        live_event(source_id="chal_tomorrow_py").event_key,
    }
    assert len(keys) == 3


def test_backfill_identity_matches_the_planned_sql():
    # Plan §4.2: id = 'rwd_v1_' || s.id ; event_key = 'daily_challenge:' || challenge_id || ':' || user_id
    submission = {"id": "csub_1a2b3c4d5e", "user_id": USER, "challenge_id": "chal_today_py", "points_awarded": 50}
    event = ld.prepare_ledger_event(
        event_id=ld.backfill_event_id(submission["id"]),
        user_id=submission["user_id"],
        source_type=ld.DAILY_CHALLENGE_SOURCE,
        source_id=submission["challenge_id"],
        points=submission["points_awarded"],
        reason=gs.RewardReason.CORRECT_ANSWER,
        origin=ld.LedgerOrigin.BACKFILL_V1,
        badge_key="daily_striker",
    )
    assert event.event_id == "rwd_v1_" + submission["id"]
    assert event.event_key == "daily_challenge:" + submission["challenge_id"] + ":" + submission["user_id"]
    # A live award for the same submission collides on event_key, so the DB keeps only one.
    assert event.event_key == live_event().event_key


@pytest.mark.parametrize("submission_id", ["", "csub 1", "csub-1", "csub:1", None, "c" * 58])
def test_malformed_submission_ids_are_rejected(submission_id):
    with pytest.raises(gs.InvalidTrustedInputError):
        ld.backfill_event_id(submission_id)


def test_longest_backfill_id_fits_the_column():
    assert len(ld.backfill_event_id("c" * 57)) == ld.MAX_EVENT_ID_LENGTH


# ==========================
# Challenge ledger decisions
# ==========================

def test_correct_answer_produces_a_ledger_event():
    result = decide(challenge_decision())
    assert result.reason is ld.LedgerDecisionReason.RECORD and result.should_record
    assert (result.event.points_delta, result.event.badge_key) == (50, "daily_striker")
    assert result.event.event_key == "daily_challenge:chal_today_py:" + USER


@pytest.mark.parametrize("decision", [
    challenge_decision(selected="A"),                          # wrong answer
    challenge_decision(selected="B", already_completed=True),  # repeat
])
def test_wrong_and_repeat_submissions_never_produce_a_row(decision):
    for policy in ld.ZeroPointPolicy:
        result = decide(decision, policy)
        assert result == ld.LedgerAwardDecision(ld.LedgerDecisionReason.NOT_A_REWARD)
        assert result.should_record is False


def test_zero_point_reward_follows_the_explicit_policy():
    zero = challenge_decision(points=0)
    recorded = decide(zero, ld.ZeroPointPolicy.RECORD)
    skipped = decide(zero, ld.ZeroPointPolicy.SKIP)
    assert recorded.should_record and recorded.event.points_delta == 0
    assert skipped == ld.LedgerAwardDecision(ld.LedgerDecisionReason.ZERO_POINTS_SKIPPED)
    # V1 parity: the challenge decision itself (and its badge) is unaffected by ledger policy.
    assert zero.achievements == (gs.DAILY_CHALLENGE_ACHIEVEMENT,)


def test_skip_policy_does_not_affect_positive_rewards():
    assert decide(challenge_decision(), ld.ZeroPointPolicy.SKIP).event.points_delta == 50


def test_zero_point_policy_has_no_default():
    with pytest.raises(TypeError):
        ld.decide_challenge_ledger_award(USER, challenge_decision(), event_id=LIVE_ID, origin=ld.LedgerOrigin.LIVE)
    for bad in (None, "", "maybe"):
        with pytest.raises(gs.InvalidTrustedInputError):
            decide(challenge_decision(), bad)


def test_decision_input_must_be_a_challenge_reward_decision():
    forged = {"challenge_id": "chal_today_py", "points_awarded": 10**6, "reason": "correct_answer"}
    with pytest.raises(gs.InvalidTrustedInputError):
        decide(forged)


def test_more_than_one_badge_cannot_be_referenced():
    two = dataclasses.replace(challenge_decision(), achievements=(gs.DAILY_CHALLENGE_ACHIEVEMENT,) * 2)
    with pytest.raises(gs.InvalidTrustedInputError):
        decide(two)


def test_decision_validates_user_and_event_id():
    with pytest.raises(gs.InvalidTrustedInputError):
        ld.decide_challenge_ledger_award("bad user", challenge_decision(), event_id=LIVE_ID,
                                         origin=ld.LedgerOrigin.LIVE, zero_point_policy=ld.ZeroPointPolicy.RECORD)
    with pytest.raises(gs.InvalidTrustedInputError):
        decide(challenge_decision(), event_id="not_an_id")


# ==========================
# Determinism, immutability, purity
# ==========================

def test_repeated_calls_are_deterministic():
    assert len({live_event() for _ in range(5)}) == 1
    assert len({decide(challenge_decision()) for _ in range(5)}) == 1
    assert ld.backfill_event_id("csub_1") == ld.backfill_event_id("csub_1")


def test_models_are_immutable():
    event = live_event()
    decision = decide(challenge_decision())
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.points_delta = 10**6
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.event = None


def test_inputs_are_not_mutated():
    decision = challenge_decision()
    snapshot = dataclasses.replace(decision)
    decide(decision)
    assert decision == snapshot


def test_no_filesystem_or_database_side_effects(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError("pure ledger domain must not do I/O")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.chdir(tmp_path)
    live_event()
    decide(challenge_decision())
    decide(challenge_decision(points=0), ld.ZeroPointPolicy.SKIP)
    ld.backfill_event_id("csub_1")
    monkeypatch.undo()
    assert list(tmp_path.iterdir()) == []


def test_uses_only_the_standard_library_and_the_gamification_service():
    tree = ast.parse((SERVICES_DIR / "points_ledger_domain.py").read_text(encoding="utf-8"))
    absolute, relative = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            absolute |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            (relative if node.level else absolute).add(node.module.split(".")[0])
    assert absolute <= set(sys.stdlib_module_names), absolute
    assert not absolute & {"sqlite3", "os", "io", "socket", "http", "urllib", "subprocess", "random", "time", "datetime", "uuid"}
    assert relative == {"gamification_service"}
