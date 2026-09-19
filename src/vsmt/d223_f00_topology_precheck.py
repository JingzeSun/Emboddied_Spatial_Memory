"""D-223/F-00 generator-only topology construction precheck.

The pure core labels every reachable position with the already frozen D-215
rule, then asks whether two distinct basin components touch one connected
bottleneck component.  Reachable positions and witness paths are private
construction provenance and are never method inputs.
"""

from __future__ import annotations

from collections import deque
import hashlib
import math
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from cpmt.hashing import canonical_json, clone_json
from .d217_estimator_development import structural_label_from_reachable


CONTRACT_SCHEMA = "vsmt-vm04-d223-f00-topology-precheck-v1"
PRIVATE_RECEIPT_SCHEMA = "vsmt-vm04-d223-f00-private-house-topology-v1"
PRIVATE_FAILURE_SCHEMA = "vsmt-vm04-d223-f00-private-house-failure-v1"
PUBLIC_SUMMARY_SCHEMA = "vsmt-vm04-d223-f00-public-summary-v1"
RULE_SHA256 = "4fa32f8940cb22516d0c004f9c4b8d7a6cb5c1cd9a85dfb6f63ef6178dd34774"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
LABELS = ("basin", "bottleneck", "unknown")
DELTAS = ((-1, 0, 0), (0, 0, -1), (0, 0, 1), (1, 0, 0))


