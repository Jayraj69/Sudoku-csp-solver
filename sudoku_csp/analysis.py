"""Empirical verification of the heuristic / propagation properties claimed in the report.

    python -m sudoku_csp.analysis            -> results/heuristic_analysis.json + .txt

P1  h_u(n) = #unassigned cells is admissible and consistent  (verified on search paths)
P2  h_2(n) = 2*h_u(n) is NOT admissible                       (counter-example)
P3  h_s(n) = #unassigned cells with |domain|>1 is admissible but NOT consistent
P4  AC-3 is sound: it never deletes a value that occurs in the (unique) solution
P5  FC is strictly weaker than AC-3: states where FC accepts an assignment that
    AC-3 refutes immediately
"""
from __future__ import annotations
import json
import os
import random

from .board import get_spec, name, to_string, is_solution
from .generator import make_puzzle
from .solvers import DomainSolver, Result, make_solver


class _Probe(DomainSolver):
    """Records h-values before/after every assignment performed by the search."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.edges = []          # (hu_before, hu_after, hs_before, hs_after, ok)

    def _h(self):
        un = [c for c in range(self.n) if not self.assigned[c]]
        return len(un), sum(1 for c in un if self.dom[c].bit_count() > 1)

    def _assign(self, cell, v):
        hu0, hs0 = self._h()
        ok = super()._assign(cell, v)
        if ok:
            hu1, hs1 = self._h()
            self.edges.append((hu0, hu1, hs0, hs1))
        return ok


def heuristic_properties(n_puzzles=40, seed=11, clues=26):
    rng = random.Random(seed)
    tot = dict(edges=0, hu_cons_viol=0, h2_adm_viol=0, hs_cons_viol=0, hs_adm_viol=0,
               max_hs_drop=0, puzzles=0)
    example = None
    for _ in range(n_puzzles):
        puz, sol = make_puzzle(9, clues, rng)
        for algo_ac3 in (False, True):
            p = _Probe(N=9, ac3=algo_ac3, time_limit=5)
            r = p.solve(puz)
            tot["puzzles"] += 1
            for hu0, hu1, hs0, hs1 in p.edges:
                tot["edges"] += 1
                tot["hu_cons_viol"] += hu0 > 1 + hu1
                tot["h2_adm_viol"] += 2 * hu0 > hu0          # true cost-to-go of a solvable state is hu0
                tot["hs_adm_viol"] += hs0 > hu0
                if hs0 > 1 + hs1:
                    tot["hs_cons_viol"] += 1
                    tot["max_hs_drop"] = max(tot["max_hs_drop"], hs0 - hs1)
                    if example is None:
                        example = dict(hs_before=hs0, hs_after=hs1, hu_before=hu0, hu_after=hu1,
                                       puzzle=to_string(puz))
    tot["example_inconsistent_edge"] = example
    return tot


def ac3_soundness(n_puzzles=200, seed=5):
    rng = random.Random(seed)
    bad = removed = cells = 0
    for _ in range(n_puzzles):
        puz, sol = make_puzzle(9, rng.choice([30, 26, 24]), rng)
        s = make_solver("MAC", 9, node_limit=0)
        s.solve(puz)                          # stops before the first search node
        for c in range(81):
            cells += 1
            if not s.dom[c] >> (sol[c] - 1) & 1:
                bad += 1
        removed += sum(81 * 9 - 0 for _ in [0]) and sum(9 - d.bit_count() for d in s.dom)
    return dict(puzzles=n_puzzles, cells_checked=cells, solution_values_removed=bad,
                total_values_pruned_by_preprocessing=removed)


def fc_vs_ac3_gap(n_puzzles=60, seed=3, clues=25):
    """Count (cell, value) trial assignments at the root where FC reports no
    wipe-out but MAC refutes the assignment immediately."""
    rng = random.Random(seed)
    trials = gap = 0
    example = None
    for _ in range(n_puzzles):
        puz, _ = make_puzzle(9, clues, rng)
        fc, mac = make_solver("FC", 9), make_solver("MAC", 9)
        for s in (fc, mac):
            s.res = Result(s.name, 9, "unsolvable")
        if not (fc.prepare(puz) and mac.prepare(puz)):
            continue
        for x in range(81):
            if fc.assigned[x]:
                continue
            for v in range(1, 10):
                if not (mac.dom[x] >> (v - 1)) & 1:
                    continue
                trials += 1
                m1, a1 = len(fc.trail), len(fc.astack)
                ok_fc = fc._assign(x, v)
                fc._undo(m1, a1)
                m2, a2 = len(mac.trail), len(mac.astack)
                ok_mac = mac._assign(x, v)
                mac._undo(m2, a2)
                if ok_fc and not ok_mac:
                    gap += 1
                    if example is None:
                        example = dict(puzzle=to_string(puz), cell=name(x), value=v)
    return dict(trial_assignments=trials, fc_accepts_mac_refutes=gap, example=example)


def main(out="results"):
    os.makedirs(out, exist_ok=True)
    res = dict(heuristics=heuristic_properties(), ac3_soundness=ac3_soundness(),
               fc_vs_ac3=fc_vs_ac3_gap())
    with open(os.path.join(out, "heuristic_analysis.json"), "w") as f:
        json.dump(res, f, indent=2)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
