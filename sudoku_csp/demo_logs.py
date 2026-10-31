"""Generate step-by-step decision logs (deliverable: 'demonstration logs').

    python -m sudoku_csp.demo_logs
"""
from __future__ import annotations
import os

from .board import parse, pretty, name
from .benchmark import NAMED
from .solvers import make_solver

EASY = "003020600900305001001806400008102900700000008006708200002609500800203009005010300"  # Norvig's grid1


def format_trace(res, N=9, limit=None):
    lines, step = [], 0
    for ev in res.trace[: limit or len(res.trace)]:
        kind, cell, v, size, pruned = ev
        if kind == "preprocess":
            lines.append(f"[pre ] AC-3 pre-processing done; total remaining candidates = {size}")
            continue
        step += 1
        if kind == "assign":
            extra = f", pruned {pruned} values" if pruned else ""
            lines.append(f"[{step:5d}] ASSIGN    {name(cell, N)} = {v:<2d} (chosen from {size} candidate"
                         f"{'s' if size != 1 else ''}{extra})")
        else:
            lines.append(f"[{step:5d}] BACKTRACK {name(cell, N)} = {v:<2d} (undo, try next value)")
    return "\n".join(lines)


def write_log(path, title, puzzle, algo, limit=None):
    grid = parse(puzzle)
    res = make_solver(algo, 9, trace=True, trace_cap=100000, time_limit=20).solve(grid)
    with open(path, "w") as f:
        f.write(f"{title}\nAlgorithm: {algo}\n\nInitial puzzle:\n{pretty(grid)}\n\n")
        f.write("Decision sequence" + (f" (first {limit} events)" if limit else "") + ":\n")
        f.write(format_trace(res, limit=limit) + "\n\n")
        if res.solution:
            f.write(f"Solution:\n{pretty(res.solution)}\n\n")
        f.write(f"Status={res.status} nodes={res.nodes} expanded={res.expanded} backtracks={res.backtracks} "
                f"checks={res.checks} prunes={res.prunes} max_depth={res.max_depth} time={res.time:.4f}s\n")
    return res


def main(out="results/logs"):
    os.makedirs(out, exist_ok=True)
    for algo in ("BT", "BT+MRV+DEG", "FC", "MAC"):
        tag = algo.replace("+", "_")
        write_log(f"{out}/demo_easy_{tag}.txt", "Norvig grid1 (easy, 30 givens)", EASY, algo)
        write_log(f"{out}/demo_inkala_{tag}.txt", "Inkala 2012 'hardest' puzzle (21 givens)",
                  NAMED["inkala-2012"], algo, limit=120)


if __name__ == "__main__":
    main()
