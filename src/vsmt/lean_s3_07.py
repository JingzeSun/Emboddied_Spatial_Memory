"""S3-07 (ruling 111-6): the external-validation statistics on 3RScan, pooled by scene, reported only, from the frozen functions.

白话：S3-07 跑完之后每套前端每个运行都有一份逐 episode 的审计结果，这个模块把它们装成“场景 × 运行”的表再算统计。一个场景
（参考扫描）配几次重扫描就有几条 episode，它们共用同一段参考扫掠，不独立，所以统计单位是场景（裁决 111-1）：
  * 合并：比值类指标（Missing 残留率、假撤回率两列、身份连续率两列、检索成功率）把分子分母跨该场景的 episode 求和再求比；逐帧类
    （节点 P／R／F1 两列、contamination AUC、规模与成本）按 episode 取均值；恢复延迟把各 episode 的物体并起来再取均值；某个 episode
    的值不可算，这个场景在该指标上就不可算（None），之后按冻结规则排除；
  * 排除清单：``lean_teacher.exclusion_over_runs``——一项指标在任一主表运行上不可算的场景，对所有臂一并排除并计数；
  * 主表：每个臂每项指标在该指标清单内场景上的均值，学习臂另给逐种子与 5 个种子的均值 ± 标准差；
  * 比较：VSMT-lean 对 AssocOnly、每个消融与每个规则臂，每项指标用与 S3-05 相同的按种子配对矩阵（``lean_teacher.seed_paired_matrix``）、
    同一两级重采样（``lean_s3_05.two_level_interval``，同一 bootstrap 种子）给出差值与 90% 区间，并给 82-1 读数——**只报告，不判门，
    没有“通过”字样**；
  * 三分解合计、规模与成本、缺失的运行（审计失败）逐条列出；表头写明“3RScan validation、n＝有效场景数、代理真值、冻结配置、不进主门”；
    不适用项（主门与固定顺序检验、LLM-op、选参与训练相关量、test 封存与读取记录、SAM 2.1 的“跨分割成立”结论）列出而不计算。
输入是合并审计的逐 episode 行与可用 episode 名单；输出是一份统计。例如某个场景有 3 条 episode、每条各 2 个身份连续事件，场景的
身份连续率就是 6 个事件里接回的比例，而不是 3 个比例的平均。它不读任何数据文件、不改任何冻结函数、不读 test、不选任何东西。
"""

from __future__ import annotations

import statistics
from typing import Any, Mapping, Sequence

from vsmt import lean_evaluation as ev
from vsmt import lean_s3_05 as s5
from vsmt import lean_s3_07_3rscan as r3
from vsmt import lean_teacher as lt

STAGE = "vsmt.lean.s3_07.statistics.v1"
FRONTS = dict(s5.FRONTS)
REPORT_METRICS = s5.REPORT_METRICS
DIRECTION = dict(s5.DIRECTION)
LEARNED_ARMS = s5.LEARNED_ARMS
#: VSMT-lean against each of these, every metric, reported only; AssocOnly first (the primary comparison of the main gate)
COMPARED_ARMS = ("AssocOnly", *s5.COMPARED_ARMS)
INTERVAL = s5.NODE_F1_INTERVAL
HEADER = "3RScan validation, n = effective scenes, proxy truth, frozen configurations, not in the main gate"
NOT_APPLICABLE = (
    "primary_gate and fixed_sequence (not computed: S3-07 is corroboration, not the main gate)",
    "LLM-op (validation-only appendix arm, not frozen, not run)",
    "selection and training quantities (nothing is selected or trained on 3RScan)",
    "test seal and read record (3RScan is not the test split)",
    "the SAM 2.1 'holds across segmentations' conclusion of fixed_sequence (both front ends are reported side by side only)",
)
STATISTICS_RULE = (
    "ruling 111-6: per front end one scene x run table per metric, scenes pooled from their episodes (ratio metrics by summed "
    "counts, per-frame metrics by the mean over episodes, recovery latency over the pooled objects); exclusion_over_runs per "
    "metric over the main-table runs; main table means on the kept scenes; VSMT-lean against AssocOnly, every ablation and every "
    "rule arm on every metric: seed-paired difference, two-level 90% interval with the S3-05 draws and seed, 82-1 reading; "
    "reported only, never gating"
)
#: how each frozen metric block pools over a scene's episodes
POOLING = {
    "node_prf1": "mean_over_episodes", "node_prf1_iou": "mean_over_episodes",
    "missing_residual_rate": "summed_counts", "false_retract_rate": "summed_counts", "false_retract_rate_in_scope": "summed_counts",
    "identity_continuity": "summed_counts", "identity_continuity_conditional": "summed_counts", "retrieval_success": "summed_counts",
    "recovery_latency_frames": "pooled_objects", "contamination_auc": "mean_over_episodes",
}
#: (ratio field, numerator field, denominator field) of each summed-counts metric
RATIO_FIELDS = {
    "missing_residual_rate": ("missing_residual_rate", "residual", "judged"),
    "false_retract_rate": ("false_retract_rate", "false_retracts", "judged_retracts"),
    "false_retract_rate_in_scope": ("false_retract_rate", "false_retracts", "judged_retracts"),
    "identity_continuity": ("identity_continuity", "kept", "events"),
    "identity_continuity_conditional": ("identity_continuity", "kept", "judged"),
    "retrieval_success": ("retrieval_success", "successes", "events"),
}


