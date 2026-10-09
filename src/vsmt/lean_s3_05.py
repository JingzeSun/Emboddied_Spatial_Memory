"""S3-05 (ruling 107, 2026-10-05): the statistics of the one test run, assembled from the frozen functions.

Ruling 107-4 fixes what is computed after the test run and how. This module arranges the merged test audits (one per
front end and run) as house x run tables and then calls only frozen functions:
  * primary gate: ``lean_teacher.primary_gate`` (VSMT-lean against AssocOnly, one exclusion list per main-gate metric,
    two-level resampling plus 82-1) once per front end, then ``fixed_sequence`` over three steps (instance
    segmentation, both metrics -> SAM 2.1 Missing residual rate -> SAM 2.1 identity continuity);
  * original gate: ``original_gate`` (against the strongest rule arm per metric on test), reported only;
  * report-only comparisons: VSMT-lean against every ablation and rule arm on every metric, with the same one exclusion
    list, two-level resampling and 82-1 as the gate (``gate_metric``; ruling 102-2: the original gate and the ablations
    use the same lists and resampling and are reported only); learned arms are paired by seed, rule arms and HandCost
    are seedless;
  * node F1: the VSMT-lean minus AssocOnly difference and its 90% interval (5th/95th percentiles of the two-level
    resampling, the same draws and bootstrap seed as the gate);
  * main table: each arm's mean per metric over the houses the metric's list keeps, with per-seed values and the mean
    +- standard deviation over the 5 seeds for learned arms (ruling 85-2 (1)); decomposition totals, size and cost,
    per-run failures, effective house counts and exclusion lists.
Input: the merged per-episode audit rows and the usable test episode list; output: one statistics object. A (run,
episode) without an audit is None in every metric (ruling 107-2); for a main-table run the house is then excluded for
the affected metrics for every arm by the one list and counted; no house is replaced. It reads no data file and changes
no frozen function.
"""

from __future__ import annotations

import math
import random
import statistics
from typing import Any, Mapping, Sequence

from vsmt import lean_arms as arms
from vsmt import lean_development as dev
from vsmt import lean_evaluation as ev
from vsmt import lean_teacher as lt

STAGE = "vsmt.lean.s3_05.v1"
FRONTS = {"instance": "simulator_instance_masks", "sam2": "sam2"}
#: every headline metric, in the evaluator's order (the eighth, retrieval success, included)
REPORT_METRICS = tuple(ev.HEADLINE_FIELD)
DIRECTION = dict(dev.BETTER)
LEARNED_ARMS = ("VSMT-lean", "NoVersion", "HeuristicLabel", "AssocOnly")
#: VSMT-lean against each of these, every metric, report only (AssocOnly is the primary comparison)
COMPARED_ARMS = ("NoVersion", "HeuristicLabel", "HandCost", "TAF", "ELU-P", "RAC", "LOW")
NODE_F1_INTERVAL = (0.05, 0.95)
STATISTICS_RULE = (
    "ruling 107-4: per front end one house x run table per metric; primary_gate (VSMT-lean vs AssocOnly) on each front end, then "
    "fixed_sequence; original_gate reported; VSMT-lean against every ablation and rule arm on every metric with the same one "
    "exclusion list, two-level resampling and 82-1 (gate_metric), reported only; node F1 difference with the 5th/95th two-level "
    "percentiles; bootstrap seed and iterations from the freeze receipt"
)


