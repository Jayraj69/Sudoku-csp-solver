"""Puzzle generation: full grids, unique-solution puzzles, invalid and unsolvable
instances, and 16x16 boards.  All functions take a seeded random.Random so
every benchmark instance is reproducible."""
from __future__ import annotations
import random

from .board import get_spec, validate, to_string
from .solvers import make_solver


def full_grid(N: int, rng: random.Random) -> list[int]:
    """Random valid solution built from the shifted base pattern followed by
    symmetry-preserving shuffles (rows/cols inside bands, bands, digit relabel)."""
    B = int(N ** 0.5)
    base = [[(B * (r % B) + r // B + c) % N + 1 for c in range(N)] for r in range(N)]
    bands = rng.sample(range(B), B)
    rows = [b * B + r for b in bands for r in rng.sample(range(B), B)]
    stacks = rng.sample(range(B), B)
    cols = [s * B + c for s in stacks for c in rng.sample(range(B), B)]
    digits = rng.sample(range(1, N + 1), N)
    return [digits[base[r][c] - 1] for r in rows for c in cols]


def count_solutions(grid: list[int], N: int = 9, limit: int = 2, node_limit=200000) -> int:
    s = make_solver("MAC", N, max_solutions=limit, node_limit=node_limit)
    res = s.solve(grid)
    return res.solutions_found


def make_puzzle(N: int, target_clues: int, rng: random.Random, unique: bool = True,
                solution: list[int] | None = None):
    """Remove cells from a random solution until `target_clues` remain.
    With unique=True a removal is kept only if the puzzle still has exactly one
    solution; generation may stop above the target if no more cells can go."""
    sol = solution or full_grid(N, rng)
    puz = list(sol)
    cells = list(range(N * N))
    rng.shuffle(cells)
    clues = N * N
    for c in cells:
        if clues <= target_clues:
            break
        keep = puz[c]
        puz[c] = 0
        if unique and count_solutions(puz, N, 2) != 1:
            puz[c] = keep
        else:
            clues -= 1
    return puz, sol


def make_invalid(N: int, rng: random.Random, kind: str = "row"):
    """Puzzle whose givens already violate a unit (duplicate digit)."""
    puz, _ = make_puzzle(N, int(N * N * 0.45), rng, unique=False)
    spec = get_spec(N)
    idx = {"row": range(0, N), "column": range(N, 2 * N), "box": range(2 * N, 3 * N),
           "any": range(0, 3 * N)}[kind]
    for _ in range(1000):
        unit = spec.units[rng.choice(list(idx))]
        filled = [c for c in unit if puz[c]]
        empty = [c for c in unit if not puz[c]]
        if filled and empty:
            puz[rng.choice(empty)] = puz[rng.choice(filled)]
            if not validate(puz, N)[0]:
                return puz
    raise RuntimeError("could not build invalid puzzle")


def make_unsolvable(N: int, rng: random.Random):
    """Reliable construction: take a solution, blank one cell x, then place
    the *remaining* digit of x's row/col/box pattern so that x sees all N digits
    without any given repeating inside a unit."""
    spec = get_spec(N)
    for _ in range(2000):
        sol = full_grid(N, rng)
        x = rng.randrange(N * N)
        r, c = divmod(x, N)
        puz = [0] * (N * N)
        # digits seen from row of x (all but sol[x]) ...
        for cc in range(N):
            if cc != c:
                puz[r * N + cc] = sol[r * N + cc]
        # ... and sol[x] placed somewhere in x's column, outside x's box and row
        v = sol[x]
        rows_ok = [rr for rr in range(N) if rr != r and rr // spec.B != r // spec.B]
        rr = rng.choice(rows_ok)
        puz[rr * N + c] = v
        if validate(puz, N)[0]:
            # sprinkle extra consistent clues from the solution elsewhere (not breaking validity)
            others = [i for i in range(N * N) if puz[i] == 0 and i != x]
            rng.shuffle(others)
            for i in others[: N * N // 6]:
                puz[i] = sol[i]
                if not validate(puz, N)[0]:
                    puz[i] = 0
            if count_solutions(puz, N, 1, node_limit=50000) == 0:
                return puz
    raise RuntimeError("could not build unsolvable puzzle")
