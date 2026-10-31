"""Five CSP solvers for Sudoku, all instrumented with the same metrics.

  BT           plain backtracking, static (row-major) variable order     [baseline]
  BT+MRV       backtracking, Minimum-Remaining-Values variable order
  BT+MRV+DEG   MRV with the Degree heuristic as tie-breaker
  FC           MRV+DEG with Forward Checking (domains are maintained)
  MAC          MRV+DEG with Maintaining Arc Consistency (AC-3 after every
               assignment, plus an AC-3 pre-processing pass)

Metric definitions (identical across algorithms)
  nodes       value assignments tried (search nodes generated)
  expanded    search states for which a variable was selected
  decisions   nodes created where the chosen variable still had >1 value
  backtracks  assignments undone after their subtree failed
  checks      constraint checks: one test of "X_i != X_j" for a pair of
              cells (BT variants, FC) or one value-support test (AC-3)
  prunes      values removed from domains (FC / MAC only)
  revisions   AC-3 arc revisions (MAC only)
  max_depth   deepest recursion level reached
"""
from __future__ import annotations
import random
import sys
import time
from collections import deque
from dataclasses import dataclass, field

from .board import get_spec, validate

sys.setrecursionlimit(10000)


class _Stop(Exception):
    """Raised internally when a node/time limit is hit."""


@dataclass
class Result:
    algorithm: str
    N: int
    status: str                    # solved | unsolvable | invalid | timeout
    solution: list | None = None
    solutions_found: int = 0
    nodes: int = 0
    expanded: int = 0
    decisions: int = 0
    backtracks: int = 0
    checks: int = 0
    prunes: int = 0
    revisions: int = 0
    max_depth: int = 0
    domain_sum: int = 0            # for average branching factor
    time: float = 0.0
    errors: list = field(default_factory=list)
    trace: list = field(default_factory=list)

    @property
    def avg_branching(self) -> float:
        return self.domain_sum / self.expanded if self.expanded else 0.0

    def as_dict(self) -> dict:
        d = {k: getattr(self, k) for k in
             ("algorithm", "N", "status", "nodes", "expanded", "decisions", "backtracks",
              "checks", "prunes", "revisions", "max_depth", "time")}
        d["avg_branching"] = round(self.avg_branching, 3)
        return d


class _Base:
    name = "base"

    def __init__(self, N: int = 9, node_limit: int | None = None,
                 time_limit: float | None = None, trace: bool = False,
                 max_solutions: int = 1, rng: random.Random | None = None,
                 trace_cap: int = 20000):
        self.N, self.spec = N, get_spec(N)
        self.n = N * N
        self.node_limit, self.time_limit = node_limit, time_limit
        self.want_trace, self.trace_cap = trace, trace_cap
        self.max_solutions, self.rng = max_solutions, rng

    # -- shared helpers -------------------------------------------------
    def _log(self, *event):
        if self.want_trace and len(self.res.trace) < self.trace_cap:
            self.res.trace.append(event)

    def _tick(self):
        r = self.res
        r.nodes += 1
        if self.node_limit is not None and r.nodes > self.node_limit:
            raise _Stop
        if self.time_limit is not None and (r.nodes & 127) == 0 \
                and time.perf_counter() - self.t0 > self.time_limit:
            raise _Stop

    def _values(self, mask: int) -> list[int]:
        vals = [b + 1 for b in range(self.N) if mask >> b & 1]
        if self.rng is not None:
            self.rng.shuffle(vals)
        return vals

    def solve(self, grid: list[int]) -> Result:
        self.res = Result(self.name, self.N, "unsolvable")
        ok, errs = validate(grid, self.N)
        if not ok:
            self.res.status, self.res.errors = "invalid", errs
            return self.res
        self.t0 = time.perf_counter()
        try:
            self._run(list(grid))
            if self.res.solutions_found:
                self.res.status = "solved"
        except _Stop:
            self.res.status = "solved" if self.res.solutions_found else "timeout"
        self.res.time = time.perf_counter() - self.t0
        return self.res

    def _record(self, grid):
        r = self.res
        r.solutions_found += 1
        if r.solution is None:
            r.solution = list(grid)
        return r.solutions_found >= self.max_solutions


