"""D-217 deterministic reservations, development sampling, and RGB-D rules."""

from __future__ import annotations

from collections import deque
import hashlib
import math
import re
from typing import Any, Mapping, Sequence

from cpmt.hashing import canonical_json, clone_json
from .d215_frontend_freeze import validate_d215_contract
from .d216_estimator_training import (
    make_house_split_manifest,
    make_reserved_house_manifest,
    validate_d216_contract,
)
from .two_house_audit import validate_source_inventory


CONTRACT_SCHEMA = "vsmt-vm04-d217-estimator-development-rgbd-v1"
PUBLIC_PLAN_SCHEMA = "vsmt-vm04-d217-public-development-plan-v1"
PRIVATE_PLAN_SCHEMA = "vsmt-vm04-d217-private-development-plan-v1"
AUDIT_SEAL_SCHEMA = "vsmt-vm04-d217-private-audit-seal-v1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SPLITS = ("train", "calibration", "audit")


class D217Error(ValueError):
    """A stable D-217 protocol or construction failure."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise D217Error(message)


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _seal(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    result = clone_json(dict(value))
    result[field] = _sha(result)
    return result


def _hex(value: Any, length: int, name: str) -> str:
    pattern = HEX40 if length == 40 else HEX64
    _require(type(value) is str and pattern.fullmatch(value) is not None,
             f"{name} must be a lowercase SHA-{length * 4}")
    return value


def validate_d217_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    value = clone_json(dict(contract))
    _require(set(value) == {
        "schema_version", "decision_id", "status", "reviewed_baseline_commit",
        "expected_reviewed_implementation_commit", "d216_binding",
        "authorization", "activation_policy", "vm04_reservations",
        "development_sample", "expansion_policy", "rgbd_generation",
        "resource_policy",
    }, "D-217 contract has unexpected fields")
    _require(value["schema_version"] == CONTRACT_SCHEMA and
             value["decision_id"] == "D-217" and value["status"] in {
                 "implementation_pending_review_all_execution_closed",
                 "frozen_executable_development_plan_and_train_calibration_rgbd",
             }, "D-217 identity or status changed")
    _require(value["reviewed_baseline_commit"] ==
             "7927e252e30d87773c7830fcfc902a58c07644f7" and
             value["d216_binding"] == {
                 "relative_path":
                     "configs/vsmt/vm04_d216_estimator_training_seal_v1.json",
                 "file_sha256":
                     "22b85ed79ae6b89e2c05a55b7878962171d47e9b7a49202ff10d4d09f00c04ea",
             }, "D-217 baseline binding changed")
    authorizations = value["authorization"]
    expected_keys = {
        "development_plan_sealing", "capacity_probe",
        "train_rgbd_generation", "calibration_rgbd_generation",
        "audit_open_or_generation", "semantic_annotation",
        "feature_materialization", "estimator_training",
        "full_house_expansion", "production_reader", "p04_p08_qualification",
        "route_or_raw_generation", "private_evaluation",
    }
    _require(set(authorizations) == expected_keys,
             "D-217 authorization keys changed")
    policy = value["activation_policy"]
    _require(policy["active_status"] ==
             "frozen_executable_development_plan_and_train_calibration_rgbd" and
             policy["activation_commit_may_change_only"] == [
                 "configs/vsmt/vm04_d217_estimator_development_rgbd_v1.json"] and
             set(policy["active_true_authorizations"]) == {
                 "development_plan_sealing", "capacity_probe",
                 "train_rgbd_generation", "calibration_rgbd_generation"} and
             set(policy["must_remain_false"]) == expected_keys - {
                 "development_plan_sealing", "capacity_probe",
                 "train_rgbd_generation", "calibration_rgbd_generation"},
             "D-217 activation policy changed")
    if value["status"] == "implementation_pending_review_all_execution_closed":
        _require(value["expected_reviewed_implementation_commit"] is None and
                 not any(authorizations.values()),
                 "D-217 review candidate must keep all execution closed")
    else:
        _hex(value["expected_reviewed_implementation_commit"], 40,
             "reviewed implementation commit")
        _require({key for key, enabled in authorizations.items() if enabled} ==
                 set(policy["active_true_authorizations"]),
                 "D-217 active authorization scope changed")
    reservations = value["vm04_reservations"]
    _require(reservations == {
        "ordering":
            "ascending_sha256(source_manifest_sha256|260914|house_id)",
        "ordering_seed": 260914,
        "p0_house_ids": ["train:004270", "train:008243"],
        "validation_house_count": 12,
        "private_confirmation_candidate_pool_count": 64,
        "validation_precedes_confirmation_pool_in_order": True,
        "confirmation_ids_public": False,
        "confirmation_public_fields": [
            "count", "commitment_list_sha256", "private_manifest_sha256"],
    }, "D-217 reservation policy changed")
    sample = value["development_sample"]
    _require(sample["sampling_salt"] ==
             "d217-estimator-development-sample-v1" and
             sample["house_counts"] == {
                 "train": 512, "calibration": 64, "audit": 64} and
             sample["observations_per_house"] == 32 and
             sample["train_observation_count"] == 16384 and
             sample["calibration_observation_count"] == 2048 and
             sample["audit_observation_count"] == 2048 and
             sample["audit_ids_and_observations_open_before_final_frontend_choice"]
             is False and
             sample["unselected_houses_may_be_added_after_audit_open"] is False
             and sample["failure_replacement_allowed"] is False,
             "D-217 development sampling changed")
    expansion = value["expansion_policy"]
    _require(expansion == {
        "train_and_calibration_may_be_used_for_debugging": True,
        "audit_may_be_used_for_debugging": False,
        "full_house_expansion_choice_count": 1,
        "choice_deadline":
            "before_audit_open_production_reader_p04_p08_route_or_raw",
        "full_expansion_restarts_normalization_weights_and_temperatures_from_zero":
            True,
        "development_cache_valid_after_full_expansion": False,
        "audit_failure_may_trigger_more_data_or_model_changes": False,
    }, "D-217 expansion boundary changed")
    rgbd = value["rgbd_generation"]
    _require(rgbd["ai2thor_version"] == "5.0.0" and
             rgbd["width"] == rgbd["height"] == 224 and
             rgbd["vertical_fov_degrees"] == 90.0 and
             rgbd["grid_size_m"] == 0.25 and
             rgbd["render_depth_image"] is True and
             rgbd["render_instance_segmentation"] is False and
             rgbd["positions_per_house"] == 8 and
             rgbd["yaw_degrees"] == [0, 90, 180, 270] and
             rgbd["public_arrays"] == [
                 "rgb_uint8", "depth_m_float32",
                 "camera_intrinsics_float64", "observation_ids"] and
             "house_id" in rgbd["public_forbidden"] and
             "instance_mask" in rgbd["public_forbidden"] and
             rgbd["house_failure_policy"] ==
             "retain_failure_without_replacement" and
             rgbd["overwrite_allowed"] is False,
             "D-217 public RGB-D boundary changed")
    resources = value["resource_policy"]
    _require(resources["capacity_probe_required_before_batch"] is True and
             resources["probe_worker_counts"] == [1, 2, 4, 8] and
             resources["worker_unit"] == "whole_house" and
             resources["wall_clock_timeout_allowed"] is False,
             "D-217 resource policy changed")
    return value


def _ordered_house_ids(ids: Sequence[str], source_sha: str, seed: int) -> list[str]:
    return sorted(ids, key=lambda house_id: hashlib.sha256(
        f"{source_sha}|{seed}|{house_id}".encode("utf-8")).hexdigest())


def ordered_sample_candidates(
    partition_rows: Sequence[Mapping[str, Any]], *, split: str,
    sampling_salt: str,
) -> list[str]:
    """Return one split's candidate houses in the frozen sampling order.

    D-221 extends the sampled prefix, so it must order candidates with exactly
    this key.  Keeping one implementation guarantees that ranks 0..N-1 stay
    identical when the prefix grows.
    """

    candidates = [row["house_id"] for row in partition_rows
                  if row["split"] == split]
    candidates.sort(key=lambda house_id: hashlib.sha256(
        f"{sampling_salt}|{split}|{house_id}".encode("utf-8")).hexdigest())
    return candidates


def public_house_ref(
    *, split: str, sample_rank: int, partition_manifest_receipt_sha256: str,
) -> str:
    """Opaque public handle for one sampled house."""

    return _sha({
        "scope": "d217-public-house", "split": split,
        "sample_rank": sample_rank,
        "partition": partition_manifest_receipt_sha256,
    })


def make_development_plan(
    *, source_inventory: Mapping[str, Any], d215_contract: Mapping[str, Any],
    d216_contract: Mapping[str, Any], d217_contract: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Freeze reservations and 512/64/64 before opening any observation."""

    d217 = validate_d217_contract(d217_contract)
    validate_d215_contract(d215_contract)
    validate_d216_contract(d216_contract)
    inventory = validate_source_inventory(source_inventory)
    ids = inventory["eligible_house_ids"]
    source_sha = inventory["source_manifest_sha256"]
    policy = d217["vm04_reservations"]
    p0 = set(policy["p0_house_ids"])
    ordered = [item for item in _ordered_house_ids(
        ids, source_sha, policy["ordering_seed"]) if item not in p0]
    validation_ids = ordered[:policy["validation_house_count"]]
    confirmation_ids = ordered[
        policy["validation_house_count"]:
        policy["validation_house_count"] +
        policy["private_confirmation_candidate_pool_count"]]
    reserved_rows = [
        {"house_id": item, "roles": ["P0_route_and_raw_development"]}
        for item in sorted(p0)
    ] + [
        {"house_id": item, "roles": ["VM04_validation"]}
        for item in validation_ids
    ] + [
        {"house_id": item, "roles": ["VM04_confirmation"]}
        for item in confirmation_ids
    ]
    reserved = make_reserved_house_manifest(reserved_rows)
    partition = make_house_split_manifest(
        source_inventory=inventory, reserved_house_manifest=reserved,
        d215_contract=d215_contract, d216_contract=d216_contract)
    rows_by_house = {row["house_id"]: row for row in inventory["houses"]}
    sample_policy = d217["development_sample"]
    selected: dict[str, list[str]] = {}
    for split in SPLITS:
        candidates = ordered_sample_candidates(
            partition["rows"], split=split,
            sampling_salt=sample_policy["sampling_salt"])
        count = sample_policy["house_counts"][split]
        _require(len(candidates) >= count,
                 f"insufficient {split} houses for frozen prefix")
        selected[split] = candidates[:count]
    train_cal_rows = []
    for split in ("train", "calibration"):
        for rank, house_id in enumerate(selected[split]):
            source = rows_by_house[house_id]
            train_cal_rows.append({
                "split": split, "sample_rank": rank, "house_id": house_id,
                "source_file_sha256": source["source_file_sha256"],
                "source_record_sha256": source["source_record_sha256"],
                "source_locator": source["source_locator"],
                "public_house_ref": public_house_ref(
                    split=split, sample_rank=rank,
                    partition_manifest_receipt_sha256=partition[
                        "partition_manifest_receipt_sha256"]),
            })
    private_plan = _seal({
        "schema_version": PRIVATE_PLAN_SCHEMA,
        "source_inventory_sha256": inventory["inventory_sha256"],
        "partition_manifest_receipt_sha256":
            partition["partition_manifest_receipt_sha256"],
        "reserved_manifest_receipt_sha256":
            reserved["reserved_manifest_receipt_sha256"],
        "rows": train_cal_rows,
        "audit_opened": False,
        "confirmation_pool_opened_to_development": False,
    }, "private_plan_sha256")
    audit_seal = _seal({
        "schema_version": AUDIT_SEAL_SCHEMA,
        "partition_manifest_receipt_sha256":
            partition["partition_manifest_receipt_sha256"],
        "house_ids": selected["audit"],
        "opened_for_generation_or_debugging": False,
    }, "audit_seal_sha256")
    confirmation_private = _seal({
        "schema_version": "vsmt-vm04-d217-private-confirmation-pool-v1",
        "house_ids": confirmation_ids,
        "opened_to_development": False,
    }, "private_confirmation_pool_sha256")
    confirmation_commitments = [hashlib.sha256(
        f"{source_sha}|{house_id}".encode("utf-8")).hexdigest()
                                for house_id in confirmation_ids]
    public_plan = _seal({
        "schema_version": PUBLIC_PLAN_SCHEMA,
        "source_manifest_sha256": source_sha,
        "partition_manifest_receipt_sha256":
            partition["partition_manifest_receipt_sha256"],
        "validation_house_ids": validation_ids,
        "confirmation_pool": {
            "count": len(confirmation_ids),
            "commitment_list_sha256": _sha(confirmation_commitments),
            "private_manifest_sha256":
                confirmation_private["private_confirmation_pool_sha256"],
        },
        "sample_counts": {split: len(selected[split]) for split in SPLITS},
        "train_calibration_private_plan_sha256":
            private_plan["private_plan_sha256"],
        "audit": {
            "count": len(selected["audit"]),
            "private_seal_sha256": audit_seal["audit_seal_sha256"],
            "opened": False,
        },
        "observations_or_labels_read": False,
        "production_reader_route_or_raw_opened": False,
    }, "public_plan_sha256")
    return {
        "public_plan": public_plan,
        "private_plan": private_plan,
        "private_partition": partition,
        "private_reserved": reserved,
        "private_audit_seal": audit_seal,
        "private_confirmation_pool": confirmation_private,
    }


