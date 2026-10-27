"""
BattleRepository contract tests (Ankush). See docs/BATTLE_REPOSITORY_CONTRACT.md.

The BattleRepository protocol below is PROVISIONAL and defined only here: no real repository
implements it and nothing in the application uses it. backend/app/services/battle_engine.py is
used unchanged; persistence only stores what the pure engine decides.

Backends (every backend test runs once per backend):
- "fake"     : InMemoryBattleRepository below. Always runs. Single-threaded and in-memory: it
               shows the expected behaviour, NOT database atomicity, locking or durability.
- "sqlite"   : opt-in via PRAGYAX_BATTLE_CONTRACT_SQLITE_FACTORY="module:callable"; gets a fresh temp
               file outside the repository.
- "postgres" : opt-in via PRAGYAX_BATTLE_CONTRACT_POSTGRES_FACTORY plus TEST_DATABASE_URL, guarded
               exactly like test_postgres_student_journey.py (local host, 'pragyax_test', not
               Supabase, never DATABASE_URL).
By default only "fake" runs and no database is contacted.

Factory signature: factory(*, database: str) -> BattleRepository (empty battle tables).
Optional hooks on the returned repository:
  contract_fail_next_write(stage)  stage in {"create", "start", "submit", "complete", "cancel"}
  contract_reopen() -> BattleRepository   a new instance over the same storage (restart)

Service modules are loaded under a throwaway package so backend/app/services/__init__.py
(which imports the repository and config) never runs here.
"""

import importlib
import importlib.util
import os
import sys
import threading
import types
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol, runtime_checkable
from urllib.parse import urlparse

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SERVICES_DIR = REPO_ROOT / "backend" / "app" / "services"
_PACKAGE = "pragyax_services_battle_contract"


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


be = _load("battle_engine")
gs = sys.modules[f"{_PACKAGE}.gamification_service"]


# ==========================
# 1. PROVISIONAL PROTOCOL
# ==========================

class TransitionResult(StrEnum):
    APPLIED = "applied"
    CONFLICT = "conflict"            # the guarded precondition no longer held; nothing written


class SheetResult(StrEnum):
    INSERTED = "inserted"
    ALREADY_SUBMITTED = "already_submitted"   # (battle_id, user_id) sheet exists; nothing written
    NOT_ACTIVE = "not_active"                 # battle not ACTIVE at write time; nothing written


@runtime_checkable
class BattleRepository(Protocol):
    """PROPOSED. Each mutating method is ONE transaction with a guarded precondition.
    Unknown battle ids raise LookupError. Conflicts are results, never exceptions."""

    def create_battle(self, state: "be.BattleState") -> None:
        """Insert a CREATED battle with its participants and a frozen copy of every question
        (answer keys included). Raises if battle_id exists; writes nothing then."""

    def load_battle(self, battle_id: str) -> "be.BattleState | None":
        """Full trusted state (server-side only); answer_sheets in participant (seat) order."""

    def start_battle(self, battle_id: str) -> TransitionResult:
        """CREATED -> ACTIVE (UPDATE ... WHERE status='created')."""

    def submit_answer_sheet(self, battle_id: str, sheet: "be.AnswerSheet") -> SheetResult:
        """Insert one participant's sheet and answers if the battle is ACTIVE; unique per
        (battle_id, user_id). Does not complete the battle."""

    def complete_battle(self, battle_id: str, result: "be.BattleResult") -> TransitionResult:
        """ACTIVE with both sheets and no result -> COMPLETED + result, exactly once."""

    def cancel_battle(self, battle_id: str, reason: str) -> TransitionResult:
        """CREATED, or ACTIVE with no sheets -> CANCELLED."""


# ==========================
# 2. INTENDED SERVICE FLOW (test-local; shows how a future service composes engine + repository)
# ==========================

