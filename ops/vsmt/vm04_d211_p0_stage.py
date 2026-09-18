#!/usr/bin/env python3
"""D-211 stage: check, seal twelve routes, then run only slot-0 raw smoke."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import importlib.metadata
import json
import os
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
from vm04_d212_route_survey import (  # noqa: E402
    make_bundle,
    make_stage_receipt,
    survey_house,
)
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
        "route_public_survey_authorized": overlay["authorization"]
        ["twelve_route_public_survey_authorized"],
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


def _available_memory_bytes() -> int | None:
    if hasattr(os, "sysconf"):
        try:
            return int(os.sysconf("SC_AVPHYS_PAGES") *
                       os.sysconf("SC_PAGE_SIZE"))
        except (OSError, ValueError, TypeError):
            pass
    return None


def _gpu_free_bytes() -> int | None:
    try:
        output = subprocess.check_output([
            "nvidia-smi", "--query-gpu=memory.free",
            "--format=csv,noheader,nounits",
        ], text=True, timeout=10)
        values = [int(row.strip()) * 1024 * 1024
                  for row in output.splitlines() if row.strip()]
        return max(values) if values else None
    except (FileNotFoundError, subprocess.SubprocessError, ValueError):
        return None


def _survey_worker_count(output_parent: Path) -> tuple[int, dict[str, Any]]:
    cpu_count = os.cpu_count() or 1
    memory_free = _available_memory_bytes()
    gpu_free = _gpu_free_bytes()
    disk_free = shutil.disk_usage(output_parent.resolve()).free
    reasons = []
    safe = 2
    if cpu_count < 4:
        safe, reasons = 1, ["fewer_than_four_logical_cpus"]
    if memory_free is not None and memory_free < 12 * 1024 ** 3:
        safe = 1
        reasons.append("less_than_12_gib_available_ram")
    if gpu_free is None or gpu_free < 6 * 1024 ** 3:
        safe = 1
        reasons.append("less_than_6_gib_verified_free_gpu_memory")
    return safe, {
        "logical_cpu_count": cpu_count,
        "available_memory_bytes": memory_free,
        "free_gpu_memory_bytes": gpu_free,
        "free_output_disk_bytes": disk_free,
        "selection_rule":
            "two_house_workers_only_with_cpu>=4_ram>=12GiB_gpu_free>=6GiB",
        "single_worker_reasons": reasons,
    }


def _survey_house_job(source_stage: str, source_root: str,
                      house_slot: int) -> dict[str, Any]:
    controller = None
    try:
        base, overlay = load_contracts()
        house, _ = _load_source_house(
            source_stage=Path(source_stage), source_root=Path(source_root),
            overlay=overlay, house_slot=house_slot)
        controller = _make_d212_controller(house, overlay)
        slots = [row["slot"] for row in base["slot_plan"]
                 if row["house_slot"] == house_slot]
        source_id = overlay["source_binding"]["houses"][house_slot][
            "source_house_id"]
        return survey_house(
            controller, house_slot=house_slot, source_house_id=source_id,
            slots=slots, contract=overlay, base_contract=base)
    except BaseException as error:
        return {
            "status": "route_survey_failure", "rows": [],
            "slot_receipts": [], "worker_error": {
                "type": type(error).__name__,
                "message_sha256": hashlib.sha256(
                    str(error).encode("utf-8")).hexdigest(),
            },
        }
    finally:
        if controller is not None:
            try:
                controller.stop()
            except BaseException:
                pass


def survey_routes(*, source_stage: Path, source_root: Path,
                  output_root: Path, reviewed_code: str) -> dict[str, Any]:
    base, overlay = load_contracts()
    activation = _execution_checkout(overlay, reviewed_code)
    _require(overlay["authorization"]
             ["twelve_route_public_survey_authorized"] is True,
             "D-212 public route survey is not authorized")
    _require(not output_root.exists(),
             "D-212 route-survey output exists; never overwrite it")
    _require(output_root.parent.exists(),
             "D-212 route-survey output parent does not exist")
    actual_workers, resource_basis = _survey_worker_count(output_root.parent)
    _require(resource_basis["free_output_disk_bytes"] >=
             overlay["resource_policy"]["minimum_data_disk_free_bytes"],
             "D-212 route survey has insufficient output disk space")
    arguments = [(str(source_stage), str(source_root), house_slot)
                 for house_slot in (0, 1)]
    if actual_workers == 2:
        with ProcessPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(_survey_house_job, *item)
                       for item in arguments]
            house_results = []
            for future in futures:
                try:
                    house_results.append(future.result())
                except BaseException as error:
                    house_results.append({
                        "status": "route_survey_failure", "rows": [],
                        "slot_receipts": [], "worker_error": {
                            "type": type(error).__name__,
                            "message_sha256": hashlib.sha256(
                                str(error).encode("utf-8")).hexdigest(),
                        },
                    })
    else:
        house_results = [_survey_house_job(*item) for item in arguments]
    receipt = make_stage_receipt(
        house_results=house_results, requested_workers=2,
        actual_workers=actual_workers, resource_basis=resource_basis)
    receipt["reviewed_implementation_commit"] = reviewed_code
    receipt["activation_commit"] = activation
    output_root.mkdir(parents=True, exist_ok=False)
    if receipt["status"] == "route_survey_complete":
        bundle = make_bundle(house_results)
        write_new_json(output_root / "route-bundle.json", bundle)
        receipt["route_bundle_sha256"] = sha256(
            output_root / "route-bundle.json")
    else:
        receipt["route_bundle_sha256"] = None
    write_new_json(output_root / "survey.receipt.json", receipt)
    _require(receipt["status"] == "route_survey_complete",
             "D-212 route survey failed; retained immutable failure receipt")
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
    house_slot: int = 0,
) -> tuple[dict[str, Any], str]:
    inventory = read_json(source_stage / "private/inventory.json")
    _require(house_slot in {0, 1}, "D-212 source house slot is invalid")
    expected = overlay["source_binding"]["houses"][house_slot]
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
    survey = subparsers.add_parser("survey-routes")
    survey.add_argument("--source-stage", type=Path, required=True)
    survey.add_argument("--source-root", type=Path, required=True)
    survey.add_argument("--output-root", type=Path, required=True)
    survey.add_argument("--reviewed-implementation", required=True)
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
    elif arguments.command == "survey-routes":
        result = survey_routes(
            source_stage=arguments.source_stage,
            source_root=arguments.source_root,
            output_root=arguments.output_root,
            reviewed_code=arguments.reviewed_implementation)
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
