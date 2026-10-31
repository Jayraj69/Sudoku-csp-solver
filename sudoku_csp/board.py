"""Board topology, parsing and input validation.

A puzzle of order N (N = 9 or 16; any perfect square works) is a flat list of
N*N cells indexed row-major.  Values are 1..N, 0 means "empty".

CSP structure
    * 3N units (N rows, N columns, N boxes), each an all-different constraint.
      Unit ids: rows 0..N-1, columns N..2N-1, boxes 2N..3N-1.
    * Two cells are *peers* when they share a unit; peers are the neighbours in
      the binary constraint graph (X_i != X_j).  9x9 cell: 20 peers, 16x16: 39.
    * Domains are bitmasks: value v <-> bit (v-1); ``spec.full`` = all N bits.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from math import isqrt

_ALPHABET = "123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_EMPTY = ".0-_"


class InvalidPuzzle(ValueError):
    """Malformed puzzle text (bad length / illegal characters)."""


@dataclass(frozen=True)
class Spec:
    N: int                 # board order
    B: int                 # box side
    n: int                 # number of cells (N*N)
    units: tuple           # 3N tuples of cell ids
    peers: tuple           # peers[c] -> tuple of cell ids
    cell_units: tuple      # cell -> (row unit, col unit, box unit)
    full: int              # (1 << N) - 1


@lru_cache(maxsize=8)
def get_spec(N: int = 9) -> Spec:
    B = isqrt(N)
    if B * B != N or not 4 <= N <= len(_ALPHABET):
        raise InvalidPuzzle(f"Unsupported board order {N}: need a perfect square (4, 9, 16, 25).")
    rows = [tuple(r * N + c for c in range(N)) for r in range(N)]
    cols = [tuple(r * N + c for r in range(N)) for c in range(N)]
    boxes = [tuple((br * B + i) * N + bc * B + j for i in range(B) for j in range(B))
             for br in range(B) for bc in range(B)]
    units = tuple(rows + cols + boxes)
    cu = [[] for _ in range(N * N)]
    for uid, u in enumerate(units):
        for c in u:
            cu[c].append(uid)
    peers = []
    for c in range(N * N):
        s = set()
        for uid in cu[c]:
            s.update(units[uid])
        s.discard(c)
        peers.append(tuple(sorted(s)))
    return Spec(N, B, N * N, units, tuple(peers), tuple(tuple(x) for x in cu), (1 << N) - 1)


def name(cell: int, N: int = 9) -> str:
    """Human-readable cell name, e.g. 'R3C5'."""
    return f"R{cell // N + 1}C{cell % N + 1}"


def symbols(N: int) -> str:
    return _ALPHABET[:N]


def parse(text: str, N: int | None = None) -> list[int]:
    """Parse a puzzle string (blanks: '.', '0', '-', '_'; whitespace, '|', '+' ignored).

    Raises InvalidPuzzle for a wrong length or illegal characters.  It does *not*
    check rule consistency - call :func:`validate` for that (solvers do it).
    """
    s = "".join(ch for ch in str(text) if not ch.isspace() and ch not in "|+").upper()
    if not s:
        raise InvalidPuzzle("Puzzle is empty.")
    if N is None:
        N = round(len(s) ** 0.5)
    if len(s) != N * N:
        raise InvalidPuzzle(f"Puzzle has {len(s)} cells; a {N}x{N} board needs {N * N}.")
    get_spec(N)
    alpha = symbols(N)
    out = []
    for i, ch in enumerate(s):
        if ch in _EMPTY:
            out.append(0)
        elif ch in alpha:
            out.append(alpha.index(ch) + 1)
        else:
            raise InvalidPuzzle(f"Illegal character {ch!r} at {name(i, N)}; allowed: {alpha} and '.' for blank.")
    return out


def validate(grid, N: int = 9):
    """Return (ok, errors). Checks length, value range and duplicate givens per unit."""
    errs: list[str] = []
    spec = get_spec(N)
    if len(grid) != spec.n:
        return False, [f"Expected {spec.n} cells, got {len(grid)}."]
    for i, v in enumerate(grid):
        if not isinstance(v, int) or v < 0 or v > N:
            errs.append(f"Value {v!r} at {name(i, N)} is outside 0..{N}.")
    if errs:
        return False, errs
    kinds = ["row"] * N + ["column"] * N + ["box"] * N
    alpha = symbols(N)
    for uid, unit in enumerate(spec.units):
        seen = {}
        for c in unit:
            v = grid[c]
            if v and v in seen:
                errs.append(f"Duplicate {alpha[v - 1]} in {kinds[uid]} {uid % N + 1}: "
                            f"{name(seen[v], N)} and {name(c, N)}.")
            elif v:
                seen[v] = c
    return not errs, errs


def is_solution(grid, N: int = 9) -> bool:
    """True iff the grid is completely filled and every unit holds each digit once."""
    spec = get_spec(N)
    if len(grid) != spec.n or any(v < 1 or v > N for v in grid):
        return False
    return all(len({grid[c] for c in u}) == N for u in spec.units)


def to_string(grid, N: int | None = None) -> str:
    N = N or round(len(grid) ** 0.5)
    alpha = symbols(N)
    return "".join("." if v == 0 else alpha[v - 1] for v in grid)


def pretty(grid, N: int | None = None) -> str:
    """ASCII grid with box separators, for CLI output and logs."""
    N = N or round(len(grid) ** 0.5)
    B = isqrt(N)
    alpha = symbols(N)
    sep = "+" + "+".join(["-" * (2 * B + 1)] * B) + "+"
    lines = []
    for r in range(N):
        if r % B == 0:
            lines.append(sep)
        segs = []
        for bc in range(B):
            segs.append(" " + " ".join("." if grid[r * N + bc * B + j] == 0 else alpha[grid[r * N + bc * B + j] - 1]
                                       for j in range(B)) + " ")
        lines.append("|" + "|".join(segs) + "|")
    lines.append(sep)
    return "\n".join(lines)
