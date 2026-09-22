"""D-224 / S1-04: frontend diagnostics on the development cache, as a pure core.

Three questions, answered on the S1-03 cache with private truth opened only after the cache was
sealed: does a frozen descriptor (or the shared ReID projection) separate the same object across
views from other objects in the same house; how often does the S0-03 recall rule miss the correct
entity as a function of its four values (ruling 46: measured against an *ideal memory* built from
private truth, so the answer is a property of the frontend and not of any arm); and how well does
a single-view fragment box overlap the whole-object truth box that ruling 45 reconstructs (the
node P/R/F1 metric matches at IoU 0.3, so a median below it would make every arm's F1 noise).

Nothing here loads a model, a simulator or a file.  The runner hands in, per frame, the cache
fragments (descriptor, centroid, box) together with the private label each fragment got from
the strict-majority rule below; the functions return numbers and the contract validator binds
every constant.

白话：这个模块回答三件事——冻结描述子分不分得开同一物体的不同视角、S0-03 的召回规则在不同
k/k′/半径下漏掉正确实体的比例、单视角色块盒与整物体真值盒的三维 IoU。输入是 cache 里每帧的色块
（描述子、质心、盒）加上诊断标注（哪个私有实例占了色块像素的严格过半）；输出是分布统计。它不
选描述子、不定任何臂的参数、不算论文指标；召回曲线用的"记忆"是由真值造的理想记忆，只作诊断。

Importable under Python 3.9 as well (no 3.10+ syntax at runtime).
"""

from __future__ import annotations

import math
import random
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from vsmt.lean_assignment import (
    REID_OUTPUT_DIMENSION, REID_SELECTION_HOUSES, REID_SELECTION_RULE_THRESHOLD, REID_TRAINING_HOUSES,
)
from vsmt.lean_object_geometry import CONTAINMENT_MARGIN_M, DRIFT_TOLERANCE_M, OBJECT_FIELDS, TABLE_FILE_NAME

CONTRACT_SCHEMA_VERSION = "vsmt-lean-s1-04-frontend-diagnostics-v1"
STAGE_ID = "S1-04"

#: Diagnostic labelling: the private instance holding a strict majority of the fragment's pixels.
LABEL_RULE = "strict_majority_of_fragment_pixels_on_one_private_instance"
LABEL_DENOMINATOR = "all_fragment_pixels_background_included"
MAJORITY_SHARE_EXCLUSIVE = 0.5

#: Cross-view separation sampling (registered so the report is reproducible).
SEPARATION_SETS = ("vits14", "vitb14", "reid_projection")
FRAMES_PER_FRAGMENT_CAP = 8
FRAGMENTS_PER_OBJECT_CAP = 64
SAMPLING_SEED = 20260922

#: Ruling 46: the recall grid the curve is reported on, and the birth neighbourhood radii.
RECALL_GRID = {
    "local_count": (1, 2, 3, 5, 8),
    "global_count": (0, 1, 2, 3, 5),
    "local_radius_m": (0.5, 1.0, 1.5, 2.0, 3.0),
}
BIRTH_RADIUS_GRID = (0.25, 0.5, 1.0)
IDEAL_MEMORY_RULE = "ideal_memory_one_entity_per_truth_object_from_its_labelled_fragments_before_t"

#: D-224-C / S0-04: the node matching threshold the IoU diagnostic is judged against.
IOU_GATE_MEDIAN = 0.3
TRUTH_BOX_RULE = "simulator_initial_axis_aligned_box_plus_recorded_translation"
STATISTICS = ("count", "mean", "median", "p10", "p25", "p75")

#: Ruling 47: the ReID head as this stage trains it.
REID_ARCHITECTURE = "single_linear_layer_from_the_frozen_descriptor_to_128_then_l2_normalisation"
REID_LOSS = "supervised_contrastive_over_labelled_fragments_of_training_houses"
REID_VALUE_SLOTS = ("temperature", "epochs", "batch_fragments", "learning_rate", "seed")

FAILURE_REASONS = (
    "source_episode_not_succeeded",
    "house_load_failed",
    "metadata_missing_or_malformed",
    "private_plane_missing_or_malformed",
    "table_invalid",
    "cache_missing_or_unsealed",
    "fragment_masks_missing",
    "training_diverged",
)


