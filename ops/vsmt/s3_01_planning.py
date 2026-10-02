#!/usr/bin/env python3
"""S3-01 planning numbers for pending ruling 102: event denominators, development re-readings, null calibration and power.

白话：待裁 102 要在碰 validation／test 之前写死主门怎样判。这个脚本只读已提交的开发集与确认集合并审计（实例分割开发集、
实例分割确认集、SAM2 开发集；VSMT-lean 与 AssocOnly 各 5 个种子，四个规则臂各一份），回答四件事：
  * 身份连续率的考题是否各臂相同：每个臂“搬动后第一次带标签重见”的事件数（与臂无关）与其中“搬动前该臂有承载实体”的
    事件数（条件定义的分母，随臂变化）；
  * 两种身份连续率定义（已登记的条件定义：分母只含搬动前有承载实体的事件；候选的共同事件定义：分母是全部重见事件，搬动前
    没有承载实体记失败）与两种排除清单（主表全部运行都可算 / 只看参与比较的两臂）下，开发读数各是多少；
  * 零效应校准：真实收益为 0 时，四种判定规则（只按 house 重采样；它加 82-1 种子稳定条件；种子与 house 两级重采样加 82-1；
    只有两级重采样）有多大概率误判“成立”；
  * 功效与情景：真实收益取若干事先列出的正值、种子波动取若干值时，按 test 尝试生成 100 个 house 折算的有效 house 数，各规则
    判“成立”的概率；另报把开发估计直接代入的情景。
模拟是半参数的：house 部分从开发数据逐 house 整行重抽（每行是该 house 5 个种子的配对差减去各种子的均值，保留真实的 house
间差异与 house 内种子噪声），种子部分另加均值 0、标准差为设定值的正态偏移，再加上设定的真实收益。例如真实收益 0、种子标准差
0.05 时，“只按 house 重采样”把这 5 个模型当成固定的，误判率会高于 5%，两级重采样不会。它不读 validation／test，不改任何合同，
数字只用于规划：开发集是样本内的，确认集只有 43 个 house，正态种子偏移与平移收益都是假设。

The two-level resampling draws house indices and seed indices independently; every drawn seed is evaluated on the same drawn
houses (houses and seeds are crossed: one trained model is audited on every house), following the crossed-array bootstrap of
Owen and Eckles; its coverage with five seeds is not guaranteed, which is why the null calibration is reported.

Usage:
  python ops/vsmt/s3_01_planning.py --output results/vsmt_lean_s3_01_planning_<commit>.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
STAGE = "vsmt.lean.s3_01.planning.v1"
SEEDS = (7, 19, 31, 43, 59)
RULE_ARMS = ("TAF", "ELU-P", "RAC", "LOW")
LEARNED = ("VSMT-lean", "AssocOnly")
LEVEL = 0.95
PLANNING_SEED = 102
TEST_ATTEMPTED = (100, 200)

#: Committed merged audits per source (file names under results/); every development and confirmation block attempted 50 houses.
SOURCES: dict[str, dict[str, Any]] = {
    "instance_dev": {
        "attempted_houses": 50,
        "learned": {"VSMT-lean": "vsmt_lean_ruling96_audit_GROUPED-A{seed}_7c76970.json",
                    "AssocOnly": "vsmt_lean_ruling95_audit_ASSOC-A{seed}_d835cd3.json"},
        "rules": "vsmt_lean_ruling95_audit_RULE-{arm}_d835cd3.json",
    },
    "instance_confirmation": {
        "attempted_houses": 50,
        "learned": {"VSMT-lean": "vsmt_lean_ruling97_audit_GROUPED-A{seed}_5176bb6.json",
                    "AssocOnly": "vsmt_lean_ruling97_audit_ASSOC-A{seed}_5176bb6.json"},
        "rules": "vsmt_lean_ruling97_audit_RULE-{arm}_5176bb6.json",
    },
    "sam2_dev": {
        "attempted_houses": 50,
        "learned": {"VSMT-lean": "vsmt_lean_s2_06_audit_VSMT-A{seed}_c0b166e.json",
                    "AssocOnly": "vsmt_lean_s2_06_audit_ASSOC-A{seed}_c0b166e.json"},
        "rules": "vsmt_lean_s2_06_audit_RULE-{arm}_c0b166e.json",
    },
}


# --------------------------------------------------------------------------
# metric definitions (per episode report of a merged node audit)
# --------------------------------------------------------------------------

def missing_residual_rate(report: Mapping[str, Any]) -> float | None:
    value = report["missing_residual_rate"]["missing_residual_rate"]
    return None if value is None else float(value)


def identity_continuity_conditional(report: Mapping[str, Any]) -> float | None:
    """The registered definition (ruling M): kept / judged; judged counts only re-observed moved objects with a pre-move carrier."""

    block = report["identity_continuity"]
    return (block["kept"] / block["judged"]) if block["judged"] else None


def identity_continuity_common(report: Mapping[str, Any]) -> float | None:
    """The candidate common-event definition: kept / every re-observed moved object; no pre-move carrier counts as not kept."""

    block = report["identity_continuity"]
    events = block["judged"] + block["no_prior_carrier"]
    return (block["kept"] / events) if events else None


METRICS: dict[str, tuple[Callable[[Mapping[str, Any]], float | None], str]] = {
    "missing_residual_rate": (missing_residual_rate, "lower"),
    "identity_continuity_conditional": (identity_continuity_conditional, "higher"),
    "identity_continuity_common": (identity_continuity_common, "higher"),
}


# --------------------------------------------------------------------------
# inputs
# --------------------------------------------------------------------------

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_files(source: Mapping[str, Any]) -> dict[tuple[str, int | None], str]:
    files: dict[tuple[str, int | None], str] = {}
    for arm, pattern in source["learned"].items():
        for seed in SEEDS:
            files[(arm, seed)] = pattern.format(seed=seed)
    for arm in RULE_ARMS:
        files[(arm, None)] = source["rules"].format(arm=arm)
    return files


def load_reports(path: Path) -> dict[str, Mapping[str, Any]]:
    merged = json.loads(path.read_text(encoding="utf-8"))
    return {str(row["episode_id"]): row["report"] for row in merged["per_episode"]}


def denominators(reports: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    totals = {"reobserved": 0, "judged": 0, "no_prior_carrier": 0, "kept": 0}
    for report in reports.values():
        block = report["identity_continuity"]
        totals["judged"] += int(block["judged"])
        totals["no_prior_carrier"] += int(block["no_prior_carrier"])
        totals["kept"] += int(block["kept"])
    totals["reobserved"] = totals["judged"] + totals["no_prior_carrier"]
    return totals


# --------------------------------------------------------------------------
# exclusion lists, difference matrices and the registered rules
# --------------------------------------------------------------------------

def defined_houses(values: Mapping[tuple[str, int | None], Mapping[str, float | None]],
                   runs: Sequence[tuple[str, int | None]]) -> list[str]:
    """Houses whose metric is defined in every listed run (X2: one list per metric; extended to the seeds)."""

    common = set.intersection(*(set(values[run]) for run in runs))
    return sorted(h for h in common if all(values[run][h] is not None for run in runs))


def difference_matrix(values: Mapping[tuple[str, int | None], Mapping[str, float | None]], houses: Sequence[str],
                      direction: str) -> np.ndarray:
    """d[h, s] = VSMT-lean minus AssocOnly at seed s, signed so that positive means VSMT-lean is better."""

    sign = -1.0 if direction == "lower" else 1.0
    return np.array([[sign * (values[("VSMT-lean", s)][h] - values[("AssocOnly", s)][h]) for s in SEEDS] for h in houses], dtype=float)


def stable_in_favour(gaps: Sequence[float]) -> bool:
    """82-1 in the favourable direction: all five seeds, at least four favourable gaps, mean > 0 and mean > sd of the gaps."""

    if len(gaps) != len(SEEDS):
        return False
    mean = statistics.fmean(gaps)
    favourable = sum(g > 0 for g in gaps)
    return favourable >= 4 and mean > 0 and abs(mean) > statistics.stdev(gaps)


def lower_index(iterations: int, level: float = LEVEL) -> int:
    """The same index rule as lean_teacher.paired_house_bootstrap: floor((1 - level) * iterations) of the sorted means."""

    return min(int(math.floor((1.0 - level) * iterations)), iterations - 1)


def house_means(matrix: np.ndarray, house_idx: np.ndarray) -> np.ndarray:
    """Resampled means of the seed-averaged house differences; house_idx has shape (iterations, n)."""

    return matrix.mean(axis=1)[house_idx].mean(axis=1)


def two_level_means(matrix: np.ndarray, house_idx: np.ndarray, seed_idx: np.ndarray) -> np.ndarray:
    """Resampled means over drawn houses x drawn seeds; every drawn seed uses the same drawn houses (crossed design).

    house_idx has shape (iterations, n) and seed_idx (iterations, seeds); result[b] = mean_i mean_j matrix[house_idx[b, i], seed_idx[b, j]].
    """

    rows = matrix[house_idx]  # (iterations, n, seeds)
    picked = np.take_along_axis(rows, np.broadcast_to(seed_idx[:, None, :], rows.shape[:2] + (seed_idx.shape[1],)), axis=2)
    return picked.mean(axis=(1, 2))


def lower_bounds(matrix: np.ndarray, rng: np.random.Generator, iterations: int) -> dict[str, float]:
    n, seeds = matrix.shape
    house_idx = rng.integers(0, n, size=(iterations, n))
    seed_idx = rng.integers(0, seeds, size=(iterations, seeds))
    index = lower_index(iterations)
    return {"house": float(np.sort(house_means(matrix, house_idx))[index]),
            "two_level": float(np.sort(two_level_means(matrix, house_idx, seed_idx))[index])}


def decisions(matrix: np.ndarray, rng: np.random.Generator, iterations: int) -> dict[str, bool]:
    """The four candidate rules on one difference matrix."""

    bounds = lower_bounds(matrix, rng, iterations)
    stable = stable_in_favour(list(matrix.mean(axis=0)))
    return {"house_only": bounds["house"] > 0, "house_and_82_1": bounds["house"] > 0 and stable,
            "two_level_and_82_1": bounds["two_level"] > 0 and stable, "two_level_only": bounds["two_level"] > 0}


def components(matrix: np.ndarray) -> dict[str, float]:
    """Two-way decomposition d[h, s] = mu + a_s + b_h + e_hs (seed, house, residual), moment estimates truncated at zero."""

    n, seeds = matrix.shape
    seed_means = matrix.mean(axis=0)
    row_means = matrix.mean(axis=1)
    mu = float(matrix.mean())
    residual = matrix - row_means[:, None] - seed_means[None, :] + mu
    var_e = float((residual ** 2).sum() / ((n - 1) * (seeds - 1))) if n > 1 else 0.0
    var_seed_means = float(np.var(seed_means, ddof=1))
    var_row_means = float(np.var(row_means, ddof=1)) if n > 1 else 0.0
    return {"mean": mu, "sd_seed": math.sqrt(max(0.0, var_seed_means - var_e / n)),
            "sd_house": math.sqrt(max(0.0, var_row_means - var_e / seeds)), "sd_residual": math.sqrt(var_e), "houses": n}


def centred_rows(matrix: np.ndarray) -> np.ndarray:
    """Each house's five seed differences minus the seed means: house heterogeneity and within-house noise, no seed effect, mean 0."""

    return matrix - matrix.mean(axis=0)[None, :]