class LeanS3_05Error(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanS3_05Error(code)


def key(arm: str, seed: int | None) -> str:
    return lt.run_key(arm, seed)


def not_applicable_keys(metric: str, keys: Sequence[str]) -> list[str]:
    """Runs of arms without RETRACT for the false-retract metrics (lean_teacher METRIC_NOT_APPLICABLE_RULE)."""

    if metric not in lt.METRIC_NOT_APPLICABLE_RULE:
        return []
    without = set(arms.arms_without_atom("RETRACT"))
    return [k for k in keys if k.split(":")[0] in without]


def tables(runs: Sequence[Mapping[str, Any]], episodes: Sequence[str]) -> tuple[dict[str, dict[str, dict[str, Any]]], list[dict[str, Any]]]:
    """Per metric {house: {run key: value or None}} over the usable test episodes, and every (run, episode) without an audit.

    ``runs`` lists ``{"arm", "seed", "rows": {episode: merged per-episode row}}``; a missing row is a failure of that run on that
    episode: None in every metric (ruling 107-2), never a replaced house."""

    _require(bool(runs) and bool(episodes), "statistics_need_runs_and_episodes")
    keys = [key(run["arm"], run.get("seed")) for run in runs]
    _require(len(set(keys)) == len(keys), "statistics_run_repeated")
    out: dict[str, dict[str, dict[str, Any]]] = {metric: {str(h): {} for h in episodes} for metric in REPORT_METRICS}
    failures = []
    for run, run_key in zip(runs, keys):
        rows = run["rows"]
        _require(set(map(str, rows)) <= set(map(str, episodes)), f"statistics_rows_outside_the_episodes:{run_key}")
        for house in episodes:
            row = rows.get(house)
            if row is None:
                failures.append({"run": run_key, "episode": house})
            for metric, field in ev.HEADLINE_FIELD.items():
                out[metric][str(house)][run_key] = None if row is None else row["report"][metric][field]
    return out, failures


def two_level_interval(matrix: Sequence[Sequence[float]], *, seed: int, iterations: int = lt.BOOTSTRAP_ITERATIONS,
                       quantiles: tuple[float, float] = NODE_F1_INTERVAL) -> list[float]:
    """The two-level resampling of lean_teacher.two_level_lower_bound (same draws for the same seed), at two percentiles.

    The lower percentile at 0.05 equals two_level_lower_bound's one-sided 95% bound; a test pins that."""

    _require(len(matrix) >= 2 and iterations >= 1, "interval_needs_two_houses")
    width = len(matrix[0])
    _require(width >= 1 and all(len(row) == width for row in matrix), "interval_matrix_ragged")
    rng = random.Random(seed)
    n = len(matrix)
    means = []
    for _ in range(iterations):
        weights = [0] * width
        for _s in range(width):
            weights[rng.randrange(width)] += 1
        row_values = [sum(w * v for w, v in zip(weights, row)) for row in matrix]
        total = sum(row_values[rng.randrange(n)] for _h in range(n))
        means.append(total / (n * width))
    means.sort()
    return [means[min(int(math.floor(q * iterations)), iterations - 1)] for q in quantiles]


def _mean_sd(values: Sequence[float]) -> dict[str, Any]:
    values = [float(v) for v in values]
    return {"mean": statistics.fmean(values) if values else None,
            "sd": statistics.stdev(values) if len(values) >= 2 else None, "n": len(values)}


def front_statistics(per_metric: Mapping[str, Mapping[str, Mapping[str, Any]]], runs: Sequence[Mapping[str, Any]], *,
                     seed: int, iterations: int = lt.BOOTSTRAP_ITERATIONS) -> dict[str, Any]:
    """Every statistic of one front end (ruling 107-4)."""

    keys = sorted({k for houses in per_metric.values() for row in houses.values() for k in row})
    main_runs = [k for k in lt.main_table_runs() if k in keys]
    gate_tables = {metric: per_metric[metric] for metric, _ in lt.MAIN_GATE}
    primary = lt.primary_gate(gate_tables, seed=seed, iterations=iterations)
    original = lt.original_gate(gate_tables, seed=seed, iterations=iterations)
    lists, table_rows, comparisons = {}, {}, {}
    for metric in REPORT_METRICS:
        table = per_metric[metric]
        skipped = not_applicable_keys(metric, main_runs)
        excluded = lt.exclusion_over_runs(table, runs=main_runs, not_applicable=skipped)
        kept = [h for h in sorted(table) if h not in set(excluded)]
        lists[metric] = {"excluded_houses": excluded, "effective_houses": len(kept), "not_applicable_runs": skipped,
                         "rule": "ruling 102-3: one list per metric over every main-table run (every arm, every seed)"}
        rows = {}
        for arm in dict.fromkeys(k.split(":")[0] for k in keys):
            arm_keys = [k for k in keys if k.split(":")[0] == arm]
            if not_applicable_keys(metric, arm_keys):
                rows[arm] = {"not_applicable": True}
                continue
            per_key = {}
            for k in arm_keys:
                values = [table[h][k] for h in kept if table[h][k] is not None]
                per_key[k] = statistics.fmean(values) if values and len(values) == len(kept) else None
            if arm in LEARNED_ARMS:
                present = [v for v in per_key.values() if v is not None]
                rows[arm] = {"per_seed": per_key, **_mean_sd(present), "seeds_with_values": len(present)}
            else:
                rows[arm] = {"mean": per_key.get(arm)}
        table_rows[metric] = rows
        comparisons[metric] = {}
        for control in COMPARED_ARMS:
            control_keys = [k for k in keys if k.split(":")[0] == control]
            if not control_keys:
                comparisons[metric][control] = {"evaluable": False, "reason": "arm_absent"}
                continue
            if not_applicable_keys(metric, control_keys):
                comparisons[metric][control] = {"not_applicable": True}
                continue
            extra = sorted(h for h in kept if any(table[h][k] is None for k in control_keys))
            block = lt.gate_metric(table, direction=DIRECTION[metric], arm="VSMT-lean", control=control,
                                   excluded_houses=excluded + extra, seed=seed, control_seeded=control in LEARNED_ARMS,
                                   iterations=iterations)
            comparisons[metric][control] = {**block, "extra_excluded_for_this_control": extra, "role": "reported, never gating"}
    node = per_metric["node_prf1"]
    node_kept = [h for h in sorted(node) if h not in set(lists["node_prf1"]["excluded_houses"])]
    try:
        matrix = lt.seed_paired_matrix(node, arm="VSMT-lean", control="AssocOnly", direction="higher", houses=node_kept)
        interval = two_level_interval(matrix, seed=seed, iterations=iterations)
        node_f1 = {"difference": sum(map(sum, matrix)) / (len(matrix) * len(matrix[0])), "interval_90": interval,
                   "houses": len(node_kept), "role": "reported only, no non-inferiority margin (ruling 102-3)"}
    except (lt.LeanTeacherError, LeanS3_05Error) as exc:  # e.g. a VSMT-lean or AssocOnly seed without a run: not evaluable
        node_f1 = {"evaluable": False, "reason": str(exc)}
    decomposition: dict[str, dict[str, int]] = {}
    size: dict[str, dict[str, Any]] = {}
    for run in runs:
        run_key = key(run["arm"], run.get("seed"))
        totals: dict[str, int] = {}
        fields: dict[str, list[float]] = {}
        for row in run["rows"].values():
            for name, value in (row.get("decomposition_totals") or {}).items():
                totals[name] = totals.get(name, 0) + int(value)
            for name, value in ((row.get("report") or {}).get("size_and_cost") or {}).items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    fields.setdefault(name, []).append(float(value))
        decomposition[run_key] = totals
        size[run_key] = {name: statistics.fmean(values) for name, values in sorted(fields.items())}
    return {"primary_gate": primary, "original_gate": original, "exclusion_lists": lists, "main_table": table_rows,
            "main_table_rule": ("each metric's mean over the houses its one list keeps (ruling 102-3: the list covers the main-table runs "
                                "only); an ablation run (NoVersion, HeuristicLabel, HandCost) missing on a kept house has no mean "
                                "(None) for that seed or arm, shown by seeds_with_values -- never a mean over fewer houses"),
            "comparisons": comparisons, "node_f1_vs_assoc_only": node_f1, "decomposition_totals": decomposition,
            "size_and_cost_episode_means": size}


def test_statistics(per_front: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """The fixed sequence over the two front ends (ruling 102-2) on top of each front end's statistics."""

    _require(set(per_front) == set(FRONTS), "statistics_need_both_front_ends")
    sequence = lt.fixed_sequence({FRONTS[front]: block["primary_gate"] for front, block in per_front.items()})
    return {"stage": STAGE, "rule": STATISTICS_RULE, "fixed_sequence": sequence, "fronts": dict(per_front)}


__all__ = [
    "COMPARED_ARMS",
    "DIRECTION",
    "FRONTS",
    "LEARNED_ARMS",
    "LeanS3_05Error",
    "NODE_F1_INTERVAL",
    "REPORT_METRICS",
    "STAGE",
    "STATISTICS_RULE",
    "front_statistics",
    "key",
    "not_applicable_keys",
    "tables",
    "test_statistics",
    "two_level_interval",
]