# ----------------------------------------------------------------------
class GridSolver(_Base):
    """Backtracking that only stores the grid (no domain bookkeeping).

    mrv=False                -> static row-major order
    mrv=True, degree=False   -> MRV, ties broken by lowest cell index
    mrv=True, degree=True    -> MRV, ties broken by largest number of
                                unassigned peers (degree heuristic)
    Legal values of a cell are always recomputed from its peers (literal
    constraint checks), which is what makes MRV costly without propagation.
    """

    def __init__(self, *a, mrv=False, degree=False, **kw):
        super().__init__(*a, **kw)
        self.mrv, self.degree = mrv, degree
        self.name = "BT+MRV+DEG" if degree else ("BT+MRV" if mrv else "BT")

    def _run(self, grid):
        self.g = grid
        self.order = [c for c in range(self.n) if grid[c] == 0]
        self.unassigned = set(self.order)
        self._search(0)

    def _legal_mask(self, cell):
        g, mask = self.g, 0
        for p in self.spec.peers[cell]:
            self.res.checks += 1
            v = g[p]
            if v:
                mask |= 1 << (v - 1)
        return self.spec.full & ~mask

    def _pick(self, depth):
        best, best_mask, best_key = None, 0, None
        peers = self.spec.peers
        for c in self.unassigned:
            m = self._legal_mask(c)
            size = m.bit_count()
            if self.degree:
                deg = sum(1 for p in peers[c] if p in self.unassigned)
                key = (size, -deg, c)
            else:
                key = (size, c)
            if best_key is None or key < best_key:
                best, best_mask, best_key = c, m, key
                if size == 0:
                    break
        return best, best_mask

    def _search(self, depth):
        r, g = self.res, self.g
        if not self.unassigned:
            return self._record(g)
        r.max_depth = max(r.max_depth, depth)
        if self.mrv:
            cell, mask = self._pick(depth)
            vals = self._values(mask)
        else:
            cell = self.order[depth]
            vals = list(range(1, self.N + 1))
            if self.rng is not None:
                self.rng.shuffle(vals)
        r.expanded += 1
        r.domain_sum += len(vals) if self.mrv else self.N
        for v in vals:
            if not self.mrv:       # literal legality test against each peer
                legal = True
                for p in self.spec.peers[cell]:
                    r.checks += 1
                    if g[p] == v:
                        legal = False
                        break
                if not legal:
                    continue
            self._tick()
            if len(vals) > 1:
                r.decisions += 1
            g[cell] = v
            self.unassigned.discard(cell)
            self._log("assign", cell, v, len(vals), 0)
            if self._search(depth + 1):
                return True
            g[cell] = 0
            self.unassigned.add(cell)
            r.backtracks += 1
            self._log("backtrack", cell, v, 0, 0)
        return False


