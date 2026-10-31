"""Command-line demo (text visualisation of the solver's decisions).

    python -m sudoku_csp.cli solve "<81 chars>" --algo MAC --trace 40
    python -m sudoku_csp.cli solve --file puzzle.txt --compare
    python -m sudoku_csp.cli random --clues 26 --seed 7 --algo FC
    python -m sudoku_csp.cli random --size 16 --clues 150 --algo MAC
"""
from __future__ import annotations

import argparse
import random
import sys

from .board import InvalidPuzzle, is_solution, parse, pretty, validate
from .demo_logs import format_trace
from .generator import make_puzzle
from .solvers import ALGORITHMS, make_solver


def _run(grid, N, algo, trace, limit):
    res = make_solver(algo, N, trace=bool(trace), trace_cap=100000, time_limit=limit).solve(grid)
    print(f"\n== {algo}: {res.status.upper()}  nodes={res.nodes} backtracks={res.backtracks} "
          f"checks={res.checks} prunes={res.prunes} depth={res.max_depth} time={res.time:.4f}s")
    if res.status == "invalid":
        for e in res.errors:
            print("  input error:", e)
        return res
    if trace:
        print(format_trace(res, N, limit=trace))
    if res.solution:
        print(pretty(res.solution, N))
        assert is_solution(res.solution, N)
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sudoku_csp", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("solve", help="solve a puzzle string / file")
    s.add_argument("puzzle", nargs="?", help="81 (or 256) chars, '.' or 0 for blanks")
    s.add_argument("--file")
    r = sub.add_parser("random", help="generate a unique-solution puzzle and solve it")
    r.add_argument("--size", type=int, default=9, choices=(9, 16))
    r.add_argument("--clues", type=int, default=28)
    r.add_argument("--seed", type=int, default=1)
    for p in (s, r):
        p.add_argument("--algo", default="MAC", choices=list(ALGORITHMS))
        p.add_argument("--compare", action="store_true", help="run all five algorithms")
        p.add_argument("--trace", type=int, default=0, metavar="K", help="print first K decision events")
        p.add_argument("--limit", type=float, default=20.0, help="time limit per run (s)")
    a = ap.parse_args(argv)

    try:
        if a.cmd == "solve":
            text = open(a.file).read() if a.file else a.puzzle
            if not text:
                ap.error("give a puzzle string or --file")
            grid = parse(text)
            N = round(len(grid) ** 0.5)
        else:
            N = a.size
            grid, _ = make_puzzle(N, a.clues, random.Random(a.seed), unique=(N == 9))
    except InvalidPuzzle as e:
        print("Invalid input:", e)
        return 2
    print("Puzzle:\n" + pretty(grid, N))
    ok, errs = validate(grid, N)
    if not ok:
        print("\nRejected before search:")
        for e in errs:
            print("  -", e)
        return 2
    for algo in (ALGORITHMS if a.compare else [a.algo]):
        _run(grid, N, algo, a.trace, a.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
