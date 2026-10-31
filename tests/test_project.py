"""pytest suite: model, validation, all five solvers, edge cases, generator."""
import random

import pytest

from sudoku_csp import (ALGORITHMS, InvalidPuzzle, get_spec, is_solution, make_solver,
                        parse, to_string, validate)
from sudoku_csp.generator import (count_solutions, full_grid, make_invalid, make_puzzle,
                                  make_unsolvable)

EASY = "003020600900305001001806400008102900700000008006708200002609500800203009005010300"
HARD = "85...24..72......9..4.........1.7..23.5...9...4...........8..7..17..........36.4."
ALL = list(ALGORITHMS)


# ---------- model ----------------------------------------------------------
def test_topology_9x9():
    s = get_spec(9)
    assert len(s.units) == 27 and all(len(u) == 9 for u in s.units)
    assert all(len(p) == 20 for p in s.peers)
    assert s.full == 0b111111111


def test_topology_16x16():
    s = get_spec(16)
    assert len(s.units) == 48 and all(len(p) == 39 for p in s.peers)


def test_unsupported_order():
    with pytest.raises(InvalidPuzzle):
        get_spec(10)


# ---------- parsing / validation --------------------------------------------
def test_parse_roundtrip_and_formats():
    g = parse(EASY)
    assert len(g) == 81 and g[2] == 3
    assert parse(to_string(g)) == g
    pretty = "\n".join(EASY[i:i + 9] for i in range(0, 81, 9))
    assert parse(pretty) == g
    assert parse(EASY.replace("0", ".")) == g


@pytest.mark.parametrize("bad", ["", "123", "x" * 81, "1" * 80])
def test_parse_rejects_malformed(bad):
    with pytest.raises(InvalidPuzzle):
        parse(bad, 9)


def test_validate_duplicate_givens():
    g = parse(EASY)
    g[0] = g[3] = 5          # same row, plus ensure clash
    ok, errs = validate(g, 9)
    assert not ok and any("Duplicate" in e for e in errs)


@pytest.mark.parametrize("algo", ALL)
def test_invalid_input_never_searched(algo):
    g = parse(EASY)
    g[0] = g[1] = 7
    r = make_solver(algo, 9).solve(g)
    assert r.status == "invalid" and r.nodes == 0 and r.errors


# ---------- solving ---------------------------------------------------------
@pytest.mark.parametrize("algo", ALL)
def test_solves_easy_and_respects_givens(algo):
    g = parse(EASY)
    r = make_solver(algo, 9, time_limit=20).solve(g)
    assert r.status == "solved" and is_solution(r.solution, 9)
    assert all(a == 0 or a == b for a, b in zip(g, r.solution))


def test_all_algorithms_agree_on_unique_solution():
    g = parse(HARD)
    sols = {a: make_solver(a, 9, time_limit=60).solve(g).solution for a in ("BT+MRV+DEG", "FC", "MAC")}
    assert None not in sols.values()
    assert len({tuple(v) for v in sols.values()}) == 1


def test_empty_board_is_solvable():
    for algo in ("FC", "MAC", "BT+MRV+DEG"):
        r = make_solver(algo, 9, time_limit=20).solve([0] * 81)
        assert r.status == "solved" and is_solution(r.solution, 9)


def test_full_valid_board_is_returned_unchanged():
    sol = full_grid(9, random.Random(1))
    r = make_solver("MAC", 9).solve(list(sol))
    assert r.status == "solved" and r.solution == sol


def test_unsolvable_detected_by_all():
    puz = make_unsolvable(9, random.Random(4))
    assert validate(puz, 9)[0]                     # rule-consistent...
    for algo in ("BT+MRV", "BT+MRV+DEG", "FC", "MAC"):
        r = make_solver(algo, 9, time_limit=30).solve(puz)
        assert r.status == "unsolvable", algo      # ...but no completion exists
    # plain BT must never claim a solution (it may exhaust its time budget instead)
    assert make_solver("BT", 9, time_limit=3).solve(puz).status in ("unsolvable", "timeout")


def test_propagation_reduces_search():
    g = parse(HARD)
    base = make_solver("BT+MRV", 9, time_limit=30).solve(g)
    mac = make_solver("MAC", 9, time_limit=30).solve(g)
    assert mac.status == "solved" and mac.nodes <= base.nodes


def test_timeout_reported_not_crashed():
    r = make_solver("BT", 9, node_limit=50).solve(parse(HARD))
    assert r.status == "timeout"


def test_multiple_solutions_counted():
    assert count_solutions([0] * 81, 9, limit=2) == 2


def test_16x16_solved_by_mac():
    puz, sol = make_puzzle(16, int(256 * .6), random.Random(3), unique=False)
    r = make_solver("MAC", 16, time_limit=60).solve(puz)
    assert r.status == "solved" and is_solution(r.solution, 16)


def test_trace_events_recorded():
    r = make_solver("FC", 9, trace=True).solve(parse(EASY))
    assert r.trace and r.trace[0][0] in ("assign", "preprocess")


# ---------- generator -------------------------------------------------------
def test_generated_puzzles_unique_and_consistent():
    rng = random.Random(11)
    puz, sol = make_puzzle(9, 30, rng, unique=True)
    assert validate(puz, 9)[0] and is_solution(sol, 9)
    assert count_solutions(puz, 9, limit=2) == 1
    assert sum(1 for v in puz if v) >= 22


def test_make_invalid_is_invalid():
    assert not validate(make_invalid(9, random.Random(2)), 9)[0]