# ----------------------------------------------------------------------
class DomainSolver(_Base):
    """MRV+Degree search over explicit bitmask domains.

    ac3=False -> Forward Checking: after assigning X=v, remove v from the
                 domains of X's unassigned peers; fail on an empty domain.
    ac3=True  -> MAC: after assigning X=v run AC-3 seeded with the arcs
                 (peer, X); cascades through every newly forced singleton.
    """

    def __init__(self, *a, ac3=False, **kw):
        super().__init__(*a, **kw)
        self.ac3 = ac3
        self.name = "MAC" if ac3 else "FC"

    # -- propagation ------------------------------------------------------
    def _set(self, cell, new):
        self.trail.append((cell, self.dom[cell]))
        self.dom[cell] = new

    def _undo(self, mark, amark):
        t = self.trail
        while len(t) > mark:
            c, d = t.pop()
            self.dom[c] = d
        a = self.astack
        while len(a) > amark:
            self.assigned[a.pop()] = False

    def _forward_check(self, cell, bit):
        r, dom = self.res, self.dom
        for p in self.spec.peers[cell]:
            r.checks += 1
            if dom[p] & bit:
                self._set(p, dom[p] & ~bit)
                r.prunes += 1
                if dom[p] == 0:
                    return False
        return True

    def _ac3(self, arcs):
        r, dom, peers = self.res, self.dom, self.spec.peers
        q = deque(arcs)
        inq = set(arcs)
        while q:
            xi, xj = q.popleft()
            inq.discard((xi, xj))
            di, dj = dom[xi], dom[xj]
            r.revisions += 1
            r.checks += di.bit_count()              # support test for each value of D(xi)
            if dj & (dj - 1) == 0 and di & dj:      # D(xj) singleton {b}: b loses support in xi
                self._set(xi, di & ~dj)
                r.prunes += 1
                if dom[xi] == 0:
                    return False
                for xk in peers[xi]:
                    if xk != xj and (xk, xi) not in inq:
                        q.append((xk, xi))
                        inq.add((xk, xi))
        return True

    def _assign(self, cell, v):
        bit = 1 << (v - 1)
        if not self.dom[cell] & bit:
            return False
        self._set(cell, bit)
        self.assigned[cell] = True
        self.astack.append(cell)
        if self.ac3:
            return self._ac3([(p, cell) for p in self.spec.peers[cell]])
        return self._forward_check(cell, bit)

    # -- search ------------------------------------------------------------
    def prepare(self, grid) -> bool:
        """Load givens and run the initial propagation (FC: peers of each given;
        MAC: AC-3 over all arcs).  Returns False if a contradiction is found."""
        n, full = self.n, self.spec.full
        self.dom = [full] * n
        self.assigned = [False] * n
        self.astack, self.trail = [], []
        ok = True
        for c, v in enumerate(grid):
            if v and ok:
                if self.ac3:
                    ok = self._assign_given_mac(c, v)
                else:
                    ok = self._assign(c, v)
        if ok and self.ac3:                          # AC-3 pre-processing over all arcs
            ok = self._ac3([(a, b) for a in range(n) for b in self.spec.peers[a]])
            self._log("preprocess", -1, 0, sum(d.bit_count() for d in self.dom), 0)
        return ok

    def _run(self, grid):
        if self.prepare(grid):
            self._search(0)

    def _assign_given_mac(self, c, v):
        # givens are loaded first and propagated together by the pre-processing pass
        bit = 1 << (v - 1)
        if not self.dom[c] & bit:
            return False
        self._set(c, bit)
        self.assigned[c] = True
        self.astack.append(c)
        return True

    def _select(self):
        dom, assigned, peers = self.dom, self.assigned, self.spec.peers
        best, best_key = None, None
        for c in range(self.n):
            if assigned[c]:
                continue
            size = dom[c].bit_count()
            if best_key is not None and size > best_key[0]:
                continue
            deg = 0
            for p in peers[c]:
                if not assigned[p]:
                    deg += 1
            key = (size, -deg, c)
            if best_key is None or key < best_key:
                best, best_key = c, key
        return best

    def _search(self, depth):
        r = self.res
        cell = self._select()
        if cell is None:
            return self._record([self.dom[c].bit_length() for c in range(self.n)])
        r.max_depth = max(r.max_depth, depth)
        mask = self.dom[cell]
        vals = self._values(mask)
        r.expanded += 1
        r.domain_sum += len(vals)
        for v in vals:
            self._tick()
            if len(vals) > 1:
                r.decisions += 1
            mark, amark, p0 = len(self.trail), len(self.astack), r.prunes
            ok = self._assign(cell, v)
            self._log("assign", cell, v, len(vals), r.prunes - p0)
            if ok and self._search(depth + 1):
                return True
            self._undo(mark, amark)
            r.backtracks += 1
            self._log("backtrack", cell, v, 0, 0)
        return False


# ----------------------------------------------------------------------
ALGORITHMS = {
    "BT": lambda **kw: GridSolver(mrv=False, degree=False, **kw),
    "BT+MRV": lambda **kw: GridSolver(mrv=True, degree=False, **kw),
    "BT+MRV+DEG": lambda **kw: GridSolver(mrv=True, degree=True, **kw),
    "FC": lambda **kw: DomainSolver(ac3=False, **kw),
    "MAC": lambda **kw: DomainSolver(ac3=True, **kw),
}


def make_solver(name: str, N: int = 9, **kw):
    return ALGORITHMS[name](N=N, **kw)