class BattleFlow:
    """Load -> pure engine validates (raising domain errors) -> guarded write. On a write
    conflict, reload and let the engine raise the correct domain error. After an accepted
    sheet, whoever sees both sheets first completes the battle; the guard makes it exactly once."""

    def __init__(self, repo):
        self.repo = repo

    def load(self, battle_id):
        state = self.repo.load_battle(battle_id)
        if state is None:
            raise LookupError(f"unknown battle {battle_id!r}")
        return state

    def create(self, config, player_one, player_two):
        state = be.create_battle(config, player_one, player_two)
        self.repo.create_battle(state)
        return state

    def start(self, battle_id):
        be.start_battle(self.load(battle_id))
        if self.repo.start_battle(battle_id) is TransitionResult.CONFLICT:
            be.start_battle(self.load(battle_id))           # raises the precise domain error
            raise be.InvalidBattleTransitionError("start conflicted")
        return self.load(battle_id)

    def submit(self, battle_id, user_id, answers):
        answers = tuple(answers)
        decided = be.submit_answers(self.load(battle_id), user_id, answers)   # validation only
        sheet = next(s for s in decided.answer_sheets if s.user_id == user_id)
        if self.repo.submit_answer_sheet(battle_id, sheet) is not SheetResult.INSERTED:
            be.submit_answers(self.load(battle_id), user_id, answers)        # raises the precise error
            raise be.InvalidBattleTransitionError("submission conflicted")
        self._complete_if_ready(battle_id)
        return self.load(battle_id)

    def _complete_if_ready(self, battle_id):
        fresh = self.load(battle_id)
        if fresh.status is be.BattleStatus.ACTIVE and len(fresh.answer_sheets) == 2:
            self.repo.complete_battle(battle_id, be.score_battle(fresh))     # CONFLICT = someone else did it

    def cancel(self, battle_id, reason):
        be.cancel_battle(self.load(battle_id), reason)
        if self.repo.cancel_battle(battle_id, reason.strip()) is TransitionResult.CONFLICT:
            be.cancel_battle(self.load(battle_id), reason)
            raise be.InvalidBattleTransitionError("cancel conflicted")
        return self.load(battle_id)

    def view(self, battle_id, viewer_user_id):
        return be.battle_view(self.load(battle_id), viewer_user_id)


# ==========================
# 3. IN-MEMORY REFERENCE FAKE (simulation only)
# ==========================

@dataclass
class _Row:
    config: object
    participants: tuple
    status: object
    sheets: dict = field(default_factory=dict)       # user_id -> AnswerSheet
    result: object = None
    cancel_reason: object = None


class InMemoryBattleRepository:
    """Stages a copy of the row, commits by replacing it; contract_fail_next_write injects a
    failure just before commit. contract_reopen shares storage (simulated restart only)."""

    def __init__(self, storage=None):
        self._rows = storage if storage is not None else {}
        self._fail_stage = None
        self.result_writes = 0

    def contract_fail_next_write(self, stage):
        self._fail_stage = stage

    def contract_reopen(self):
        return InMemoryBattleRepository(self._rows)

    def _commit(self, stage, battle_id, row):
        if self._fail_stage == stage:
            self._fail_stage = None
            raise RuntimeError(f"injected failure at {stage}")
        self._rows[battle_id] = row

    def _row(self, battle_id):
        if battle_id not in self._rows:
            raise LookupError(f"unknown battle {battle_id!r}")
        return self._rows[battle_id]

    @staticmethod
    def _copy(row):
        return _Row(row.config, row.participants, row.status, dict(row.sheets), row.result, row.cancel_reason)

    def create_battle(self, state):
        if not isinstance(state, be.BattleState) or state.status is not be.BattleStatus.CREATED:
            raise ValueError("only a CREATED BattleState can be inserted")
        battle_id = state.config.battle_id
        if battle_id in self._rows:
            raise ValueError(f"battle {battle_id!r} already exists")
        self._commit("create", battle_id, _Row(state.config, state.participants, state.status))

    def load_battle(self, battle_id):
        row = self._rows.get(battle_id)
        if row is None:
            return None
        sheets = tuple(row.sheets[p.user_id] for p in row.participants if p.user_id in row.sheets)
        return be.BattleState(row.config, row.participants, row.status, sheets, row.result, row.cancel_reason)

    def start_battle(self, battle_id):
        row = self._row(battle_id)
        if row.status is not be.BattleStatus.CREATED:
            return TransitionResult.CONFLICT
        staged = self._copy(row)
        staged.status = be.BattleStatus.ACTIVE
        self._commit("start", battle_id, staged)
        return TransitionResult.APPLIED

    def submit_answer_sheet(self, battle_id, sheet):
        row = self._row(battle_id)
        if not isinstance(sheet, be.AnswerSheet) or all(p.user_id != sheet.user_id for p in row.participants):
            raise ValueError("sheet must belong to a participant")       # FK/participant check
        if row.status is not be.BattleStatus.ACTIVE:
            return SheetResult.NOT_ACTIVE
        if sheet.user_id in row.sheets:
            return SheetResult.ALREADY_SUBMITTED
        staged = self._copy(row)
        staged.sheets[sheet.user_id] = sheet
        self._commit("submit", battle_id, staged)
        return SheetResult.INSERTED

    def complete_battle(self, battle_id, result):
        row = self._row(battle_id)
        if row.status is not be.BattleStatus.ACTIVE or len(row.sheets) != 2 or row.result is not None:
            return TransitionResult.CONFLICT
        staged = self._copy(row)
        staged.status, staged.result = be.BattleStatus.COMPLETED, result
        self._commit("complete", battle_id, staged)
        self.result_writes += 1
        return TransitionResult.APPLIED

    def cancel_battle(self, battle_id, reason):
        row = self._row(battle_id)
        allowed = row.status is be.BattleStatus.CREATED or (row.status is be.BattleStatus.ACTIVE and not row.sheets)
        if not allowed:
            return TransitionResult.CONFLICT
        staged = self._copy(row)
        staged.status, staged.cancel_reason = be.BattleStatus.CANCELLED, reason
        self._commit("cancel", battle_id, staged)
        return TransitionResult.APPLIED


