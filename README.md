# Sudoku Solver Using Constraint Satisfaction
Sudoku is modelled as a CSP (81 variables, domains in 1..9, 27 all-different units). Five solvers are
implemented and compared with identical instrumentation:

| Solver | Variable order | Inference | Role |
|---|---|---|---|
| `BT` | row-major | none | baseline |
| `BT+MRV` | smallest remaining domain | none | advanced |
| `BT+MRV+DEG` | MRV, ties -> highest degree | none | improved |
| `FC` | MRV + degree | forward checking | optimised |
| `MAC` | MRV + degree | AC-3 after every assignment (+ pre-processing) | optimised |

## Setup
```bash
python -m venv .venv && source .venv/bin/activate      # Python 3.11+
pip install -r requirements.txt
```

## Run
```bash
streamlit run app.py                                    # GUI demo (step replay, compare all solvers, 16x16)
python -m sudoku_csp.cli solve "<81 chars>" --algo MAC --trace 40
python -m sudoku_csp.cli random --clues 26 --seed 7 --compare
python -m sudoku_csp.cli random --size 16 --clues 150 --algo FC
pytest -q                                               # 30 tests
```

## Reproduce every number / figure of the report
```bash
python -m sudoku_csp.benchmark          # ~8 min -> results/benchmark_results.csv (seed 2026)
python -m sudoku_csp.analysis           # heuristic property experiments -> results/heuristic_analysis.json
python -m sudoku_csp.demo_logs          # step-by-step decision logs -> results/logs/
python -m sudoku_csp.figures            # tables + plots -> results/*.csv, results/figures/*.png
```
**Norvig (easy50, top95, hardest) and Kaggle (Radcliffe, 3M puzzles) sets.** They need internet, so run once on your
machine and benchmark them on top of the built-in families:
```bash
python scripts/fetch_data.py
python -m sudoku_csp.benchmark --extra data/top95.txt --extra-label norvig-top95 --extra-n 95
python -m sudoku_csp.benchmark --extra data/easy50.txt --extra-label norvig-easy50 --extra-n 50
```
(Kaggle: `kaggle datasets download -d radcliffe/3-million-sudoku-puzzles-with-ratings -p data --unzip`, then pass the CSV.)

## Metric definitions (same for every solver)
`nodes` = value assignments tried; `backtracks` = assignments undone after their subtree failed; `checks` = one test of
X_i != X_j (BT variants, FC) or one value-support test (AC-3); `prunes` = values removed from domains;
`max_depth`; wall-clock `time`. Time limits: 5 s (9x9), 15 s (16x16); a hit limit is reported as `timeout`, never as a result.

## Layout
```
sudoku_csp/board.py       topology (units, peers), parse, validate, pretty-print
sudoku_csp/solvers.py     GridSolver (BT, BT+MRV, BT+MRV+DEG) and DomainSolver (FC, MAC)
sudoku_csp/generator.py   unique-solution puzzles, 16x16, invalid and unsolvable instances
sudoku_csp/benchmark.py   harness  |  analysis.py  heuristic/propagation experiments
sudoku_csp/demo_logs.py   decision logs  |  figures.py  plots and tables  |  cli.py  command line
app.py                    Streamlit GUI     tests/   pytest suite     docs/  report inputs, viva notes
```

## Proposal / guideline coverage
| Requirement | Where |
|---|---|
| PEAS, formulation (state, actions, goal, cost) | report Sec. 2 |
| Baseline BT, MRV, Degree, FC, AC-3 (MAC) | `sudoku_csp/solvers.py` |
| Completeness / optimality / time / space analysis | report Sec. 4 |
| Admissibility and consistency of heuristics + counter-examples | report Sec. 4.4, `analysis.py` |
| Norvig / Kaggle data, own generator (invalid, unsolvable, 16x16) | `generator.py`, `benchmark.py --extra` |
| Benchmark table small / medium / large, 3 plot types | `results/benchmark_summary.csv`, `results/figures/` |
| Error & failure analysis | report Sec. 8 |
| Interactive prototype, unseen inputs, bad-input handling | `app.py`, `cli.py` |
| Demonstration logs (exact decision sequences) | `results/logs/demo_*.txt` |
| Report, slides, viva preparation | `docs/` |
