# Viva preparation - be able to explain every answer in your own words

Each of you is examined individually, including a walkthrough of code you wrote. Split the code between you
(e.g. board/validation + generator; GridSolver; DomainSolver + benchmark/GUI) and make sure each person can
explain their part line by line.

**State space and branching factor.** State = partial assignment. Initial = validated givens. Depth = number of empty
cells E (every solution path has exactly E assignments). Branching <= 9 for plain BT; observed average branching with
MRV/FC/MAC is ~1.0-1.1 because MRV picks cells with one candidate first (`avg_branching` column). Raw search space
<= 9^E; for 57 empties that is ~10^54 - the reason heuristics matter.

**Completeness / optimality.** All five solvers are complete: pruning only removes values that cannot be in any solution
(AC-3 soundness was checked: 0 of 16,200 solution values removed). Sudoku is a satisfaction problem; all solutions cost E,
so "optimal" is trivial; what we minimise is search effort. Time: O(9^E) worst case for BT; AC-3 is O(e*d^3) per call
(e = 1620 arcs, d = 9). Space: O(E) recursion depth + O(N^2) domains + trail.

**Heuristic admissibility / consistency.** h_u(n) = #unassigned cells equals the true remaining cost h*(n) -> admissible and
consistent (h(n) = 1 + h(n') along every edge). h_2 = 2*h_u overestimates -> not admissible (all 10,751 edges violate).
h_s = #cells with |domain| > 1 is admissible but not consistent (3,030 edges violate; example in report Sec. 4.4).
MRV/Degree are *ordering* heuristics: they never affect correctness, only the size of the tree.

**Why FC/MAC need fewer nodes but sometimes more time.** They do more work per node (pruning, queue). Checks are not
comparable across families (one pair test vs one support test). On 16x16 in pure Python the overhead plus heavy-tailed
runtimes mean BT+MRV solved more puzzles than MAC within 15 s - report this honestly.

**Dead ends / cycles.** A dead end = empty domain (or no legal digit); the search backtracks. No cycles: each branch assigns
a new variable, depth strictly increases. Unsolvable puzzle: all 4 domain-aware solvers prove it instantly; plain BT
times out on 6 of 7 (it must exhaust the tree).

**AC-3 limits.** Arc consistency on the binary != constraints is weaker than all-different (Hall sets / hidden singles), so
search is still needed; FC accepted 2,164 of 11,112 trial assignments that AC-3 refutes immediately.

**Likely questions.** Why bitmasks? Why count nodes *and* checks? Why is BT+MRV+DEG not always better than BT+MRV
(tie-breaking changes the tree; on 49 medium puzzles means were 642 vs 624 nodes)? What does a time-out mean? How did you
make sure puzzles have a unique solution (count_solutions with limit 2)? How do you detect invalid input?