class D223F00Error(ValueError):
    """A stable F-00 contract, boundary, or topology failure."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise D223F00Error(message)


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _seal(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    result = clone_json(dict(value))
    result[field] = _sha(result)
    return result


def _hex(value: Any, pattern: re.Pattern[str], name: str) -> str:
    _require(type(value) is str and pattern.fullmatch(value) is not None,
             f"{name} must be a lowercase hexadecimal digest")
    return value


def validate_f00_contract(
    contract: Mapping[str, Any], *, d223_contract: Mapping[str, Any],
    d215_contract: Mapping[str, Any], d211_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the review candidate without opening real execution."""

    value = clone_json(dict(contract))
    _require(set(value) == {
        "schema_version", "decision_id", "stage_id", "status",
        "reviewed_baseline_commit", "expected_reviewed_implementation_commit",
        "bindings", "authorization", "activation_policy", "fixed_houses",
        "topology_rule", "simulator_query", "output_boundary",
        "resource_policy", "stop_policy",
    }, "F-00 contract has unexpected fields")
    _require(value["schema_version"] == CONTRACT_SCHEMA and
             value["decision_id"] == "D-223" and value["stage_id"] == "F-00",
             "F-00 contract identity changed")
    pending = "implementation_pending_review_all_execution_closed"
    active = "frozen_real_two_house_topology_precheck"
    _require(value["status"] in {pending, active}, "F-00 status changed")
    _hex(value["reviewed_baseline_commit"], HEX40, "reviewed baseline commit")

    bindings = value["bindings"]
    _require(bindings == {
        "d223_relative_path":
            "configs/vsmt/vm04_d223_p08_topological_qualification_v1.json",
        "d223_file_sha256":
            "737b4a7e108dca30931884460d294d36cc571c2d50fe5bc12daa0ebf9f288b18",
        "d215_relative_path":
            "configs/vsmt/vm04_d215_frontend_freeze_v1.json",
        "d215_file_sha256":
            "c3d6736f67b300eca03882c081e56e6bf4d65ad1913bcc411df8477fbd188db8",
        "d211_source_binding_relative_path":
            "configs/vsmt/vm04_d211_p0_seal_single_smoke_v2.json",
        "d211_source_binding_file_sha256":
            "9742dba79f2e72880221fe5cd5d63b00a219ebf77a8160461b9ef960e21e8711",
    }, "F-00 frozen contract bindings changed")

    _require(d223_contract.get("status") == "approved_design_all_execution_closed" and
             d223_contract.get("authorization") and
             not any(d223_contract["authorization"].values()),
             "D-223 approval or closed execution boundary changed")
    reference = d215_contract.get("semantic_structural_estimator", {}).get(
        "label_boundary", {}).get("structural_reference_rule")
    _require(reference == d223_contract.get("change", {}).get("inherited_constants"),
             "D-215 structural rule no longer equals D-223 inherited constants")
    _require(d211_contract.get("source_binding", {}).get("houses") ==
             value["fixed_houses"], "F-00 fixed houses changed from D-211")

    expected_auth = {
        "real_two_house_topology_precheck", "route_or_raw_generation",
        "production_reader", "private_evaluation", "estimator_retraining",
        "audit_rerun",
    }
    authorization = value["authorization"]
    _require(set(authorization) == expected_auth and
             all(type(flag) is bool for flag in authorization.values()),
             "F-00 authorization fields changed")
    policy = value["activation_policy"]
    _require(policy == {
        "active_status": active,
        "active_true_authorizations": ["real_two_house_topology_precheck"],
        "must_remain_false": [
            "route_or_raw_generation", "production_reader",
            "private_evaluation", "estimator_retraining", "audit_rerun"],
        "activation_commit_may_change_only": [
            "configs/vsmt/vm04_d223_f00_topology_precheck_v1.json"],
        "executable_checkout_must_be_clean": True,
        "executable_checkout_parent_must_equal_reviewed_implementation_commit": True,
    }, "F-00 activation policy changed")
    if value["status"] == pending:
        _require(value["expected_reviewed_implementation_commit"] is None and
                 not any(authorization.values()),
                 "F-00 review candidate must keep real execution closed")
    else:
        _hex(value["expected_reviewed_implementation_commit"], HEX40,
             "reviewed implementation commit")
        _require({name for name, enabled in authorization.items() if enabled} ==
                 {"real_two_house_topology_precheck"},
                 "F-00 active authorization scope changed")

    _require(value["topology_rule"] == {
        "implementation":
            "vsmt.d217_estimator_development.structural_label_from_reachable",
        "d215_structural_reference_rule_sha256": RULE_SHA256,
        "new_numeric_parameters": 0,
        "required_signature": ["basin", "bottleneck", "basin"],
        "basin_runs_must_belong_to_distinct_basin_components": True,
        "unknown_may_bridge_signature": False,
        "route_path_must_use_cardinal_reachable_edges": True,
    }, "F-00 topology semantics changed")
    _require(value["simulator_query"] == {
        "package": "ai2thor", "package_version": "5.0.0",
        "platform": "CloudRendering", "action": "GetReachablePositions",
        "grid_size_m": 0.25, "render_depth_image": False,
        "render_instance_segmentation": False,
        "rgb_depth_or_instance_arrays_read_or_saved": False,
    }, "F-00 simulator query boundary changed")
    _require(value["output_boundary"] == {
        "private_house_receipt_contains_positions_and_labels": True,
        "public_summary_contains_positions_or_source_house_ids": False,
        "reachable_graph_supplied_to_method_cache_candidate_selector_or_adapter": False,
        "raw_generated": False, "production_reader_started": False,
        "private_room_or_object_truth_used": False,
        "overwrite_existing_output_allowed": False,
    }, "F-00 output boundary changed")
    resources = value["resource_policy"]
    _require(resources == {
        "independent_house_units": 2, "requested_worker_count": 2,
        "actual_worker_count_rule":
            "two_or_stop_before_simulator_query_if_preflight_fails",
        "minimum_available_ram_bytes": 4294967296,
        "minimum_free_disk_bytes": 4294967296,
        "wall_clock_timeout_allowed": False,
        "deterministic_merge_order": [0, 1],
    }, "F-00 resource policy changed")
    _require(value["stop_policy"] == {
        "both_fixed_house_queries_must_succeed_before_continuation": True,
        "continue_to_f01_if_any_house_has_signature": True,
        "if_neither_house_has_signature": "pause_for_scene_design_decision",
        "automatic_house_replacement": False,
        "automatic_rule_or_threshold_change": False,
        "automatic_f01_start": False,
    }, "F-00 stop policy changed")
    return value


def assert_real_precheck_authorized(contract: Mapping[str, Any]) -> None:
    _require(contract.get("status") ==
             contract.get("activation_policy", {}).get("active_status") and
             contract.get("authorization", {}).get(
                 "real_two_house_topology_precheck") is True,
             "F-00 real two-house topology precheck is closed pending code review")


def _normalize_positions(
    positions: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, float]], dict[tuple[int, int, int], dict[str, float]]]:
    _require(type(positions) in {list, tuple} and positions,
             "reachable positions are empty")
    by_key: dict[tuple[int, int, int], dict[str, float]] = {}
    for index, raw in enumerate(positions):
        _require(type(raw) is dict and set(raw) >= {"x", "y", "z"},
                 f"reachable position {index} is malformed")
        row = {axis: float(raw[axis]) for axis in ("x", "y", "z")}
        _require(all(math.isfinite(value) for value in row.values()),
                 f"reachable position {index} is non-finite")
        key = tuple(round(row[axis] / 0.25) for axis in ("x", "y", "z"))
        _require(key not in by_key,
                 "reachable positions collide on the frozen 0.25m grid")
        by_key[key] = row
    ordered_keys = sorted(by_key)
    return [by_key[key] for key in ordered_keys], by_key