# ==========================
# 4. BACKEND SELECTION (real backends opt-in only)
# ==========================

def _guarded_test_database_url():
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


def _load_factory(spec):
    module_name, _, attr = spec.partition(":")
    if not module_name or not attr:
        pytest.fail(f"factory spec must be 'module:callable', got {spec!r}")
    return getattr(importlib.import_module(module_name), attr)


def fake_factory(*, database):
    return InMemoryBattleRepository()


@pytest.fixture(params=["fake", "sqlite", "postgres"])
def backend(request, tmp_path):
    kind = request.param
    if kind == "fake":
        return kind, fake_factory(database="memory")
    if kind == "sqlite":
        spec = os.getenv("PRAGYAX_BATTLE_CONTRACT_SQLITE_FACTORY", "").strip()
        if not spec:
            pytest.skip("no approved SQLite BattleRepository implementation (set PRAGYAX_BATTLE_CONTRACT_SQLITE_FACTORY)")
        db_file = tmp_path / "battle_contract.db"
        if REPO_ROOT in db_file.resolve().parents:
            pytest.fail("contract SQLite database must live outside the repository")
        return kind, _load_factory(spec)(database=str(db_file))
    spec = os.getenv("PRAGYAX_BATTLE_CONTRACT_POSTGRES_FACTORY", "").strip()
    if not spec:
        pytest.skip("no approved PostgreSQL BattleRepository implementation (set PRAGYAX_BATTLE_CONTRACT_POSTGRES_FACTORY)")
    url = _guarded_test_database_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL not set; battle contract tests never use DATABASE_URL")
    return kind, _load_factory(spec)(database=url)


def require_hook(kind, repo, name):
    hook = getattr(repo, name, None)
    if hook is None:
        pytest.skip(f"{kind} backend exposes no {name} hook")
    return hook


def require_real(kind, what):
    if kind == "fake":
        pytest.skip(f"{what} is a real-database property; the in-memory fake cannot demonstrate it")


# ==========================
# 5. FIXTURE DATA
# ==========================

ASHA = be.BattleParticipant("usr_asha01", "Asha")
RAVI = be.BattleParticipant("usr_ravi02", "Ravi")
MEERA = "usr_meera03"
KEYS = {"bq_1": "B", "bq_2": "C", "bq_3": "A"}
ALL_RIGHT = {"bq_1": "B", "bq_2": "C", "bq_3": "A"}
ONE_RIGHT = {"bq_1": "B", "bq_2": "A", "bq_3": "D"}


def config(battle_id="btl_001"):
    return be.BattleConfig(battle_id, tuple(
        be.BattleQuestion(q, f"Question {q}?", "a", "b", "c", "d", k, f"SECRET-EXPLANATION-{q}", "Lists")
        for q, k in KEYS.items()
    ))


