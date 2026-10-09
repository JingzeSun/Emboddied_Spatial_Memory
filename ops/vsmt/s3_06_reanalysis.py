#!/usr/bin/env python3
"""S3-06 (ruling 113, 2026-10-08: 「推送 41f19cc；待裁 113 全按推荐」): the read-only reanalysis of the committed S3-05 exports.

S3-06 checks that every number of the paper can be recomputed from committed files alone and adds the read-only descriptive
numbers the writing still needs. Inputs: only the committed S3-05 exports in ``results/`` (two merged-audit files, inputs,
statistics, manifest) and the S3-04 freeze receipt. Outputs, two files:
  * ``vsmt_lean_s3_06_reanalysis_<tag>.json``:
    - D1, replay check: recomputes the statistics from the merged audits with the frozen ``lean_s3_05.tables`` /
      ``front_statistics`` / ``test_statistics`` at the receipt's bootstrap seed, iteration count and ``test_runs``; they
      must equal the committed statistics value for value (except ``receipt_sha256`` and ``written_utc``); otherwise exit 3,
      writing only the differing fields and no reading;
    - D2, report-only comparison of VSMT-lean against AssocOnly on every metric: the freeze receipt's statistics plan
      (``statistics.ablations.arms``) lists AssocOnly, but the S3-05 implementation (``lean_s3_05.COMPARED_ARMS``) did not
      compute it; the same frozen function is called with the plan's list of controls;
    - D3, two-sided 90% intervals of every report-only comparison (``lean_s3_05.two_level_interval``, same seed, same draws;
      the 5th percentile must equal the exported one-sided lower bound);
    - D4, event and denominator counts per metric; D5, per-house paired differences of the two main-gate metrics; D6, the
      shares of the three-way decomposition; D7, size and cost (runtime as an order of magnitude only);
    - D8, consistency checks (identity and retrieval event counts equal across runs on the same house; the per-episode
      identity of the three-way decomposition);
  * ``vsmt_lean_s3_06_paper_index_<tag>.json``: per paper table / figure the result file (sha256 checked against the manifest
    of its stage), fields, generating command and commit (ruling 113-5).
Example: if one D1 number differs from the committed statistics, the script stops and lists that field: the export or the
environment is at fault, and no new number is produced. Committed files only: no test root, no server, no training, no
frozen function changed; D2-D8 are descriptive readings computed after test was seen, with no gate and no multiplicity
correction.

Usage (repository root, a commit whose src/, ops/, configs/ and the input files have no uncommitted changes, whose inputs are
tracked by git, and whose src/ and configs/ equal the freeze commit's):
    python ops/vsmt/s3_06_reanalysis.py run [--workers N] [--out-dir results] [--replace]
    python ops/vsmt/s3_06_reanalysis.py index --reanalysis-tag <tag>   (only the paper index, e.g. after S3-07 added its exports)
Exit codes: 0 done; 2 refused (uncommitted or untracked code or inputs, an input that is missing or differs from its manifest,
src/ or configs/ that differ from the freeze commit, or outputs of this commit that already exist without --replace); 3 the
replay differs from the committed statistics (nothing but the differing fields is written); 4 written, but a consistency check
reported a problem; 1 an unexpected error (traceback).
"""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vsmt import lean_s3_04 as s4  # noqa: E402
from vsmt import lean_s3_05 as s5  # noqa: E402
from vsmt import lean_teacher as lt  # noqa: E402

STAGE = "vsmt.lean.s3_06.reanalysis.v1"
RULING = "113 (2026-10-08, 「推送 41f19cc；待裁 113 全按推荐」), items 113-3 and 113-5"
S3_05_TAG = "8d58475"
S3_04_TAG = "dea8c20"
FRONTS = tuple(s5.FRONTS)
METHOD_ARM, ASSOC_ONLY = lt.PRIMARY_COMPARISON
#: keys of the committed statistics that a replay does not reproduce by construction
VOLATILE_KEYS = ("receipt_sha256", "written_utc")
#: the code the run executes; their committed bytes are what the output is bound to
BOUND_PATHS = ("src", "ops", "configs")
EXIT_OK, EXIT_REFUSED, EXIT_REPLAY_DIFFERS, EXIT_PROBLEMS = 0, 2, 3, 4
#: Windows refuses more than 61 worker processes
MAX_WORKERS = 61 if os.name == "nt" else 4096
#: D4: the count fields of each metric's per-episode report, summed per run over the metric's kept houses
COUNT_FIELDS = {
    "node_prf1": ("matched", "predicted", "truth"),
    "node_prf1_iou": ("matched", "predicted", "truth"),
    "missing_residual_rate": ("residual", "judged", "not_yet_observable"),
    "false_retract_rate": ("false_retracts", "judged_retracts", "ambiguous_retracts"),
    "false_retract_rate_in_scope": ("false_retracts", "judged_retracts", "ambiguous_retracts"),
    "identity_continuity": ("kept", "events", "no_prior_carrier"),
    "identity_continuity_conditional": ("kept", "judged"),
    "retrieval_success": ("successes", "events", "no_query", "empty_candidates"),
    "recovery_latency_frames": ("recovered", "unrecovered", "never_observable"),
}
#: D8: per-episode counts that only the front end and the truth decide, so every run of a front end must agree on them
SHARED_EVENT_FIELDS = (("identity_continuity", "events"), ("retrieval_success", "events"), ("retrieval_success", "no_query"))
#: D2 fields that must equal the primary gate's block for the two main-gate metrics (the same function, the same inputs)
GATE_FIELDS = ("houses", "excluded_houses", "mean_advantage", "seed_paired_gaps", "stable_82_1", "lower_bound_two_level",
               "lower_bound_house_only_sensitivity", "passed")
DESCRIPTIVE = ("descriptive, computed after the one test run from committed exports; never gating; no multiple-comparison "
               "correction (ruling 102-2: comparisons outside the fixed sequence are reported only)")
#: D3 and D5 values are advantages, oriented as gate_metric orients them
SIGN = ("advantage of VSMT-lean over the control: positive favours VSMT-lean; for metrics where lower is better (Missing "
        "residual rate, false-retract rates, recovery latency, contamination AUC) the sign is flipped, as in gate_metric")
TRUNCATED = "...more differences not listed"