def _neighbors(key: tuple[int, int, int], keys: set[tuple[int, int, int]]):
    for delta in DELTAS:
        candidate = tuple(key[index] + delta[index] for index in range(3))
        if candidate in keys:
            yield candidate


def _components(
    keys: set[tuple[int, int, int]],
) -> list[tuple[tuple[int, int, int], ...]]:
    remaining = set(keys)
    result = []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        component = {start}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for neighbor in _neighbors(current, keys):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    queue.append(neighbor)
        result.append(tuple(sorted(component)))
    return result


def _shortest_path(
    start: tuple[int, int, int], end: tuple[int, int, int],
    allowed: set[tuple[int, int, int]],
) -> list[tuple[int, int, int]]:
    queue = deque([start])
    parent = {start: None}
    while queue:
        current = queue.popleft()
        if current == end:
            break
        for neighbor in _neighbors(current, allowed):
            if neighbor not in parent:
                parent[neighbor] = current
                queue.append(neighbor)
    _require(end in parent, "connected bottleneck component has no internal path")
    path = []
    current = end
    while current is not None:
        path.append(current)
        current = parent[current]
    return list(reversed(path))


def implementation_file_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def analyze_reachable_topology(
    positions: Sequence[Mapping[str, Any]], *, house_slot: int,
    source_house_id: str, source_record_sha256: str,
) -> dict[str, Any]:
    """Create a private generator-only receipt for one fixed house."""

    _require(type(house_slot) is int and house_slot in {0, 1},
             "house slot must be 0 or 1")
    _require(type(source_house_id) is str and source_house_id,
             "source house ID is missing")
    _hex(source_record_sha256, HEX64, "source record digest")
    ordered, by_key = _normalize_positions(positions)
    key_by_xyz = {
        (row["x"], row["y"], row["z"]): key for key, row in by_key.items()}
    labels_by_key = {}
    for row in ordered:
        key = key_by_xyz[(row["x"], row["y"], row["z"])]
        label = structural_label_from_reachable(ordered, row)
        _require(label in LABELS, "frozen D-215 rule returned an unknown label")
        labels_by_key[key] = label

    components_by_label = {
        label: _components({key for key, value in labels_by_key.items()
                            if value == label}) for label in LABELS}
    basin_component = {
        key: index for index, component in
        enumerate(components_by_label["basin"]) for key in component}
    candidates = []
    signature_count = 0
    all_keys = set(by_key)
    for bottleneck_index, component_tuple in enumerate(
            components_by_label["bottleneck"]):
        component = set(component_tuple)
        boundaries: dict[int, list[tuple[tuple[int, int, int],
                                         tuple[int, int, int]]]] = {}
        for bottleneck_key in component_tuple:
            for neighbor in _neighbors(bottleneck_key, all_keys):
                basin_index = basin_component.get(neighbor)
                if basin_index is not None:
                    boundaries.setdefault(basin_index, []).append(
                        (neighbor, bottleneck_key))
        basin_ids = sorted(boundaries)
        for left_offset, left_id in enumerate(basin_ids):
            for right_id in basin_ids[left_offset + 1:]:
                signature_count += 1
                paths = []
                for left_basin, left_bottleneck in sorted(boundaries[left_id]):
                    for right_basin, right_bottleneck in sorted(
                            boundaries[right_id]):
                        middle = _shortest_path(
                            left_bottleneck, right_bottleneck, component)
                        path = [left_basin, *middle, right_basin]
                        paths.append((len(path), tuple(path), path))
                best = min(paths)
                candidates.append((best[0], best[1], bottleneck_index,
                                   left_id, right_id, best[2]))
    selected = min(candidates) if candidates else None
    witness = [] if selected is None else [{
        "grid_key": list(key), "position": by_key[key],
        "structural_label": labels_by_key[key],
    } for key in selected[-1]]
    position_labels = [{
        "grid_key": list(key), "position": by_key[key],
        "structural_label": labels_by_key[key],
    } for key in sorted(by_key)]
    receipt = {
        "schema_version": PRIVATE_RECEIPT_SCHEMA,
        "house_slot": house_slot,
        "source_house_id": source_house_id,
        "source_record_sha256": source_record_sha256,
        "reachable_input_sha256": _sha(ordered),
        "reachable_position_count": len(ordered),
        "structural_label_counts": {
            label: sum(value == label for value in labels_by_key.values())
            for label in LABELS},
        "connected_component_counts": {
            label: len(components_by_label[label]) for label in LABELS},
        "qualifying_signature_count": signature_count,
        "qualifying_path_exists": selected is not None,
        "selected_witness_path": witness,
        "position_labels": position_labels,
        "d215_structural_reference_rule_sha256": RULE_SHA256,
        "implementation_file_sha256": implementation_file_sha256(),
        "new_numeric_parameters": 0,
        "generator_only_construction_information": True,
        "reachable_graph_supplied_to_method_cache_candidate_selector_or_adapter":
            False,
        "rgb_depth_or_instance_arrays_read_or_saved": False,
        "private_room_or_object_truth_used": False,
        "raw_generated": False,
        "production_reader_started": False,
    }
    return _seal(receipt, "private_house_receipt_sha256")


