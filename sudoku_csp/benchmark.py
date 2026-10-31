"""Benchmark harness.

    python -m sudoku_csp.benchmark                 # full run  -> results/benchmark_results.csv
    python -m sudoku_csp.benchmark --quick         # small smoke run
    python -m sudoku_csp.benchmark --extra data/top95.txt --extra-label norvig-top95

Instance families (all generated with seed 2026, hence reproducible):
  9x9 clue sweep   40, 36, 32, 29, 26, 24 givens   (unique-solution puzzles)
  9x9 named hard   Inkala, Norvig 'hardest', Norvig hard1, 17-clue puzzle
  16x16            55 %, 48 %, 42 % of cells given  (solvable by construction)
  edge cases       invalid (duplicate givens) and unsolvable puzzles
Optional extra files (Norvig easy50/top95/hardest, Kaggle CSV) can be added.
"""
from __future__ import annotations
import argparse
import csv
import os
import random
import time

import pandas as pd

from .board import parse, to_string, validate, is_solution
from .generator import make_puzzle, make_invalid, make_unsolvable
from .solvers import ALGORITHMS, make_solver

SEED = 2026
NAMED = {
    "inkala-2012": "800000000003600000070090200050007000000045700000100030001000068008500010090000400",
    "norvig-hardest": "85...24..72......9..4.........1.7..23.5...9...4...........8..7..17..........36.4.",
    "norvig-hard1": "4.....8.5.3..........7......2.....6.....8.4......1.......6.3.7.5..2.....1.4......",
    "17-clue": "000000010400000000020000000000050407008000300001090000300400200050100000000806000",
}


def size_class(row) -> str:
    if row["kind"] != "solve":
        return "edge"
    if row["N"] == 16:
        return "large"
    return "small" if row["clues"] >= 32 else "medium"


def build_instances(per_set: int = 15, per_set16: int = 5, seed: int = SEED) -> list[dict]:
    rng = random.Random(seed)
    out = []

    def add(fam, N, grid, kind="solve", **extra):
        out.append(dict(id=f"{fam}-{sum(1 for o in out if o['family']==fam)+1:02d}", family=fam,
                        N=N, clues=sum(1 for v in grid if v), puzzle=to_string(grid), kind=kind, **extra))

    for clues in (40, 36, 32, 29, 26, 24):
        for _ in range(per_set):
            g, _ = make_puzzle(9, clues, rng, unique=True)
            add(f"9x9-c{clues}", 9, g)
    for k, s in NAMED.items():
        add(f"named-{k}", 9, parse(s))
    for dens in (0.55, 0.48, 0.42):
        for _ in range(per_set16):
            g, _ = make_puzzle(16, int(256 * dens), rng, unique=False)
            add(f"16x16-d{int(dens*100)}", 16, g)
    for kind in ("row", "column", "box"):
        for N in (9, 16):
            add(f"invalid-{N}x{N}", N, make_invalid(N, rng, kind), kind="invalid")
    for N, reps in ((9, 5), (16, 2)):
        for _ in range(reps):
            add(f"unsolvable-{N}x{N}", N, make_unsolvable(N, rng), kind="unsolvable")
    for o in out:
        o["size_class"] = size_class(o)
    return out


def load_extra(path: str, label: str, limit: int | None = None) -> list[dict]:
    """Load puzzles from a Norvig-style text file (one 81-char puzzle per line,
    or Grid-formatted blocks) or a Kaggle CSV with a 'puzzle' column."""
    rows = []
    if path.endswith(".csv"):
        df = pd.read_csv(path)
        col = "puzzle" if "puzzle" in df.columns else "quizzes"
        for s in df[col].astype(str).head(limit):
            rows.append(s)
    else:
        buf = []
        for line in open(path):
            line = line.strip()
            if not line or line.startswith("Grid"):
                if buf and len("".join(buf)) >= 81:
                    rows.append("".join(buf)); buf = []
                continue
            buf.append(line)
            if len("".join(buf)) == 81:
                rows.append("".join(buf)); buf = []
        if buf and len("".join(buf)) >= 81:
            rows.append("".join(buf))
    out = []
    for i, s in enumerate(rows[:limit], 1):
        g = parse(s, 9)
        out.append(dict(id=f"{label}-{i:03d}", family=label, N=9, clues=sum(1 for v in g if v),
                        puzzle=to_string(g), kind="solve",
                        size_class="small" if sum(1 for v in g if v) >= 32 else "medium"))
    return out


def run(instances, algos, limits, out_csv, log=print):
    fields = ["id", "family", "size_class", "kind", "N", "clues", "empties", "algorithm", "status",
              "correct", "nodes", "expanded", "decisions", "backtracks", "checks", "prunes",
              "revisions", "max_depth", "avg_branching", "time", "time_limit"]
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        t_start = time.time()
        for i, inst in enumerate(instances, 1):
            N = inst["N"]
            grid = parse(inst["puzzle"], N)
            tl = limits[N]
            for a in algos:
                res = make_solver(a, N, time_limit=tl).solve(grid)
                if inst["kind"] == "solve":
                    correct = res.status == "solved" and is_solution(res.solution, N) and \
                        all(g == 0 or g == s for g, s in zip(grid, res.solution))
                    if res.status == "timeout":
                        correct = None
                elif inst["kind"] == "invalid":
                    correct = res.status == "invalid"
                else:
                    correct = res.status == "unsolvable" if res.status != "timeout" else None
                row = res.as_dict()
                row.update(id=inst["id"], family=inst["family"], size_class=inst["size_class"],
                           kind=inst["kind"], clues=inst["clues"], empties=N * N - inst["clues"],
                           correct=correct, time_limit=tl)
                row["time"] = round(row["time"], 5)
                w.writerow({k: row.get(k) for k in fields})
            f.flush()
            if i % 5 == 0 or i == len(instances):
                log(f"[{i}/{len(instances)}] {inst['id']}  elapsed {time.time()-t_start:.0f}s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--limit9", type=float, default=5.0, help="time limit per run, 9x9 (s)")
    ap.add_argument("--limit16", type=float, default=15.0, help="time limit per run, 16x16 (s)")
    ap.add_argument("--extra", help="extra puzzle file (Norvig .txt or Kaggle .csv)")
    ap.add_argument("--extra-label", default="extra")
    ap.add_argument("--extra-n", type=int, default=50)
    args = ap.parse_args()

    inst = build_instances(per_set=3 if args.quick else 15, per_set16=1 if args.quick else 5)
    if args.extra:
        inst += load_extra(args.extra, args.extra_label, args.extra_n)
    os.makedirs(args.out, exist_ok=True)
    pd.DataFrame(inst).to_csv(os.path.join(args.out, "benchmark_instances.csv"), index=False)
    run(inst, list(ALGORITHMS), {9: args.limit9, 16: args.limit16},
        os.path.join(args.out, "benchmark_results.csv"))


if __name__ == "__main__":
    main()
