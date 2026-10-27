"""
Unit tests for backend/app/services/leaderboard_engine.py (Ankush's module).

Pure-function tests: no database, FastAPI app, clock or shared state; any order works.
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
_PACKAGE = "pragyax_services_leaderboard_under_test"


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


lb = _load("leaderboard_engine")
gs = sys.modules[f"{_PACKAGE}.gamification_service"]

PLATFORM = lb.LeaderboardScope(lb.ScopeType.PLATFORM)


def member(user_id, points, name=None):
    return lb.LeaderboardMember(user_id, name or f"Name {user_id}", points)


def ids(entries):
    return [e.user_id for e in entries]


def ranks(entries):
    return [e.rank for e in entries]


# ==========================
# Ordering and ranking
# ==========================

def test_orders_by_points_descending():
    board = lb.build_leaderboard(PLATFORM, [member("usr_c", 10), member("usr_a", 90), member("usr_b", 50)])
    assert ids(board.entries) == ["usr_a", "usr_b", "usr_c"]
    assert ranks(board.entries) == [1, 2, 3]
    assert [e.total_points for e in board.entries] == [90, 50, 10]


def test_ties_use_competition_ranking_and_user_id_order():
    board = lb.build_leaderboard(PLATFORM, [
        member("usr_d", 50), member("usr_b", 80), member("usr_a", 80), member("usr_c", 50), member("usr_e", 10),
    ])
    assert ids(board.entries) == ["usr_a", "usr_b", "usr_c", "usr_d", "usr_e"]
    assert ranks(board.entries) == [1, 1, 3, 3, 5]             # competition ranking (1, 1, 3)
    assert [e.position for e in board.entries] == [1, 2, 3, 4, 5]


def test_all_tied_and_zero_points():
    board = lb.build_leaderboard(PLATFORM, [member("usr_b", 0), member("usr_a", 0)])
    assert ids(board.entries) == ["usr_a", "usr_b"] and ranks(board.entries) == [1, 1]


def test_tie_break_is_independent_of_input_order():
    members = [member(f"usr_{c}", 50 if c in "aceg" else 30) for c in "abcdefgh"]
    expected = lb.build_leaderboard(PLATFORM, members).entries
    rng = random.Random(1234)                     # local generator; global random state untouched
    for _ in range(20):
        shuffled = members[:]
        rng.shuffle(shuffled)
        assert lb.build_leaderboard(PLATFORM, shuffled).entries == expected


def test_user_id_tie_break_uses_plain_string_order():
    board = lb.build_leaderboard(PLATFORM, [member("usr_b", 5), member("USR_Z", 5), member("usr_10", 5), member("usr_9", 5)])
    assert ids(board.entries) == ["USR_Z", "usr_10", "usr_9", "usr_b"]   # code-point order, documented


def test_empty_leaderboard():
    board = lb.build_leaderboard(PLATFORM, [])
    assert board.entries == () and board.total_participants == 0
    page = lb.paginate(board)
    assert page.entries == () and page.total_participants == 0
    assert lb.to_learner_rows(page, "usr_a") == ()
    assert lb.viewer_standing(board, "usr_a") is None


def test_single_participant():
    board = lb.build_leaderboard(PLATFORM, [member("usr_solo", 0)])
    assert ranks(board.entries) == [1] and board.total_participants == 1


# ==========================
# Pagination
# ==========================

def ten_members():
    return [member(f"usr_{i:02d}", 100 - (i // 2) * 10) for i in range(10)]   # pairs tie: 100,100,90,90,...


def test_top_n_and_pagination_keep_global_ranks():
    board = lb.build_leaderboard(PLATFORM, ten_members())
    top3 = lb.top_n(board, 3)
    assert ranks(top3.entries) == [1, 1, 3] and top3.total_participants == 10
    page2 = lb.paginate(board, offset=3, limit=3)
    assert ids(page2.entries) == ["usr_03", "usr_04", "usr_05"]
    assert ranks(page2.entries) == [3, 5, 5]                        # not renumbered from 1
    assert [e.position for e in page2.entries] == [4, 5, 6]
    pages = [lb.paginate(board, offset=o, limit=4).entries for o in (0, 4, 8)]
    assert sum(pages, ()) == board.entries


def test_pagination_beyond_the_end_is_empty_not_an_error():
    board = lb.build_leaderboard(PLATFORM, ten_members())
    assert lb.paginate(board, offset=10, limit=5).entries == ()
    assert lb.paginate(board, offset=500, limit=5).entries == ()
    assert len(lb.paginate(board, offset=8, limit=5).entries) == 2
    assert len(lb.top_n(board, lb.MAX_PAGE_SIZE).entries) == 10


@pytest.mark.parametrize("offset, limit", [
    (-1, 10), (0, 0), (0, -5), (0, lb.MAX_PAGE_SIZE + 1), (True, 10), (0, True), (1.5, 10), (0, "10"), (None, 10),
])
def test_invalid_pagination_is_a_submission_error(offset, limit):
    board = lb.build_leaderboard(PLATFORM, ten_members())
    with pytest.raises(gs.InvalidSubmissionError):
        lb.paginate(board, offset=offset, limit=limit)


def test_invalid_top_n_is_a_submission_error():
    board = lb.build_leaderboard(PLATFORM, ten_members())
    for n in (0, -1, lb.MAX_PAGE_SIZE + 1):
        with pytest.raises(gs.InvalidSubmissionError):
            lb.top_n(board, n)


# ==========================
# Validation
# ==========================

def test_duplicate_users_are_rejected():
    with pytest.raises(gs.InvalidTrustedInputError):
        lb.build_leaderboard(PLATFORM, [member("usr_a", 10), member("usr_b", 5), member("usr_a", 99)])


@pytest.mark.parametrize("points", [-1, -100, True, False, 1.5, "10", None])
def test_negative_or_non_integer_points_are_rejected(points):
    with pytest.raises(gs.InvalidTrustedInputError):
        member("usr_a", points)


@pytest.mark.parametrize("user_id", ["", "usr a", "usr:a", "usr_a\n", None, 7, "u" * 65])
def test_malformed_identities_are_rejected(user_id):
    with pytest.raises(gs.InvalidTrustedInputError):
        member(user_id, 10)


@pytest.mark.parametrize("name", ["", "   ", None, 5, "n" * 101])
def test_malformed_display_names_are_rejected(name):
    with pytest.raises(gs.InvalidTrustedInputError):
        lb.LeaderboardMember("usr_a", name, 10)


def test_wrong_member_types_are_rejected():
    with pytest.raises(gs.InvalidTrustedInputError):
        lb.build_leaderboard(PLATFORM, [{"user_id": "usr_a", "total_points": 10**9}])
    with pytest.raises(gs.InvalidTrustedInputError):
        lb.build_leaderboard(PLATFORM, "usr_a")
    with pytest.raises(gs.InvalidTrustedInputError):
        lb.build_leaderboard("platform", [member("usr_a", 1)])


@pytest.mark.parametrize("scope_type, scope_id", [
    ("league", None), ("platform", "clg_1"), ("college", None), ("company", ""),
    ("college", "clg 1"), ("company", "co:1"), ("college", "c" * 65), (None, None),
])
def test_invalid_scopes_are_rejected(scope_type, scope_id):
    with pytest.raises(gs.InvalidTrustedInputError):
        lb.LeaderboardScope(scope_type, scope_id)


def test_scope_keys_are_stable():
    assert PLATFORM.key == "platform"
    assert lb.LeaderboardScope("college", "clg_iitd").key == "college:clg_iitd"
    assert lb.LeaderboardScope(lb.ScopeType.COMPANY, "co_acme").key == "company:co_acme"
    assert lb.LeaderboardScope("college", "clg_iitd") == lb.LeaderboardScope(lb.ScopeType.COLLEGE, "clg_iitd")


# ==========================
# Scopes and membership
# ==========================

def everyone():
    return [member("usr_a", 90), member("usr_b", 70), member("usr_c", 50), member("usr_d", 30)]


def test_scoped_leaderboards_rank_only_their_members():
    college = lb.LeaderboardScope("college", "clg_iitd")
    company = lb.LeaderboardScope("company", "co_acme")
    c_board = lb.build_leaderboard(college, everyone(), lb.ScopeMembership(college, {"usr_b", "usr_d"}))
    k_board = lb.build_leaderboard(company, everyone(), lb.ScopeMembership(company, frozenset({"usr_a", "usr_c", "usr_d"})))
    p_board = lb.build_leaderboard(PLATFORM, everyone())
    assert ids(c_board.entries) == ["usr_b", "usr_d"] and ranks(c_board.entries) == [1, 2]
    assert ids(k_board.entries) == ["usr_a", "usr_c", "usr_d"] and ranks(k_board.entries) == [1, 2, 3]
    assert ids(p_board.entries) == ["usr_a", "usr_b", "usr_c", "usr_d"]
    assert lb.viewer_standing(c_board, "usr_d").rank == 2 and lb.viewer_standing(p_board, "usr_d").rank == 4


def test_members_listed_but_without_points_rows_are_simply_absent():
    college = lb.LeaderboardScope("college", "clg_iitd")
    board = lb.build_leaderboard(college, everyone(), lb.ScopeMembership(college, {"usr_b", "usr_zz"}))
    assert ids(board.entries) == ["usr_b"]


def test_scope_membership_rules():
    college = lb.LeaderboardScope("college", "clg_iitd")
    other = lb.LeaderboardScope("college", "clg_other")
    with pytest.raises(gs.InvalidTrustedInputError):                       # membership required
        lb.build_leaderboard(college, everyone())
    with pytest.raises(gs.InvalidTrustedInputError):                       # membership for another scope
        lb.build_leaderboard(college, everyone(), lb.ScopeMembership(other, {"usr_a"}))
    with pytest.raises(gs.InvalidTrustedInputError):                       # platform takes none
        lb.build_leaderboard(PLATFORM, everyone(), lb.ScopeMembership(college, {"usr_a"}))
    with pytest.raises(gs.InvalidTrustedInputError):                       # no platform membership lists
        lb.ScopeMembership(PLATFORM, {"usr_a"})
    with pytest.raises(gs.InvalidTrustedInputError):                       # malformed member id
        lb.ScopeMembership(college, {"usr a"})
    with pytest.raises(gs.InvalidTrustedInputError):                       # bare string is not a collection
        lb.ScopeMembership(college, "usr_a")


def test_invalid_members_are_rejected_even_if_outside_the_scope():
    college = lb.LeaderboardScope("college", "clg_iitd")
    with pytest.raises(gs.InvalidTrustedInputError):
        lb.build_leaderboard(college, everyone() + [member("usr_a", 1)], lb.ScopeMembership(college, {"usr_b"}))


# ==========================
# Privacy-safe projections
# ==========================

def test_learner_rows_expose_no_private_fields():
    board = lb.build_leaderboard(PLATFORM, [member("usr_secret_1", 90, "Asha"), member("usr_secret_2", 40, "Ravi")])
    rows = lb.to_learner_rows(lb.top_n(board, 10), viewer_user_id="usr_secret_2")
    assert {f.name for f in dataclasses.fields(lb.LeaderboardRow)} == {"rank", "display_name", "total_points", "is_viewer"}
    assert rows == (lb.LeaderboardRow(1, "Asha", 90, False), lb.LeaderboardRow(2, "Ravi", 40, True))
    assert "usr_secret" not in repr(rows)


def test_viewer_standing_and_rows_without_viewer():
    board = lb.build_leaderboard(PLATFORM, ten_members())
    assert lb.viewer_standing(board, "usr_05") == lb.LeaderboardRow(5, "Name usr_05", 80, True)
    assert lb.viewer_standing(board, "usr_unknown") is None
    assert not any(r.is_viewer for r in lb.to_learner_rows(lb.top_n(board, 10)))
    with pytest.raises(gs.InvalidTrustedInputError):
        lb.viewer_standing(board, "bad id")


def test_display_names_are_trimmed():
    board = lb.build_leaderboard(PLATFORM, [lb.LeaderboardMember("usr_a", "  Asha  ", 5)])
    assert board.entries[0].display_name == "Asha"


def test_client_supplied_ranks_or_points_cannot_enter():
    # The only way in is LeaderboardMember (validated trusted totals); ranks are always computed.
    forged = [{"user_id": "usr_x", "display_name": "X", "total_points": 10**9, "rank": 1}]
    with pytest.raises(gs.InvalidTrustedInputError):
        lb.rank_members(forged)
    assert "rank" not in {f.name for f in dataclasses.fields(lb.LeaderboardMember)}


# ==========================
# Immutability, determinism, purity
# ==========================

def test_inputs_are_not_mutated_and_outputs_are_frozen():
    members = [member("usr_b", 10), member("usr_a", 20)]
    snapshot = list(members)
    board = lb.build_leaderboard(PLATFORM, members)
    assert members == snapshot
    with pytest.raises(dataclasses.FrozenInstanceError):
        board.entries[0].rank = 99
    with pytest.raises(dataclasses.FrozenInstanceError):
        members[0].total_points = 10**9
    assert isinstance(board.entries, tuple)


def test_results_are_deterministic():
    runs = {lb.build_leaderboard(PLATFORM, ten_members()) for _ in range(5)}
    assert len(runs) == 1
    assert len({lb.paginate(next(iter(runs)), offset=2, limit=3) for _ in range(5)}) == 1


def test_accepts_generators():
    assert lb.build_leaderboard(PLATFORM, (m for m in ten_members())) == lb.build_leaderboard(PLATFORM, ten_members())


def test_no_filesystem_network_database_clock_or_random_use(monkeypatch):
    state = random.getstate()

    def forbidden(*args, **kwargs):
        raise AssertionError("leaderboard engine must be pure")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    college = lb.LeaderboardScope("college", "clg_iitd")
    board = lb.build_leaderboard(college, ten_members(), lb.ScopeMembership(college, {"usr_01", "usr_02"}))
    lb.to_learner_rows(lb.paginate(board, offset=0, limit=5), "usr_01")
    lb.viewer_standing(board, "usr_02")
    monkeypatch.undo()
    assert random.getstate() == state


def test_source_imports_only_stdlib_and_owned_modules():
    tree = ast.parse((SERVICES_DIR / "leaderboard_engine.py").read_text(encoding="utf-8"))
    absolute, relative, attributes = set(), set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            absolute |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            (relative if node.level else absolute).add(node.module.split(".")[0])
        elif isinstance(node, ast.Attribute):
            attributes.add(node.attr)
    assert absolute <= set(sys.stdlib_module_names), absolute
    assert not absolute & {"sqlite3", "os", "io", "socket", "http", "urllib", "random", "secrets", "time", "datetime", "uuid"}
    assert relative == {"gamification_service", "points_ledger_domain"}
    assert not attributes & {"now", "today", "utcnow", "execute", "connect"}