def make_private_failure(
    *, house_slot: int, source_house_id: str, source_record_sha256: str,
    error_type: str, message: str,
) -> dict[str, Any]:
    _require(type(house_slot) is int and house_slot in {0, 1},
             "failure house slot must be 0 or 1")
    _hex(source_record_sha256, HEX64, "source record digest")
    _require(all(type(value) is str and value for value in
                 (source_house_id, error_type, message)),
             "failure identity and message must be nonempty text")
    return _seal({
        "schema_version": PRIVATE_FAILURE_SCHEMA,
        "house_slot": house_slot,
        "source_house_id": source_house_id,
        "source_record_sha256": source_record_sha256,
        "error_type": error_type,
        "message": message,
        "replacement_allowed": False,
        "rule_or_threshold_change_allowed": False,
        "raw_generated": False,
        "production_reader_started": False,
    }, "private_failure_receipt_sha256")


def make_public_summary(
    private_receipts: Sequence[Mapping[str, Any]], *,
    requested_worker_count: int, actual_worker_count: int,
    resource_basis: Mapping[str, Any], execution_commit: str,
) -> dict[str, Any]:
    """Publish counts and existence only; omit graph coordinates and house IDs."""

    _hex(execution_commit, HEX40, "execution commit")
    _require(type(private_receipts) in {list, tuple} and
             [row.get("house_slot") for row in private_receipts] == [0, 1],
             "private receipts must be in deterministic house-slot order")
    rows = []
    for receipt in private_receipts:
        if receipt.get("schema_version") == PRIVATE_RECEIPT_SCHEMA:
            seal_field = "private_house_receipt_sha256"
            _require(receipt.get(seal_field) == _sha({
                key: value for key, value in receipt.items()
                if key != seal_field}),
                "private house receipt is malformed or unsealed")
            rows.append({
                "house_slot": receipt["house_slot"], "status": "success",
                "reachable_position_count": receipt["reachable_position_count"],
                "structural_label_counts": receipt["structural_label_counts"],
                "connected_component_counts":
                    receipt["connected_component_counts"],
                "qualifying_signature_count":
                    receipt["qualifying_signature_count"],
                "qualifying_path_exists": receipt["qualifying_path_exists"],
                "private_receipt_sha256": receipt[seal_field],
            })
        else:
            _require(receipt.get("schema_version") == PRIVATE_FAILURE_SCHEMA,
                     "private F-00 outcome has an unknown schema")
            seal_field = "private_failure_receipt_sha256"
            _require(receipt.get(seal_field) == _sha({
                key: value for key, value in receipt.items()
                if key != seal_field}),
                "private failure receipt is malformed or unsealed")
            rows.append({
                "house_slot": receipt["house_slot"], "status": "failure",
                "reachable_position_count": None,
                "structural_label_counts": None,
                "connected_component_counts": None,
                "qualifying_signature_count": None,
                "qualifying_path_exists": False,
                "private_receipt_sha256": receipt[seal_field],
            })
    summary = {
        "schema_version": PUBLIC_SUMMARY_SCHEMA,
        "stage_id": "F-00", "execution_commit": execution_commit,
        "requested_worker_count": requested_worker_count,
        "actual_worker_count": actual_worker_count,
        "resource_basis": clone_json(dict(resource_basis)),
        "deterministic_merge_order": [0, 1],
        "houses": rows,
        "continue_to_f01": (all(row["status"] == "success" for row in rows)
                            and any(row["qualifying_path_exists"]
                                    for row in rows)),
        "automatic_f01_started": False,
        "contains_positions_or_source_house_ids": False,
        "reachable_graph_supplied_to_method_cache_candidate_selector_or_adapter":
            False,
        "raw_generated": False,
        "production_reader_started": False,
    }
    return _seal(summary, "public_summary_sha256")