def sheet(options):
    return [be.AnswerSubmission(q, o) for q, o in options.items()]


def started(flow, battle_id="btl_001", players=(ASHA, RAVI)):
    flow.create(config(battle_id), *players)
    return flow.start(battle_id)


# ==========================
# 6. CONTRACT TESTS (every backend)
# ==========================

def test_c01_protocol_conformance(backend):
    _, repo = backend
    assert isinstance(repo, BattleRepository)


def test_c02_create_snapshots_questions_and_participants(backend):
    _, repo = backend
    flow = BattleFlow(repo)
    created = flow.create(config(), ASHA, RAVI)
    loaded = flow.load("btl_001")
    assert loaded == created
    assert loaded.config.questions == config().questions                  # frozen copy incl. keys
    assert [q.correct_option for q in loaded.config.questions] == ["B", "C", "A"]
    assert repo.load_battle("btl_missing") is None
    with pytest.raises(Exception):                                         # duplicate battle id
        repo.create_battle(be.create_battle(config(), ASHA, RAVI))


def test_c03_full_lifecycle_and_completion(backend):
    _, repo = backend
    flow = BattleFlow(repo)
    assert started(flow).status is be.BattleStatus.ACTIVE
    after_first = flow.submit("btl_001", ASHA.user_id, sheet(ALL_RIGHT))
    assert after_first.status is be.BattleStatus.ACTIVE and after_first.result is None
    done = flow.submit("btl_001", RAVI.user_id, sheet(ONE_RIGHT))
    assert done.status is be.BattleStatus.COMPLETED
    assert (done.result.outcome, done.result.winner_user_id) == (be.BattleOutcome.WIN, ASHA.user_id)
    assert [s.correct for s in done.result.scores] == [3, 1]


def test_c04_saved_result_matches_domain_scoring_and_pure_engine(backend):
    _, repo = backend
    flow = BattleFlow(repo)
    started(flow)
    flow.submit("btl_001", RAVI.user_id, sheet(ONE_RIGHT))                # order differs from c03
    done = flow.submit("btl_001", ASHA.user_id, sheet(ALL_RIGHT))
    assert done.result == be.score_battle(done)
    pure = be.start_battle(be.create_battle(config(), ASHA, RAVI))
    pure = be.submit_answers(be.submit_answers(pure, RAVI.user_id, sheet(ONE_RIGHT)), ASHA.user_id, sheet(ALL_RIGHT))
    assert done.result == pure.result


def test_c05_identical_results_and_views_after_reload(backend):
    kind, repo = backend
    flow = BattleFlow(repo)
    started(flow)
    flow.submit("btl_001", ASHA.user_id, sheet(ALL_RIGHT))
    done = flow.submit("btl_001", RAVI.user_id, sheet(ONE_RIGHT))
    views = {u: flow.view("btl_001", u) for u in (ASHA.user_id, RAVI.user_id)}
    reopened = BattleFlow(require_hook(kind, repo, "contract_reopen")())
    again = reopened.load("btl_001")
    assert (again.status, again.result, again.answer_sheets) == (done.status, done.result, done.answer_sheets)
    assert {u: reopened.view("btl_001", u) for u in views} == views


def test_c06_duplicate_submission_rejected(backend):
    _, repo = backend
    flow = BattleFlow(repo)
    started(flow)
    flow.submit("btl_001", ASHA.user_id, sheet(ALL_RIGHT))
    with pytest.raises(be.InvalidBattleTransitionError):
        flow.submit("btl_001", ASHA.user_id, sheet(ONE_RIGHT))
    assert repo.submit_answer_sheet("btl_001", be.AnswerSheet(ASHA.user_id, (("bq_1", "A"),))) is SheetResult.ALREADY_SUBMITTED
    assert flow.load("btl_001").answer_sheets[0].answers == tuple(ALL_RIGHT.items())


def test_c07_third_party_rejected(backend):
    _, repo = backend
    flow = BattleFlow(repo)
    started(flow)
    with pytest.raises(be.UnauthorizedParticipantError):
        flow.submit("btl_001", MEERA, sheet(ALL_RIGHT))
    with pytest.raises(be.UnauthorizedParticipantError):
        flow.view("btl_001", MEERA)
    with pytest.raises(Exception):                                        # repository-level guard too
        repo.submit_answer_sheet("btl_001", be.AnswerSheet(MEERA, (("bq_1", "B"),)))
    assert flow.load("btl_001").answer_sheets == ()