class LeanS3_07Error(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanS3_07Error(code)


# --------------------------------------------------------------------------
# scenes
# --------------------------------------------------------------------------

def scene_of(episode_id: str) -> str:
    """The reference scan (statistical unit) of an S3-07 episode id ``3rscan-<reference>-<rescan>``."""

    _require(isinstance(episode_id, str) and episode_id.startswith(r3.EPISODE_PREFIX), "episode_id_not_3rscan:" + str(episode_id))
    body = episode_id[len(r3.EPISODE_PREFIX):]
    reference, rescan = body[:36], body[37:]
    _require(body[36:37] == "-" and r3.SCAN_ID.fullmatch(reference) is not None and r3.SCAN_ID.fullmatch(rescan) is not None,
             "episode_id_malformed:" + episode_id)
    return reference


def scenes_of(episodes: Sequence[str]) -> dict[str, list[str]]:
    """Scene -> its episodes, in sorted order."""

    out: dict[str, list[str]] = {}
    for episode in sorted(set(map(str, episodes))):
        out.setdefault(scene_of(episode), []).append(episode)
    return out


# --------------------------------------------------------------------------
# pooling one run's episodes of a scene into one report block per metric
# --------------------------------------------------------------------------

def _counts(reports: Sequence[Mapping[str, Any]], metric: str, fields: Sequence[str]) -> dict[str, int]:
    out = {}
    for field in fields:
        values = [report[metric][field] for report in reports]
        _require(all(type(v) is int and v >= 0 for v in values), f"count_invalid:{metric}:{field}")
        out[field] = sum(values)
    return out


def pool_scene(reports: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """One run's episode reports of a scene -> one report with the frozen fields per metric (``POOLING`` per metric)."""

    _require(bool(reports), "pool_needs_reports")
    for report in reports:
        lt.assert_report_keys(report)
    out: dict[str, dict[str, Any]] = {}
    for metric, rule in POOLING.items():
        if rule == "summed_counts":
            ratio, numerator, denominator = RATIO_FIELDS[metric]
            summed = _counts(reports, metric, [f for f in lt.METRIC_FIELDS[metric] if f != ratio])
            out[metric] = {ratio: (summed[numerator] / summed[denominator]) if summed[denominator] else None, **summed}
        elif rule == "mean_over_episodes":
            field = ev.HEADLINE_FIELD[metric]
            values = [report[metric][field] for report in reports]
            block: dict[str, Any] = {field: statistics.fmean(values) if all(v is not None for v in values) else None}
            for name in lt.METRIC_FIELDS[metric]:
                if name == field:
                    continue
                items = [report[metric][name] for report in reports]
                if all(type(v) is int for v in items):
                    block[name] = sum(items)
                elif all(isinstance(v, (int, float)) and v is not None for v in items):
                    block[name] = statistics.fmean(float(v) for v in items)
                else:
                    block[name] = None
            out[metric] = block
        else:  # recovery latency: the objects of every episode pooled, mean over the recovered ones
            per_object: dict[str, Any] = {}
            unrecovered: list[str] = []
            never: list[str] = []
            for index, report in enumerate(reports):
                block = report[metric]
                for key, value in block["per_object"].items():
                    per_object[f"{index}:{key}"] = value
                unrecovered.extend(f"{index}:{key}" for key in block["unrecovered"])
                never.extend(f"{index}:{key}" for key in block["never_observable"])
            finite = [v for v in per_object.values() if v is not None]
            out[metric] = {"recovery_latency_frames": (sum(finite) / len(finite)) if finite else None, "recovered": len(finite),
                           "unrecovered": sorted(unrecovered), "never_observable": sorted(never), "per_object": per_object}
    size = [report["size_and_cost"] for report in reports]
    out["size_and_cost"] = {name: statistics.fmean(float(s[name]) for s in size)
                            for name in ("active_entity_count", "lifecycle_version_count", "runtime_per_frame_s")}
    out["size_and_cost"]["peak_memory_bytes"] = max(int(s["peak_memory_bytes"]) for s in size)
    lt.assert_report_keys(out)  # the pooled block stays within the frozen metric fields
    return out


def scene_tables(runs: Sequence[Mapping[str, Any]], episodes: Sequence[str]) -> dict[str, Any]:
    """Per metric {scene: {run key: pooled value or None}} over the usable episodes, plus the pooled reports and the failures.

    ``runs`` lists ``{"arm", "seed", "rows": {episode: merged per-episode row}}`` as S3-05 does; a run with no row on an episode
    failed there (107-2): its scene is None on every metric for that run (and then excluded by the one list), never replaced."""

    _require(bool(runs) and bool(episodes), "statistics_need_runs_and_episodes")
    by_scene = scenes_of(episodes)
    keys = [s5.key(run["arm"], run.get("seed")) for run in runs]
    _require(len(set(keys)) == len(keys), "statistics_run_repeated")
    per_metric: dict[str, dict[str, dict[str, Any]]] = {metric: {scene: {} for scene in by_scene} for metric in REPORT_METRICS}
    pooled: dict[str, dict[str, Any]] = {k: {} for k in keys}
    failures: list[dict[str, Any]] = []
    for run, run_key in zip(runs, keys):
        rows = run["rows"]
        _require(set(map(str, rows)) <= set(map(str, episodes)), f"statistics_rows_outside_the_episodes:{run_key}")
        for scene, members in by_scene.items():
            missing = [e for e in members if e not in rows]
            failures.extend({"run": run_key, "episode": e, "scene": scene} for e in missing)
            if missing:
                for metric in REPORT_METRICS:
                    per_metric[metric][scene][run_key] = None
                continue
            report = pool_scene([rows[e]["report"] for e in members])
            pooled[run_key][scene] = report
            for metric, field in ev.HEADLINE_FIELD.items():
                per_metric[metric][scene][run_key] = report[metric][field]
    return {"per_metric": per_metric, "pooled": pooled, "scenes": by_scene, "failures": failures}


# --------------------------------------------------------------------------
# statistics of one front end
# --------------------------------------------------------------------------

def _mean_sd(values: Sequence[float]) -> dict[str, Any]:
    values = [float(v) for v in values]
    return {"mean": statistics.fmean(values) if values else None,
            "sd": statistics.stdev(values) if len(values) >= 2 else None, "n": len(values)}


def comparison(table: Mapping[str, Mapping[str, Any]], *, metric: str, control: str, kept: Sequence[str], seed: int,
               iterations: int) -> dict[str, Any]:
    """VSMT-lean against one control on one metric: seed-paired difference, two-level 90% interval, 82-1 reading; no verdict."""

    seeded = control in LEARNED_ARMS
    control_keys = [lt.run_key(control, s) for s in lt.GATE_SEEDS] if seeded else [lt.run_key(control)]
    arm_keys = [lt.run_key("VSMT-lean", s) for s in lt.GATE_SEEDS]
    present = {k for scene in kept for k in table[scene]}
    missing = sorted(k for k in arm_keys + control_keys if k not in present)
    base = {"arm": "VSMT-lean", "control": control, "direction": DIRECTION[metric], "role": "reported only, never gating"}
    if missing:
        return {**base, "evaluable": False, "reason": "runs_missing:" + ",".join(missing)}
    scenes = [scene for scene in kept if all(table[scene].get(k) is not None for k in arm_keys + control_keys)]
    extra = sorted(set(kept) - set(scenes))
    if len(scenes) < 2:
        return {**base, "evaluable": False, "reason": "fewer_than_two_scenes", "scenes": len(scenes), "extra_excluded": extra}
    matrix = lt.seed_paired_matrix(table, arm="VSMT-lean", control=control, direction=DIRECTION[metric], houses=scenes,
                                   control_seeded=seeded)
    gaps = [sum(row[s] for row in matrix) / len(matrix) for s in range(len(lt.GATE_SEEDS))]
    mean = sum(sum(row) for row in matrix) / (len(matrix) * len(lt.GATE_SEEDS))
    interval = s5.two_level_interval(matrix, seed=seed, iterations=iterations, quantiles=INTERVAL)
    return {**base, "evaluable": True, "scenes": len(scenes), "extra_excluded_for_this_control": extra, "mean_advantage": mean,
            "interval_90": interval, "seed_paired_gaps": gaps, "stable_82_1": lt.seed_stability(gaps)}


def front_statistics(tables_block: Mapping[str, Any], runs: Sequence[Mapping[str, Any]], *, seed: int,
                     iterations: int = lt.BOOTSTRAP_ITERATIONS) -> dict[str, Any]:
    """Every statistic of one front end (ruling 111-6): lists, main table, comparisons, decomposition, size and cost."""

    per_metric = tables_block["per_metric"]
    keys = sorted({k for scenes in per_metric.values() for row in scenes.values() for k in row})
    main_runs = [k for k in lt.main_table_runs() if k in keys]
    lists, table_rows, comparisons = {}, {}, {}
    for metric in REPORT_METRICS:
        table = per_metric[metric]
        skipped = s5.not_applicable_keys(metric, main_runs)
        excluded = lt.exclusion_over_runs(table, runs=main_runs, not_applicable=skipped)
        kept = [scene for scene in sorted(table) if scene not in set(excluded)]
        lists[metric] = {"excluded_scenes": excluded, "effective_scenes": len(kept), "not_applicable_runs": skipped,
                         "rule": "ruling 102-3 applied per scene: one list per metric over every main-table run"}
        rows = {}
        for arm in dict.fromkeys(k.split(":")[0] for k in keys):
            arm_keys = [k for k in keys if k.split(":")[0] == arm]
            if s5.not_applicable_keys(metric, arm_keys):
                rows[arm] = {"not_applicable": True}
                continue
            per_key = {}
            for k in arm_keys:
                values = [table[scene][k] for scene in kept if table[scene].get(k) is not None]
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
            elif s5.not_applicable_keys(metric, control_keys):
                comparisons[metric][control] = {"not_applicable": True}
            else:
                comparisons[metric][control] = comparison(table, metric=metric, control=control, kept=kept, seed=seed,
                                                          iterations=iterations)
    decomposition: dict[str, dict[str, int]] = {}
    size: dict[str, dict[str, Any]] = {}
    for run in runs:
        run_key = s5.key(run["arm"], run.get("seed"))
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
    return {"header": HEADER, "scenes": len(tables_block["scenes"]), "episodes": sum(len(v) for v in tables_block["scenes"].values()),
            "pooling": dict(POOLING), "exclusion_lists": lists, "main_table": table_rows,
            "main_table_rule": ("each metric's mean over the scenes its one list keeps; a learned arm missing on a kept scene has no "
                                "mean (None) for that seed, shown by seeds_with_values -- never a mean over fewer scenes"),
            "comparisons": comparisons, "decomposition_totals": decomposition, "size_and_cost_episode_means": size,
            "failures": list(tables_block["failures"])}


def external_statistics(per_front: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """The S3-07 statistics over the front ends present: no fixed sequence, no gate, the not-applicable list stated."""

    _require(bool(per_front) and set(per_front) <= set(FRONTS), "statistics_need_a_registered_front_end")
    for block in per_front.values():
        _require("primary_gate" not in block and "fixed_sequence" not in block, "gate_block_in_external_statistics")
    return {"stage": STAGE, "header": HEADER, "rule": STATISTICS_RULE, "not_applicable": list(NOT_APPLICABLE),
            "fronts_missing": sorted(set(FRONTS) - set(per_front)), "fronts": dict(per_front)}


__all__ = [
    "COMPARED_ARMS", "DIRECTION", "FRONTS", "HEADER", "LEARNED_ARMS", "LeanS3_07Error", "NOT_APPLICABLE", "POOLING",
    "REPORT_METRICS", "STAGE", "STATISTICS_RULE", "comparison", "external_statistics", "front_statistics", "pool_scene",
    "scene_of", "scene_tables", "scenes_of",
]
