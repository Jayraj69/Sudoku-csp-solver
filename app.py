"""Streamlit demo:  streamlit run app.py

Interactive visualisation of the Sudoku CSP solvers: pick / paste / generate a
puzzle, run any of the five algorithms, step through the decision trace, and
compare all algorithms side by side.  Bad input is rejected with a clear message.
"""
import random

import pandas as pd
import streamlit as st

from sudoku_csp.benchmark import NAMED
from sudoku_csp.board import InvalidPuzzle, is_solution, name, parse, symbols, validate
from sudoku_csp.generator import make_puzzle
from sudoku_csp.solvers import ALGORITHMS, make_solver

EASY = "003020600900305001001806400008102900700000008006708200002609500800203009005010300"
EXAMPLES = {"Easy (Norvig grid1)": EASY, **{f"Hard: {k}": v for k, v in NAMED.items()},
            "Invalid (duplicate 5 in row 1)": "55" + "." * 79,
            "Unsolvable (no duplicates, still impossible)":
                "12345678.........9.............................................................."}

st.set_page_config(page_title="Sudoku CSP Solver", layout="wide")
st.title("Sudoku as a CSP - Backtracking, MRV, Degree, Forward Checking, AC-3 (MAC)")
st.caption("ECSCT24301 Foundation of AI - Applied AI Project Track")


def board_html(cur, givens, N, highlight=None, bad=()):
    B, alpha = int(N ** 0.5), symbols(N)
    cell = 34 if N == 9 else 26
    rows = []
    for r in range(N):
        tds = []
        for c in range(N):
            i, v = r * N + c, cur[r * N + c]
            colour = "#111" if givens[i] else "#0b6bcb"
            bg = "#ffe08a" if i == highlight else ("#f9c0c0" if i in bad else "#fff")
            left = "3px solid #222" if c % B == 0 else "1px solid #aaa"
            top = "3px solid #222" if r % B == 0 else "1px solid #aaa"
            right = "3px solid #222" if c == N - 1 else "0"
            bottom = "3px solid #222" if r == N - 1 else "0"
            tds.append(f"<td style='width:{cell}px;height:{cell}px;text-align:center;font:600 {cell * .5}px monospace;"
                       f"color:{colour};background:{bg};border-left:{left};border-top:{top};"
                       f"border-right:{right};border-bottom:{bottom}'>{'' if v == 0 else alpha[v - 1]}</td>")
        rows.append("<tr>" + "".join(tds) + "</tr>")
    return "<table style='border-collapse:collapse'>" + "".join(rows) + "</table>"


with st.sidebar:
    st.header("1. Puzzle")
    src = st.radio("Source", ["Example", "Generate random", "Paste / edit"])
    N = 9
    if src == "Example":
        text = EXAMPLES[st.selectbox("Example", list(EXAMPLES))]
    elif src == "Generate random":
        N = st.radio("Board", [9, 16], horizontal=True)
        clues = st.slider("Givens", 22 if N == 9 else 110, 45 if N == 9 else 200, 28 if N == 9 else 150)
        seed = st.number_input("Seed", 0, 99999, 7)
        g, _ = make_puzzle(N, clues, random.Random(seed), unique=(N == 9))
        from sudoku_csp.board import to_string
        text = to_string(g, N)
    else:
        text = st.text_area("81 (9x9) or 256 (16x16) characters; '.' or 0 = blank", EASY, height=140)
    st.header("2. Algorithm")
    algo = st.selectbox("Solver", list(ALGORITHMS), index=4)
    limit = st.slider("Time limit (s)", 1, 60, 10)
    run = st.button("Solve", type="primary")

try:
    grid = parse(text)
    N = round(len(grid) ** 0.5)
except InvalidPuzzle as e:
    st.error(f"Invalid input: {e}")
    st.stop()

ok, errs = validate(grid, N)
givens = [bool(v) for v in grid]
left, right = st.columns([1, 1])
with left:
    st.subheader("Puzzle")
    bad = set()
    if not ok:
        for e in errs:
            st.error(e)
        import re
        for m in re.findall(r"R(\d+)C(\d+)", " ".join(errs)):
            bad.add((int(m[0]) - 1) * N + int(m[1]) - 1)
    st.markdown(board_html(grid, givens, N, bad=bad), unsafe_allow_html=True)
    st.caption(f"{sum(givens)} givens, {N * N - sum(givens)} empty cells")

if run or ok and st.session_state.get("last_text") == text:
    st.session_state["last_text"] = text
    if not ok:
        st.warning("Search skipped: the puzzle breaks the rules before any digit is placed.")
        st.stop()
    res = make_solver(algo, N, trace=True, trace_cap=20000, time_limit=limit).solve(grid)
    with right:
        st.subheader(f"{algo}: {res.status.upper()}")
        cols = st.columns(4)
        cols[0].metric("Nodes", f"{res.nodes:,}")
        cols[1].metric("Backtracks", f"{res.backtracks:,}")
        cols[2].metric("Checks", f"{res.checks / 1e6:.2f}M" if res.checks >= 1e6 else f"{res.checks:,}")
        cols[3].metric("Time (s)", f"{res.time:.3f}")
        if res.status == "solved":
            assert is_solution(res.solution, N)
            st.markdown(board_html(res.solution, givens, N), unsafe_allow_html=True)
            st.caption("black = given, blue = solved by the agent")
        elif res.status == "unsolvable":
            st.error("Search exhausted: this puzzle has NO solution.")
        else:
            st.warning("Time limit reached before the search finished.")

    evs = [e for e in res.trace if e[0] != "preprocess"]
    if evs:
        st.subheader("Step-by-step decisions")
        k = st.slider("Replay step", 0, len(evs), min(len(evs), 1))
        cur, last = list(grid), None
        for kind, cell, v, size, pruned in evs[:k]:
            cur[cell] = v if kind == "assign" else 0
            last = cell
        st.markdown(board_html(cur, givens, N, highlight=last), unsafe_allow_html=True)
        if k:
            kind, cell, v, size, pruned = evs[k - 1]
            st.write(f"Step {k}: **{kind.upper()}** {name(cell, N)} = {symbols(N)[v - 1]}"
                     + (f" (from {size} candidate(s))" if kind == "assign" else ""))

    st.subheader("Compare all algorithms on this puzzle")
    rows = []
    for a in ALGORITHMS:
        r = make_solver(a, N, time_limit=min(limit, 10)).solve(grid)
        rows.append(dict(algorithm=a, status=r.status, nodes=r.nodes, backtracks=r.backtracks,
                         checks=r.checks, prunes=r.prunes, time_s=round(r.time, 4)))
    df = pd.DataFrame(rows)
    st.dataframe(df, hide_index=True, width="stretch")
    st.bar_chart(df.set_index("algorithm")["nodes"])