class LeanDiagnosticsError(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanDiagnosticsError(code)


# --------------------------------------------------------------------------
# labelling and small numerics
# --------------------------------------------------------------------------

def overlap_from_masks(fragment_mask: Any, labels: Any, object_of_label: Mapping[int, str]) -> dict[str, float]:
    """Share of the fragment's pixels on each private instance (denominator: all fragment pixels)."""

    binary = np.asarray(fragment_mask, dtype=bool)
    label_image = np.asarray(labels)
    _require(binary.shape == label_image.shape, "mask_shape_mismatch")
    total = int(binary.sum())
    _require(total > 0, "fragment_mask_empty")
    values, counts = np.unique(label_image[binary], return_counts=True)
    out: dict[str, float] = {}
    for value, count in zip(values.tolist(), counts.tolist()):
        key = object_of_label.get(int(value))
        if key is None:
            continue  # background (0) or a label without an object id
        out[key] = out.get(key, 0.0) + count / total
    return dict(sorted(out.items()))


def label_fragment(overlap: Mapping[str, float]) -> str | None:
    """The object holding a strict majority of the fragment's pixels, else None."""

    best_key = None
    best = 0.0
    for key, share in overlap.items():
        share = float(share)
        _require(0.0 <= share <= 1.0 + 1e-9, "overlap_share_invalid")
        if share > best or (share == best and best_key is not None and key < best_key):
            best_key, best = key, share
    return best_key if best > MAJORITY_SHARE_EXCLUSIVE else None


def summarise(values: Iterable[float]) -> dict[str, Any]:
    """count/mean/median/p10/p25/p75 of a sample (None when empty)."""

    data = np.asarray([float(v) for v in values], dtype=np.float64)
    if data.size == 0:
        return {name: (0 if name == "count" else None) for name in STATISTICS}
    return {
        "count": int(data.size),
        "mean": float(data.mean()),
        "median": float(np.median(data)),
        "p10": float(np.percentile(data, 10)),
        "p25": float(np.percentile(data, 25)),
        "p75": float(np.percentile(data, 75)),
    }


def l2_normalise(vector: Sequence[float]) -> list[float]:
    array = np.asarray(vector, dtype=np.float64)
    norm = float(np.linalg.norm(array))
    _require(math.isfinite(norm) and norm > 0.0, "vector_not_normalisable")
    return (array / norm).tolist()


def mean_descriptor(vectors: Sequence[Sequence[float]]) -> list[float]:
    _require(len(vectors) > 0, "no_vectors")
    return l2_normalise(np.mean(np.asarray(vectors, dtype=np.float64), axis=0))


# --------------------------------------------------------------------------
# cross-view separation
# --------------------------------------------------------------------------

def _per_frame_object_means(frames: Sequence[Mapping[str, Any]], descriptor_key: str) -> list[dict[str, list[float]]]:
    means: list[dict[str, list[float]]] = []
    for frame in frames:
        grouped: dict[str, list[Sequence[float]]] = {}
        for fragment in frame["fragments"]:
            key = fragment.get("object")
            if key is not None:
                grouped.setdefault(key, []).append(fragment[descriptor_key])
        means.append({key: mean_descriptor(vectors) for key, vectors in sorted(grouped.items())})
    return means


def separation_statistics(
    frames: Sequence[Mapping[str, Any]], *, descriptor_key: str = "descriptor",
    seed: int = SAMPLING_SEED, frames_per_fragment_cap: int = FRAMES_PER_FRAGMENT_CAP,
    fragments_per_object_cap: int = FRAGMENTS_PER_OBJECT_CAP, separate_objects: Iterable[str] = (),
) -> dict[str, Any]:
    """Cross-view separation of one descriptor set over one episode.

    白话：对每个物体最多抽 64 个带标签色块，每个色块最多配 8 个它也出现的别的帧；正分＝色块与
    该物体在那一帧的均值描述子的余弦，负分＝那一帧里别的物体均值描述子的最高余弦，分离度＝正−负。
    那一帧若没有别的物体，这一对不算。输出分布统计与样本数；`separate_objects`（例如 add 的物
    体）单列。
    """

    means = _per_frame_object_means(frames, descriptor_key)
    by_object: dict[str, list[tuple[int, Sequence[float]]]] = {}
    for index, frame in enumerate(frames):
        for fragment in frame["fragments"]:
            key = fragment.get("object")
            if key is not None:
                by_object.setdefault(key, []).append((index, fragment[descriptor_key]))
    rng = random.Random(seed)
    separated = set(separate_objects)
    pooled: list[float] = []
    special: list[float] = []
    pairs = 0
    for key in sorted(by_object):
        items = by_object[key]
        if len(items) > fragments_per_object_cap:
            items = rng.sample(items, fragments_per_object_cap)
        other_frames = sorted(index for index, table in enumerate(means) if key in table)
        for index, descriptor in items:
            candidates = [u for u in other_frames if u != index]
            if len(candidates) > frames_per_fragment_cap:
                candidates = rng.sample(candidates, frames_per_fragment_cap)
            vector = np.asarray(descriptor, dtype=np.float64)
            for u in candidates:
                table = means[u]
                others = [np.dot(vector, np.asarray(table[p], dtype=np.float64)) for p in table if p != key]
                if not others:
                    continue
                positive = float(np.dot(vector, np.asarray(table[key], dtype=np.float64)))
                value = positive - float(max(others))
                pairs += 1
                (special if key in separated else pooled).append(value)
    return {
        "objects": len(by_object),
        "pairs": pairs,
        "statistics": summarise(pooled),
        "separate_objects_statistics": summarise(special),
        "values": pooled,
    }


# --------------------------------------------------------------------------
# ideal memory and the recall curve (ruling 46)
# --------------------------------------------------------------------------

class IdealMemory:
    """One entity per truth object seen so far, from its labelled fragments (diagnostic only)."""

    def __init__(self) -> None:
        self._sum: dict[str, np.ndarray] = {}
        self._centroid: dict[str, np.ndarray] = {}
        self._count: dict[str, int] = {}

    def __len__(self) -> int:
        return len(self._count)

    def __contains__(self, key: str) -> bool:
        return key in self._count

    def view(self) -> dict[str, Any]:
        """The memory in the shape ``lean_assignment.recall_for_fragment`` reads."""

        entities = []
        for key in sorted(self._count):
            entities.append({
                "entity_id": key,
                "descriptor_mean": l2_normalise(self._sum[key]),
                "centroid_m": (self._centroid[key] / self._count[key]).tolist(),
                "state": "active",
            })
        return {"entities": entities}

    def update(self, fragments: Iterable[Mapping[str, Any]], *, descriptor_key: str = "descriptor") -> None:
        for fragment in fragments:
            key = fragment.get("object")
            if key is None:
                continue
            vector = np.asarray(fragment[descriptor_key], dtype=np.float64)
            centroid = np.asarray(fragment["centroid_m"], dtype=np.float64)
            if key in self._count:
                self._sum[key] = self._sum[key] + vector
                self._centroid[key] = self._centroid[key] + centroid
                self._count[key] += 1
            else:
                self._sum[key] = vector.copy()
                self._centroid[key] = centroid.copy()
                self._count[key] = 1


def recall_ranks(fragment: Mapping[str, Any], memory: Mapping[str, Any], target: str, *,
                 descriptor_key: str = "descriptor") -> dict[str, Any]:
    """Where the target entity ranks in the two S0-03 recall channels for one fragment.

    Reproduces ``lean_assignment.recall_for_fragment`` exactly (cosine descending, ties by smaller
    entity id) but returns ranks, so one pass answers every grid point: the target is recalled at
    (k, k', R) iff ``global_rank < k'`` or (``distance <= R`` and ``local_rank(R) < k``).
    """

    entities = memory["entities"]
    ids = [str(e["entity_id"]) for e in entities]
    _require(target in ids, "target_not_in_memory")
    vector = np.asarray(fragment[descriptor_key], dtype=np.float64)
    centroid = np.asarray(fragment["centroid_m"], dtype=np.float64)
    matrix = np.asarray([e["descriptor_mean"] for e in entities], dtype=np.float64)
    norms = np.linalg.norm(matrix, axis=1) * float(np.linalg.norm(vector))
    cosines = (matrix @ vector) / np.where(norms > 0.0, norms, 1.0)
    distances = np.linalg.norm(np.asarray([e["centroid_m"] for e in entities], dtype=np.float64) - centroid, axis=1)
    index = ids.index(target)
    better = (cosines > cosines[index]) | ((cosines == cosines[index]) & (np.asarray(ids) < target))
    return {
        "global_rank": int(better.sum()),
        "distance_m": float(distances[index]),
        "cosine": float(cosines[index]),
        "better": better,
        "distances": distances,
    }


def recalled_at(ranks: Mapping[str, Any], *, local_count: int, global_count: int, local_radius_m: float) -> bool:
    if ranks["global_rank"] < global_count:
        return True
    if ranks["distance_m"] > local_radius_m:
        return False
    local_rank = int((ranks["better"] & (ranks["distances"] <= local_radius_m)).sum())
    return local_rank < local_count


def recall_curve(
    frames: Sequence[Mapping[str, Any]], *, descriptor_key: str = "descriptor",
    grid: Mapping[str, Sequence[Any]] = RECALL_GRID, birth_radius_grid: Sequence[float] = BIRTH_RADIUS_GRID,
) -> dict[str, Any]:
    """recall_miss over the grid, memory sizes, and birth-neighbourhood counts, for one episode.

    白话：逐帧走一遍：先用当前理想记忆判每个带标签、且其物体已在记忆里的色块在各 (k, k′, R) 下
    有没有召回到正确实体，再把这一帧的带标签色块并进记忆。物体不在记忆里的色块是真 BIRTH，只
    统计它附近各半径内的实体数。输出每个网格点的决定数与漏召回数、记忆规模的最大值与 p95。
    """

    memory = IdealMemory()
    points = [(k, g, r) for k in grid["local_count"] for g in grid["global_count"] for r in grid["local_radius_m"]]
    decisions = {point: 0 for point in points}
    misses = {point: 0 for point in points}
    sizes: list[int] = []
    births = 0
    neighbourhood: dict[float, list[int]] = {float(r): [] for r in birth_radius_grid}
    for frame in frames:
        view = memory.view() if len(memory) else {"entities": []}
        sizes.append(len(memory))
        for fragment in frame["fragments"]:
            key = fragment.get("object")
            if key is None:
                continue
            if key in memory:
                ranks = recall_ranks(fragment, view, key, descriptor_key=descriptor_key)
                for point in points:
                    decisions[point] += 1
                    if not recalled_at(ranks, local_count=point[0], global_count=point[1], local_radius_m=point[2]):
                        misses[point] += 1
            else:
                births += 1
                if view["entities"]:
                    centroid = np.asarray(fragment["centroid_m"], dtype=np.float64)
                    distances = np.linalg.norm(
                        np.asarray([e["centroid_m"] for e in view["entities"]], dtype=np.float64) - centroid, axis=1)
                    for r in neighbourhood:
                        neighbourhood[r].append(int((distances <= r).sum()))
                else:
                    for r in neighbourhood:
                        neighbourhood[r].append(0)
        memory.update(frame["fragments"], descriptor_key=descriptor_key)
    rows = []
    for point in points:
        n, m = decisions[point], misses[point]
        rows.append({"local_count": point[0], "global_count": point[1], "local_radius_m": point[2],
                     "decisions": n, "recall_miss": m, "recall_miss_rate": (m / n if n else None)})
    return {
        "grid_points": rows,
        "decisions_total": decisions[points[0]] if points else 0,
        "births_total": births,
        "memory_size_max": (max(sizes) if sizes else 0),
        "memory_size_p95": (int(np.percentile(np.asarray(sizes), 95)) if sizes else 0),
        "birth_neighbourhood": {str(r): summarise(counts) for r, counts in neighbourhood.items()},
    }


def merge_recall_curves(curves: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Pool per-episode curves: counts add, memory sizes take the max / max of p95."""

    _require(len(curves) > 0, "no_curves")
    rows: dict[tuple, dict[str, Any]] = {}
    for curve in curves:
        for row in curve["grid_points"]:
            point = (row["local_count"], row["global_count"], row["local_radius_m"])
            entry = rows.setdefault(point, {"local_count": point[0], "global_count": point[1], "local_radius_m": point[2],
                                            "decisions": 0, "recall_miss": 0})
            entry["decisions"] += row["decisions"]
            entry["recall_miss"] += row["recall_miss"]
    merged = []
    for point in sorted(rows):
        entry = rows[point]
        entry["recall_miss_rate"] = entry["recall_miss"] / entry["decisions"] if entry["decisions"] else None
        merged.append(entry)
    return {
        "grid_points": merged,
        "decisions_total": sum(c["decisions_total"] for c in curves),
        "births_total": sum(c["births_total"] for c in curves),
        "memory_size_max": max(c["memory_size_max"] for c in curves),
        "memory_size_p95_max_over_episodes": max(c["memory_size_p95"] for c in curves),
        "episodes": len(curves),
    }


# --------------------------------------------------------------------------
# fragment-versus-truth IoU (ruling 45)
# --------------------------------------------------------------------------

def iou_statistics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Distribution of fragment-box IoU against the truth box and against the proxy box.

    Each row: ``iou_truth`` (float), ``iou_proxy`` (float or None), ``pickupable``, ``receptacle``.
    """

    truth = [float(r["iou_truth"]) for r in rows]
    proxy = [float(r["iou_proxy"]) for r in rows if r.get("iou_proxy") is not None]
    groups = {"pickupable": [], "receptacle": [], "other": []}
    for r in rows:
        name = "pickupable" if r.get("pickupable") else ("receptacle" if r.get("receptacle") else "other")
        groups[name].append(float(r["iou_truth"]))
    stats = summarise(truth)
    return {
        "truth": stats,
        "proxy_observed_set_box": summarise(proxy),
        "by_group": {name: summarise(values) for name, values in groups.items()},
        "gate_median_iou": IOU_GATE_MEDIAN,
        "median_below_gate": (None if stats["median"] is None else bool(stats["median"] < IOU_GATE_MEDIAN)),
    }


# --------------------------------------------------------------------------
# contract
# --------------------------------------------------------------------------

def validate_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Check that the S1-04 machine contract agrees with this implementation."""

    _require(isinstance(contract, Mapping), "contract_not_object")
    _require(contract.get("schema_version") == CONTRACT_SCHEMA_VERSION, "contract_schema_version_invalid")
    _require(contract.get("stage_id") == STAGE_ID, "contract_stage_id_invalid")
    geometry = contract["object_geometry"]
    _require(geometry["file"] == TABLE_FILE_NAME, "contract_geometry_file_mismatch")
    _require(tuple(geometry["fields"]) == OBJECT_FIELDS, "contract_geometry_fields_mismatch")
    _require(geometry["truth_box_rule"] == TRUTH_BOX_RULE, "contract_truth_box_rule_mismatch")
    checks = geometry["residual_checks"]
    _require(checks["drift_tolerance_m"] == DRIFT_TOLERANCE_M, "contract_drift_tolerance_mismatch")
    _require(checks["containment_margin_m"] == CONTAINMENT_MARGIN_M, "contract_containment_margin_mismatch")
    for name in ("boxes_are_in_the_episode_frame", "one_reload_per_episode_no_action_but_the_bootstrap_teleport",
                 "observed_set_box_is_a_proxy_comparison_column", "no_generated_episode_file_is_modified"):
        _require(geometry[name] is True, "contract_geometry_claim_weakened:" + name)
    labelling = contract["fragment_labelling"]
    _require(labelling["rule"] == LABEL_RULE, "contract_label_rule_mismatch")
    _require(labelling["denominator"] == LABEL_DENOMINATOR, "contract_label_denominator_mismatch")
    _require(labelling["majority_share_exclusive"] == MAJORITY_SHARE_EXCLUSIVE, "contract_majority_share_mismatch")
    _require(labelling["labelling_is_diagnostic_only_not_the_s0_04_teacher"] is True, "contract_labelling_scope_weakened")
    separation = contract["separation"]
    _require(tuple(separation["descriptor_sets"]) == SEPARATION_SETS, "contract_separation_sets_mismatch")
    _require(separation["frames_per_fragment_cap"] == FRAMES_PER_FRAGMENT_CAP
             and separation["fragments_per_object_cap"] == FRAGMENTS_PER_OBJECT_CAP
             and separation["sampling_seed"] == SAMPLING_SEED, "contract_separation_sampling_mismatch")
    _require(tuple(separation["statistics"]) == STATISTICS, "contract_statistics_mismatch")
    curve = contract["recall_curve"]
    _require(curve["memory"] == IDEAL_MEMORY_RULE, "contract_ideal_memory_rule_mismatch")
    _require({k: tuple(v) for k, v in curve["grid"].items()} == RECALL_GRID, "contract_recall_grid_mismatch")
    _require(tuple(curve["birth_neighbourhood_radius_m_grid"]) == BIRTH_RADIUS_GRID, "contract_birth_grid_mismatch")
    _require(curve["uses_s0_03_recall_for_fragment"] is True and curve["freeze_after_curve_once"] is True,
             "contract_recall_curve_claim_weakened")
    _require(curve["split"] == "development_cache_only_never_validation_or_test", "contract_recall_split_mismatch")
    iou = contract["fragment_truth_iou"]
    _require(iou["gate_median_iou"] == IOU_GATE_MEDIAN and iou["gate_is_a_pause_point_not_a_tuning_knob"] is True,
             "contract_iou_gate_mismatch")
    reid = contract["reid_training"]
    _require(reid["architecture"] == REID_ARCHITECTURE and reid["loss"] == REID_LOSS, "contract_reid_recipe_mismatch")
    _require(reid["output_dimension"] == REID_OUTPUT_DIMENSION, "contract_reid_dimension_mismatch")
    _require(reid["holdout"]["training_houses"] == REID_TRAINING_HOUSES
             and reid["holdout"]["selection_houses"] == REID_SELECTION_HOUSES, "contract_reid_holdout_mismatch")
    _require(reid["selection_rule_threshold"] == REID_SELECTION_RULE_THRESHOLD, "contract_reid_threshold_mismatch")
    _require(reid["trained_once_then_frozen"] is True and reid["weights_file_carries_no_private_bytes"] is True,
             "contract_reid_claim_weakened")
    open_slots = contract["policy_values_without_defaults"]
    for name in REID_VALUE_SLOTS:
        slot = "reid_training." + name
        if reid[name] is None:
            _require(slot in open_slots, "contract_reid_value_null_but_not_registered_as_open:" + name)
        else:
            _require(slot not in open_slots, "contract_reid_value_frozen_but_still_listed_as_open:" + name)
    _require(tuple(contract["failure_reasons"]) == FAILURE_REASONS, "contract_failure_reasons_mismatch")
    _require("coverage_ratios" in contract["not_in_this_stage"] and contract["coverage_ratios"]["status"] == "deferred_to_s2_01",
             "contract_coverage_scope_mismatch")
    policy = contract.get("activation_policy")
    opened = set(policy["active_true_authorizations"]) if policy else set()
    if policy:
        _require(isinstance(policy.get("opened_by"), str) and bool(policy["opened_by"]), "contract_activation_policy_names_no_ruling")
    for name, value in contract["authorization"].items():
        _require(isinstance(value, bool), "contract_authorization_not_boolean:" + name)
        _require(value is False or name in opened, "contract_bit_opened_without_a_ruling:" + name)
    return dict(contract)


__all__ = [
    "BIRTH_RADIUS_GRID",
    "CONTRACT_SCHEMA_VERSION",
    "FAILURE_REASONS",
    "FRAGMENTS_PER_OBJECT_CAP",
    "FRAMES_PER_FRAGMENT_CAP",
    "IOU_GATE_MEDIAN",
    "IdealMemory",
    "LABEL_RULE",
    "LeanDiagnosticsError",
    "MAJORITY_SHARE_EXCLUSIVE",
    "RECALL_GRID",
    "REID_VALUE_SLOTS",
    "SAMPLING_SEED",
    "SEPARATION_SETS",
    "STATISTICS",
    "iou_statistics",
    "l2_normalise",
    "label_fragment",
    "mean_descriptor",
    "merge_recall_curves",
    "overlap_from_masks",
    "recall_curve",
    "recall_ranks",
    "recalled_at",
    "separation_statistics",
    "summarise",
    "validate_contract",
]