def test_c08_invalid_transitions_rejected_and_nothing_written(backend):
    _, repo = backend
    flow = BattleFlow(repo)
    flow.create(config(), ASHA, RAVI)
    with pytest.raises(be.InvalidBattleTransitionError):                 # submit before start
        flow.submit("btl_001", ASHA.user_id, sheet(ALL_RIGHT))
    flow.start("btl_001")
    with pytest.raises(be.InvalidBattleTransitionError):                 # start twice
        flow.start("btl_001")
    assert repo.start_battle("btl_001") is TransitionResult.CONFLICT
    assert repo.complete_battle("btl_001", be.BattleResult(
        "btl_001", (be.ParticipantScore(ASHA.user_id, 3, 3, 3), be.ParticipantScore(RAVI.user_id, 0, 3, 3)),
        be.BattleOutcome.WIN, ASHA.user_id)) is TransitionResult.CONFLICT  # no sheets: cannot complete
    flow.submit("btl_001", ASHA.user_id, sheet(ALL_RIGHT))
    with pytest.raises(be.InvalidBattleTransitionError):                 # cancel after a sheet
        flow.cancel("btl_001", "abort")
    state = flow.load("btl_001")
    assert (state.status, state.result, len(state.answer_sheets)) == (be.BattleStatus.ACTIVE, None, 1)
    with pytest.raises(LookupError):
        repo.start_battle("btl_missing")


def test_c09_cancelled_battle_cannot_start_submit_or_complete(backend):
    _, repo = backend
    flow = BattleFlow(repo)
    flow.create(config(), ASHA, RAVI)
    cancelled = flow.cancel("btl_001", "  opponent left  ")
    assert (cancelled.status, cancelled.cancel_reason) == (be.BattleStatus.CANCELLED, "opponent left")
    with pytest.raises(be.InvalidBattleTransitionError):
        flow.start("btl_001")
    assert repo.submit_answer_sheet("btl_001", be.AnswerSheet(ASHA.user_id, tuple(ALL_RIGHT.items()))) is SheetResult.NOT_ACTIVE
    assert repo.complete_battle("btl_001", be.BattleResult(
        "btl_001", (be.ParticipantScore(ASHA.user_id, 0, 0, 3), be.ParticipantScore(RAVI.user_id, 0, 0, 3)),
        be.BattleOutcome.TIE, None)) is TransitionResult.CONFLICT
    view = flow.view("btl_001", ASHA.user_id)
    assert (view.status, view.result, view.review) == (be.BattleStatus.CANCELLED, None, ())
    active_cancel = BattleFlow(repo)
    started(active_cancel, "btl_002")
    assert active_cancel.cancel("btl_002", "timeout").status is be.BattleStatus.CANCELLED


@pytest.mark.parametrize("stage", ["create", "start", "submit", "complete", "cancel"])
def test_c10_failed_write_leaves_no_partial_state_and_retry_succeeds(backend, stage):
    kind, repo = backend
    fail = require_hook(kind, repo, "contract_fail_next_write")
    flow = BattleFlow(repo)
    if stage == "create":
        fail("create")
        with pytest.raises(Exception):
            flow.create(config(), ASHA, RAVI)
        assert repo.load_battle("btl_001") is None
        flow.create(config(), ASHA, RAVI)
        assert flow.load("btl_001").status is be.BattleStatus.CREATED
        return
    flow.create(config(), ASHA, RAVI)
    if stage == "cancel":
        fail("cancel")
        with pytest.raises(Exception):
            flow.cancel("btl_001", "abort")
        assert flow.load("btl_001").status is be.BattleStatus.CREATED
        assert flow.cancel("btl_001", "abort").status is be.BattleStatus.CANCELLED
        return
    if stage == "start":
        fail("start")
        with pytest.raises(Exception):
            flow.start("btl_001")
        assert flow.load("btl_001").status is be.BattleStatus.CREATED
        assert flow.start("btl_001").status is be.BattleStatus.ACTIVE
        return
    flow.start("btl_001")
    if stage == "submit":
        fail("submit")
        with pytest.raises(Exception):
            flow.submit("btl_001", ASHA.user_id, sheet(ALL_RIGHT))
        assert flow.load("btl_001").answer_sheets == ()
        assert len(flow.submit("btl_001", ASHA.user_id, sheet(ALL_RIGHT)).answer_sheets) == 1
        return
    flow.submit("btl_001", ASHA.user_id, sheet(ALL_RIGHT))               # stage == "complete"
    fail("complete")
    with pytest.raises(Exception):
        flow.submit("btl_001", RAVI.user_id, sheet(ONE_RIGHT))
    # The second sheet committed (its own transaction); completion did not.
    stuck = flow.load("btl_001")
    assert (stuck.status, stuck.result, len(stuck.answer_sheets)) == (be.BattleStatus.ACTIVE, None, 2)
    # Retry = re-run the completion step: idempotent, exactly once.
    flow._complete_if_ready("btl_001")
    done = flow.load("btl_001")
    assert done.status is be.BattleStatus.COMPLETED and done.result == be.score_battle(done)