def simulate(rows: np.ndarray, *, effect: float, sd_seed: float, houses: int, replicates: int, iterations: int,
             rng: np.random.Generator) -> dict[str, float]:
    """Share of replicates in which each rule passes: rows resampled whole, a seed offset ~ N(0, sd_seed) per seed, plus effect."""

    passed = {"house_only": 0, "house_and_82_1": 0, "two_level_and_82_1": 0, "two_level_only": 0}
    for _ in range(replicates):
        base = rows[rng.integers(0, rows.shape[0], size=houses)]
        offsets = rng.normal(0.0, sd_seed, size=rows.shape[1]) if sd_seed > 0 else np.zeros(rows.shape[1])
        verdict = decisions(effect + offsets[None, :] + base, rng, iterations)
        for name, ok in verdict.items():
            passed[name] += int(ok)
    return {name: count / replicates for name, count in passed.items()}


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def build(args: argparse.Namespace) -> dict[str, Any]:
    rng = np.random.default_rng(PLANNING_SEED)
    report: dict[str, Any] = {
        "stage": STAGE, "code_commit": git_commit(), "script_sha256": sha256(Path(__file__)), "python": sys.version.split()[0],
        "numpy": np.__version__, "platform": platform.platform(), "planning_seed": PLANNING_SEED,
        "settings": {"reading_iterations": args.reading_iterations, "simulation_iterations": args.simulation_iterations,
                     "null_replicates": args.null_replicates, "power_replicates": args.power_replicates, "level": LEVEL,
                     "test_attempted_houses": list(TEST_ATTEMPTED), "null_sd_seed": args.null_sd_seed,
                     "power_sd_seed": args.power_sd_seed, "effects": {k: v for k, v in args.effects.items()}},
        "inputs": {}, "denominators": {}, "readings": {}, "components": {}, "null_calibration": {}, "power": {}, "plug_in": {},
    }
    for source_name, source in SOURCES.items():
        files = run_files(source)
        reports = {}
        for run, name in files.items():
            path = RESULTS / name
            report["inputs"][name] = sha256(path)
            reports[run] = load_reports(path)
        report["denominators"][source_name] = {
            f"{arm}:{seed}" if seed is not None else arm: denominators(reports[(arm, seed)]) for arm, seed in files}
        reobserved = {run: {h: r["identity_continuity"]["judged"] + r["identity_continuity"]["no_prior_carrier"]
                            for h, r in reports[run].items()} for run in files}
        houses_all = sorted(set.intersection(*(set(v) for v in reobserved.values())))
        report["denominators"][source_name]["reobserved_events_identical_across_runs"] = all(
            len({reobserved[run][h] for run in files}) == 1 for h in houses_all)
        main_runs = list(files)
        pair_runs = [(arm, seed) for arm in LEARNED for seed in SEEDS]
        for metric, (value_of, direction) in METRICS.items():
            values = {run: {h: value_of(r) for h, r in reports[run].items()} for run in files}
            for list_name, runs in (("main_table", main_runs), ("pair", pair_runs)):
                houses = defined_houses(values, runs)
                matrix = difference_matrix(values, houses, direction)
                gaps = [float(g) for g in matrix.mean(axis=0)]
                per_seed_sets = []
                for s in SEEDS:
                    hs = [h for h in houses_all if values[("VSMT-lean", s)].get(h) is not None and values[("AssocOnly", s)].get(h) is not None]
                    sign = -1.0 if direction == "lower" else 1.0
                    per_seed_sets.append(statistics.fmean(sign * (values[("VSMT-lean", s)][h] - values[("AssocOnly", s)][h]) for h in hs))
                bounds = lower_bounds(matrix, rng, args.reading_iterations)
                key = f"{source_name}|{metric}|{list_name}"
                report["readings"][key] = {
                    "houses": len(houses), "houses_per_attempted": len(houses) / source["attempted_houses"],
                    "seed_paired_gaps": gaps, "mean": float(matrix.mean()), "stable_in_favour_82_1": stable_in_favour(gaps),
                    "lower_bound_house_only": bounds["house"], "lower_bound_two_level": bounds["two_level"],
                    "per_seed_house_sets_mean_gap_as_in_the_82_1_readings": statistics.fmean(per_seed_sets),
                }
                report["components"][key] = components(matrix)
                if list_name != ("pair" if metric == "identity_continuity_conditional" else "main_table"):
                    continue  # simulate on the list each definition would use (conditional: the two compared arms; others: X2)
                rows = centred_rows(matrix)
                share = len(houses) / source["attempted_houses"]
                sizes = {str(t): max(3, round(share * t)) for t in TEST_ATTEMPTED}
                report["null_calibration"][key] = {
                    f"sd_seed={sd}": {"houses": sizes["100"], **simulate(rows, effect=0.0, sd_seed=sd, houses=sizes["100"],
                                                                            replicates=args.null_replicates,
                                                                            iterations=args.simulation_iterations, rng=rng)}
                    for sd in args.null_sd_seed}
                family = "missing_residual_rate" if metric == "missing_residual_rate" else "identity_continuity"
                grid = {}
                for effect in args.effects[family]:
                    for sd in args.power_sd_seed:
                        for size_name, size in sizes.items():
                            if size_name != "100" and metric != "identity_continuity_common":
                                continue
                            grid[f"effect={effect}|sd_seed={sd}|test={size_name}"] = {
                                "houses": size, **simulate(rows, effect=effect, sd_seed=sd, houses=size,
                                                           replicates=args.power_replicates,
                                                           iterations=args.simulation_iterations, rng=rng)}
                report["power"][key] = grid
                comp = report["components"][key]
                report["plug_in"][key] = {"effect": comp["mean"], "sd_seed": comp["sd_seed"], "houses": sizes["100"],
                                          **simulate(rows, effect=comp["mean"], sd_seed=comp["sd_seed"], houses=sizes["100"],
                                                     replicates=args.power_replicates, iterations=args.simulation_iterations, rng=rng)}
    report["plain_language_zh"] = (
        "规划用数字，只读已提交的开发集与确认集合并审计。denominators：各臂身份连续率的事件数（reobserved 与臂无关；judged 是条件定义"
        "的分母，随臂变化）。readings：两种定义、两种排除清单下的开发读数（样本内）。null_calibration：真实收益为 0 时各判定规则判“成立”"
        "的比例（应不超过 5%）。power：事先列出的真实收益与种子波动下各规则判“成立”的比例。plug_in：把开发估计直接代入的情景，"
        "不是 S3 的预测。")
    report["caveats"] = [
        "development readings are in-sample (30 of 39 houses train the heads); the confirmation block has 43 houses",
        "the simulation resamples whole development house rows and adds normal seed offsets and a constant shift; bounded and discrete "
        "metrics are treated as additive",
        "simulation iterations are fewer than the registered 10,000; pass shares carry Monte Carlo error of about "
        "sqrt(p(1-p)/replicates)",
        "houses per test = (defined development houses / 50 attempted) x test houses attempted",
    ]
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--output", required=True)
    parser.add_argument("--reading-iterations", type=int, default=10_000)
    parser.add_argument("--simulation-iterations", type=int, default=1_000)
    parser.add_argument("--null-replicates", type=int, default=2_000)
    parser.add_argument("--power-replicates", type=int, default=500)
    args = parser.parse_args(argv)
    args.null_sd_seed = [0.0, 0.02, 0.05, 0.10]
    args.power_sd_seed = [0.0, 0.03, 0.06]
    args.effects = {"missing_residual_rate": [0.05, 0.10, 0.20], "identity_continuity": [0.02, 0.04, 0.06, 0.08, 0.10, 0.15]}
    report = build(args)
    Path(args.output).write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    for key, value in report["readings"].items():
        print(f"[s3-01-planning] {key}: houses {value['houses']}, mean {value['mean']:+.4f}, 82-1 {value['stable_in_favour_82_1']}, "
              f"LB house {value['lower_bound_house_only']:+.4f}, LB two-level {value['lower_bound_two_level']:+.4f}")
    print(f"[s3-01-planning] wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
