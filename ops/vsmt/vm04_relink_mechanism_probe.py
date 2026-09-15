#!/usr/bin/env python3
"""Reproduce one frozen VM04 RELINK slot with independent simulator controls."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

try:
    import resource
except ImportError:  # Local pure tests run on Windows.
    resource = None

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import vm04_two_house_audit as audit  # noqa: E402
import vm04_two_house_worker as generator  # noqa: E402
import vm04_target_action_probe as old_probe  # noqa: E402
import vm04_target_action_probe_worker as old_worker  # noqa: E402
from vsmt.vm04_target_contract import validate_target_boundary_proposal  # noqa: E402
from vsmt.vm04_target_eligibility import authored_asset_ids  # noqa: E402
from vsmt.vm04_target_selection_v3 import select_private_targets_at_fixed_pose  # noqa: E402

CONFIG_PATH = ROOT / "configs/vsmt/vm04_relink_mechanism_probe_v1.json"
TARGET_PATH = ROOT / "configs/vsmt/vm04_target_boundary_proposal_v3.json"
V1_REPORT_PATH = ROOT / "results/vsmt_vm04_target_action_probe_v1.json"
EXPORT_PATH = ROOT / "results/vsmt_vm04_relink_mechanism_probe_v1.json"
BOUND_FILES = (
    "configs/vsmt/vm04_relink_mechanism_probe_v1.json",
    "ops/vsmt/vm04_relink_mechanism_probe.py",
    "ops/vsmt/vm04_two_house_worker.py",
    "ops/vsmt/vm04_target_action_probe_worker.py",
    "src/vsmt/vm04_target_selection_v3.py",
    "configs/vsmt/vm04_target_boundary_proposal_v3.json",
    "tests/test_vm04_relink_mechanism_probe.py",
)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def load_config():
    config = audit.read_json(CONFIG_PATH)
    target = validate_target_boundary_proposal(audit.read_json(TARGET_PATH))
    require(config["version"] == "vsmt-vm04-relink-mechanism-probe-v1" and
            config["status"] == "frozen_diagnostic_reproduction_only" and
            config["authorized_reproduction"] is True and
            config["generation_authorized"] is False and
            config["training_authorized"] is False and
            config["fixed_house_id"] == "train:008243" and
            config["fixed_family_id"] == "audit-family:01" and
            config["fixed_slot"] == 12 and
            config["fixed_replicate"] == 1 and
            config["fixed_program"] == "RELINK" and
            config["modes_in_deterministic_merge_order"] == [
                "registered_forced", "same_request_nonforced",
                "registered_forced_physics_paused"] and
            config["replay_registered_camera_frames_before_intervention"] == 24 and
            config["replay_registered_camera_frames_after_intervention"] == 8 and
            config["do_not_reselect_house_pose_target_or_program"] is True and
            config["maximum_relink_position_error_m"] == 0.005 and
            config["resource_sample_interval_seconds"] == 0.25 and
            config["minimum_cgroup_headroom_to_observed_one_worker_demand_ratio"] == 4.0 and
            config["minimum_gpu_headroom_to_observed_one_worker_demand_ratio"] == 2.0 and
            config["minimum_static_cgroup_headroom_bytes"] == 8589934592 and
            config["minimum_static_gpu_free_bytes"] == 8589934592 and
            config["minimum_static_data_disk_free_bytes"] == 8589934592 and
            config["maximum_worker_address_space_bytes"] == 42949672960 and
            config["no_wall_clock_failure_limit"] is True and
            config["source_target_contract_sha256"] == audit.sha256(TARGET_PATH) and
            target["status"] == "frozen_target_probe_only" and
            target["generation_authorized"] is False and
            config["source_public_report_sha256"] == audit.sha256(V1_REPORT_PATH),
            "RELINK diagnostic scope/gate/source changed")
    for key in ("source_action_probe_receipt_sha256",
                "source_scan_receipt_sha256", "source_public_report_sha256",
                "source_target_contract_sha256"):
        require(re.fullmatch(r"[0-9a-f]{64}", config[key]) is not None,
                "invalid diagnostic digest: " + key)
    return config, target


def binding_sha256(reviewed_code):
    require(audit.git("rev-parse", "HEAD") == reviewed_code and
            not audit.git("status", "--porcelain") and
            Path(audit.git("rev-parse", "--show-toplevel")).resolve() == ROOT,
            "diagnostic requires exact clean reviewed checkout")
    return {relative: audit.sha256(ROOT / relative) for relative in BOUND_FILES}


def inputs(config, source_stage, scan_stage, source_root):
    source_receipt, _ = audit._marker(source_stage, "probe")
    require(audit.sha256(source_stage / "probe.receipt.json") ==
            config["source_action_probe_receipt_sha256"] and
            source_receipt["episodes_generated"] == 0 and
            source_receipt["training_steps"] == 0 and
            audit.sha256(scan_stage / "scan.receipt.json") ==
            config["source_scan_receipt_sha256"],
            "original probe/scan receipt changed")
    scan_config, _ = old_probe.load_config()
    old_probe.scan_inputs(scan_config, scan_stage, source_root)
    family_root = source_stage / "execution" / config["fixed_family_id"]
    source_worker_path = family_root / "private/worker.receipt.json"
    source_worker = audit.read_json(source_worker_path)
    registered_sha = next(row["sha256"] for row in
                          source_receipt["family_worker_receipts"]
                          if row["family_id"] == config["fixed_family_id"])
    require(audit.sha256(source_worker_path) == registered_sha and
            source_worker["slots"][config["fixed_slot"]]["slot"] ==
            config["fixed_slot"], "original private worker/slot changed")
    slot_path = family_root / "private" / ("slot_%02d.json" % config["fixed_slot"])
    require(audit.sha256(slot_path) == source_worker["slots"][
        config["fixed_slot"]]["private_slot_sha256"],
        "original private slot diagnosis changed")
    slot = audit.read_json(slot_path)
    require(slot["program"] == config["fixed_program"] and
            slot["replicate"] == config["fixed_replicate"] and
            slot["slot"] == config["fixed_slot"] and
            slot["status"] == "terminal_poststate_mismatch" and
            len(slot["v3_target_instance_ids"]) == 1,
            "diagnostic must reproduce original failed RELINK target")
    return slot_path


def aabb_limits(row):
    box = row.get("axisAlignedBoundingBox", {})
    points = box.get("cornerPoints") if type(box) is dict else None
    if not (type(points) is list and len(points) >= 2):
        return None
    try:
        return {axis: (min(float(point[axis]) for point in points),
                       max(float(point[axis]) for point in points))
                for axis in ("x", "y", "z")}
    except (KeyError, TypeError, ValueError):
        return None


def translated_aabb_overlap(event, target_id, requested_position):
    """Coarse private AABB intersections; never claim collider contact."""
    objects = old_worker.metadata_objects(event)
    target = objects.get(target_id)
    if target is None:
        return {"available": False, "intersections": []}
    limits = aabb_limits(target)
    if limits is None:
        return {"available": False, "intersections": []}
    offset = {axis: float(requested_position[axis]) -
              float(target["position"][axis]) for axis in ("x", "y", "z")}
    intersections = []
    for other_id, other in objects.items():
        if other_id == target_id:
            continue
        other_limits = aabb_limits(other)
        if other_limits is None:
            continue
        if all(minimum + offset[axis] < other_limits[axis][1] and
               maximum + offset[axis] > other_limits[axis][0]
               for axis, (minimum, maximum) in limits.items()):
            intersections.append({"other_object_id": other_id,
                                  "other_object_type": other.get("objectType")})
    return {"available": True, "intersection_count": len(intersections),
            "intersections": intersections,
            "interpretation": "axis_aligned_bounds_only_not_collider_contact"}


def target_snapshot(event, target_id):
    metadata = event.metadata
    row = old_worker.metadata_objects(event).get(target_id, {})
    return {"position": row.get("position"), "rotation": row.get("rotation"),
            "pickupable": row.get("pickupable"),
            "moveable": row.get("moveable"),
            "is_moving": row.get("isMoving"),
            "is_picked_up": row.get("isPickedUp"),
            "visible_mask_pixels": old_worker.visible_pixels(event, target_id),
            "is_scene_at_rest": metadata.get("isSceneAtRest"),
            "last_action_success": metadata.get("lastActionSuccess"),
            "error_code": metadata.get("errorCode"),
            "error_message": metadata.get("errorMessage")}


def adapted_request(original, mode):
    require(original["action"] == "TeleportObject" and
            original["forceAction"] is True and
            mode in ("registered_forced", "same_request_nonforced",
                     "registered_forced_physics_paused"),
            "diagnostic request is not registered RELINK")
    request = dict(original)
    request["forceAction"] = mode != "same_request_nonforced"
    return request


def execute_trial(house, pose, original_slot, scan_top2, contract, mode,
                  *, physics_step_count=0):
    """Fresh controller; replay frozen camera path, change only one control."""
    target_id = original_slot["v3_target_instance_ids"][0]
    result = {"schema_version": "vsmt-vm04-private-relink-mechanism-trial-v1",
              "mode": mode, "fixed_slot": original_slot["slot"],
              "target_object_id": target_id, "camera_actions": [],
              "control_actions": [], "registered_request": None,
              "attempted_request": None, "pre_intervention": None,
              "immediate_post_intervention": None, "terminal_poststate": None,
              "semantic_positive_label_issued": False,
              "memory_history_checked": False, "status": "not_started"}
    controller = None
    try:
        controller = generator.make_controller(house)
        initial = generator.teleport_to_initial_viewpoint(controller, pose)
        require(initial.metadata.get("lastActionSuccess") is True,
                "frozen initial pose rejected")
        initial_objects = old_worker.metadata_objects(initial)
        live_top2 = generator.rank_visible_instance_ids(
            initial.instance_masks, set(initial_objects))[:2]
        require(live_top2 == scan_top2 ==
                original_slot["live_scan_top2_instance_ids"],
                "original live scene/scan target changed")
        assets = authored_asset_ids(house)
        selected = select_private_targets_at_fixed_pose(
            "RELINK", initial.instance_masks, initial_objects, assets,
            contract=contract)
        require(selected == [target_id],
                "frozen original asset target changed")
        original = generator.intervention_actions(
            "RELINK", 24, selected, initial_objects)[0]
        registered = next(row["arguments"] for row in original_slot["actions"]
                          if row["phase"] == "external_intervention" and
                          row["frame_index"] == 24)
        require(original == registered,
                "registered RELINK request/source code changed")
        result["registered_request"] = original
        for frame in range(24):
            action, _ = generator.registered_agent_action(
                original_slot["replicate"], frame)
            event = controller.step(**action)
            result["camera_actions"].append({"frame": frame,
                "diagnostic": generator.intervention_event_diagnostic(event),
                "target": target_snapshot(event, target_id)})
            require(event.metadata.get("lastActionSuccess") is True,
                    "registered pre-intervention camera action rejected")
        result["pre_intervention"] = target_snapshot(event, target_id)
        result["requested_pose_aabb"] = translated_aabb_overlap(
            event, target_id, original["position"])
        if mode == "registered_forced_physics_paused":
            paused = controller.step(action="PausePhysicsAutoSim")
            result["control_actions"].append({"action": "PausePhysicsAutoSim",
                "diagnostic": generator.intervention_event_diagnostic(paused),
                "target": target_snapshot(paused, target_id)})
            if paused.metadata.get("lastActionSuccess") is not True:
                result["status"] = "physics_pause_control_rejected"
                return result
        request = adapted_request(original, mode)
        result["attempted_request"] = request
        event = controller.step(**request)
        result["immediate_post_intervention"] = target_snapshot(event, target_id)
        result["intervention_diagnostic"] = (
            generator.intervention_event_diagnostic(event))
        result["actual_pose_aabb"] = translated_aabb_overlap(
            event, target_id, result["immediate_post_intervention"]["position"])
        if event.metadata.get("lastActionSuccess") is False:
            result["status"] = "simulator_action_rejected"
            return result
        for frame in range(24, 32):
            action, _ = generator.registered_agent_action(
                original_slot["replicate"], frame)
            event = controller.step(**action)
            result["camera_actions"].append({"frame": frame,
                "diagnostic": generator.intervention_event_diagnostic(event),
                "target": target_snapshot(event, target_id)})
            require(event.metadata.get("lastActionSuccess") is True,
                    "registered post-intervention camera action rejected")
        result["terminal_poststate"] = target_snapshot(event, target_id)
        done = controller.step(action="Done")
        result["control_actions"].append({"action": "Done",
            "diagnostic": generator.intervention_event_diagnostic(done),
            "target": target_snapshot(done, target_id)})
        if physics_step_count:
            require(mode == "registered_forced_physics_paused" and
                    type(physics_step_count) is int and physics_step_count > 0,
                    "manual physics requires the paused original request")
            result["manual_physics_steps"] = []
            for index in range(physics_step_count):
                stepped = controller.step(action="AdvancePhysicsStep",
                                          timeStep=0.01)
                result["manual_physics_steps"].append({
                    "index": index, "time_step_s": 0.01,
                    "diagnostic": generator.intervention_event_diagnostic(stepped),
                    "target": target_snapshot(stepped, target_id)})
                if stepped.metadata.get("lastActionSuccess") is not True:
                    result["status"] = "manual_physics_step_rejected"
                    return result
        result["status"] = "recorded_full_registered_path"
        return result
    except Exception as error:
        result.update(status="reproduction_failed_before_conclusion",
                      error_type=type(error).__name__, error=str(error))
        return result
    finally:
        if controller is not None:
            try:
                controller.stop()
            except Exception as error:
                result.update(status="controller_stop_failed",
                              stop_error_type=type(error).__name__,
                              stop_error=str(error))


def run_worker(args):
    config, contract = load_config()
    require(resource is not None, "simulator worker requires Linux limits")
    resource.setrlimit(resource.RLIMIT_AS, (
        config["maximum_worker_address_space_bytes"],
        config["maximum_worker_address_space_bytes"]))
    require(args.mode in config["modes_in_deterministic_merge_order"],
            "unregistered reproduction mode")
    slot_path = inputs(config, args.source_stage, args.scan_stage,
                       args.source_root)
    original = audit.read_json(slot_path)
    scan_receipt = audit.read_json(args.scan_stage / "scan.receipt.json")
    family = next(row for row in scan_receipt["families"]
                  if row["family_id"] == config["fixed_family_id"])
    scan_family = args.scan_stage / "execution" / config["fixed_family_id"]
    viewpoints = audit.read_json(scan_family / "initial_viewpoints.json")
    selection = viewpoints["selected_pose_rank_indices"]
    pose = viewpoints["ranked_poses"][selection[config["fixed_slot"]]]
    private_scan = audit.read_json(scan_family /
        "private/viewpoint-target-audit.json")["spaced_top_18"]
    scan_top2 = private_scan[config["fixed_slot"]]["target_instance_ids"][:2]
    inventory = audit.read_json(args.scan_stage / "private/inventory.json")
    house_row = next(row for row in inventory["houses"]
                     if row["house_id"] == config["fixed_house_id"])
    house = generator.load_source_record(
        args.source_root, house_row["source_locator"])
    require(generator.canonical_sha256(house) ==
            house_row["source_record_sha256"] and
            audit.sha256(scan_family / "initial_viewpoints.json") ==
            family["family_viewpoints_sha256"] and
            scan_top2 == original["scan_top2_instance_ids"],
            "original house/pose/scan target changed")
    result = execute_trial(house, pose, original, scan_top2, contract, args.mode)
    audit.write_new_json(args.stage / "private" / (args.mode + ".json"), result)
    print("RELINK_MECHANISM_WORKER mode=%s status=%s" %
          (args.mode, result["status"]), flush=True)
    require(result["status"] not in (
        "reproduction_failed_before_conclusion", "controller_stop_failed"),
        "reproduction failed: preserve private trial")


def check(reviewed_code, output_root):
    config, _ = load_config()
    bindings = binding_sha256(reviewed_code)
    require(old_probe.safe_visible_cpu_count() >= 2,
            "two independent pure checks need two CPUs")
    stage = output_root.resolve() / ("vsmt-vm04-relink-mechanism-check-v1-" +
                                   reviewed_code[:12])
    require(not stage.exists(), "check stage exists: preserve it")
    stage.mkdir(parents=True)
    groups = (("mechanism", "tests.test_vm04_relink_mechanism_probe"),
              ("frozen_action", "tests.test_vm04_target_action_probe_worker"))
    children = []
    for name, module in groups:
        path = stage / (name + ".log")
        with path.open("x", encoding="utf-8") as handle:
            child = subprocess.Popen([sys.executable, "-B", "-m", "unittest",
                                      "-v", module], cwd=ROOT, stdout=handle,
                                     stderr=subprocess.STDOUT)
        children.append((name, child, path))
    exits = []
    for name, child, path in children:
        code = child.wait()
        output = path.read_text(encoding="utf-8")
        print("[%s] %s" % (name, output), end="", flush=True)
        exits.append({"group": name, "exit_code": code,
                      "log_sha256": audit.sha256(path)})
    success = len(children) == 2 and all(row["exit_code"] == 0 for row in exits)
    receipt = stage / "check.receipt.json"
    audit.write_new_json(receipt, {"schema_version":
        "vsmt-vm04-relink-mechanism-check-v1", "reviewed_code": reviewed_code,
        "bound_sha256": bindings, "config_status": config["status"],
        "requested_workers": 2, "actual_workers": len(children),
        "worker_exits": exits, "deterministic_merge_order":
        [name for name, _ in groups], "simulator_started": False,
        "episodes_generated": 0, "training_steps": 0, "success": success})
    if success:
        audit.write_new_json(stage / "check.success.json", {
            "schema_version": "vsmt-vm04-relink-mechanism-check-success-v1",
            "receipt_sha256": audit.sha256(receipt), "success": True})
    require(success, "pure mechanism check failed")
    print("RELINK_MECHANISM_CHECK_OK workers=2 stage=%s" % stage, flush=True)


def resource_sample():
    memory = audit._cgroup_memory_headroom_bytes()
    gpu = old_probe.gpu_free_bytes_by_device()
    require(type(memory) is int and memory > 0 and len(gpu) == 1,
            "resource sampler requires one GPU and a cgroup memory limit")
    return memory, gpu[0]


def resource_gate(baseline, minimum, dispatch, ratio, static_minimum):
    """Fail closed on zero or missing measured scene demand."""
    if not all(type(value) is int and value > 0 for value in
               (baseline, minimum, dispatch)):
        return False, 0
    demand = max(0, baseline - minimum)
    return demand > 0 and dispatch >= max(static_minimum, ratio * demand), demand


def run(reviewed_code, source_stage, scan_stage, source_root, output_root):
    config, _ = load_config()
    bindings = binding_sha256(reviewed_code)
    inputs(config, source_stage, scan_stage, source_root)
    check_stage = output_root.resolve() / (
        "vsmt-vm04-relink-mechanism-check-v1-" + reviewed_code[:12])
    check_receipt, _ = audit._marker(check_stage, "check")
    require(check_receipt["reviewed_code"] == reviewed_code and
            check_receipt["bound_sha256"] == bindings and
            check_receipt["requested_workers"] ==
            check_receipt["actual_workers"] == 2,
            "diagnostic code/check marker changed")
    cpus = old_probe.safe_visible_cpu_count()
    baseline_memory, baseline_gpu = resource_sample()
    disk = shutil.disk_usage(output_root.resolve()).free
    require(cpus >= 2 and baseline_memory >=
            config["minimum_static_cgroup_headroom_bytes"] and
            baseline_gpu >= config["minimum_static_gpu_free_bytes"] and
            disk >= config["minimum_static_data_disk_free_bytes"],
            "fixed RELINK reproduction lacks safe CPU/RAM/GPU/disk resources")
    simulator = Path(audit.read_json(audit.ENVIRONMENT_PATH)[
        "environment_separation"]["simulator_process"]["environment_path"]) / "bin/python"
    require(simulator.is_file(), "frozen simulator Python missing")
    stage = output_root.resolve() / ("vsmt-vm04-relink-mechanism-v1-" +
                                   reviewed_code[:12])
    require(not stage.exists(), "diagnostic stage exists: preserve it")
    (stage / "private").mkdir(parents=True)
    environment = dict(os.environ, PYTHONUNBUFFERED="1", OMP_NUM_THREADS="1",
                       OPENBLAS_NUM_THREADS="1",
                       XDG_RUNTIME_DIR=str(output_root.resolve() / "runtime"))
    Path(environment["XDG_RUNTIME_DIR"]).mkdir(parents=True, exist_ok=True)
    args = ["--source-stage", str(source_stage.resolve()),
            "--scan-stage", str(scan_stage.resolve()),
            "--source-root", str(source_root.resolve()),
            "--stage", str(stage)]
    worker = [str(simulator), "-B", str(Path(__file__).resolve())]
    modes = config["modes_in_deterministic_merge_order"]
    children = []
    samples = []
    dispatch_error = None
    started = time.monotonic()
    first_log = stage / "private" / (modes[0] + ".log")
    try:
        with first_log.open("x", encoding="utf-8") as handle:
            child = subprocess.Popen([*worker, "worker", *args, "--mode", modes[0]],
                                     cwd=ROOT, stdout=handle,
                                     stderr=subprocess.STDOUT, env=environment)
        children.append((modes[0], child, first_log))
        while True:
            memory, gpu = resource_sample()
            samples.append({"elapsed_seconds": time.monotonic() - started,
                            "cgroup_headroom_bytes": memory,
                            "gpu_free_bytes": gpu})
            try:
                first_exit = child.wait(timeout=config[
                    "resource_sample_interval_seconds"])
                break
            except subprocess.TimeoutExpired:
                continue
        require(first_exit == 0 and (stage / "private" /
                (modes[0] + ".json")).is_file(),
                "registered original reproduction failed")
        minimum_memory = min(row["cgroup_headroom_bytes"] for row in samples)
        minimum_gpu = min(row["gpu_free_bytes"] for row in samples)
        dispatch_memory, dispatch_gpu = resource_sample()
        memory_safe, memory_demand = resource_gate(
            baseline_memory, minimum_memory, dispatch_memory,
            config["minimum_cgroup_headroom_to_observed_one_worker_demand_ratio"],
            config["minimum_static_cgroup_headroom_bytes"])
        gpu_safe, gpu_demand = resource_gate(
            baseline_gpu, minimum_gpu, dispatch_gpu,
            config["minimum_gpu_headroom_to_observed_one_worker_demand_ratio"],
            config["minimum_static_gpu_free_bytes"])
        require(memory_safe and gpu_safe and
                shutil.disk_usage(output_root.resolve()).free >=
                config["minimum_static_data_disk_free_bytes"],
                "sampled original scene demand lacks safe two-worker headroom")
        for mode in modes[1:]:
            log = stage / "private" / (mode + ".log")
            with log.open("x", encoding="utf-8") as handle:
                child = subprocess.Popen([*worker, "worker", *args,
                    "--mode", mode], cwd=ROOT, stdout=handle,
                    stderr=subprocess.STDOUT, env=environment)
            children.append((mode, child, log))
    except Exception as error:
        dispatch_error = {"error_type": type(error).__name__, "error": str(error)}
        memory_demand = locals().get("memory_demand")
        gpu_demand = locals().get("gpu_demand")
        dispatch_memory = locals().get("dispatch_memory")
        dispatch_gpu = locals().get("dispatch_gpu")
    exits = []
    for mode, child, log in children:
        exit_code = child.wait()
        output = log.read_text(encoding="utf-8")
        print("[%s] %s" % (mode, output), end="", flush=True)
        path = stage / "private" / (mode + ".json")
        exits.append({"mode": mode, "exit_code": exit_code,
                      "private_trial_sha256": audit.sha256(path)
                      if path.is_file() else None,
                      "private_log_sha256": audit.sha256(log)})
    samples_path = stage / "private/resource-samples.json"
    audit.write_new_json(samples_path, {"schema_version":
        "vsmt-vm04-relink-mechanism-resource-samples-v1",
        "baseline_memory_headroom_bytes": baseline_memory,
        "baseline_gpu_free_bytes": baseline_gpu,
        "samples": samples, "dispatch_memory_headroom_bytes": dispatch_memory,
        "dispatch_gpu_free_bytes": dispatch_gpu})
    success = (dispatch_error is None and len(children) == 3 and
               all(row["exit_code"] == 0 and
                   row["private_trial_sha256"] is not None for row in exits))
    receipt = stage / "mechanism.receipt.json"
    audit.write_new_json(receipt, {"schema_version":
        "vsmt-vm04-relink-mechanism-receipt-v1",
        "reviewed_code": reviewed_code, "bound_sha256": bindings,
        "source_action_probe_receipt_sha256":
            config["source_action_probe_receipt_sha256"],
        "source_scan_receipt_sha256": config["source_scan_receipt_sha256"],
        "requested_workers": 3, "actual_workers": len(children),
        "capacity_benchmark_mode": modes[0],
        "two_independent_control_workers_dispatched_after_benchmark":
            len(children) == 3,
        "resource_evidence": {"visible_cpu_count": cpus,
            "starting_disk_free_bytes": disk,
            "observed_cgroup_demand_bytes": memory_demand,
            "observed_gpu_demand_bytes": gpu_demand,
            "private_samples_sha256": audit.sha256(samples_path)},
        "worker_exits": exits, "dispatch_error": dispatch_error,
        "deterministic_merge_order": modes,
        "episodes_generated": 0, "training_steps": 0,
        "semantic_positive_labels_issued": 0,
        "wall_seconds": time.monotonic() - started, "success": success})
    if success:
        audit.write_new_json(stage / "mechanism.success.json", {
            "schema_version": "vsmt-vm04-relink-mechanism-success-v1",
            "receipt_sha256": audit.sha256(receipt), "success": True})
    print("RELINK_MECHANISM_%s stage=%s workers=%s" %
          ("OK" if success else "FAILED", stage, len(children)), flush=True)
    require(success, "mechanism reproduction incomplete: preserve original stage")


def anonymous_trial_summary(trial):
    """Report simulator request/actual delta, never target identity or pose."""
    planned = trial["registered_request"]["position"]
    immediate = trial["immediate_post_intervention"]
    terminal = trial["terminal_poststate"]
    def delta(snapshot):
        position = snapshot["position"] if snapshot else None
        return ({axis: round(float(position[axis]) - float(planned[axis]), 6)
                 for axis in ("x", "y", "z")}
                if type(position) is dict else None)
    return {"mode": trial["mode"], "trial_status": trial["status"],
            "last_action_success": trial.get("intervention_diagnostic", {}).get(
                "last_action_success"),
            "error_code_present": bool(trial.get("intervention_diagnostic", {}).get(
                "error_code")),
            "immediate_delta_xyz_m": delta(immediate),
            "terminal_delta_xyz_m": delta(terminal),
            "requested_pose_aabb_intersection_count": trial.get(
                "requested_pose_aabb", {}).get("intersection_count"),
            "actual_pose_aabb_intersection_count": trial.get(
                "actual_pose_aabb", {}).get("intersection_count"),
            "collision_or_reachability_verified": False,
            "memory_history_checked": False,
            "semantic_positive_label_issued": False}


def export(reviewed_code, stage):
    config, _ = load_config()
    bindings = binding_sha256(reviewed_code)
    receipt, _ = audit._marker(stage, "mechanism")
    require(receipt["reviewed_code"] == reviewed_code and
            receipt["bound_sha256"] == bindings and
            receipt["requested_workers"] == receipt["actual_workers"] == 3 and
            receipt["deterministic_merge_order"] ==
            config["modes_in_deterministic_merge_order"] and
            receipt["episodes_generated"] == receipt["training_steps"] == 0 and
            not EXPORT_PATH.exists(), "mechanism receipt/code/export changed")
    samples_path = stage / "private/resource-samples.json"
    require(audit.sha256(samples_path) == receipt["resource_evidence"][
            "private_samples_sha256"], "private resource trace changed")
    private_rows = []
    for row in receipt["worker_exits"]:
        path = stage / "private" / (row["mode"] + ".json")
        log = stage / "private" / (row["mode"] + ".log")
        require(row["exit_code"] == 0 and
                audit.sha256(path) == row["private_trial_sha256"] and
                audit.sha256(log) == row["private_log_sha256"],
                "private mechanism trial/log changed")
        trial = audit.read_json(path)
        require(trial["mode"] == row["mode"] and
                trial["fixed_slot"] == config["fixed_slot"] and
                trial["memory_history_checked"] is False and
                trial["semantic_positive_label_issued"] is False,
                "original slot or semantic boundary changed")
        private_rows.append(anonymous_trial_summary(trial))
    require([row["mode"] for row in private_rows] ==
            config["modes_in_deterministic_merge_order"],
            "reproduction merge order changed")
    audit.write_new_json(EXPORT_PATH, {
        "schema_version": "vsmt-vm04-relink-mechanism-public-report-v1",
        "status": "one_fixed_relink_slot_controlled_diagnostic_only",
        "reviewed_code": reviewed_code,
        "mechanism_receipt_sha256": audit.sha256(stage / "mechanism.receipt.json"),
        "source_v1_probe_receipt_sha256":
            config["source_action_probe_receipt_sha256"],
        "source_scan_receipt_sha256": config["source_scan_receipt_sha256"],
        "requested_workers": receipt["requested_workers"],
        "actual_workers": receipt["actual_workers"],
        "trials": private_rows, "resource_evidence": receipt["resource_evidence"],
        "private_ids_exported": False,
        "collision_or_reachability_verified": False,
        "memory_history_checked": False,
        "semantic_positive_labels_issued": 0,
        "episodes_generated": 0, "training_steps": 0})
    print("RELINK_MECHANISM_EXPORT_OK report=%s" % EXPORT_PATH, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=("contract", "check", "run", "worker",
                                         "export"))
    parser.add_argument("--reviewed-code")
    parser.add_argument("--source-stage", type=Path)
    parser.add_argument("--scan-stage", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--stage", type=Path)
    parser.add_argument("--mode")
    args = parser.parse_args()
    if args.step == "contract":
        config, _ = load_config()
        print("RELINK_MECHANISM_CONTRACT_OK status=%s generation=false training=false" %
              config["status"])
    elif args.step == "check":
        check(args.reviewed_code, args.output_root)
    elif args.step == "run":
        run(args.reviewed_code, args.source_stage, args.scan_stage,
            args.source_root, args.output_root)
    elif args.step == "worker":
        run_worker(args)
    else:
        export(args.reviewed_code, args.stage)


if __name__ == "__main__":
    main()