def test_c11_result_is_stored_exactly_once(backend):
    _, repo = backend
    flow = BattleFlow(repo)
    started(flow)
    flow.submit("btl_001", ASHA.user_id, sheet(ALL_RIGHT))
    done = flow.submit("btl_001", RAVI.user_id, sheet(ONE_RIGHT))
    forged = be.BattleResult("btl_001", done.result.scores, be.BattleOutcome.TIE, None)
    assert repo.complete_battle("btl_001", forged) is TransitionResult.CONFLICT
    flow._complete_if_ready("btl_001")                                    # a racing completer: no-op
    assert flow.load("btl_001").result == done.result
    if hasattr(repo, "result_writes"):
        assert repo.result_writes == 1


def test_c12_no_answer_key_or_opponent_answers_before_completion(backend):
    _, repo = backend
    flow = BattleFlow(repo)
    started(flow)
    flow.submit("btl_001", ASHA.user_id, sheet({"bq_1": "B", "bq_2": "C", "bq_3": "D"}))
    for viewer in (ASHA.user_id, RAVI.user_id):
        view = flow.view("btl_001", viewer)
        assert view.result is None and view.review == ()
        assert "SECRET-EXPLANATION" not in repr(view)
    ravi = flow.view("btl_001", RAVI.user_id)
    assert ravi.opponent_submitted and ravi.viewer_answers == () and "'D'" not in repr(ravi)
    flow.submit("btl_001", RAVI.user_id, sheet(ONE_RIGHT))
    review = flow.view("btl_001", RAVI.user_id).review
    assert review[2].answers == ((ASHA.user_id, "D"), (RAVI.user_id, "D"))   # visible after completion


def test_c13_separate_battles_and_participants_are_isolated(backend):
    _, repo = backend
    flow = BattleFlow(repo)
    started(flow, "btl_one")
    started(flow, "btl_two")
    started(flow, "btl_three", players=(RAVI, be.BattleParticipant(MEERA, "Meera")))
    flow.submit("btl_one", ASHA.user_id, sheet(ALL_RIGHT))
    flow.submit("btl_two", ASHA.user_id, sheet(ONE_RIGHT))
    assert flow.load("btl_three").answer_sheets == ()
    one = flow.submit("btl_one", RAVI.user_id, sheet(ONE_RIGHT))
    assert flow.load("btl_two").status is be.BattleStatus.ACTIVE
    assert one.result.winner_user_id == ASHA.user_id
    with pytest.raises(be.UnauthorizedParticipantError):
        flow.view("btl_three", ASHA.user_id)


def test_c14_invalid_answers_never_reach_storage(backend):
    _, repo = backend
    flow = BattleFlow(repo)
    started(flow)
    for bad in ([be.AnswerSubmission("bq_9", "A")], [be.AnswerSubmission("bq_1", "Z")], sheet({"bq_1": "B"})):
        with pytest.raises(gs.InvalidSubmissionError):
            flow.submit("btl_001", ASHA.user_id, bad)
    assert flow.load("btl_001").answer_sheets == ()


# ==========================
# 7. REAL-DATABASE-ONLY CONTRACT TESTS (skipped for the fake by design)
# ==========================

