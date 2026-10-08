#!/usr/bin/env python3
"""S4: the paper's data figures, drawn from the committed results.

白话：画论文里的数据图，每个数都直接取自 ``results/`` 里已提交的导出，不算新的统计量，也不做事后亚组挑选。
- ``gate.pdf``：主门固定顺序三步（对同配方 AssocOnly）与原主门（对最强规则臂，只报告）的点图。点是五个种子平均的优势，横线是两级
  重采样的双侧 90% 区间（左端就是检验用的单侧 95% 下界），竖短线是五个种子各自的配对差。例如 SAM 2.1 身份连续率那一行的区间跨过 0，
  五个种子只有一个在 0 右边，所以第三步不成立。
- ``comparisons.pdf``：VSMT-lean 对其余八个臂、七项指标的优势，三格（ProcTHOR 实例分割、ProcTHOR SAM 2.1、3RScan 实例分割），
  格子按双侧 90% 区间着色：区间整个在 0 右边（VSMT-lean 更好）、整个在 0 左边（对方更好）或跨 0。它是描述性的，不是检验；
  它取代了原附录的两张逐指标区间表与 3RScan 表。
输入：S3-05 统计、S3-06 复算（区间）、S3-07 外部验证统计；输出：``paper/figures/*.pdf``。它不等于新的分析：所有区间都是导出里已有的数。
图 1（概览）与图 2（单帧流程）是 TikZ 手绘，不含数据，在 ``paper/figures/overview.tex``、``method.tex``。

Usage (repository root): python paper/tools/make_figures.py [--png]   (--png also writes PNG previews, not committed)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
OUT = ROOT / "paper" / "figures"
STATISTICS = "vsmt_lean_s3_05_statistics_8d58475.json"
REANALYSIS = "vsmt_lean_s3_06_reanalysis_cd3ee83.json"
EXTERNAL = "vsmt_lean_s3_07_statistics_aa94373.json"
COMPARED = ("AssocOnly", "NoVersion", "HeuristicLabel", "HandCost", "TAF", "ELU-P", "RAC", "LOW")
#: (metric key, column label, decimals) for the comparison matrix; advantages are signed so that > 0 favours VSMT-lean
MATRIX_METRICS = (
    ("node_prf1", "F1", 3), ("missing_residual_rate", "MRR", 3), ("false_retract_rate_in_scope", "FRR$_\\mathrm{in}$", 3),
    ("identity_continuity", "IdC", 3), ("retrieval_success", "Retr.", 3), ("recovery_latency_frames", "Lat.", 1),
    ("contamination_auc", "Cont.", 3),
)
WIDTH_IN = 3.45  # one IEEE column
FULL_WIDTH_IN = 7.16  # two IEEE columns
INK, MUTED, GRID = "#222222", "#666666", "#d9d9d9"
#: comparison-matrix fills: VSMT-lean better / other arm better (interval excludes zero) / interval includes zero / undefined
FILL = {"better": "#c6dbef", "worse": "#f6c9ad", "open": "#ffffff", "undefined": "#f0f0f0"}
ACCENT = "#D55E00"  # VSMT-lean (Okabe-Ito vermillion)


def load(name: str) -> Any:
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def gate_figure(stats: Mapping[str, Any], reanalysis: Mapping[str, Any]) -> plt.Figure:
    """The fixed-order test of the primary hypothesis and the original gate, as a dot plot with intervals.

    The 90% interval is the exported two-sided two-level interval (S3-06 D3); its lower end must equal the one-sided 95%
    lower bound that the S3-05 test used, which is checked here so that the figure cannot drift from the test."""

    panels = (("missing_residual_rate", "(a) Missing residual rate: reduction by VSMT-lean", (-0.1, 0.62), ("1", "2")),
              ("identity_continuity", "(b) Identity continuity: gain by VSMT-lean", (-0.075, 0.25), ("1", "3")))
    front_names = {"instance": "instance", "sam2": "SAM 2.1"}
    left, right = 0.335, 0.80
    figure, axes = plt.subplots(2, 1, figsize=(WIDTH_IN, 2.2))
    figure.subplots_adjust(left=left, right=right, top=0.905, bottom=0.135, hspace=0.75)
    for axis, (metric, title, limits, steps) in zip(axes, panels):
        rows = []
        for step, front in zip(steps, ("instance", "sam2")):
            block = stats["fronts"][front]["primary_gate"]["metrics"][metric]
            interval = reanalysis["d3_intervals"][front][metric]["AssocOnly"]["interval_90"]
            rows.append((f"vs. AssocOnly, {front_names[front]}", block, interval, f"step {step}: "))
        for front in ("instance", "sam2"):
            block = stats["fronts"][front]["original_gate"]["metrics"][metric]
            control = block["strongest_control"]
            interval = reanalysis["d3_intervals"][front][metric][control]["interval_90"]
            rows.append((f"vs. {control}, {front_names[front]}", block, interval, ""))
        for label, block, interval, _ in rows:
            if abs(interval[0] - block["lower_bound_two_level"]) > 1e-12:
                raise SystemExit(f"interval and lower bound disagree for {metric} {label}")
        positions = [0, 1, 2.55, 3.55]
        for y, (label, block, interval, prefix) in zip(positions, rows):
            axis.plot(interval, [y, y], color=ACCENT, linewidth=1.3, solid_capstyle="butt", zorder=2)
            axis.plot([interval[0]] * 2, [y - 0.2, y + 0.2], color=ACCENT, linewidth=1.3, zorder=2)
            axis.scatter(block["seed_paired_gaps"], [y + 0.38] * len(block["seed_paired_gaps"]), marker="|", s=26,
                         color=MUTED, linewidths=0.9, zorder=2)
            holds = bool(block["passed"])
            axis.scatter([block["mean_advantage"]], [y], s=22, marker="o", zorder=3, linewidths=1.0,
                         color=ACCENT if holds else "white", edgecolors=ACCENT)
            axis.text(1.04, y, prefix + ("holds" if holds else "fails"), transform=axis.get_yaxis_transform(),
                      ha="left", va="center", fontsize=6.6, color=INK)
        axis.axvline(0, color=INK, linewidth=0.6, zorder=1)
        axis.axhline(1.775, color=GRID, linewidth=0.6)
        axis.text(1.04, 1.775, "original gate:", transform=axis.get_yaxis_transform(), ha="left", va="center",
                  fontsize=6.3, color=MUTED, style="italic")
        axis.set_yticks(positions, [row[0] for row in rows], fontsize=6.6)
        axis.set_ylim(4.05, -0.55)
        axis.set_xlim(*limits)
        figure.text(0.012, axis.get_position().y1 + 0.022, title, fontsize=6.9, ha="left", va="bottom", color=INK)
        axis.tick_params(axis="x", labelsize=6.6, length=2, pad=1.5)
        axis.tick_params(axis="y", length=0)
        axis.grid(True, axis="x", linewidth=0.3, color=GRID)
        for side in ("top", "right", "left"):
            axis.spines[side].set_visible(False)
    axes[1].set_xlabel("Advantage of VSMT-lean (> 0 favours VSMT-lean)", fontsize=6.6, labelpad=1.5)
    return figure


def matrix_cell(entry: Mapping[str, Any] | None) -> tuple[str, float | None]:
    """The fill class and the advantage of one comparison; the class follows the exported two-sided 90% interval."""

    if not entry or entry.get("not_applicable") or entry.get("interval_90") is None:
        return "undefined", None
    low, high = entry["interval_90"]
    return ("better" if low > 0 else "worse" if high < 0 else "open"), entry["mean_advantage"]


def cell_text(value: float, decimals: int) -> str:
    """A compact signed number: rates without the leading zero (+.527), latency in frames (+24.7); a value that rounds
    to zero is printed unsigned."""

    text = f"{0:.{decimals}f}" if round(value, decimals) == 0 else f"{value:+.{decimals}f}"
    if decimals == 3:
        text = text.replace("0.", ".", 1)
    return text.replace("-", "−")


def comparisons_figure(reanalysis: Mapping[str, Any], external: Mapping[str, Any]) -> plt.Figure:
    """VSMT-lean against every other arm, every metric, three data panels; cells coloured by the 90% interval."""

    panels = (
        ("(a) ProcTHOR test, instance masks", reanalysis["d3_intervals"]["instance"]),
        ("(b) ProcTHOR test, SAM 2.1 masks", reanalysis["d3_intervals"]["sam2"]),
        ("(c) 3RScan validation, instance masks", external["fronts"]["instance"]["comparisons"]),
    )
    figure, axes = plt.subplots(1, 3, figsize=(FULL_WIDTH_IN, 1.82), gridspec_kw={"wspace": 0.05},
                                constrained_layout=False)
    figure.subplots_adjust(left=0.127, right=0.997, top=0.78, bottom=0.13)
    rows, columns = len(COMPARED), len(MATRIX_METRICS)
    for index, (axis, (title, comparisons)) in enumerate(zip(axes, panels)):
        for row, arm in enumerate(COMPARED):
            for column, (key, _, decimals) in enumerate(MATRIX_METRICS):
                kind, value = matrix_cell((comparisons.get(key) or {}).get(arm))
                axis.add_patch(Rectangle((column, row), 1, 1, facecolor=FILL[kind], edgecolor="white", linewidth=1.2))
                text = "–" if value is None else cell_text(value, decimals)
                axis.text(column + 0.5, row + 0.52, text, ha="center", va="center", fontsize=6.1, color=INK,
                          fontweight="bold" if kind in ("better", "worse") else "normal")
        axis.axhline(4, color=INK, linewidth=0.6)
        axis.set_xlim(0, columns)
        axis.set_ylim(rows, 0)
        axis.set_xticks([column + 0.5 for column in range(columns)], [label for _, label, _ in MATRIX_METRICS], fontsize=6.6)
        axis.xaxis.tick_top()
        axis.tick_params(length=0, pad=1.5)
        axis.set_title(title, fontsize=7.0, pad=10)
        if index == 0:
            axis.set_yticks([row + 0.5 for row in range(rows)], [f"vs. {arm}" for arm in COMPARED], fontsize=6.6)
        else:
            axis.set_yticks([])
        for side in axis.spines.values():
            side.set_visible(False)
    handles = [Rectangle((0, 0), 1, 1, facecolor=FILL[kind], edgecolor=MUTED, linewidth=0.4)
               for kind in ("better", "worse", "open", "undefined")]
    labels = ["VSMT-lean better", "other arm better", "90% interval includes 0", "not defined (never retracts)"]
    figure.legend(handles, labels, loc="lower center", ncol=4, fontsize=6.6, frameon=False, handlelength=1.4,
                  bbox_to_anchor=(0.55, -0.015), columnspacing=2.2)
    return figure


def main() -> int:
    stats, reanalysis, external = load(STATISTICS), load(REANALYSIS), load(EXTERNAL)
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42, "svg.hashsalt": "vsmt-lean", "font.family": "DejaVu Sans"})
    figures = (("gate.pdf", gate_figure(stats, reanalysis)), ("comparisons.pdf", comparisons_figure(reanalysis, external)))
    for name, figure in figures:
        figure.savefig(OUT / name, metadata={"CreationDate": None, "ModDate": None})
        if "--png" in sys.argv[1:]:
            figure.savefig((OUT / name).with_suffix(".png"), dpi=200)
        plt.close(figure)
        print(f"paper/figures/{name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
