#!/usr/bin/env python3
"""D-211 stage: check, seal twelve routes, then run only slot-0 raw smoke."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
OPS = Path(__file__).resolve().parent
for item in (SRC, OPS):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.d210_place_memory import validate_contract as validate_d210_contract  # noqa: E402
from vsmt.d211_p0_smoke import (  # noqa: E402
    ROUTE_BUNDLE_SCHEMA,
    assert_single_slot_smoke_authorized,
    build_sealed_route_batch,
    validate_d211_contract,
    validate_route_execution_binding,
)
from vm04_d211_raw_smoke import run_raw_smoke_core  # noqa: E402
import vm04_two_house_audit as source_audit  # noqa: E402
import vm04_two_house_worker as source_worker  # noqa: E402


BASE_CONTRACT_PATH = ROOT / "configs/vsmt/vm04_d210_dual_layer_p0_v1.json"
CONTRACT_PATH = ROOT / "configs/vsmt/vm04_d211_p0_seal_single_smoke_v2.json"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"),
                      object_pairs_hook=_reject_duplicate_pairs)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_new_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(value))
        handle.write("\n")


def git(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=ROOT, text=True).strip()


def load_contracts() -> tuple[dict[str, Any], dict[str, Any]]:
    base_raw = read_json(BASE_CONTRACT_PATH)
    base = validate_d210_contract(base_raw)
    overlay_raw = read_json(CONTRACT_PATH)
    overlay = validate_d211_contract(overlay_raw, base_contract=base)
    _require(sha256(BASE_CONTRACT_PATH) ==
             overlay["base_contract"]["file_sha256"],
             "D-210 base contract file bytes changed")
    source_report_path = ROOT / overlay["source_binding"][
        "source_report_relative_path"]
    _require(source_report_path.is_file() and sha256(source_report_path) ==
             overlay["source_binding"]["source_report_file_sha256"],
             "D-211 source report file changed")
    report = read_json(source_report_path)
    observed = [{
        "house_slot": index,
        "source_house_id": row["source_house_id"],
        "source_record_sha256": row["source_record_sha256"],
    } for index, row in enumerate(report["families"])]
    _require(observed == overlay["source_binding"]["houses"] and
             report["episodes_generated"] == 0 and
             report["interventions_performed"] == 0,
             "D-211 source report no longer supports the fixed houses")
    return base, overlay


def _execution_checkout(overlay: dict[str, Any], reviewed_code: str) -> str:
    assert_single_slot_smoke_authorized(
        overlay, base_contract=load_contracts()[0],
        reviewed_implementation_commit=reviewed_code)
    head = git("rev-parse", "HEAD")
    parent = git("rev-parse", "HEAD^")
    _require(parent == reviewed_code and head != reviewed_code,
             "execution requires one activation commit whose parent is the reviewed implementation")
    changed = git("diff", "--name-only", reviewed_code, head).splitlines()
    _require(changed == overlay["activation_policy"]
             ["activation_commit_may_change_only"],
             "activation commit changed files outside its one-file allowlist")
    _require(not git("status", "--porcelain"),
             "D-211 execution requires a clean checkout")
    return head


def check() -> dict[str, Any]:
    base, overlay = load_contracts()
    expected = overlay["expected_reviewed_implementation_commit"]
    executable = (overlay["status"] ==
                  "frozen_executable_seal_and_single_slot_smoke" and
                  expected is not None)
    return {
        "decision_id": "D-212",
        "reviewed_baseline_commit": overlay["reviewed_baseline_commit"],
        "expected_reviewed_implementation_commit": expected,
        "source_house_ids": [row["source_house_id"]
                             for row in overlay["source_binding"]["houses"]],
        "route_slot_count": base["batch"]["episode_count"],
        "raw_smoke_slot": overlay["single_slot_smoke"]["slot"],
        "raw_smoke_scenario": overlay["single_slot_smoke"]["scenario_id"],
        "private_simulator_pose_capture_authorized": overlay["authorization"]
        ["private_simulator_pose_capture_authorized"],
        "private_instance_and_entity_truth_capture_authorized":
            overlay["authorization"]
            ["private_instance_and_entity_truth_capture_authorized"],
        "twelve_slot_raw_generation_authorized": False,
        "adapter_materialization_authorized": False,
        "private_evaluation_authorized": False,
        "execution_authorized": executable,
    }


def seal_routes(
    *, route_bundle_path: Path, output_root: Path, reviewed_code: str,
) -> dict[str, Any]:
    base, overlay = load_contracts()
    _execution_checkout(overlay, reviewed_code)
    _require(overlay["authorization"]["source_house_binding_authorized"] is True
             and overlay["authorization"]["twelve_route_sealing_authorized"]
             is True, "D-211 route sealing is not authorized")
    # The caller-controlled input path remains untouched until all gates pass.
    bundle = read_json(route_bundle_path)
    _require(type(bundle) is dict and set(bundle) == {
        "schema_version", "rows"} and
        bundle["schema_version"] == ROUTE_BUNDLE_SCHEMA,
        "D-211 route bundle is invalid")
    public, private, bindings = build_sealed_route_batch(
        rows=bundle["rows"], contract=overlay, base_contract=base)
    _require(not output_root.exists(),
             "D-211 sealed route root exists; never overwrite it")
    for row in bundle["rows"]:
        route = row["route_plan"]
        slot = route["slot"]
        write_new_json(output_root / "provenance/routes" /
                       f"slot_{slot:02d}.json", route)
        write_new_json(output_root / "provenance/route-evidence" /
                       f"slot_{slot:02d}.json", row["public_route_evidence"])
        write_new_json(output_root / "private/reachable-scans" /
                       f"slot_{slot:02d}.json", row["reachable_scan"])
        write_new_json(output_root / "private/scenario-receipts" /
                       f"slot_{slot:02d}.json", row["scenario_receipt"])
    write_new_json(output_root / "public/manifest.json", public)
    write_new_json(output_root / "private/manifest.json", private)
    write_new_json(output_root / "private/route-bindings.json", bindings)
    evidence_index = {
        "schema_version": "vsmt-vm04-d212-sealed-route-evidence-index-v1",
        "rows": [{
            "slot": slot,
            "public_route_evidence_sha256": sha256(
                output_root / "provenance/route-evidence" /
                f"slot_{slot:02d}.json"),
            "reachable_scan_sha256": sha256(
                output_root / "private/reachable-scans" /
                f"slot_{slot:02d}.json"),
            "scenario_receipt_sha256": sha256(
                output_root / "private/scenario-receipts" /
                f"slot_{slot:02d}.json"),
        } for slot in range(12)],
    }
    write_new_json(output_root / "private/route-evidence-index.json",
                   evidence_index)
    receipt = {
        "schema_version": "vsmt-vm04-d212-route-seal-receipt-v1",
        "reviewed_implementation_commit": reviewed_code,
        "activation_commit": git("rev-parse", "HEAD"),
        "slot_count": 12,
        "public_manifest_sha256": sha256(
            output_root / "public/manifest.json"),
        "private_manifest_sha256": sha256(
            output_root / "private/manifest.json"),
        "route_bindings_sha256": sha256(
            output_root / "private/route-bindings.json"),
        "route_evidence_index_sha256": sha256(
            output_root / "private/route-evidence-index.json"),
        "simulator_started": False, "episodes_generated": 0,
        "route_replacement_after_smoke_outcome_allowed": False,
    }
    write_new_json(output_root / "route-seal.receipt.json", receipt)
    return receipt


def _load_sealed_smoke_inputs(
    sealed_root: Path, *, base: dict[str, Any], overlay: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any],
           dict[str, Any], str, str]:
    receipt = read_json(sealed_root / "route-seal.receipt.json")
    public = read_json(sealed_root / "public/manifest.json")
    private = read_json(sealed_root / "private/manifest.json")
    bindings = read_json(sealed_root / "private/route-bindings.json")
    evidence_index_path = sealed_root / "private/route-evidence-index.json"
    evidence_index = read_json(evidence_index_path)
    _require(receipt["slot_count"] == 12 and
             receipt["public_manifest_sha256"] ==
             sha256(sealed_root / "public/manifest.json") and
             receipt["private_manifest_sha256"] ==
             sha256(sealed_root / "private/manifest.json") and
             receipt["route_bindings_sha256"] ==
             sha256(sealed_root / "private/route-bindings.json") and
             receipt["route_evidence_index_sha256"] ==
             sha256(evidence_index_path) and
             receipt["episodes_generated"] == 0,
             "D-211 route-seal receipt or files changed")
    _require(type(evidence_index) is dict and
             evidence_index.get("schema_version") ==
             "vsmt-vm04-d212-sealed-route-evidence-index-v1" and
             [row.get("slot") for row in evidence_index.get("rows", [])] ==
             list(range(12)), "D-212 sealed evidence index changed")
    slot = overlay["single_slot_smoke"]["slot"]
    route = read_json(sealed_root / "provenance/routes" /
                      f"slot_{slot:02d}.json")
    public_evidence = read_json(sealed_root / "provenance/route-evidence" /
                                f"slot_{slot:02d}.json")
    reachable_scan = read_json(sealed_root / "private/reachable-scans" /
                               f"slot_{slot:02d}.json")
    scenario_receipt = read_json(
        sealed_root / "private/scenario-receipts" / f"slot_{slot:02d}.json")
    evidence_row = evidence_index["rows"][slot]
    _require(evidence_row == {
        "slot": slot,
        "public_route_evidence_sha256": sha256(
            sealed_root / "provenance/route-evidence" /
            f"slot_{slot:02d}.json"),
        "reachable_scan_sha256": sha256(
            sealed_root / "private/reachable-scans" /
            f"slot_{slot:02d}.json"),
        "scenario_receipt_sha256": sha256(
            sealed_root / "private/scenario-receipts" /
            f"slot_{slot:02d}.json"),
    }, "D-212 smoke route evidence files changed after seal")
    binding = next(row for row in bindings["bindings"] if row["slot"] == slot)
    binding = validate_route_execution_binding(
        binding, route_plan=route, reachable_scan=reachable_scan,
        public_route_evidence=public_evidence,
        scenario_receipt=scenario_receipt, contract=overlay,
        base_contract=base)
    public_row = next(row for row in public["episodes"] if row["slot"] == slot)
    private_row = next(row for row in private["episodes"] if row["slot"] == slot)
    _require(public_row["episode_id"] == private_row["episode_id"] and
             private_row["source_house_id"] ==
             overlay["source_binding"]["houses"][0]["source_house_id"],
             "D-211 smoke episode/source binding changed")
    return (route, binding, reachable_scan, public_evidence, scenario_receipt,
            public_row["episode_id"], receipt["public_manifest_sha256"])


def _load_source_house(
    *, source_stage: Path, source_root: Path, overlay: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    inventory = read_json(source_stage / "private/inventory.json")
    expected = overlay["source_binding"]["houses"][0]
    row = next(item for item in inventory["houses"]
               if item["house_id"] == expected["source_house_id"])
    _require(row["source_record_sha256"] == expected["source_record_sha256"],
             "D-211 source inventory record changed")
    locator = row["source_locator"]
    source_file = (source_root.resolve() / locator["relative_path"]).resolve()
    _require(source_root.resolve() in source_file.parents and
             source_file.is_file() and
             source_audit.sha256(source_file) == row["source_file_sha256"],
             "D-211 source file escaped, is missing, or changed")
    house = source_worker.load_source_record(source_root, locator)
    _require(source_worker.canonical_sha256(house) ==
             expected["source_record_sha256"],
             "D-211 loaded source record digest changed")
    return house, expected["source_record_sha256"]


def _make_d212_controller(house: dict[str, Any], overlay: dict[str, Any]):
    """Create the smoke controller with every movement/sensor value explicit."""

    from ai2thor.controller import Controller
    from ai2thor.platform import CloudRendering

    runtime = overlay["simulator_runtime"]
    _require(importlib.metadata.version("ai2thor") ==
             runtime["ai2thor_package_version"],
             "installed AI2-THOR package version differs from D-212")
    upgraded = source_worker.upgrade_house_schema_v1(
        house, source_worker.load_pinned_asset_id_database())
    controller = Controller(
        platform=CloudRendering, scene=upgraded,
        width=runtime["width"], height=runtime["height"],
        fieldOfView=runtime["field_of_view_degrees"],
        gridSize=runtime["grid_size_m"],
        snapToGrid=runtime["snap_to_grid"],
        rotateStepDegrees=runtime["rotate_step_degrees"],
        renderDepthImage=runtime["render_depth_image"],
        renderInstanceSegmentation=runtime["render_instance_segmentation"],
    )
    initial = controller.last_event
    if initial.metadata.get("lastActionSuccess") is not True:
        error = initial.metadata.get("errorMessage") or "unknown scene creation error"
        controller.stop()
        raise RuntimeError("initial ProcTHOR scene creation failed: %s" % error)
    if not initial.metadata.get("objects"):
        controller.stop()
        raise RuntimeError("initial ProcTHOR scene has no objects")
    try:
        source_worker.bootstrap_house_agent(controller, upgraded)
    except Exception:
        controller.stop()
        raise
    return controller


def run_smoke(
    *, sealed_root: Path, source_stage: Path, source_root: Path,
    output_root: Path, reviewed_code: str,
) -> dict[str, Any]:
    base, overlay = load_contracts()
    _execution_checkout(overlay, reviewed_code)
    _require(not output_root.exists(),
             "D-211 smoke output exists; never overwrite or rerun in place")
    free = shutil.disk_usage(output_root.parent.resolve()).free
    _require(free >= overlay["resource_policy"]["minimum_data_disk_free_bytes"],
             "D-211 smoke has insufficient data-disk free space")
    (route, binding, reachable_scan, public_evidence, scenario_receipt,
     episode_id, public_manifest_sha) = (
        _load_sealed_smoke_inputs(
            sealed_root, base=base, overlay=overlay))
    house, source_record_sha = _load_source_house(
        source_stage=source_stage, source_root=source_root, overlay=overlay)
    controller = None
    stop_error = None
    worker_error = None
    result = None
    try:
        controller = _make_d212_controller(house, overlay)
        result = run_raw_smoke_core(
            controller, route_plan=route, execution_binding=binding,
            d211_contract=overlay, reachable_scan=reachable_scan,
            public_route_evidence=public_evidence,
            scenario_receipt=scenario_receipt, base_contract=base,
            output_root=output_root, source_record_sha256=source_record_sha,
            public_manifest_sha256=public_manifest_sha,
            episode_id=episode_id,
        )
    except BaseException as error:
        worker_error = {
            "type": type(error).__name__,
            "message_sha256": hashlib.sha256(
                str(error).encode("utf-8")).hexdigest(),
        }
    finally:
        if controller is not None:
            try:
                controller.stop()
            except BaseException as error:  # preserve raw prefix and report stop
                stop_error = {
                    "type": type(error).__name__,
                    "message_sha256": hashlib.sha256(
                        str(error).encode("utf-8")).hexdigest(),
                }
    output_root.mkdir(parents=True, exist_ok=True)
    raw_receipt_path = output_root / "smoke.receipt.json"
    raw_status = (result["status"] if result is not None else
                  (read_json(raw_receipt_path)["status"]
                   if raw_receipt_path.is_file() else "not_started"))
    stage_receipt = {
        "schema_version": "vsmt-vm04-d212-smoke-stage-receipt-v1",
        "reviewed_implementation_commit": reviewed_code,
        "activation_commit": git("rev-parse", "HEAD"),
        "episode_id": episode_id,
        "slot": 0,
        "raw_smoke_receipt_sha256": (
            sha256(raw_receipt_path) if raw_receipt_path.is_file() else None),
        "raw_status": raw_status,
        "worker_error": worker_error,
        "controller_stop_succeeded": stop_error is None,
        "controller_stop_error": stop_error,
        "worker_count": 1,
        "twelve_slot_generation_started": False,
        "adapter_materialized": False,
        "private_evaluation_performed": False,
    }
    write_new_json(output_root / "stage.receipt.json", stage_receipt)
    if worker_error is not None:
        raise RuntimeError("D-211 raw smoke worker failed; retained stage receipt")
    if stop_error is not None:
        raise RuntimeError("D-211 controller stop failed; retained stage receipt")
    return stage_receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check")
    seal = subparsers.add_parser("seal-routes")
    seal.add_argument("--route-bundle", type=Path, required=True)
    seal.add_argument("--output-root", type=Path, required=True)
    seal.add_argument("--reviewed-implementation", required=True)
    smoke = subparsers.add_parser("run-smoke")
    smoke.add_argument("--sealed-root", type=Path, required=True)
    smoke.add_argument("--source-stage", type=Path, required=True)
    smoke.add_argument("--source-root", type=Path, required=True)
    smoke.add_argument("--output-root", type=Path, required=True)
    smoke.add_argument("--reviewed-implementation", required=True)
    arguments = parser.parse_args()
    if arguments.command == "check":
        result = check()
    elif arguments.command == "seal-routes":
        result = seal_routes(
            route_bundle_path=arguments.route_bundle,
            output_root=arguments.output_root,
            reviewed_code=arguments.reviewed_implementation)
    else:
        result = run_smoke(
            sealed_root=arguments.sealed_root,
            source_stage=arguments.source_stage,
            source_root=arguments.source_root,
            output_root=arguments.output_root,
            reviewed_code=arguments.reviewed_implementation)
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