def _parallel(n, target):
    barrier, errors = threading.Barrier(n), []

    def run(i):
        try:
            barrier.wait()
            target(i)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return errors


def test_d01_simultaneous_player_submissions_complete_exactly_once(backend):
    kind, repo = backend
    require_real(kind, "simultaneous submission handling")
    flow = BattleFlow(repo)
    started(flow)
    players = [(ASHA.user_id, ALL_RIGHT), (RAVI.user_id, ONE_RIGHT)]
    errors = _parallel(2, lambda i: flow.submit("btl_001", players[i][0], sheet(players[i][1])))
    assert errors == []
    done = flow.load("btl_001")
    assert done.status is be.BattleStatus.COMPLETED and done.result == be.score_battle(done)


def test_d02_same_player_parallel_submissions_store_one_sheet(backend):
    kind, repo = backend
    require_real(kind, "unique answer-sheet constraint under concurrency")
    flow = BattleFlow(repo)
    started(flow)
    results = []
    errors = _parallel(4, lambda i: results.append(
        repo.submit_answer_sheet("btl_001", be.AnswerSheet(ASHA.user_id, tuple(ALL_RIGHT.items())))))
    assert errors == []
    assert sorted(results) == sorted([SheetResult.INSERTED] + [SheetResult.ALREADY_SUBMITTED] * 3)


def test_d03_parallel_completion_writes_one_result(backend):
    kind, repo = backend
    require_real(kind, "transactional result creation and locking")
    flow = BattleFlow(repo)
    started(flow)
    repo.submit_answer_sheet("btl_001", be.AnswerSheet(ASHA.user_id, tuple(ALL_RIGHT.items())))
    repo.submit_answer_sheet("btl_001", be.AnswerSheet(RAVI.user_id, tuple(ONE_RIGHT.items())))
    result = be.score_battle(flow.load("btl_001"))
    outcomes = []
    errors = _parallel(4, lambda i: outcomes.append(repo.complete_battle("btl_001", result)))
    assert errors == []
    assert sorted(outcomes) == sorted([TransitionResult.APPLIED] + [TransitionResult.CONFLICT] * 3)


def test_d04_concurrent_cancel_and_submit_are_consistent(backend):
    kind, repo = backend
    require_real(kind, "lost-update prevention between cancel and submit")
    flow = BattleFlow(repo)
    started(flow)
    outcomes = {}

    def act(i):
        if i == 0:
            outcomes["cancel"] = repo.cancel_battle("btl_001", "race")
        else:
            outcomes["submit"] = repo.submit_answer_sheet("btl_001", be.AnswerSheet(ASHA.user_id, tuple(ALL_RIGHT.items())))

    assert _parallel(2, act) == []
    state = flow.load("btl_001")
    if outcomes["cancel"] is TransitionResult.APPLIED:
        assert outcomes["submit"] is SheetResult.NOT_ACTIVE and state.answer_sheets == ()
        assert state.status is be.BattleStatus.CANCELLED
    else:
        assert outcomes["submit"] is SheetResult.INSERTED and state.status is be.BattleStatus.ACTIVE


def test_d05_recovery_after_process_restart(backend):
    kind, repo = backend
    require_real(kind, "durability across a real process restart")
    reopen = require_hook(kind, repo, "contract_reopen")
    flow = BattleFlow(repo)
    started(flow)
    flow.submit("btl_001", ASHA.user_id, sheet(ALL_RIGHT))
    restarted = BattleFlow(reopen())
    done = restarted.submit("btl_001", RAVI.user_id, sheet(ONE_RIGHT))
    assert done.status is be.BattleStatus.COMPLETED and done.result == be.score_battle(done)


# ==========================
# 8. ENGINE COMPATIBILITY (backend-independent)
# ==========================

def test_e01_battle_engine_public_api_unchanged():
    expected = {"create_battle", "start_battle", "submit_answers", "cancel_battle", "score_battle",
                "learner_questions", "battle_view", "BattleState", "BattleResult", "AnswerSheet",
                "BattleStatus", "UnauthorizedParticipantError", "InvalidBattleTransitionError"}
    assert expected <= set(dir(be))
    assert be.MAX_BATTLE_QUESTIONS == 20
