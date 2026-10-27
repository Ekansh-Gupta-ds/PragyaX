"""
GamificationRepository contract tests (Ankush). See docs/GAMIFICATION_REPOSITORY_CONTRACT.md.

Every test runs once per *backend*:
- "fake"     : ContractFakeRepository below. Always runs. In-memory, single-threaded; it proves the
               contract's expected behaviour, NOT database atomicity or concurrency.
- "sqlite"   : opt-in. Runs only if PRAGYAX_CONTRACT_SQLITE_FACTORY="module:callable" is set.
               The factory gets a fresh temp file outside the repository.
- "postgres" : opt-in. Runs only if PRAGYAX_CONTRACT_POSTGRES_FACTORY and TEST_DATABASE_URL are set
               and TEST_DATABASE_URL passes the same isolation guard as test_postgres_student_journey.py
               (local host, database 'pragyax_test', not Supabase, not DATABASE_URL).
No real implementation exists yet, so by default only "fake" runs and no database is ever contacted.

Factory signature (for future implementations):
    factory(seed: ContractSeed, *, database: str) -> GamificationRepository
where `database` is a temp SQLite path or the guarded TEST_DATABASE_URL. The factory must create the
seeded users, challenge rows and badges. It may expose an optional hook
`contract_fail_next_write(stage: str)` (stage: "ledger" | "badges") to enable rollback tests;
backends without it skip those tests.

Service modules are loaded under a throwaway package so backend/app/services/__init__.py (which
imports the repository and config) never runs here.
"""

import ast
import importlib
import importlib.util
import json
import os
import sys
import threading
import types
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SERVICES_DIR = REPO_ROOT / "backend" / "app" / "services"
_PACKAGE = "pragyax_services_repository_contract"