class ReanalysisError(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ReanalysisError(code)


# --------------------------------------------------------------------------
# files
# --------------------------------------------------------------------------

def load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    """The S3 export format (``json.dumps(..., indent=1)``), written with LF line ends on every platform."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, indent=1))
    os.replace(tmp, path)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def export_path(results: Path, stage: str, kind: str, tag: str) -> Path:
    return Path(results) / f"vsmt_lean_{stage}_{kind}_{tag}.json"


def manifest_problems(results: Path, manifest: Mapping[str, Any], names: Sequence[str] | None = None) -> list[str]:
    """Each named export of a stage manifest exists in ``results`` with the manifest's sha256 and byte count."""

    problems = []
    for name in (names if names is not None else sorted(manifest["exports"])):
        entry = manifest["exports"].get(name)
        path = Path(results) / name
        if entry is None:
            problems.append(f"not_in_manifest:{name}")
        elif not path.exists():
            problems.append(f"export_missing:{name}")
        elif file_sha256(path) != entry["sha256"] or path.stat().st_size != entry["bytes"]:
            problems.append(f"export_differs_from_manifest:{name}")
    return problems


def group_name(arm: str, index: int, seed: int | None) -> str:
    """The merged-audit key of one test run (the same rule as ``ops/vsmt/s3_03_manifest.group_name``)."""

    return f"{arm}-c{int(index):02d}" + ("" if seed is None else f"-s{int(seed)}")


def load_inputs(results: Path, *, s3_05_tag: str = S3_05_TAG, s3_04_tag: str = S3_04_TAG) -> tuple[dict[str, Any], list[str]]:
    """The committed S3-05 exports and the S3-04 receipt, each checked against its stage manifest before use."""

    results = Path(results)
    manifests = [export_path(results, "s3_05", "manifest", s3_05_tag), export_path(results, "s3_04", "manifest", s3_04_tag)]
    missing = [f"input_missing:{path.name}" for path in manifests if not path.exists()]
    if missing:
        return {}, missing
    manifest, freeze_manifest = (load_json(path) for path in manifests)
    freeze_name = export_path(results, "s3_04", "freeze", s3_04_tag).name
    read = [export_path(results, "s3_05", kind, s3_05_tag).name
            for kind in ("statistics", "inputs", *(f"merged_{front}" for front in FRONTS))]
    problems = [f"not_in_manifest:{name}" for name in read if name not in manifest.get("exports", {})]
    problems += manifest_problems(results, manifest) + manifest_problems(results, freeze_manifest, [freeze_name])
    if problems:  # nothing is loaded from a file that is missing or differs from its manifest
        return {}, problems
    receipt = load_json(results / freeze_name)
    if s4.receipt_body_sha256(receipt) != receipt.get("receipt_sha256"):
        problems.append("receipt_body_digest_differs")
    loaded = {
        "manifest": manifest,
        "receipt": receipt,
        "statistics": load_json(export_path(results, "s3_05", "statistics", s3_05_tag)),
        "inputs": load_json(export_path(results, "s3_05", "inputs", s3_05_tag)),
        "merged": {front: load_json(export_path(results, "s3_05", f"merged_{front}", s3_05_tag)) for front in FRONTS},
        "tags": {"s3_05": s3_05_tag, "s3_04": s3_04_tag},
    }
    for name in ("statistics", "inputs", "manifest"):
        if loaded[name].get("receipt_sha256") != receipt.get("receipt_sha256"):
            problems.append(f"receipt_digest_differs:{name}")
    return loaded, problems


# --------------------------------------------------------------------------
# the runs of one front end, as the S3-05 stats step assembled them
# --------------------------------------------------------------------------

def front_episodes(inputs: Mapping[str, Any], front: str) -> list[str]:
    return [str(row["episode_id"]) for row in inputs["episodes"][front]["test"]]


def front_runs(receipt: Mapping[str, Any], merged_front: Mapping[str, Any], front: str) -> list[dict[str, Any]]:
    """The receipt's test runs in its order, each with its merged per-episode rows (``s3_05_manifest.cmd_stats``).

    A run without a merged group is a run whose every episode failed, as ``cmd_stats`` treats it (no rows, so every metric
    of it is None); a merged group that the receipt does not list is an error."""

    runs, names = [], []
    for run in receipt["fronts"][front]["test_runs"]:
        name = group_name(run["arm"], run["config_index"], run["seed"])
        group = merged_front.get(name, {"arm": run["arm"], "per_episode": []})
        _require(group.get("arm") == run["arm"], f"merged_group_arm_differs:{front}:{name}")
        runs.append({"arm": run["arm"], "seed": run["seed"],
                     "rows": {str(row["episode_id"]): row for row in group["per_episode"]}})
        names.append(name)
    _require(set(merged_front) <= set(names), f"merged_group_not_in_the_receipt:{front}")
    return runs


def plan_controls(receipt: Mapping[str, Any]) -> tuple[str, ...]:
    """The controls of the frozen statistics plan: S3-05's reported list plus every planned ablation it left out (AssocOnly)."""

    planned = [str(arm) for arm in receipt["statistics"]["ablations"]["arms"]]
    return tuple(s5.COMPARED_ARMS) + tuple(arm for arm in planned if arm not in s5.COMPARED_ARMS)


@contextlib.contextmanager
def compared_arms(arms: Sequence[str]) -> Iterator[None]:
    """``lean_s3_05.front_statistics`` reads its reported controls from the module constant ``COMPARED_ARMS``; this runs it with
    the plan's list (D2) and always restores the frozen value."""

    saved = s5.COMPARED_ARMS
    s5.COMPARED_ARMS = tuple(arms)
    try:
        yield
    finally:
        s5.COMPARED_ARMS = saved


# --------------------------------------------------------------------------
# worker tasks (top level, so that a process pool can run them on every platform)
# --------------------------------------------------------------------------

def front_statistics_task(task: Mapping[str, Any]) -> dict[str, Any]:
    """D1 and D2 together: the frozen ``front_statistics`` with the plan's controls."""

    with compared_arms(task["controls"]):
        return s5.front_statistics(task["tables"], task["runs"], seed=task["seed"], iterations=task["iterations"])


def interval_task(task: Mapping[str, Any]) -> dict[str, Any]:
    """D3: the 5th and 95th two-level percentiles of one comparison, on exactly the houses its gate block used."""

    table, control = task["table"], task["control"]
    excluded = {str(house) for house in task["excluded_houses"]}
    houses = [str(house) for house in sorted(table) if str(house) not in excluded]
    matrix = lt.seed_paired_matrix(table, arm=METHOD_ARM, control=control, direction=task["direction"], houses=houses,
                                   control_seeded=control in s5.LEARNED_ARMS)
    low, high = s5.two_level_interval(matrix, seed=task["seed"], iterations=task["iterations"])
    return {"interval_90": [low, high], "houses": len(houses)}


def run_tasks(function: Callable[[Mapping[str, Any]], Any], tasks: Mapping[str, Mapping[str, Any]],
              executor: concurrent.futures.Executor | None) -> dict[str, Any]:
    """Every task by key, inline or on the pool; the results come back keyed, so the merge order does not depend on timing."""

    if executor is None:
        return {key: function(task) for key, task in tasks.items()}
    futures = {key: executor.submit(function, task) for key, task in tasks.items()}
    return {key: futures[key].result() for key in tasks}


# --------------------------------------------------------------------------
# D1 replay
# --------------------------------------------------------------------------

def normalise(payload: Any) -> Any:
    """The JSON form, so that tuples and lists compare equal the way the committed export stores them."""

    return json.loads(json.dumps(payload))


def json_differences(left: Any, right: Any, path: str = "", limit: int = 50) -> list[str]:
    """The paths where two JSON values differ; after ``limit`` paths the list ends with ``TRUNCATED`` (more may differ)."""

    out: list[str] = []

    def walk(a: Any, b: Any, where: str) -> None:
        if len(out) >= limit:
            if out[-1] != TRUNCATED:
                out.append(TRUNCATED)
            return
        if isinstance(a, dict) and isinstance(b, dict):
            for key in sorted(set(a) | set(b)):
                if key not in a or key not in b:
                    out.append(f"{where}.{key}:missing_on_{'left' if key not in a else 'right'}")
                else:
                    walk(a[key], b[key], f"{where}.{key}")
        elif isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                out.append(f"{where}:length_{len(a)}_vs_{len(b)}")
            for index, (x, y) in enumerate(zip(a, b)):
                walk(x, y, f"{where}[{index}]")
        elif type(a) is not type(b) or a != b:
            out.append(where or ".")

    walk(left, right, path)
    return out


def strip_controls(front: Mapping[str, Any], controls: Sequence[str]) -> dict[str, Any]:
    """One front end's statistics as S3-05 computed them: the plan's extra controls removed from every metric's comparisons."""

    out = normalise(front)
    for block in out["comparisons"].values():
        for arm in controls:
            block.pop(arm, None)
    return out


def replay(front_stats: Mapping[str, Mapping[str, Any]], *, extra_controls: Sequence[str], episodes: Mapping[str, int],
           failures: Mapping[str, Sequence[Any]]) -> dict[str, Any]:
    """``s3_05_manifest.cmd_stats`` again: each front end with its episode count and failures, then the fixed sequence."""

    per_front = {front: {**strip_controls(front_stats[front], extra_controls), "episodes": episodes[front],
                         "failures": list(failures[front])} for front in FRONTS}
    return normalise(s5.test_statistics(per_front))


def committed_core(statistics_export: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in statistics_export.items() if key not in VOLATILE_KEYS}


# --------------------------------------------------------------------------
# D2 .. D8
# --------------------------------------------------------------------------

def d2_assoc_only(front: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """VSMT-lean against AssocOnly on every metric, and the check that the two gate metrics equal the primary gate's blocks."""

    blocks = {metric: front["comparisons"][metric][ASSOC_ONLY] for metric in s5.REPORT_METRICS}
    problems = []
    for metric, _direction in lt.MAIN_GATE:
        gate = front["primary_gate"]["metrics"][metric]
        for field in GATE_FIELDS:
            if normalise(blocks[metric].get(field)) != normalise(gate.get(field)):
                problems.append(f"d2_differs_from_primary_gate:{metric}.{field}")
    return blocks, problems


def interval_tasks(front_name: str, tables: Mapping[str, Any], comparisons: Mapping[str, Mapping[str, Any]],
                   controls: Sequence[str], *, seed: int, iterations: int) -> dict[str, dict[str, Any]]:
    """D3 tasks for one front end: every evaluable comparison of ``controls`` on every metric."""

    tasks = {}
    for metric in s5.REPORT_METRICS:
        for control in controls:
            block = comparisons.get(metric, {}).get(control)
            if not block or block.get("not_applicable") or not block.get("evaluable", False):
                continue
            tasks[f"{front_name}|{metric}|{control}"] = {
                "table": tables[metric], "control": control, "direction": s5.DIRECTION[metric],
                "excluded_houses": block["excluded_houses"], "seed": seed, "iterations": iterations}
    return tasks


def d3_intervals(results: Mapping[str, Mapping[str, Any]], front_stats: Mapping[str, Mapping[str, Any]]
                 ) -> tuple[dict[str, Any], list[str]]:
    """Two-sided 90% intervals by front end, metric and control; the 5th percentile must equal the exported one-sided bound,
    and the AssocOnly node-F1 interval must equal ``node_f1_vs_assoc_only``."""

    out: dict[str, Any] = {front: {} for front in FRONTS}
    problems = []
    for key in sorted(results):
        front, metric, control = key.split("|")
        block = front_stats[front]["comparisons"][metric][control]
        interval = results[key]["interval_90"]
        if interval[0] != block["lower_bound_two_level"]:
            problems.append(f"d3_lower_percentile_differs:{key}")
        if results[key]["houses"] != block["houses"]:
            problems.append(f"d3_houses_differ:{key}")
        out[front].setdefault(metric, {})[control] = {"mean_advantage": block["mean_advantage"], "interval_90": interval,
                                                      "houses": block["houses"]}
    for front in FRONTS:
        node = front_stats[front]["node_f1_vs_assoc_only"]
        mine = out[front].get("node_prf1", {}).get(ASSOC_ONLY)
        if node.get("interval_90") is not None and (mine is None or normalise(mine["interval_90"]) != normalise(node["interval_90"])):
            problems.append(f"d3_node_f1_interval_differs:{front}")
    return out, problems


def _count(value: Any) -> int:
    """A count field of the evaluator's report: an int, or a list of objects counted by its length; None counts 0."""

    if value is None:
        return 0
    if isinstance(value, (list, tuple, dict)):
        return len(value)
    _require(isinstance(value, int) and not isinstance(value, bool), f"count_field_not_an_integer:{value!r}")
    return int(value)


def _arm_of(key: str) -> str:
    return key.split(":")[0]


def _per_arm(per_run: Mapping[str, Mapping[str, float]]) -> dict[str, Any]:
    """Learned arms: each seed and the mean over seeds; seedless arms: their one run."""

    arms: dict[str, Any] = {}
    for key in per_run:
        arms.setdefault(_arm_of(key), []).append(key)
    out = {}
    for arm, keys in arms.items():
        if len(keys) == 1 and ":" not in keys[0]:
            out[arm] = dict(per_run[keys[0]])
            continue
        fields = list(per_run[keys[0]])
        out[arm] = {"per_seed": {key: dict(per_run[key]) for key in keys},
                    "mean": {field: statistics.fmean(per_run[key][field] for key in keys) for field in fields}}
    return out


def d4_counts(runs: Sequence[Mapping[str, Any]], front: Mapping[str, Any]) -> dict[str, Any]:
    """Event and denominator counts per metric and run, twice: over the houses that metric's one list keeps (what the main-table
    mean is computed on) and over every usable episode (the absolute counts; for recovery latency the excluded houses are the
    ones where some run recovered nothing, so most unrecovered objects sit there)."""

    out = {}
    keys = [s5.key(run["arm"], run["seed"]) for run in runs]
    for metric, fields in COUNT_FIELDS.items():
        listed_out = set(front["exclusion_lists"][metric]["excluded_houses"])
        skipped = set(s5.not_applicable_keys(metric, keys))  # arms without RETRACT have no false-retract counts
        kept: dict[str, dict[str, int]] = {}
        every: dict[str, dict[str, int]] = {}
        for run, key in zip(runs, keys):
            if key in skipped:
                continue
            kept[key], every[key] = {field: 0 for field in fields}, {field: 0 for field in fields}
            for house, row in run["rows"].items():
                block = row["report"][metric]
                for field in fields:
                    value = _count(block.get(field))
                    every[key][field] += value
                    if house not in listed_out:
                        kept[key][field] += value
        out[metric] = {"fields": list(fields), "not_applicable": sorted({_arm_of(key) for key in skipped}),
                       "kept_houses": front["exclusion_lists"][metric]["effective_houses"],
                       "excluded_houses": len(listed_out),
                       "per_arm_kept_houses": _per_arm(kept), "per_arm_all_houses": _per_arm(every),
                       "use": ("per_arm_kept_houses goes with the main-table mean of this metric (the same houses); "
                               "per_arm_all_houses gives the absolute counts over every usable episode")}
    return out


def _quantiles(values: Sequence[float]) -> dict[str, float]:
    ordered = sorted(values)
    q25, median, q75 = statistics.quantiles(ordered, n=4, method="inclusive")
    return {"min": ordered[0], "q25": q25, "median": median, "q75": q75, "max": ordered[-1]}


def d5_per_house(tables: Mapping[str, Any], front: Mapping[str, Any]) -> dict[str, Any]:
    """The seed-paired advantage of VSMT-lean over AssocOnly in every house the gate kept, for both gate metrics."""

    out = {}
    for metric, direction in lt.MAIN_GATE:
        block = front["primary_gate"]["metrics"][metric]
        excluded = set(block["excluded_houses"])
        houses = [house for house in sorted(tables[metric]) if house not in excluded]
        matrix = lt.seed_paired_matrix(tables[metric], arm=METHOD_ARM, control=ASSOC_ONLY, direction=direction, houses=houses)
        means = [sum(row) / len(row) for row in matrix]
        out[metric] = {
            "direction": direction, "sign": SIGN, "seeds": list(lt.GATE_SEEDS), "houses": len(houses),
            "per_house": {house: {"per_seed": row, "mean": mean} for house, row, mean in zip(houses, matrix, means)},
            "summary": {"favourable": sum(m > 0 for m in means), "unfavourable": sum(m < 0 for m in means),
                        "zero": sum(m == 0 for m in means), "house_mean_quantiles": _quantiles(means)},
        }
    return out


def d6_decomposition(front: Mapping[str, Any]) -> dict[str, Any]:
    """Pooled totals and shares of the three-way decomposition per arm (each arm over its own decisions)."""

    pooled: dict[str, dict[str, int]] = {}
    runs: dict[str, int] = {}
    for key, totals in front["decomposition_totals"].items():
        arm = _arm_of(key)
        runs[arm] = runs.get(arm, 0) + 1
        for name, value in totals.items():
            pooled.setdefault(arm, {})[name] = pooled.get(arm, {}).get(name, 0) + int(value)
    out = {}
    for arm, totals in pooled.items():
        decisions = totals["decisions"]
        out[arm] = {"runs": runs[arm], "totals": totals,
                    "per_run_mean": {name: value / runs[arm] for name, value in totals.items()},
                    "shares": {name: value / decisions for name, value in totals.items() if name != "decisions"}}
    return {"per_arm": out, "note": ("each arm's shares are over its own decisions; the decision sets differ (AssocOnly makes "
                                     "association decisions only, arms that keep more entities make more existence decisions), "
                                     "so the shares are not ranked across arms")}


def d7_size_and_cost(front: Mapping[str, Any]) -> dict[str, Any]:
    """Mean, minimum and maximum over each arm's runs of the per-episode means; the runtime is indicative only."""

    by_arm: dict[str, list[Mapping[str, float]]] = {}
    for key, values in front["size_and_cost_episode_means"].items():
        by_arm.setdefault(_arm_of(key), []).append(values)
    out = {}
    for arm, rows in by_arm.items():
        out[arm] = {field: {"mean": statistics.fmean(row[field] for row in rows), "min": min(row[field] for row in rows),
                            "max": max(row[field] for row in rows)} for field in rows[0]}
    return {"per_arm": out, "note": ("each field is the episode mean of the run (peak_memory_bytes: the episode mean of each "
                                     "episode's peak), then mean, min and max over the arm's runs. runtime_per_frame_s is pool "
                                     "wall clock measured while many audits shared the hosts (B1, w4, w5); it is not comparable "
                                     "across arms. Entity and version counts are deterministic.")}


def d8_consistency(runs: Sequence[Mapping[str, Any]], episodes: Sequence[str]) -> tuple[dict[str, Any], list[str]]:
    """Every run of a front end saw the same identity and retrieval events in each house; the decomposition adds up."""

    problems = []
    checked = {"shared_event_fields": [f"{metric}.{field}" for metric, field in SHARED_EVENT_FIELDS], "houses": len(episodes),
               "runs": len(runs), "decomposition_rows": 0}
    for metric, field in SHARED_EVENT_FIELDS:
        for house in episodes:
            values = {_count(run["rows"][house]["report"][metric].get(field)) for run in runs if house in run["rows"]}
            if len(values) > 1:
                problems.append(f"d8_events_differ_across_runs:{metric}.{field}:{house}")
    for run in runs:
        for house, row in run["rows"].items():
            totals = row.get("decomposition_totals") or {}
            checked["decomposition_rows"] += 1
            if sum(int(v) for k, v in totals.items() if k != "decisions") != int(totals.get("decisions", -1)):
                problems.append(f"d8_decomposition_does_not_add_up:{s5.key(run['arm'], run['seed'])}:{house}")
    judged = {}
    for house in episodes:
        values = sorted({_count(run["rows"][house]["report"]["missing_residual_rate"].get("judged"))
                         for run in runs if house in run["rows"]})
        if len(values) > 1:
            judged[house] = values
    checked["missing_residual_judged_differs_across_runs"] = judged
    return checked, problems


# --------------------------------------------------------------------------
# the paper index (ruling 113-5)
# --------------------------------------------------------------------------

S3_05_COMMAND = ("S3_05_GO=4fd08d4fc6d0 RECEIPT=/root/autodl-tmp/vsmt_private/s3-04-dea8c20/freeze_receipt.json "
                 "bash ops/vsmt/s3_05_test.sh all  (B1, worktree s3-05-8d58475; run once, test read once -- never rerun)")
REANALYSIS_COMMAND = "python ops/vsmt/s3_06_reanalysis.py run"
#: Each table and figure of the paper: content, committed files (``{s3_06}`` is this run's tag), fields, command and commits.
PAPER_ITEMS: tuple[dict[str, Any], ...] = (
    {"item": "table_1_main_instance", "content": "main table, simulator instance masks: 9 arms x node F1 (two columns), Missing "
     "residual rate, false-retract rate (two columns), identity continuity, retrieval success, recovery latency with unrecovered "
     "counts, contamination AUC; effective houses per column",
     "files": ["vsmt_lean_s3_05_statistics_8d58475.json", "vsmt_lean_s3_06_reanalysis_{s3_06}.json"],
     "fields": ["fronts.instance.main_table", "fronts.instance.exclusion_lists", "d4_counts.instance"],
     "command": S3_05_COMMAND + "; " + REANALYSIS_COMMAND, "commits": {"run": "8d58475", "frozen": "dea8c20"}},
    {"item": "table_2_main_sam2", "content": "the same main table, SAM 2.1",
     "files": ["vsmt_lean_s3_05_statistics_8d58475.json", "vsmt_lean_s3_06_reanalysis_{s3_06}.json"],
     "fields": ["fronts.sam2.main_table", "fronts.sam2.exclusion_lists", "d4_counts.sam2"],
     "command": S3_05_COMMAND + "; " + REANALYSIS_COMMAND, "commits": {"run": "8d58475", "frozen": "dea8c20"}},
    {"item": "table_3_main_gate", "content": "fixed-sequence main gate (three steps) and the original gate (reported only)",
     "files": ["vsmt_lean_s3_05_statistics_8d58475.json"],
     "fields": ["fixed_sequence", "fronts.instance.primary_gate", "fronts.sam2.primary_gate", "fronts.instance.original_gate",
                "fronts.sam2.original_gate"],
     "command": S3_05_COMMAND, "commits": {"run": "8d58475", "frozen": "dea8c20"}},
    {"item": "table_4_ablations", "content": "NoVersion, HandCost, HeuristicLabel and AssocOnly against VSMT-lean, every metric: "
     "difference, two-sided 90% interval, one-sided lower bound, 82-1 (descriptive)",
     "files": ["vsmt_lean_s3_05_statistics_8d58475.json", "vsmt_lean_s3_06_reanalysis_{s3_06}.json"],
     "fields": ["fronts.<front>.comparisons", "d2_assoc_only", "d3_intervals"],
     "command": REANALYSIS_COMMAND, "commits": {"run": "8d58475", "reanalysis": "{s3_06}"}},
    {"item": "table_5_rule_arms", "content": "TAF, ELU-P, RAC and LOW against VSMT-lean, metric by metric (descriptive)",
     "files": ["vsmt_lean_s3_05_statistics_8d58475.json", "vsmt_lean_s3_06_reanalysis_{s3_06}.json"],
     "fields": ["fronts.<front>.comparisons", "d3_intervals"],
     "command": REANALYSIS_COMMAND, "commits": {"run": "8d58475", "reanalysis": "{s3_06}"}},
    {"item": "table_6_decomposition", "content": "three-way decomposition per arm (shares over each arm's own decisions)",
     "files": ["vsmt_lean_s3_05_statistics_8d58475.json", "vsmt_lean_s3_06_reanalysis_{s3_06}.json"],
     "fields": ["fronts.<front>.decomposition_totals", "d6_decomposition"],
     "command": REANALYSIS_COMMAND, "commits": {"run": "8d58475", "reanalysis": "{s3_06}"}},
    {"item": "table_7_size_and_cost", "content": "active entities, lifecycle versions, peak memory; runtime indicative only",
     "files": ["vsmt_lean_s3_05_statistics_8d58475.json", "vsmt_lean_s3_06_reanalysis_{s3_06}.json"],
     "fields": ["fronts.<front>.size_and_cost_episode_means", "d7_size_and_cost"],
     "command": REANALYSIS_COMMAND, "commits": {"run": "8d58475", "reanalysis": "{s3_06}"}},
    {"item": "table_8_external_3rscan", "content": ("frozen arms on 3RScan validation, instance column only: 108 episodes "
     "pooled into 46 scenes, masks rendered from the annotated meshes, proxy truth, descriptive, never gating; the SAM 2.1 "
     "column is not computable with the frozen front end (3 of 110 episodes usable, ruling 111 amendment 3)"),
     "files": ["vsmt_lean_s3_07_statistics_aa94373.json", "vsmt_lean_s3_07_merged_instance_aa94373.json",
               "vsmt_lean_s3_07_inputs_aa94373.json", "vsmt_lean_s3_07_e3_aa94373.json"],
     "fields": ["fronts.instance.main_table", "fronts.instance.comparisons", "fronts.instance.exclusion_lists",
                "fronts.instance.cache_data_failures", "fronts_missing", "not_applicable"],
     "command": ("FRONTS=instance bash ops/vsmt/s3_07_external.sh audit  (B1 + w4 + w5, worktree s3-07-aa94373; code on branch "
                 "s3-07-impl, not merged into main)"),
     "commits": {"run": "aa94373", "frozen": "dea8c20"}},
    {"item": "figure_2_tradeoff", "content": "Missing residual rate against node F1 per arm, both front ends, seed ranges",
     "files": ["vsmt_lean_s3_05_statistics_8d58475.json"], "fields": ["fronts.<front>.main_table"],
     "command": "plotting script (planned)", "commits": {"run": "8d58475"}},
    {"item": "figure_3_per_house", "content": "seed-paired house differences of the two gate metrics, both front ends",
     "files": ["vsmt_lean_s3_06_reanalysis_{s3_06}.json"], "fields": ["d5_per_house"],
     "command": REANALYSIS_COMMAND, "commits": {"reanalysis": "{s3_06}"}},
    {"item": "appendix_selection", "content": "one configuration per arm, the 102-4 constraint, grid-edge picks, validation events",
     "files": ["vsmt_lean_s3_04_selection_instance_dea8c20.json", "vsmt_lean_s3_04_selection_sam2_dea8c20.json",
               "vsmt_lean_s3_04_freeze_dea8c20.json"],
     "fields": ["selection", "fronts.<front>.test_runs"], "command": "bash ops/vsmt/s3_04_freeze.sh all  (B1)",
     "commits": {"frozen": "dea8c20"}},
    {"item": "appendix_selection_curves", "content": "validation readings of every configuration (selection only, no claim)",
     "files": ["vsmt_lean_s3_03_readings_instance_10f7013.json", "vsmt_lean_s3_03_readings_sam2_10f7013.json"],
     "fields": ["readings"], "command": ("ADOPT_CALIBRATION_INSTANCE=<74905f4 pass root>/calibration "
                                         "bash ops/vsmt/s3_03_train_select.sh all  (B1)"),
     "commits": {"run": "5c9ec8d", "verified": "5a9fd94", "tag": "10f7013"}},
    {"item": "appendix_training", "content": "training receipts with per-epoch association and existence loss terms",
     "files": ["vsmt_lean_s3_03_trainings_instance_10f7013.json", "vsmt_lean_s3_03_trainings_sam2_10f7013.json"],
     "fields": ["trainings"], "command": "bash ops/vsmt/s3_03_train_select.sh all  (B1)",
     "commits": {"run": "5c9ec8d", "verified": "5a9fd94", "tag": "10f7013"}},
    {"item": "appendix_data", "content": ("manifests, yields and failure reasons, both caches; the test seal's digest is in the "
                                          "S3-02 manifest (the seal file itself is not committed, LOG-303)"),
     "files": ["vsmt_lean_s3_02_manifest_3f6ef1d.json", "vsmt_lean_s3_02_test_summary_3f6ef1d.json",
               "vsmt_lean_s3_02_raw_train_3f6ef1d.json", "vsmt_lean_s3_02_raw_validation_3f6ef1d.json"],
     "fields": ["splits", "exports"], "command": "bash ops/vsmt/s3_02_data.sh all  (environment and resume: EXECUTE LOG-303)",
     "commits": {"generate": "3f6ef1d", "registration": "4ad0233", "after_hold": "74905f4"}},
    {"item": "appendix_power", "content": "null calibration, sensitivity table and power planning of the gate",
     "files": ["vsmt_lean_s3_01_planning_6c57903.json"], "fields": ["."],
     "command": "python ops/vsmt/s3_01_planning.py", "commits": {"run": "6c57903"}},
    {"item": "appendix_llm_op", "content": "LLM-op on one validation episode per front end (n = 1, descriptive)",
     "status": "partial: the other arms' per-episode validation values on train-08800 live in the S3-03 run root on B1 and "
               "are not exported yet",
     "files": ["vsmt_lean_llm_op_dea8c20.json"], "fields": ["."], "command": "bash ops/vsmt/llm_op.sh plan ... export",
     "commits": {"run": "dea8c20"}},
)
STAGE_MANIFESTS = ("vsmt_lean_s3_02_manifest_3f6ef1d.json", "vsmt_lean_s3_03_manifest_10f7013.json",
                   "vsmt_lean_s3_04_manifest_dea8c20.json", "vsmt_lean_s3_05_manifest_8d58475.json",
                   "vsmt_lean_s3_07_manifest_aa94373.json")


def _shown(path: Path) -> str:
    """A path as the index records it: relative to the repository when it is inside it."""

    path = Path(path).resolve()
    return path.relative_to(ROOT).as_posix() if ROOT in path.parents else str(path)


def index_inputs() -> list[str]:
    """The committed files the paper index reads (the stage manifests and every listed file except this run's outputs)."""

    names = set(STAGE_MANIFESTS)
    for item in PAPER_ITEMS:
        names.update(name for name in item["files"] if "{s3_06}" not in name)
    return sorted(names)


def paper_index(results: Path, tag: str, *, outputs: Path | None = None) -> tuple[dict[str, Any], list[str]]:
    """Every paper item with its files' sha256 and size, each compared with the stage manifest that lists it (when one does).

    This run's own outputs (names with its tag) are looked up in ``outputs`` first, so a stale copy in ``results`` is never
    hashed in their place; every other file comes from ``results``."""

    listed: dict[str, tuple[str, Mapping[str, Any]]] = {}
    for manifest_name in STAGE_MANIFESTS:
        manifest = load_json(Path(results) / manifest_name)
        for name, entry in manifest["exports"].items():
            listed[name] = (manifest_name, entry)
    problems, items = [], []
    for item in PAPER_ITEMS:
        files = []
        for template in item["files"]:
            name = template.format(s3_06=tag)
            own = "{s3_06}" in template and outputs is not None
            path = (Path(outputs) if own else Path(results)) / name
            digest = file_sha256(path) if path.exists() else None
            size = path.stat().st_size if path.exists() else None
            manifest_name, entry = listed.get(name, (None, None))
            matches = None if entry is None else (digest == entry["sha256"] and size == entry["bytes"])
            record = {"file": _shown(path), "sha256": digest, "bytes": size, "manifest": manifest_name,
                      "matches_manifest": matches}
            if digest is None:
                problems.append(f"index_file_missing:{name}")
            elif matches is False:
                problems.append(f"index_file_differs_from_manifest:{name}")
            files.append(record)
        items.append({**{key: value for key, value in item.items() if key != "files"},
                      "commits": {key: str(value).format(s3_06=tag) for key, value in item["commits"].items()},
                      "files": files, "status": item.get("status", "ready")})
    return {"stage": STAGE, "ruling": RULING, "tag": tag, "items": items, "manifests": list(STAGE_MANIFESTS),
            "plain_language_zh": ("论文每张表／图对应 results/ 里哪个文件、哪些字段、哪条命令与哪个提交；每个文件都重算了 sha256，"
                                  "并与列出它的阶段 manifest 比对。")}, problems


# --------------------------------------------------------------------------
# the run
# --------------------------------------------------------------------------

def reanalyse(loaded: Mapping[str, Any], *, workers: int = 1) -> dict[str, Any]:
    """D1 .. D8 on loaded inputs; ``replay_equal`` False means D1 failed and only the differing fields are returned."""

    receipt = loaded["receipt"]
    seed = int(receipt["statistics"]["bootstrap_seed"])
    iterations = int(receipt["statistics"]["bootstrap_iterations"])
    controls = plan_controls(receipt)
    extra = [arm for arm in controls if arm not in s5.COMPARED_ARMS]
    runs, tables, failures, episodes = {}, {}, {}, {}
    for front in FRONTS:
        episodes[front] = front_episodes(loaded["inputs"], front)
        runs[front] = front_runs(receipt, loaded["merged"][front], front)
        tables[front], failures[front] = s5.tables(runs[front], episodes[front])
    committed = loaded["statistics"]
    front_tasks = {front: {"tables": tables[front], "runs": runs[front], "seed": seed, "iterations": iterations,
                           "controls": controls} for front in FRONTS}
    first_wave = {}
    for front in FRONTS:  # the committed comparisons fix the houses of every S3-05 control already
        first_wave.update(interval_tasks(front, tables[front], committed["fronts"][front]["comparisons"], s5.COMPARED_ARMS,
                                         seed=seed, iterations=iterations))
    actual = max(1, min(int(workers), MAX_WORKERS, len(front_tasks) + len(first_wave)))
    timing: dict[str, float] = {}
    started = time.time()
    executor = concurrent.futures.ProcessPoolExecutor(max_workers=actual) if actual > 1 else None
    try:
        pending_fronts = None
        if executor is not None:
            pending_fronts = {front: executor.submit(front_statistics_task, task) for front, task in front_tasks.items()}
        intervals = run_tasks(interval_task, first_wave, executor)
        front_stats = ({front: future.result() for front, future in pending_fronts.items()} if pending_fronts is not None
                       else {front: front_statistics_task(task) for front, task in front_tasks.items()})
        timing["d1_d2_and_first_intervals_s"] = time.time() - started
        replayed = replay(front_stats, extra_controls=extra, episodes={f: len(episodes[f]) for f in FRONTS}, failures=failures)
        differences = json_differences(normalise(committed_core(committed)), replayed)
        if differences:
            return {"replay_equal": False, "differences": differences, "workers": {"requested": workers, "actual": actual}}
        second_wave = {}
        for front in FRONTS:
            second_wave.update(interval_tasks(front, tables[front], front_stats[front]["comparisons"], extra, seed=seed,
                                              iterations=iterations))
        intervals.update(run_tasks(interval_task, second_wave, executor))
        timing["all_intervals_s"] = time.time() - started
    finally:
        if executor is not None:
            executor.shutdown(cancel_futures=True)  # nothing is pending on the normal path; an early stop drops the rest
    problems: list[str] = []
    d2, d3, d4, d5, d6, d7, d8 = {}, {}, {}, {}, {}, {}, {}
    d3_all, d3_problems = d3_intervals(intervals, front_stats)
    problems += d3_problems
    for front in FRONTS:
        d2[front], gate_problems = d2_assoc_only(front_stats[front])
        problems += [f"{front}:{item}" for item in gate_problems]
        d3[front] = d3_all[front]
        d4[front] = d4_counts(runs[front], front_stats[front])
        d5[front] = d5_per_house(tables[front], front_stats[front])
        d6[front] = d6_decomposition(front_stats[front])
        d7[front] = d7_size_and_cost(front_stats[front])
        d8[front], consistency = d8_consistency(runs[front], episodes[front])
        problems += [f"{front}:{item}" for item in consistency]
    return {
        "replay_equal": True, "differences": [], "problems": problems,
        "d1_replay": {"equal": True, "compared": "every key of the committed statistics except " + ", ".join(VOLATILE_KEYS),
                      "bootstrap_seed": seed, "bootstrap_iterations": iterations},
        "d2_assoc_only": {"plan_controls": list(controls), "added": extra, "per_front": d2,
                          "source": ("the frozen receipt's statistics plan lists AssocOnly among the reported ablations "
                                     "(statistics.ablations.arms); lean_s3_05.COMPARED_ARMS left it out. The plan names "
                                     "lean_teacher.ablation_report (a house-only bootstrap); S3-05 reported every ablation with "
                                     "gate_metric instead (ruling 107-4 (a): the same two-level resampling and 82-1 as the gate), "
                                     "and D2 does the same. A block's 'passed' field is gate_metric's mechanical output, not a "
                                     "gate: these comparisons never gate")},
        "sign_convention": SIGN,
        "d3_intervals": d3, "d4_counts": d4, "d5_per_house": d5, "d6_decomposition": d6, "d7_size_and_cost": d7,
        "d8_consistency": d8, "workers": {"requested": workers, "actual": actual,
                                          "tasks": len(front_tasks) + len(intervals),
                                          "sharding": "one task per front end (D1/D2), one per front end x metric x control (D3)",
                                          "merge_order": "by task key, independent of completion order"},
        "timing_s": timing,
    }


def git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=str(ROOT), text=True)


def code_state(inputs: Sequence[str]) -> tuple[str, list[str]]:
    """HEAD and the bound paths (code and inputs) with uncommitted changes."""

    head = git("rev-parse", "HEAD").strip()
    status = git("status", "--porcelain", "--", *BOUND_PATHS, *inputs)
    return head, [line[3:] for line in status.splitlines() if line.strip()]


def untracked(inputs: Sequence[str]) -> list[str]:
    """Inputs that git does not track (an ignored folder such as ``outputs/`` never shows up in ``git status``)."""

    tracked = set(git("ls-files", "--", *inputs).split())
    return [name for name in inputs if name not in tracked]


def frozen_code_differs(freeze_commit: str) -> bool:
    """Whether the committed ``src/`` or ``configs/`` differ from the freeze commit: the functions D1..D8 call must be the frozen
    ones (``ops/`` is not compared: it gains this script, and the reanalysis runs no S3-05 entry point)."""

    return subprocess.run(["git", "diff", "--quiet", freeze_commit, "HEAD", "--", "src", "configs"], cwd=str(ROOT)).returncode != 0


def memory_bytes() -> int | None:
    """Physical memory (or the cgroup limit when lower), best effort, for the resource record."""

    try:
        if os.name == "nt":
            import ctypes

            class Status(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                            ("available", ctypes.c_ulonglong), ("page_total", ctypes.c_ulonglong),
                            ("page_available", ctypes.c_ulonglong), ("virtual_total", ctypes.c_ulonglong),
                            ("virtual_available", ctypes.c_ulonglong), ("extended", ctypes.c_ulonglong)]

            status = Status()
            status.length = ctypes.sizeof(Status)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return int(status.total)
        total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        limit = Path("/sys/fs/cgroup/memory.max")
        if limit.exists() and limit.read_text().strip().isdigit():
            total = min(total, int(limit.read_text().strip()))
        return int(total)
    except (OSError, ValueError, AttributeError):
        return None


def environment(receipt: Mapping[str, Any]) -> dict[str, Any]:
    frozen = str((receipt.get("environment") or {}).get("python", ""))
    here = platform.python_version()
    return {"python": here, "executable": sys.executable, "platform": platform.platform(), "cpu_count": os.cpu_count(),
            "memory_bytes": memory_bytes(), "processor": platform.processor(), "frozen_python": frozen,
            "python_minor_matches_the_freeze": frozen.split(".")[:2] == here.split(".")[:2]}


def command_run(args: argparse.Namespace) -> int:
    results, out_dir = Path(args.results).resolve(), Path(args.out_dir).resolve()
    if ROOT not in results.parents:
        print(f"refused: --results must be inside the repository ({ROOT}); the output is bound to committed inputs")
        return EXIT_REFUSED
    paths = sorted(results.glob(f"vsmt_lean_s3_05_*_{S3_05_TAG}.json"))
    paths += [results / f"vsmt_lean_s3_04_{kind}_{S3_04_TAG}.json" for kind in ("freeze", "manifest")]
    input_names = [path.relative_to(ROOT).as_posix() for path in paths]
    input_names += [(results / name).relative_to(ROOT).as_posix() for name in index_inputs()
                    if (results / name).relative_to(ROOT).as_posix() not in input_names]
    head, dirty = code_state(input_names)
    if dirty:
        print(f"refused: uncommitted changes in {dirty[:10]} (the output is bound to the committed code and inputs)")
        return EXIT_REFUSED
    loose = untracked(input_names)
    if loose:
        print(f"refused: inputs that git does not track: {loose[:10]}")
        return EXIT_REFUSED
    tag = head[:7]
    targets = [out_dir / f"vsmt_lean_s3_06_{kind}_{tag}.json" for kind in ("reanalysis", "paper_index", "replay_differences")]
    existing = [path.name for path in targets if path.exists()]
    if existing and not args.replace:
        print(f"refused: {existing} already exist for this commit; pass --replace to write them again on purpose")
        return EXIT_REFUSED
    try:
        loaded, problems = load_inputs(results)
    except (OSError, ValueError) as exc:  # unreadable or malformed inputs are a refusal, not a result
        print(f"refused: the inputs could not be read: {exc!r}")
        return EXIT_REFUSED
    if problems:
        print(f"refused: {problems[:10]}")
        return EXIT_REFUSED
    freeze_commit = str(loaded["receipt"].get("freeze_commit") or "")
    if not freeze_commit or frozen_code_differs(freeze_commit):
        print(f"refused: src/ or configs/ at HEAD differ from the freeze commit {freeze_commit or '(none recorded)'}")
        return EXIT_REFUSED
    env = environment(loaded["receipt"])
    if not env["python_minor_matches_the_freeze"]:
        print(f"[s3-06] note: Python {env['python']} here, {env['frozen_python']} at the freeze; a replay difference may then be "
              "the interpreter, not the exports")
    requested = int(args.workers) if args.workers else (os.cpu_count() or 1)
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    outcome = reanalyse(loaded, workers=requested)
    base = {"stage": STAGE, "ruling": RULING, "code_commit": head, "freeze_commit": freeze_commit,
            "frozen_src_and_configs": "equal to the freeze commit (git diff --quiet)", "started_utc": started,
            "written_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "environment": env,
            "inputs": {name: file_sha256(ROOT / name) for name in input_names},
            "receipt_sha256": loaded["receipt"]["receipt_sha256"]}
    if not outcome["replay_equal"]:
        path = targets[2]
        write_json(path, {**base, "differences": outcome["differences"], "workers": outcome["workers"],
                          "plain_language_zh": "D1 复算与已提交的 S3-05 统计不相等：只列出不同的字段，不写任何读数。"})
        count = len([item for item in outcome["differences"] if item != TRUNCATED])
        more = " or more" if TRUNCATED in outcome["differences"] else ""
        print(f"[s3-06] the replay differs from the committed statistics in {count}{more} fields: {path}")
        return EXIT_REPLAY_DIFFERS
    write_json(targets[0], {**base, "role": DESCRIPTIVE, **{k: v for k, v in outcome.items() if k != "replay_equal"},
                            "plain_language_zh": ("S3-06 只读复算：D1 逐值复现了已提交的 S3-05 统计；D2～D8 是看过 test 之后"
                                                  "算的描述性读数，不作门、不做多重比较校正。")})
    index, index_problems = paper_index(results, tag, outputs=out_dir)
    write_json(targets[1], {**index, "code_commit": head, "written_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "problems": index_problems})
    problems = outcome["problems"] + index_problems
    print(f"[s3-06] D1 replay equal; {len(problems)} problems; workers {outcome['workers']['actual']}; "
          f"{targets[0].name} and {targets[1].name} written")
    return EXIT_PROBLEMS if problems else EXIT_OK


def command_index(args: argparse.Namespace) -> int:
    """Only the paper index, against an already committed reanalysis (for example after a later stage adds its exports):
    no replay and no statistics are recomputed, every listed file is hashed again and compared with its stage manifest."""

    results, out_dir = Path(args.results).resolve(), Path(args.out_dir).resolve()
    if ROOT not in results.parents:
        print(f"refused: --results must be inside the repository ({ROOT}); the index is bound to committed files")
        return EXIT_REFUSED
    reanalysis = results / f"vsmt_lean_s3_06_reanalysis_{args.reanalysis_tag}.json"
    input_names = [(results / name).relative_to(ROOT).as_posix() for name in index_inputs()]
    input_names.append(reanalysis.relative_to(ROOT).as_posix())
    head, dirty = code_state(input_names)
    if dirty:
        print(f"refused: uncommitted changes in {dirty[:10]} (the index is bound to the committed code and files)")
        return EXIT_REFUSED
    loose = untracked(input_names)
    if loose:
        print(f"refused: files that git does not track: {loose[:10]}")
        return EXIT_REFUSED
    tag = head[:7]
    target = out_dir / f"vsmt_lean_s3_06_paper_index_{tag}.json"
    if target.exists() and not args.replace:
        print(f"refused: {target.name} already exists for this commit; pass --replace to write it again on purpose")
        return EXIT_REFUSED
    index, problems = paper_index(results, str(args.reanalysis_tag))  # the reanalysis is a committed file here
    write_json(target, {**index, "tag": tag, "reanalysis_tag": str(args.reanalysis_tag), "code_commit": head,
                        "written_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "problems": problems})
    print(f"[s3-06] paper index {target.name} written against reanalysis {args.reanalysis_tag}; {len(problems)} problems")
    return EXIT_PROBLEMS if problems else EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S3-06 (ruling 113): read-only reanalysis of the committed S3-05 exports")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="D1 replay, then D2..D8 and the paper index")
    run.add_argument("--results", default=str(ROOT / "results"), help="the committed exports (read only)")
    run.add_argument("--out-dir", default=str(ROOT / "results"), help="where the two outputs are written")
    run.add_argument("--workers", type=int, default=0, help="worker processes (default: the CPU count)")
    run.add_argument("--replace", action="store_true", help="write again over this commit's existing outputs")
    index = sub.add_parser("index", help="only the paper index, against a committed reanalysis")
    index.add_argument("--reanalysis-tag", required=True, help="the tag of the committed vsmt_lean_s3_06_reanalysis_<tag>.json")
    index.add_argument("--results", default=str(ROOT / "results"), help="the committed exports (read only)")
    index.add_argument("--out-dir", default=str(ROOT / "results"), help="where the index is written")
    index.add_argument("--replace", action="store_true", help="write again over this commit's existing index")
    args = parser.parse_args(argv)
    try:
        return command_run(args) if args.command == "run" else command_index(args)
    except ReanalysisError as exc:
        print(f"refused: {exc}")
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
