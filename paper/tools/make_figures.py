#!/usr/bin/env python3
"""S4: the paper's data figures, drawn from the committed results.

白话：画论文里两张数据图。图 2 是“陈旧实体（Missing 残留率）对节点 F1”的取舍散点，两套前端各一格，学习臂画五个种子的范围，
看出没有哪个方法两项同时最好；图 3 是主门两项的逐 house 配对差（house 上五个种子的均值），看出效应在 house 间怎么分布，
例如 SAM 2.1 身份连续率大多数 house 两臂相同。输入只有 ``results/`` 里已提交的 S3-05 统计与 S3-06 复算；输出是
``paper/figures/*.pdf``。它不计算新的统计量，也不做事后亚组挑选。

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

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
OUT = ROOT / "paper" / "figures"
STATISTICS = "vsmt_lean_s3_05_statistics_8d58475.json"
REANALYSIS = "vsmt_lean_s3_06_reanalysis_cd3ee83.json"
FRONTS = (("instance", "Simulator instance masks"), ("sam2", "SAM 2.1 masks"))
#: learned arms (filled markers) and rule-based arms (open markers); colours from the Okabe-Ito palette
STYLE = {
    "VSMT-lean": ("#D55E00", "o", True), "AssocOnly": ("#0072B2", "s", True), "NoVersion": ("#CC79A7", "D", True),
    "HeuristicLabel": ("#009E73", "^", True), "HandCost": ("#56B4E9", "v", False), "TAF": ("#000000", "s", False),
    "ELU-P": ("#E69F00", "o", False), "RAC": ("#999999", "D", False), "LOW": ("#000000", "^", False),
}
WIDTH_IN = 3.45  # one IEEE column


def load(name: str) -> Any:
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def seed_range(entry: Mapping[str, Any]) -> tuple[float, float] | None:
    values = [value for value in (entry.get("per_seed") or {}).values() if value is not None]
    return (min(values), max(values)) if values else None


def tradeoff_figure(stats: Mapping[str, Any]) -> plt.Figure:
    """Figure 2: Missing residual rate (x, lower is better) against node F1 (y), one panel per front end."""

    figure, axes = plt.subplots(1, 2, figsize=(WIDTH_IN * 2, 2.2), constrained_layout=True)
    for axis, (front, title) in zip(axes, FRONTS):
        table = stats["fronts"][front]["main_table"]
        for arm, (colour, marker, filled) in STYLE.items():
            mrr, f1 = table["missing_residual_rate"][arm], table["node_prf1"][arm]
            x, y = mrr["mean"], f1["mean"]
            x_range, y_range = seed_range(mrr), seed_range(f1)
            if x_range and y_range:
                axis.errorbar(x, y, xerr=[[x - x_range[0]], [x_range[1] - x]], yerr=[[y - y_range[0]], [y_range[1] - y]],
                              fmt="none", ecolor=colour, elinewidth=0.8, capsize=1.5)
            axis.scatter(x, y, s=28, marker=marker, color=colour if filled else "white", edgecolors=colour, linewidths=1.0,
                         zorder=3, label=arm)
        axis.set_title(title, fontsize=8)
        axis.set_xlabel("Missing residual rate (lower is better)", fontsize=7)
        axis.set_ylabel("Node F1", fontsize=7)
        axis.tick_params(labelsize=7)
        axis.grid(True, linewidth=0.3, alpha=0.5)
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="outside right center", fontsize=6.5, frameon=False)
    return figure


def per_house_figure(reanalysis: Mapping[str, Any]) -> plt.Figure:
    """Figure 3: per-house paired advantage of VSMT-lean over AssocOnly on the two gate metrics (house mean over seeds)."""

    metrics = (("missing_residual_rate", "Missing residual rate"), ("identity_continuity", "Identity continuity"))
    figure, axes = plt.subplots(2, 2, figsize=(WIDTH_IN * 2, 3.4), sharey="row", constrained_layout=True)
    for column, (front, title) in enumerate(FRONTS):
        for row, (metric, name) in enumerate(metrics):
            block = reanalysis["d5_per_house"][front][metric]
            means = sorted(entry["mean"] for entry in block["per_house"].values())
            colours = ["#D55E00" if value > 0 else "#0072B2" if value < 0 else "#999999" for value in means]
            axis = axes[row][column]
            axis.bar(range(len(means)), means, color=colours, width=0.85)
            axis.axhline(0, color="black", linewidth=0.5)
            summary = block["summary"]
            axis.set_title(f"{title}: {name}\n{block['houses']} houses; favourable {summary['favourable']}, "
                           f"unfavourable {summary['unfavourable']}, zero {summary['zero']}", fontsize=7)
            axis.set_xticks([])
            axis.tick_params(labelsize=7)
            if column == 0:
                axis.set_ylabel("Advantage\n(house mean)", fontsize=7)
    return figure


def main() -> int:
    stats, reanalysis = load(STATISTICS), load(REANALYSIS)
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42, "svg.hashsalt": "vsmt-lean", "font.family": "DejaVu Sans"})
    for name, figure in (("tradeoff.pdf", tradeoff_figure(stats)), ("per_house.pdf", per_house_figure(reanalysis))):
        figure.savefig(OUT / name, metadata={"CreationDate": None, "ModDate": None})
        if "--png" in sys.argv[1:]:
            figure.savefig((OUT / name).with_suffix(".png"), dpi=200)
        plt.close(figure)
        print(f"paper/figures/{name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