def _load(module_name):
    if _PACKAGE not in sys.modules:
        package = types.ModuleType(_PACKAGE)
        package.__path__ = [str(SERVICES_DIR)]
        sys.modules[_PACKAGE] = package
    full_name = f"{_PACKAGE}.{module_name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    spec = importlib.util.spec_from_file_location(full_name, SERVICES_DIR / f"{module_name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


gi = _load("gamification_integration")
gs = sys.modules[f"{_PACKAGE}.gamification_service"]
ld = sys.modules[f"{_PACKAGE}.points_ledger_domain"]

ALICE, BOB = "usr_alice01", "usr_bob0002"
PY_HIGH = "assessment.subj_python.high_score"

# Full V1 seed row (connection.py), so real factories can satisfy every NOT NULL column.
V1_CHALLENGE = {
    "id": "chal_today_py", "title": "Python Daily Challenge: The List Mutation Trap",
    "topic": "Python List References & Shallow Copying", "difficulty": "Medium",
    "description": "Determine the final output of the matrix operation.",
    "code_snippet": "matrix = [[0] * 3] * 3\nmatrix[0][0] = 7\nprint([row[0] for row in matrix])",
    "question_type": "multiple_choice",
    "option_a": "[7, 0, 0]", "option_b": "[7, 7, 7]",
    "option_c": "[[7, 0, 0], [0, 0, 0], [0, 0, 0]]", "option_d": "A TypeError occurs during inner assignment",
    "correct_option": "B", "explanation": "The outer multiplication shares one inner list.", "points": 50,
}
SECOND_CHALLENGE = {**V1_CHALLENGE, "id": "chal_second_py", "correct_option": "C", "points": 30}


@dataclass(frozen=True)
class ContractSeed:
    users: tuple[str, ...] = (ALICE, BOB)
    challenges: tuple[dict, ...] = (V1_CHALLENGE, SECOND_CHALLENGE)
    badges: dict = field(default_factory=dict)        # user_id -> iterable of badge_key


# ==========================
# Reference fake (simulation only)
# ==========================

class ContractFakeRepository:
    """Minimal in-memory implementation of the protocol. Each write stages copies and commits
    at the end; contract_fail_next_write() injects one failure at a given stage."""

    def __init__(self, seed: ContractSeed):
        self._users = set(seed.users)
        self._challenges = {row["id"]: dict(row) for row in seed.challenges}
        self._submissions = {}                         # (user, challenge) -> ChallengeWrite
        self._ledger = {}                              # event_key -> LedgerEvent
        self._badges = {u: set(keys) for u, keys in seed.badges.items()}
        self._fail_stage = None

    def contract_fail_next_write(self, stage):
        self._fail_stage = stage

    def _maybe_fail(self, stage):
        if self._fail_stage == stage:
            self._fail_stage = None
            raise RuntimeError(f"injected failure at {stage}")

    def get_challenge(self, challenge_id):
        row = self._challenges.get(challenge_id)
        return dict(row) if row is not None else None

    def has_completed_challenge(self, user_id, challenge_id):
        return (user_id, challenge_id) in self._submissions

    def get_badge_keys(self, user_id):
        return frozenset(self._badges.get(user_id, ()))

    def record_challenge_outcome(self, write):
        if not isinstance(write, gi.ChallengeWrite):
            raise TypeError("write must be a ChallengeWrite")
        if write.user_id not in self._users or write.challenge_id not in self._challenges:
            raise LookupError("unknown user or challenge (a real DB raises on the foreign key)")
        key = (write.user_id, write.challenge_id)
        if key in self._submissions:
            return gi.WriteResult.ALREADY_COMPLETED
        submissions, ledger = dict(self._submissions), dict(self._ledger)
        badges = {u: set(k) for u, k in self._badges.items()}
        submissions[key] = write
        if write.ledger_event is not None:
            ledger.setdefault(write.ledger_event.event_key, write.ledger_event)
        self._maybe_fail("ledger")
        for award in write.badges:
            badges.setdefault(write.user_id, set()).add(award.badge_key)
        self._maybe_fail("badges")
        self._submissions, self._ledger, self._badges = submissions, ledger, badges
        return gi.WriteResult.INSERTED

    def insert_badges(self, user_id, awards):
        if user_id not in self._users:
            raise LookupError("unknown user")
        if not all(isinstance(a, gs.AchievementAward) for a in awards):
            raise TypeError("awards must be AchievementAward items")
        held = set(self._badges.get(user_id, ()))
        inserted = []
        for award in awards:
            if award.badge_key not in held:
                held.add(award.badge_key)
                inserted.append(award.badge_key)
        self._maybe_fail("badges")
        self._badges[user_id] = held
        return tuple(inserted)

    def get_reward_records(self, user_id):
        return [gs.RewardRecord(e.event_key, e.points_delta) for e in self._ledger.values() if e.user_id == user_id]


def fake_factory(seed, *, database):
    return ContractFakeRepository(seed)


# ==========================
# Backend selection (opt-in real backends)
# ==========================

def _load_factory(spec):
    module_name, _, attr = spec.partition(":")
    if not module_name or not attr:
        pytest.fail(f"factory spec must be 'module:callable', got {spec!r}")
    return getattr(importlib.import_module(module_name), attr)


def _guarded_test_database_url():
    """Same isolation rules as test_postgres_student_journey.py; never returns DATABASE_URL."""
    url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not url:
        return None
    prod = os.getenv("DATABASE_URL", "").strip()
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if url == prod or (prod and host == (urlparse(prod).hostname or "").lower()):
        pytest.fail("TEST_DATABASE_URL must not match DATABASE_URL")
    if host not in ("127.0.0.1", "localhost", "::1") or "supabase" in host:
        pytest.fail(f"TEST_DATABASE_URL host {host!r} is not local")
    if parsed.path.lstrip("/") != "pragyax_test":
        pytest.fail("TEST_DATABASE_URL database must be 'pragyax_test'")
    return url


@pytest.fixture(params=["fake", "sqlite", "postgres"])
def backend(request, tmp_path):
    """Returns (kind, make_repo) where make_repo(seed) builds a fresh repository."""
    kind = request.param
    if kind == "fake":
        return kind, lambda seed=ContractSeed(): fake_factory(seed, database="memory")
    if kind == "sqlite":
        spec = os.getenv("PRAGYAX_CONTRACT_SQLITE_FACTORY", "").strip()
        if not spec:
            pytest.skip("no SQLite GamificationRepository implementation yet (set PRAGYAX_CONTRACT_SQLITE_FACTORY)")
        db_file = tmp_path / "gamification_contract.db"
        if REPO_ROOT in db_file.resolve().parents:
            pytest.fail("contract SQLite database must live outside the repository")
        factory = _load_factory(spec)
        return kind, lambda seed=ContractSeed(): factory(seed, database=str(db_file))
    spec = os.getenv("PRAGYAX_CONTRACT_POSTGRES_FACTORY", "").strip()
    if not spec:
        pytest.skip("no PostgreSQL GamificationRepository implementation yet (set PRAGYAX_CONTRACT_POSTGRES_FACTORY)")
    url = _guarded_test_database_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL not set; PostgreSQL contract tests never use DATABASE_URL")
    factory = _load_factory(spec)
    return kind, lambda seed=ContractSeed(): factory(seed, database=url)


def make_adapter(repo, policy=ld.ZeroPointPolicy.RECORD):
    counter = iter(range(1, 10**9))
    return gi.GamificationIntegration(repo, new_event_id=lambda: f"rwd_{next(counter):032x}", zero_point_policy=policy)


def write_for(user, challenge=V1_CHALLENGE, option=None, *, event_id="rwd_" + "a" * 32, badges=None):
    """A correct-answer ChallengeWrite built with the real domain functions (as the adapter would)."""
    config = gs.ChallengeConfig(challenge["id"], challenge["correct_option"], challenge["points"])
    decision = gs.compute_challenge_reward(config, option or challenge["correct_option"], already_completed=False)
    ledger = ld.decide_challenge_ledger_award(user, decision, event_id=event_id, origin=ld.LedgerOrigin.LIVE,
                                              zero_point_policy=ld.ZeroPointPolicy.RECORD)
    return gi.ChallengeWrite(user, config.challenge_id, option or challenge["correct_option"], decision.is_correct,
                             decision.points_awarded, ledger.event,
                             decision.achievements if badges is None else badges)


def total_points(repo, user):
    return gs.aggregate_points(repo.get_reward_records(user)).total_points


def require_failure_hook(kind, repo):
    hook = getattr(repo, "contract_fail_next_write", None)
    if hook is None:
        pytest.skip(f"{kind} backend exposes no contract_fail_next_write hook; rollback not testable here")
    return hook


# ==========================
# R. Repository-level contract
# ==========================

def test_r01_protocol_conformance(backend):
    _, make_repo = backend
    assert isinstance(make_repo(), gi.GamificationRepository)


def test_r02_get_challenge_returns_trusted_serialisable_row(backend):
    _, make_repo = backend
    repo = make_repo()
    row = repo.get_challenge("chal_today_py")
    assert {"id", "correct_option", "points", "explanation"} <= set(row)
    assert (row["id"], row["correct_option"], row["points"]) == ("chal_today_py", "B", 50)
    json.dumps(dict(row))                     # timestamps etc. must already be serialisable values
    assert repo.get_challenge("chal_missing") is None


def test_r03_first_write_inserts_and_marks_completion(backend):
    _, make_repo = backend
    repo = make_repo()
    assert repo.has_completed_challenge(ALICE, "chal_today_py") is False
    assert repo.record_challenge_outcome(write_for(ALICE)) is gi.WriteResult.INSERTED
    assert repo.has_completed_challenge(ALICE, "chal_today_py") is True
    assert repo.get_badge_keys(ALICE) == frozenset({"daily_striker"})
    assert total_points(repo, ALICE) == 50


def test_r04_wrong_answer_write_records_completion_without_rewards(backend):
    _, make_repo = backend
    repo = make_repo()
    wrong = gi.ChallengeWrite(ALICE, "chal_today_py", "A", False, 0, None, ())
    assert repo.record_challenge_outcome(wrong) is gi.WriteResult.INSERTED
    assert repo.has_completed_challenge(ALICE, "chal_today_py") is True
    assert list(repo.get_reward_records(ALICE)) == [] and repo.get_badge_keys(ALICE) == frozenset()


def test_r05_duplicate_submission_writes_nothing_else(backend):
    _, make_repo = backend
    repo = make_repo()
    repo.record_challenge_outcome(write_for(ALICE))
    replay = write_for(ALICE, event_id="rwd_" + "b" * 32,
                       badges=(gs.AchievementAward("extra_badge", "t", "d", "zap"),))
    assert repo.record_challenge_outcome(replay) is gi.WriteResult.ALREADY_COMPLETED
    assert repo.get_badge_keys(ALICE) == frozenset({"daily_striker"})
    assert total_points(repo, ALICE) == 50 and len(list(repo.get_reward_records(ALICE))) == 1


def test_r06_duplicate_reward_event_is_stored_once(backend):
    _, make_repo = backend
    repo = make_repo()
    first = write_for(ALICE)
    repo.record_challenge_outcome(first)
    # Same ledger event (same event_key) attached to a different submission row.
    other = gi.ChallengeWrite(ALICE, "chal_second_py", "C", True, 30, first.ledger_event, ())
    assert repo.record_challenge_outcome(other) is gi.WriteResult.INSERTED
    records = list(repo.get_reward_records(ALICE))
    assert [r.event_key for r in records] == [first.ledger_event.event_key]
    assert total_points(repo, ALICE) == 50


@pytest.mark.parametrize("stage", ["ledger", "badges"])
def test_r07_failed_write_rolls_back_and_retry_succeeds(backend, stage):
    kind, make_repo = backend
    repo = make_repo()
    require_failure_hook(kind, repo)(stage)
    with pytest.raises(Exception):
        repo.record_challenge_outcome(write_for(ALICE))
    assert repo.has_completed_challenge(ALICE, "chal_today_py") is False
    assert repo.get_badge_keys(ALICE) == frozenset() and list(repo.get_reward_records(ALICE)) == []
    assert repo.record_challenge_outcome(write_for(ALICE)) is gi.WriteResult.INSERTED
    assert total_points(repo, ALICE) == 50


def test_r08_badge_inserts_are_idempotent(backend):
    _, make_repo = backend
    repo = make_repo()
    award = gs.AchievementAward(PY_HIGH, "Python Programming Virtuoso", "Scored 80%+ on the Python Programming assessment", "award")
    assert repo.insert_badges(ALICE, (award,)) == (PY_HIGH,)
    assert repo.insert_badges(ALICE, (award,)) == ()
    assert repo.get_badge_keys(ALICE) == frozenset({PY_HIGH})


def test_r09_insert_badges_reports_only_new_keys(backend):
    _, make_repo = backend
    repo = make_repo(ContractSeed(badges={ALICE: {"daily_striker"}}))
    awards = (gs.DAILY_CHALLENGE_ACHIEVEMENT, gs.AchievementAward("brand_new", "t", "d", "award"))
    assert repo.insert_badges(ALICE, awards) == ("brand_new",)


def test_r10_failed_badge_insert_rolls_back(backend):
    kind, make_repo = backend
    repo = make_repo()
    require_failure_hook(kind, repo)("badges")
    with pytest.raises(Exception):
        repo.insert_badges(ALICE, (gs.AchievementAward("brand_new", "t", "d", "award"),))
    assert repo.get_badge_keys(ALICE) == frozenset()


def test_r11_seeded_legacy_badges_are_visible(backend):
    _, make_repo = backend
    repo = make_repo(ContractSeed(badges={ALICE: {"py_master"}}))
    assert repo.get_badge_keys(ALICE) == frozenset({"py_master"})


def test_r12_users_are_isolated(backend):
    _, make_repo = backend
    repo = make_repo()
    repo.record_challenge_outcome(write_for(ALICE))
    assert repo.has_completed_challenge(BOB, "chal_today_py") is False
    assert repo.get_badge_keys(BOB) == frozenset()
    assert list(repo.get_reward_records(BOB)) == []
    assert repo.record_challenge_outcome(write_for(BOB, event_id="rwd_" + "c" * 32)) is gi.WriteResult.INSERTED
    assert (total_points(repo, ALICE), total_points(repo, BOB)) == (50, 50)


def test_r13_points_total_sums_distinct_events(backend):
    _, make_repo = backend
    repo = make_repo()
    repo.record_challenge_outcome(write_for(ALICE))
    repo.record_challenge_outcome(write_for(ALICE, SECOND_CHALLENGE, event_id="rwd_" + "d" * 32, badges=()))
    summary = gs.aggregate_points(repo.get_reward_records(ALICE))
    assert (summary.total_points, summary.counted_records, summary.invalid_records) == (80, 2, 0)


def test_r14_invalid_input_raises_and_writes_nothing(backend):
    _, make_repo = backend
    repo = make_repo()
    with pytest.raises(Exception):
        repo.record_challenge_outcome({"user_id": ALICE, "challenge_id": "chal_today_py", "points_awarded": 10**6})
    with pytest.raises(Exception):
        repo.insert_badges(ALICE, ({"badge_key": "forged"},))
    with pytest.raises(Exception):     # unknown user: a real DB fails on the foreign key
        repo.record_challenge_outcome(write_for("usr_nobody", event_id="rwd_" + "e" * 32))
    assert repo.has_completed_challenge(ALICE, "chal_today_py") is False
    assert repo.get_badge_keys(ALICE) == frozenset()


def test_r15_concurrent_first_submissions_award_once(backend):
    kind, make_repo = backend
    if kind == "fake":
        pytest.skip("concurrency is a real-database property; the in-memory fake cannot demonstrate it")
    repo = make_repo()
    barrier, results, errors = threading.Barrier(4), [], []

    def submit(i):
        try:
            barrier.wait()
            results.append(repo.record_challenge_outcome(write_for(ALICE, event_id=f"rwd_{i:032x}")))
        except Exception as exc:          # recorded, then asserted below
            errors.append(exc)

    threads = [threading.Thread(target=submit, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == [], errors          # conflicts must surface as ALREADY_COMPLETED, never as exceptions
    assert sorted(results) == sorted([gi.WriteResult.INSERTED] + [gi.WriteResult.ALREADY_COMPLETED] * 3)
    assert total_points(repo, ALICE) == 50


# ==========================
# A. Adapter over the repository (end-to-end, V1 semantics)
# ==========================

def test_a01_first_correct_submission_v1_response(backend):
    _, make_repo = backend
    repo = make_repo()
    outcome = make_adapter(repo).submit_daily_challenge(ALICE, "chal_today_py", "b")
    assert outcome.to_v1_response() == {
        "challenge_id": "chal_today_py", "is_correct": True, "points_awarded": 50,
        "correct_option": "B", "explanation": V1_CHALLENGE["explanation"],
    }
    assert make_adapter(repo).get_points_summary(ALICE).total_points == 50


def test_a02_wrong_answer_then_retry_is_blocked(backend):
    _, make_repo = backend
    adapter = make_adapter(make_repo())
    wrong = adapter.submit_daily_challenge(ALICE, "chal_today_py", "A")
    assert (wrong.is_correct, wrong.points_awarded) == (False, 0)
    retry = adapter.submit_daily_challenge(ALICE, "chal_today_py", "B")
    assert retry.v1_error_detail == "Challenge already completed by this user today"
    assert adapter.get_points_summary(ALICE).total_points == 0


def test_a03_duplicate_and_invalid_inputs_use_v1_messages(backend):
    _, make_repo = backend
    adapter = make_adapter(make_repo())
    adapter.submit_daily_challenge(ALICE, "chal_today_py", "B")
    assert adapter.submit_daily_challenge(ALICE, "chal_today_py", "B").v1_error_detail == \
        "Challenge already completed by this user today"
    assert adapter.submit_daily_challenge(ALICE, "chal_today_py", "Z").v1_error_detail == \
        "selected_option must be A, B, C, or D."
    assert adapter.submit_daily_challenge(ALICE, "chal_missing", "B").v1_error_detail == "Challenge not found"
    assert adapter.get_points_summary(ALICE).total_points == 50


def test_a04_legacy_py_master_blocks_python_high_score(backend):
    _, make_repo = backend
    repo = make_repo(ContractSeed(badges={ALICE: {"py_master"}}))
    adapter = make_adapter(repo)
    assert adapter.award_assessment_badges(ALICE, 5, 5, "subj_python", "Python Programming") == ()
    assert adapter.award_assessment_badges(BOB, 5, 5, "subj_python", "Python Programming") == (PY_HIGH,)
    assert adapter.award_assessment_badges(BOB, 5, 5, "subj_python", "Python Programming") == ()
    assert repo.get_badge_keys(ALICE) == frozenset({"py_master"})


def test_a05_v1_contract_matches_the_actual_v1_sources():
    """Backend-independent: the adapter's V1 shapes must equal what the V1 code declares."""
    schema = ast.parse((REPO_ROOT / "backend/app/schemas/challenges.py").read_text(encoding="utf-8"))
    (response_cls,) = [n for n in schema.body if isinstance(n, ast.ClassDef) and n.name == "ChallengeResultResponse"]
    fields = [n.target.id for n in response_cls.body if isinstance(n, ast.AnnAssign)]
    sample = gi.ChallengeSubmissionOutcome(gi.SubmissionStatus.ACCEPTED, "chal_today_py", True, 50, "B", "x")
    assert list(sample.to_v1_response()) == fields

    router = (REPO_ROOT / "backend/app/routers/challenges.py").read_text(encoding="utf-8")
    repository = (REPO_ROOT / "backend/app/database/repository.py").read_text(encoding="utf-8")
    assert f'"{gi.V1_INVALID_OPTION_DETAIL}"' in router
    assert f'"{gi.V1_NOT_FOUND_DETAIL}"' in repository
    assert f'"{gi.V1_ALREADY_COMPLETED_DETAIL}"' in repository
