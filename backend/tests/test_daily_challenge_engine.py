"""
Unit tests for backend/app/services/daily_challenge_engine.py (Ankush's module).

Pure-function tests: no database, no FastAPI app, no clock, no shared mutable state; any
order works. The engine uses a relative import of gamification_service, so it is loaded
under a throwaway package whose __path__ is the services folder. That never runs
backend/app/services/__init__.py, which imports the repository and config
(see test_gamification_service.py for why that matters to test_api_flow.py).
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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

SERVICES_DIR = Path(__file__).resolve().parents[1] / "app" / "services"
_PACKAGE = "pragyax_services_challenge_engine_under_test"


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


ce = _load("daily_challenge_engine")
ld = _load("points_ledger_domain")
gs = sys.modules[f"{_PACKAGE}.gamification_service"]

IST = timezone(timedelta(hours=5, minutes=30))   # fixed offset: no tz database needed


def challenge(challenge_id, subject_id="subj_python", correct="B", points=50, **overrides):
    fields = dict(
        challenge_id=challenge_id, subject_id=subject_id, title=f"Title {challenge_id}", topic="Lists",
        difficulty="Medium", description="What is printed?", code_snippet="print(1)",
        option_a="1", option_b="2", option_c="3", option_d="4",
        correct_option=correct, explanation="Because.", points=points,
    )
    fields.update(overrides)
    return ce.ChallengeDefinition(**fields)


def pool(subject_id, *ids):
    return ce.ChallengePool(subject_id, tuple(challenge(i, subject_id) for i in ids))


PY_POOL_IDS = ("py_a", "py_b", "py_c")


# ==========================
# Models and validation
# ==========================

def test_v1_seed_challenge_is_representable():
    # Same id, answer and points as the V1 seed row (connection.py); V1 itself is untouched.
    seed = challenge("chal_today_py", correct="B", points=50)
    assert (seed.challenge_id, seed.correct_option, seed.points) == ("chal_today_py", "B", 50)


@pytest.mark.parametrize("bad_id", ["", "chal today", "chal:1", "chal\n", None, 7, "c" * 65])
def test_malformed_challenge_ids_are_rejected(bad_id):
    with pytest.raises(gs.InvalidTrustedInputError):
        challenge(bad_id)


@pytest.mark.parametrize("bad_subject", ["", "subj python", "subj.python", None])
def test_malformed_subject_ids_are_rejected(bad_subject):
    with pytest.raises(gs.InvalidTrustedInputError):
        challenge("py_a", subject_id=bad_subject)
    with pytest.raises(gs.InvalidTrustedInputError):
        ce.ChallengePool(bad_subject, (challenge("py_a"),))


@pytest.mark.parametrize("overrides", [
    {"correct": "E"}, {"correct": ""}, {"points": -1}, {"points": True}, {"points": 1.5},
    {"title": " "}, {"option_c": ""}, {"explanation": None}, {"question_type": "essay"},
])
def test_invalid_challenge_fields_are_rejected(overrides):
    with pytest.raises(gs.InvalidTrustedInputError):
        challenge("py_a", **overrides)


def test_empty_pool_is_rejected():
    for empty in ((), [], iter(())):
        with pytest.raises(gs.InvalidTrustedInputError):
            ce.ChallengePool("subj_python", empty)


def test_duplicate_challenge_ids_are_rejected():
    with pytest.raises(gs.InvalidTrustedInputError):
        ce.ChallengePool("subj_python", (challenge("py_a"), challenge("py_b"), challenge("py_a", title="Other")))


def test_pool_rejects_challenges_from_another_subject_or_wrong_types():
    with pytest.raises(gs.InvalidTrustedInputError):
        ce.ChallengePool("subj_python", (challenge("py_a"), challenge("ds_a", "subj_datasci")))
    with pytest.raises(gs.InvalidTrustedInputError):
        ce.ChallengePool("subj_python", ({"challenge_id": "py_a"},))
    with pytest.raises(gs.InvalidTrustedInputError):
        ce.ChallengePool("subj_python", "py_a")


# ==========================
# Dates
# ==========================

@pytest.mark.parametrize("text, expected", [
    ("2026-10-27", date(2026, 10, 27)),
    ("2028-02-29", date(2028, 2, 29)),      # leap day
    ("2000-02-29", date(2000, 2, 29)),      # leap year divisible by 400
    ("2026-12-31", date(2026, 12, 31)),
])
def test_valid_iso_dates_parse(text, expected):
    assert ce.parse_challenge_date(text) == expected


@pytest.mark.parametrize("text", [
    "2027-02-29", "1900-02-29", "2026-13-01", "2026-00-10", "2026-04-31",
    "20261027", "2026-10-27T00:00:00", " 2026-10-27", "2026/10/27", "27-10-2026", "", None, 20261027,
])
def test_malformed_dates_are_rejected(text):
    with pytest.raises(gs.InvalidTrustedInputError):
        ce.parse_challenge_date(text)


@pytest.mark.parametrize("bad", ["2026-10-27", datetime(2026, 10, 27, 12, tzinfo=timezone.utc), None, 20261027])
def test_selection_requires_a_plain_date(bad):
    with pytest.raises(gs.InvalidTrustedInputError):
        ce.select_daily_challenge(pool("subj_python", *PY_POOL_IDS), bad)


def test_challenge_date_uses_the_platform_timezone_boundary():
    late_utc = datetime(2026, 10, 27, 20, 0, tzinfo=timezone.utc)   # 01:30 on the 28th in IST
    assert ce.challenge_date_for(late_utc, timezone.utc) == date(2026, 10, 27)
    assert ce.challenge_date_for(late_utc, IST) == date(2026, 10, 28)
    just_before_midnight_ist = datetime(2026, 10, 27, 18, 29, 59, tzinfo=timezone.utc)
    assert ce.challenge_date_for(just_before_midnight_ist, IST) == date(2026, 10, 27)


def test_naive_datetimes_and_bad_timezones_are_rejected():
    with pytest.raises(gs.InvalidTrustedInputError):
        ce.challenge_date_for(datetime(2026, 10, 27, 12), timezone.utc)
    with pytest.raises(gs.InvalidTrustedInputError):
        ce.challenge_date_for(date(2026, 10, 27), timezone.utc)
    with pytest.raises(gs.InvalidTrustedInputError):
        ce.challenge_date_for(datetime(2026, 10, 27, tzinfo=timezone.utc), "Asia/Kolkata")


# ==========================
# Selection
# ==========================

def test_same_date_gives_same_challenge():
    p = pool("subj_python", *PY_POOL_IDS)
    day = date(2026, 10, 27)
    assert len({ce.select_daily_challenge(p, day).challenge_id for _ in range(10)}) == 1


def test_consecutive_dates_rotate_round_robin_in_id_order():
    p = pool("subj_python", *PY_POOL_IDS)
    start = date(2026, 10, 27)
    picked = [ce.select_daily_challenge(p, start + timedelta(days=i)).challenge_id for i in range(7)]
    first = PY_POOL_IDS.index(picked[0])
    assert picked == [PY_POOL_IDS[(first + i) % 3] for i in range(7)]   # documented: index = ordinal % len
    assert picked[0] == PY_POOL_IDS[start.toordinal() % 3]
    assert picked[0] == picked[3] == picked[6]                           # repeats every len(pool) days


def test_rotation_crosses_month_year_and_leap_day_without_gaps():
    p = pool("subj_python", "py_a", "py_b")
    days = [date(2028, 2, 28), date(2028, 2, 29), date(2028, 3, 1), date(2027, 12, 31), date(2028, 1, 1)]
    picks = [ce.select_daily_challenge(p, d).challenge_id for d in days]
    assert picks[0] != picks[1] != picks[2]
    assert picks[3] != picks[4]


def test_selection_ignores_the_order_challenges_were_supplied_in():
    challenges = [challenge(i) for i in ("py_c", "py_a", "py_b")]
    shuffled = list(reversed(challenges))
    a = ce.ChallengePool("subj_python", tuple(challenges))
    b = ce.ChallengePool("subj_python", tuple(shuffled))
    assert a == b
    assert [c.challenge_id for c in a.challenges] == ["py_a", "py_b", "py_c"]
    for offset in range(6):
        day = date(2026, 1, 1) + timedelta(days=offset)
        assert ce.select_daily_challenge(a, day) == ce.select_daily_challenge(b, day)


def test_single_challenge_pool_always_returns_it():
    # Degenerate case = today's V1 behaviour: the same static challenge every day.
    p = pool("subj_python", "chal_today_py")
    days = [date(2026, 10, 27) + timedelta(days=i) for i in range(40)]
    assert {ce.select_daily_challenge(p, d).challenge_id for d in days} == {"chal_today_py"}


def test_subjects_use_their_own_pools():
    py, ds = pool("subj_python", *PY_POOL_IDS), pool("subj_datasci", "ds_a", "ds_b")
    day = date(2026, 10, 27)
    picks = ce.select_daily_challenges([ds, py], day)
    assert [c.subject_id for c in picks] == ["subj_datasci", "subj_python"]
    assert picks[0] == ce.select_daily_challenge(ds, day)
    assert picks[1] == ce.select_daily_challenge(py, day)
    assert picks[0].challenge_id.startswith("ds_") and picks[1].challenge_id.startswith("py_")
    assert ce.select_daily_challenges([py, ds], day) == picks          # pool order irrelevant


def test_multi_subject_selection_validates_inputs():
    py = pool("subj_python", *PY_POOL_IDS)
    with pytest.raises(gs.InvalidTrustedInputError):
        ce.select_daily_challenges([py, pool("subj_python", "py_z")], date(2026, 10, 27))
    with pytest.raises(gs.InvalidTrustedInputError):
        ce.select_daily_challenges([py, "not a pool"], date(2026, 10, 27))
    with pytest.raises(gs.InvalidTrustedInputError):
        ce.select_daily_challenges("subj_python", date(2026, 10, 27))
    assert ce.select_daily_challenges([], date(2026, 10, 27)) == ()


def test_select_requires_a_pool():
    with pytest.raises(gs.InvalidTrustedInputError):
        ce.select_daily_challenge([challenge("py_a")], date(2026, 10, 27))


# ==========================
# Learner projection
# ==========================

def test_learner_view_never_contains_the_answer_or_explanation():
    secret = challenge("py_a", correct="C", explanation="SECRET-EXPLANATION-TEXT")
    view = ce.to_learner_view(secret, date(2026, 10, 27))
    field_names = {f.name for f in dataclasses.fields(ce.LearnerChallengeView)}
    assert not field_names & {"correct_option", "explanation"}
    assert "SECRET-EXPLANATION-TEXT" not in repr(view)
    assert view.challenge_date == "2026-10-27"
    assert (view.option_c, view.points, view.question_type) == ("3", 50, "multiple_choice")


def test_learner_view_does_not_mutate_the_trusted_challenge():
    trusted = challenge("py_a", correct="C")
    before = dataclasses.replace(trusted)
    ce.to_learner_view(trusted, date(2026, 10, 27))
    assert trusted == before and trusted.correct_option == "C"   # key still available server-side


def test_learner_view_validates_inputs():
    with pytest.raises(gs.InvalidTrustedInputError):
        ce.to_learner_view({"challenge_id": "py_a"}, date(2026, 10, 27))
    with pytest.raises(gs.InvalidTrustedInputError):
        ce.to_learner_view(challenge("py_a"), "2026-10-27")


# ==========================
# Immutability, purity, compatibility
# ==========================

def test_models_are_immutable():
    p = pool("subj_python", *PY_POOL_IDS)
    view = ce.to_learner_view(p.challenges[0], date(2026, 10, 27))
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.challenges[0].correct_option = "A"
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.challenges = ()
    with pytest.raises(dataclasses.FrozenInstanceError):
        view.points = 10**6
    assert isinstance(p.challenges, tuple)


def test_caller_lists_are_not_mutated():
    supplied = [challenge("py_c"), challenge("py_a")]
    snapshot = list(supplied)
    ce.ChallengePool("subj_python", supplied)
    assert supplied == snapshot


def test_no_random_clock_network_filesystem_or_database_use(monkeypatch):
    state = random.getstate()

    def forbidden(*args, **kwargs):
        raise AssertionError("daily challenge engine must be pure")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    p = pool("subj_python", *PY_POOL_IDS)
    for i in range(30):
        day = date(2026, 1, 1) + timedelta(days=i)
        ce.to_learner_view(ce.select_daily_challenge(p, day), day)
    ce.select_daily_challenges([p], date(2026, 10, 27))
    ce.parse_challenge_date("2028-02-29")
    ce.challenge_date_for(datetime(2026, 10, 27, 20, tzinfo=timezone.utc), IST)
    monkeypatch.undo()
    assert random.getstate() == state


def test_module_has_no_clock_or_randomness_in_its_source():
    tree = ast.parse((SERVICES_DIR / "daily_challenge_engine.py").read_text(encoding="utf-8"))
    absolute, relative, attributes = set(), set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            absolute |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            (relative if node.level else absolute).add(node.module.split(".")[0])
        elif isinstance(node, ast.Attribute):
            attributes.add(node.attr)
    assert absolute <= set(sys.stdlib_module_names), absolute
    assert not absolute & {"random", "secrets", "time", "os", "io", "socket", "sqlite3", "uuid", "zoneinfo", "http", "urllib"}
    assert relative == {"gamification_service"}
    assert not attributes & {"now", "today", "utcnow", "time"}


def test_existing_gamification_and_ledger_behaviour_is_unaffected():
    decision = gs.compute_challenge_reward(gs.ChallengeConfig("chal_today_py", "B", 50), "B", already_completed=False)
    assert (decision.points_awarded, decision.achievements) == (50, (gs.DAILY_CHALLENGE_ACHIEVEMENT,))
    assert gs.reward_event_key("usr_1", "daily_challenge", "chal_today_py") == "daily_challenge:chal_today_py:usr_1"
    event = ld.decide_challenge_ledger_award(
        "usr_1", decision, event_id="rwd_abc", origin=ld.LedgerOrigin.LIVE, zero_point_policy=ld.ZeroPointPolicy.RECORD
    ).event
    assert event.event_key == "daily_challenge:chal_today_py:usr_1"


def test_selected_challenge_feeds_the_existing_reward_rules_unchanged():
    # Integration shape only (no wiring): selection -> ChallengeConfig -> existing reward decision.
    day = date(2026, 10, 27)
    picked = ce.select_daily_challenge(pool("subj_python", *PY_POOL_IDS), day)
    config = gs.ChallengeConfig(picked.challenge_id, picked.correct_option, picked.points)
    assert gs.compute_challenge_reward(config, "B", already_completed=False).points_awarded == 50
    assert gs.compute_challenge_reward(config, "A", already_completed=False).points_awarded == 0