def select_reachable_positions(
    house_id: str, positions: Sequence[Mapping[str, Any]], *, split_salt: str,
    count: int = 8, minimum_separation_m: float = 1.0,
) -> list[dict[str, float]]:
    """Apply the D-215 hash order and 3-D greedy separation exactly once."""

    unique = sorted({
        (round(float(row["x"]), 6), round(float(row["y"]), 6),
         round(float(row["z"]), 6)) for row in positions
    })
    ordered = sorted(unique, key=lambda point: hashlib.sha256(
        (f"{split_salt}|{house_id}|x={point[0]:.6f},"
         f"y={point[1]:.6f},z={point[2]:.6f}").encode("utf-8")).hexdigest())
    selected: list[tuple[float, float, float]] = []
    minimum_squared = minimum_separation_m ** 2
    for point in ordered:
        if all(sum((left - right) ** 2 for left, right in zip(point, prior))
               >= minimum_squared - 1e-12 for prior in selected):
            selected.append(point)
            if len(selected) == count:
                break
    _require(len(selected) == count,
             "house has fewer than eight hash-ordered 1m-separated positions")
    return [{"x": x, "y": y, "z": z} for x, y, z in selected]


def structural_label_from_reachable(
    positions: Sequence[Mapping[str, Any]], anchor: Mapping[str, Any],
) -> str:
    """Apply the frozen training-only local basin/bottleneck graph rule."""

    spacing = 0.25
    points = [(float(row["x"]), float(row["y"]), float(row["z"]))
              for row in positions]
    _require(points, "reachable positions are empty")
    anchor_point = (float(anchor["x"]), float(anchor["y"]), float(anchor["z"]))
    nearest = min(range(len(points)), key=lambda index: sum(
        (points[index][axis] - anchor_point[axis]) ** 2 for axis in range(3)))
    _require(math.dist(points[nearest], anchor_point) <= 0.2 + 1e-12,
             "anchor does not snap to reachable graph within 0.2m")
    keys = {(round(x / spacing), round(y / spacing), round(z / spacing)): index
            for index, (x, y, z) in enumerate(points)}
    adjacency: list[list[int]] = [[] for _ in points]
    for key, index in keys.items():
        for delta in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1)):
            neighbor = (key[0] + delta[0], key[1], key[2] + delta[2])
            if neighbor in keys:
                adjacency[index].append(keys[neighbor])
    distances = {nearest: 0}
    queue = deque([nearest])
    while queue:
        current = queue.popleft()
        if distances[current] >= 8:
            continue
        for neighbor in adjacency[current]:
            if neighbor not in distances:
                distances[neighbor] = distances[current] + 1
                queue.append(neighbor)
    local = set(distances)
    remaining = {index for index in local
                 if math.dist(points[index], points[nearest]) > 0.35 + 1e-12}
    components: list[set[int]] = []
    while remaining:
        start = min(remaining)
        component = {start}
        frontier = [start]
        remaining.remove(start)
        while frontier:
            current = frontier.pop()
            for neighbor in adjacency[current]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    frontier.append(neighbor)
        components.append(component)
    qualifying = [component for component in components
                  if len(component) >= 8 and max(
                      math.dist(points[index], points[nearest])
                      for index in component) >= 1.0 - 1e-12]
    if len(qualifying) >= 2:
        return "bottleneck"
    basin_count = sum(math.dist(point, points[nearest]) <= 1.0 + 1e-12
                      for point in points)
    return "basin" if basin_count >= 37 else "unknown"
