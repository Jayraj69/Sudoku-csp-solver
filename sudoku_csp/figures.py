"""Create every table and figure of the report from results/*.csv.

    python -m sudoku_csp.figures            (after python -m sudoku_csp.benchmark)
"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

from .board import parse, pretty
from .solvers import ALGORITHMS, make_solver

ORDER = list(ALGORITHMS)
COL = {"BT": "#7f7f7f", "BT+MRV": "#1f77b4", "BT+MRV+DEG": "#2ca02c", "FC": "#ff7f0e", "MAC": "#d62728"}
MARK = {"BT": "o", "BT+MRV": "s", "BT+MRV+DEG": "^", "FC": "D", "MAC": "v"}
plt.rcParams.update({"font.size": 10, "axes.grid": True, "grid.alpha": .3, "figure.dpi": 150})


def _save(fig, out, name):
    fig.tight_layout()
    fig.savefig(os.path.join(out, "figures", name), dpi=170)
    plt.close(fig)


def load(res_dir="results"):
    d = pd.read_csv(os.path.join(res_dir, "benchmark_results.csv"))
    d["timeout"] = d["status"] == "timeout"
    return d


def summary_table(d, out):
    s = d[d.kind == "solve"]
    g = s.groupby(["size_class", "algorithm"])
    t = g.agg(instances=("id", "nunique"), solved=("status", lambda x: int((x == "solved").sum())),
              timeouts=("timeout", "sum"), mean_time_s=("time", "mean"), median_time_s=("time", "median"),
              mean_nodes=("nodes", "mean"), mean_backtracks=("backtracks", "mean"),
              mean_checks=("checks", "mean"), mean_prunes=("prunes", "mean")).reset_index()
    t["algorithm"] = pd.Categorical(t["algorithm"], ORDER, ordered=True)
    t["size_class"] = pd.Categorical(t["size_class"], ["small", "medium", "large"], ordered=True)
    t = t.sort_values(["size_class", "algorithm"])
    t.round(4).to_csv(os.path.join(out, "benchmark_summary.csv"), index=False)
    return t


def sweep_plots(d, out):
    s = d[(d.kind == "solve") & (d.N == 9) & d.family.str.startswith("9x9-c")]
    for metric, ylabel, name in (("time", "Mean runtime per puzzle (s, log scale)", "fig1_time_vs_empties.png"),
                                 ("nodes", "Mean nodes generated (log scale)", "fig2_nodes_vs_complexity.png"),
                                 ("backtracks", "Mean backtracks (log scale)", "fig3_backtracks.png")):
        fig, ax = plt.subplots(figsize=(6.2, 4))
        for a in ORDER:
            m = s[s.algorithm == a].groupby("empties")[metric].mean()
            ax.plot(m.index, m.values.clip(min=1e-4 if metric == "time" else 0.5), marker=MARK[a], color=COL[a], label=a)
        ax.set_yscale("log")
        ax.set_xlabel("Empty cells (search depth / state-space size)")
        ax.set_ylabel(ylabel)
        ax.set_title("9x9 clue sweep (unique-solution puzzles; time-outs plotted at the cap)", fontsize=9)
        ax.legend()
        _save(fig, out, name)


def pruning_plot(d, out):
    s = d[(d.kind == "solve")]
    med = s.groupby(["size_class", "algorithm"])["nodes"].median().unstack()
    med = med[ORDER]
    red = (1 - med.div(med["BT"], axis=0)) * 100
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    w = 0.16
    classes = [c for c in ["small", "medium", "large"] if c in red.index]
    for i, a in enumerate(ORDER[1:]):
        ax.bar(np.arange(len(classes)) + (i - 1.5) * w, [red.loc[c, a] for c in classes], w, color=COL[a], label=a)
    ax.set_xticks(range(len(classes)))
    ax.set_xticklabels([{"small": "small (>=32 clues)", "medium": "medium (<32 clues)", "large": "large (16x16)"}[c] for c in classes])
    ax.set_ylabel("Search-tree reduction vs BT (%)")
    ax.set_title("Pruning efficiency (median nodes; higher = more of the tree pruned)", fontsize=9)
    ax.legend(ncol=2, fontsize=8)
    _save(fig, out, "fig4_pruning_efficiency.png")
    red.round(2).to_csv(os.path.join(out, "pruning_efficiency.csv"))


def large_plot(d, out):
    s = d[(d.kind == "solve") & (d.N == 16)]
    if s.empty:
        return
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.8))
    fams = sorted(s.family.unique(), reverse=True)
    w = 0.16
    for i, a in enumerate(ORDER):
        v = [s[(s.algorithm == a) & (s.family == f)]["time"].mean() for f in fams]
        axs[0].bar(np.arange(len(fams)) + (i - 2) * w, v, w, color=COL[a], label=a)
        ok = [int(((s.algorithm == a) & (s.family == f) & (s.status == "solved")).sum()) for f in fams]
        axs[1].bar(np.arange(len(fams)) + (i - 2) * w, ok, w, color=COL[a], label=a)
    for ax, t in zip(axs, ("Mean runtime (s) - capped at time limit", "Puzzles solved within limit")):
        ax.set_xticks(range(len(fams)))
        ax.set_xticklabels([f.replace("16x16-d", "").replace("d", "") + "% given" for f in fams])
        ax.set_title(t, fontsize=9)
    axs[0].legend(fontsize=7)
    _save(fig, out, "fig5_scalability_16x16.png")


def named_plot(d, out):
    s = d[d.family.str.startswith("named-")]
    if s.empty:
        return
    p = s.pivot_table(index="family", columns="algorithm", values="nodes")[ORDER]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    w = 0.16
    for i, a in enumerate(ORDER):
        ax.bar(np.arange(len(p)) + (i - 2) * w, p[a].clip(lower=1), w, color=COL[a], label=a)
    ax.set_yscale("log")
    ax.set_xticks(range(len(p)))
    ax.set_xticklabels([x.replace("named-", "") for x in p.index], fontsize=8)
    ax.set_ylabel("Nodes generated (log)")
    ax.set_title("Named hard puzzles (bars for BT may be time-out lower bounds)", fontsize=9)
    ax.legend(fontsize=7)
    _save(fig, out, "fig6_named_hard.png")
    p.to_csv(os.path.join(out, "named_hard_nodes.csv"))


def checks_plot(d, out):
    s = d[(d.kind == "solve") & (d.N == 9)]
    m = s.groupby("algorithm")[["nodes", "checks"]].median().loc[ORDER]
    fig, ax = plt.subplots(figsize=(6, 3.6))
    x = np.arange(len(ORDER))
    ax.bar(x - .2, m["nodes"], .4, label="nodes", color="#4c72b0")
    ax.bar(x + .2, m["checks"], .4, label="constraint checks", color="#dd8452")
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(ORDER, fontsize=8)
    ax.legend()
    ax.set_title("Median effort per 9x9 puzzle: fewer nodes != fewer checks", fontsize=9)
    _save(fig, out, "fig7_nodes_vs_checks.png")


def edge_table(d, out):
    e = d[d.kind != "solve"]
    t = e.groupby(["kind", "algorithm"]).agg(cases=("id", "nunique"),
                                              correct=("correct", lambda x: int((x == True).sum())),  # noqa: E712
                                              timeouts=("timeout", "sum"), mean_nodes=("nodes", "mean")).reset_index()
    t.to_csv(os.path.join(out, "edge_case_summary.csv"), index=False)


def box(ax, xy, w, h, text, fc="#dbe9f6"):
    ax.add_patch(FancyBboxPatch(xy, w, h, boxstyle="round,pad=0.02,rounding_size=0.05", fc=fc, ec="#34495e", lw=1.2))
    ax.text(xy[0] + w / 2, xy[1] + h / 2, text, ha="center", va="center", fontsize=8)


def arrow(ax, a, b):
    ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="->", color="#34495e", lw=1.2))


def diagrams(out):
    fig, ax = plt.subplots(figsize=(8, 5.4))
    ax.set_xlim(0, 10); ax.set_ylim(0, 7.2); ax.axis("off"); ax.grid(False)
    box(ax, (0.3, 6.2), 2.6, .8, "Puzzle input\n(string / file / generator)")
    box(ax, (3.7, 6.2), 2.6, .8, "parse() + validate()\nlength, symbols, duplicate givens", "#fde9d9")
    box(ax, (7.1, 6.2), 2.6, .8, "Reject with message\n(invalid input)", "#f9c0c0")
    arrow(ax, (2.9, 6.6), (3.7, 6.6)); arrow(ax, (6.3, 6.6), (7.1, 6.6))
    box(ax, (3.7, 4.9), 2.6, .8, "CSP model\n81 vars, domains (bitmasks)\n27 all-different units")
    arrow(ax, (5.0, 6.2), (5.0, 5.7))
    box(ax, (0.3, 3.4), 2.8, .9, "SELECT-VARIABLE\nstatic | MRV | MRV + Degree", "#e2f0d9")
    box(ax, (3.6, 3.4), 2.8, .9, "ASSIGN value\n(natural order)", "#e2f0d9")
    box(ax, (6.9, 3.4), 2.8, .9, "INFERENCE\nnone | Forward Checking | AC-3 (MAC)", "#e2f0d9")
    arrow(ax, (5.0, 4.9), (1.7, 4.3)); arrow(ax, (3.1, 3.85), (3.6, 3.85)); arrow(ax, (6.4, 3.85), (6.9, 3.85))
    box(ax, (6.9, 2.0), 2.8, .8, "Domain wipe-out / conflict?\n-> BACKTRACK, try next value", "#fde9d9")
    arrow(ax, (8.3, 3.4), (8.3, 2.8))
    arrow(ax, (6.9, 2.5), (5.6, 3.4))
    box(ax, (0.3, 2.0), 2.8, .8, "Goal test first:\nall cells assigned & 27 units OK?", "#fff2cc")
    arrow(ax, (1.7, 3.4), (1.7, 2.8))
    box(ax, (3.6, .5), 2.8, .9, "Solution + metrics + trace\n(nodes, backtracks, checks, time)", "#d9d2e9")
    arrow(ax, (2.6, 2.0), (4.2, 1.4))
    box(ax, (6.9, .5), 2.8, .9, "Streamlit GUI / CLI /\nbenchmark harness", "#d9d2e9")
    arrow(ax, (6.4, .95), (6.9, .95))
    ax.set_title("Solver architecture", fontsize=11)
    _save(fig, out, "fig_architecture.png")

    fig, ax = plt.subplots(figsize=(9, 1.9))
    ax.set_xlim(0, 10); ax.set_ylim(0, 2); ax.axis("off"); ax.grid(False)
    steps = ["1 Problem\n& PEAS", "2 State-space\nmodel", "3 Data /\nbenchmarks", "4 Baseline\nBT", "5 MRV, Degree,\nFC, AC-3",
             "6 Heuristic\nanalysis", "7 Benchmark", "8 Failure\nanalysis", "9 GUI /\ndemo"]
    for i, s in enumerate(steps):
        box(ax, (i * 1.1 + .02, .5), 1.0, 1.0, s, "#dbe9f6")
        if i:
            arrow(ax, (i * 1.1 - .08, 1.0), (i * 1.1 + .02, 1.0))
    _save(fig, out, "fig_pipeline.png")


def board_figure(grid, sol, N, title, path, out):
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.7))
    B = int(N ** 0.5)
    for ax, g, t in zip(axs, (grid, sol), ("Input puzzle", "Solved by the agent")):
        ax.set_xlim(0, N); ax.set_ylim(N, 0); ax.set_aspect("equal"); ax.axis("off"); ax.grid(False)
        for k in range(N + 1):
            lw = 2.2 if k % B == 0 else .5
            ax.plot([0, N], [k, k], color="k", lw=lw); ax.plot([k, k], [0, N], color="k", lw=lw)
        for i, v in enumerate(g):
            if v:
                given = grid[i] != 0
                ax.text(i % N + .5, i // N + .55, "0123456789ABCDEFG"[v], ha="center", va="center",
                        fontsize=11 if N == 9 else 7, color="k" if given else "#0b6bcb", fontweight="bold")
        ax.set_title(t, fontsize=10)
    fig.suptitle(title, fontsize=10)
    _save(fig, out, path)


def demo_boards(out):
    easy = parse("003020600900305001001806400008102900700000008006708200002609500800203009005010300")
    inkala = parse("800000000003600000070090200050007000000045700000100030001000068008500010090000400")
    for g, algo, title, path in ((easy, "MAC", "Norvig grid1 (easy), solved with MAC", "fig_demo_easy.png"),
                                 (inkala, "MAC", "Inkala 2012 puzzle, solved with MAC", "fig_demo_inkala.png")):
        r = make_solver(algo, 9, time_limit=30).solve(g)
        board_figure(g, r.solution, 9, title, path, out)


def main(res_dir="results"):
    os.makedirs(os.path.join(res_dir, "figures"), exist_ok=True)
    d = load(res_dir)
    t = summary_table(d, res_dir)
    sweep_plots(d, res_dir); pruning_plot(d, res_dir); large_plot(d, res_dir)
    named_plot(d, res_dir); checks_plot(d, res_dir); edge_table(d, res_dir)
    diagrams(res_dir); demo_boards(res_dir)
    print(t.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
