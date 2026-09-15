#!/usr/bin/env python3
"""Two fixed-slot replicas test whether physics advances resolve RELINK overlap."""

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
except ImportError:  # Windows pure checks do not run simulator workers.
    resource = None

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import vm04_two_house_audit as audit  # noqa: E402
import vm04_two_house_worker as generator  # noqa: E402
import vm04_relink_mechanism_probe as base  # noqa: E402

CONFIG_PATH = ROOT / "configs/vsmt/vm04_relink_physics_step_probe_v1.json"
SOURCE_REPORT_PATH = ROOT / "results/vsmt_vm04_relink_mechanism_probe_v1.json"
EXPORT_PATH = ROOT / "results/vsmt_vm04_relink_physics_step_probe_v1.json"
BOUND_FILES = (
    "configs/vsmt/vm04_relink_physics_step_probe_v1.json",
    "ops/vsmt/vm04_relink_physics_step_probe.py",
    "ops/vsmt/vm04_relink_mechanism_probe.py",
    "ops/vsmt/vm04_two_house_worker.py",
    "src/vsmt/vm04_target_selection_v3.py",
    "configs/vsmt/vm04_target_boundary_proposal_v3.json",
    "tests/test_vm04_relink_physics_step_probe.py",
)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def load_config():
    config = audit.read_json(CONFIG_PATH)
    source, _ = base.load_config()
    require(config["version"] == "vsmt-vm04-relink-physics-step-probe-v1" and
            config["status"] == "frozen_fixed_slot_physics_diagnostic_only" and
            config["authorized_reproduction"] is True and
            config["generation_authorized"] is False and
            config["training_authorized"] is False and
            config["source_mechanism_public_report_sha256"] ==
            audit.sha256(SOURCE_REPORT_PATH) and
            config["source_action_probe_receipt_sha256"] ==
            source["source_action_probe_receipt_sha256"] and
            config["source_scan_receipt_sha256"] ==
            source["source_scan_receipt_sha256"] and
            config["fixed_family_id"] == source["fixed_family_id"] and
            config["fixed_slot"] == source["fixed_slot"] and
            config["fixed_house_id"] == source["fixed_house_id"] and
            config["fixed_target_policy"] ==
            "same_original_private_authored_asset_id_only" and
            config["replicas"] == 2 and
            config["manual_physics_steps_per_replica"] == 50 and
            config["manual_physics_time_step_seconds"] == 0.01 and
            config["minimum_static_cgroup_headroom_bytes"] == 8589934592 and
            config["minimum_static_gpu_free_bytes"] == 8589934592 and
            config["minimum_static_data_disk_free_bytes"] == 8589934592 and
            config["minimum_cgroup_headroom_to_source_sampled_demand_ratio"] == 4.0 and
            config["minimum_gpu_headroom_to_source_sampled_demand_ratio"] == 2.0 and
            config["maximum_worker_address_space_bytes"] == 42949672960 and
            config["no_wall_clock_failure_limit"] is True,
            "manual physics probe scope/gate/source changed")
    for key in ("source_mechanism_receipt_sha256",
                "source_mechanism_public_report_sha256",
                "source_action_probe_receipt_sha256",
                "source_scan_receipt_sha256"):
        require(re.fullmatch(r"[0-9a-f]{64}", config[key]) is not None,
                "invalid physics source digest")
    return config


def binding_sha256(reviewed_code):
    require(audit.git("rev-parse", "HEAD") == reviewed_code and
            not audit.git("status", "--porcelain") and
            Path(audit.git("rev-parse", "--show-toplevel")).resolve() == ROOT,
            "physics diagnostic requires clean exact checkout")
    return {relative: audit.sha256(ROOT / relative) for relative in BOUND_FILES}


def source_inputs(config, mechanism_stage, source_stage, scan_stage, source_root):
    receipt, _ = audit._marker(mechanism_stage, "mechanism")
    require(audit.sha256(mechanism_stage / "mechanism.receipt.json") ==
            config["source_mechanism_receipt_sha256"] and
            receipt["requested_workers"] == receipt["actual_workers"] == 3 and
            receipt["episodes_generated"] == receipt["training_steps"] == 0 and
            receipt["source_action_probe_receipt_sha256"] ==
            config["source_action_probe_receipt_sha256"] and
            receipt["source_scan_receipt_sha256"] ==
            config["source_scan_receipt_sha256"],
            "original three-control receipt/source changed")
    rows = {row["mode"]: row for row in receipt["worker_exits"]}
    original_path = mechanism_stage / "private/registered_forced.json"
    nonforced_path = mechanism_stage / "private/same_request_nonforced.json"
    paused_path = (mechanism_stage /
                   "private/registered_forced_physics_paused.json")
    require(all(audit.sha256(path) == rows[mode]["private_trial_sha256"]
                for mode, path in (("registered_forced", original_path),
                                   ("same_request_nonforced", nonforced_path),
                                   ("registered_forced_physics_paused", paused_path))),
            "original three private controls changed")
    original = audit.read_json(original_path)
    nonforced = audit.read_json(nonforced_path)
    paused = audit.read_json(paused_path)
    require(original["intervention_diagnostic"]["last_action_success"] is True and
            nonforced["intervention_diagnostic"]["last_action_success"] is False and
            paused["intervention_diagnostic"]["last_action_success"] is True and
            original["target_object_id"] == nonforced["target_object_id"] ==
            paused["target_object_id"] and
            original["registered_request"] == nonforced["registered_request"] ==
            paused["registered_request"],
            "source controls do not share the original asset/request")
    base_config, _ = base.load_config()
    slot_path = base.inputs(base_config, source_stage, scan_stage, source_root)
    return audit.read_json(slot_path), receipt, original, nonforced, paused


def run_worker(args):
    config = load_config()
    require(resource is not None and args.replica in (0, 1),
            "Linux simulator and fixed replica required")
    resource.setrlimit(resource.RLIMIT_AS, (
        config["maximum_worker_address_space_bytes"],
        config["maximum_worker_address_space_bytes"]))
    original_slot, _, _, _, _ = source_inputs(
        config, args.mechanism_stage, args.source_stage,
        args.scan_stage, args.source_root)
    scan_receipt = audit.read_json(args.scan_stage / "scan.receipt.json")
    family = next(row for row in scan_receipt["families"]
                  if row["family_id"] == config["fixed_family_id"])
    scan_family = args.scan_stage / "execution" / config["fixed_family_id"]
    viewpoints = audit.read_json(scan_family / "initial_viewpoints.json")
    pose = viewpoints["ranked_poses"][viewpoints[
        "selected_pose_rank_indices"][config["fixed_slot"]]]
    scan_top2 = audit.read_json(scan_family /
        "private/viewpoint-target-audit.json")["spaced_top_18"][
        config["fixed_slot"]]["target_instance_ids"][:2]
    inventory = audit.read_json(args.scan_stage / "private/inventory.json")
    house_row = next(row for row in inventory["houses"]
                     if row["house_id"] == config["fixed_house_id"])
    house = generator.load_source_record(
        args.source_root, house_row["source_locator"])
    require(generator.canonical_sha256(house) ==
            house_row["source_record_sha256"] and
            audit.sha256(scan_family / "initial_viewpoints.json") ==
            family["family_viewpoints_sha256"] and
            scan_top2 == original_slot["scan_top2_instance_ids"],
            "physics replica house/pose/target changed")
    _, contract = base.load_config()
    trial = base.execute_trial(
        house, pose, original_slot, scan_top2, contract,
        "registered_forced_physics_paused", physics_step_count=config[
            "manual_physics_steps_per_replica"])
    trial["replica"] = args.replica
    trial["schema_version"] = "vsmt-vm04-private-relink-physics-step-trial-v1"
    path = args.stage / "private" / ("replica_%02d.json" % args.replica)
    audit.write_new_json(path, trial)
    print("RELINK_PHYSICS_STEP_WORKER replica=%s status=%s steps=%s" %
          (args.replica, trial["status"],
           len(trial.get("manual_physics_steps", []))), flush=True)
    require(trial["status"] == "recorded_full_registered_path" and
            len(trial["manual_physics_steps"]) == 50,
            "manual physics replica incomplete: preserve private trace")


def check(reviewed_code, output_root):
    config = load_config()
    bindings = binding_sha256(reviewed_code)
    require(base.old_probe.safe_visible_cpu_count() >= 2,
            "two independent physics pure checks need two CPUs")
    stage = output_root.resolve() / ("vsmt-vm04-relink-physics-check-v1-" +
                                   reviewed_code[:12])
    require(not stage.exists(), "physics check stage exists")
    stage.mkdir(parents=True)
    groups = (("physics", "tests.test_vm04_relink_physics_step_probe"),
              ("original", "tests.test_vm04_relink_mechanism_probe"))
    children = []
    for name, module in groups:
        log = stage / (name + ".log")
        with log.open("x", encoding="utf-8") as handle:
            child = subprocess.Popen([sys.executable, "-B", "-m", "unittest",
                                      "-v", module], cwd=ROOT, stdout=handle,
                                     stderr=subprocess.STDOUT)
        children.append((name, child, log))
    exits = []
    for name, child, log in children:
        code = child.wait()
        print("[%s] %s" % (name, log.read_text(encoding="utf-8")),
              end="", flush=True)
        exits.append({"group": name, "exit_code": code,
                      "log_sha256": audit.sha256(log)})
    success = len(children) == 2 and all(row["exit_code"] == 0 for row in exits)
    receipt = stage / "check.receipt.json"
    audit.write_new_json(receipt, {
        "schema_version": "vsmt-vm04-relink-physics-check-v1",
        "reviewed_code": reviewed_code, "bound_sha256": bindings,
        "config_status": config["status"],
        "requested_workers": 2, "actual_workers": len(children),
        "worker_exits": exits, "deterministic_merge_order":
        [name for name, _ in groups], "simulator_started": False,
        "episodes_generated": 0, "training_steps": 0, "success": success})
    if success:
        audit.write_new_json(stage / "check.success.json", {
            "schema_version": "vsmt-vm04-relink-physics-check-success-v1",
            "receipt_sha256": audit.sha256(receipt), "success": True})
    require(success, "physics pure check failed")
    print("RELINK_PHYSICS_CHECK_OK workers=2 stage=%s" % stage, flush=True)


def run(reviewed_code, mechanism_stage, source_stage, scan_stage,
        source_root, output_root):
    config = load_config()
    bindings = binding_sha256(reviewed_code)
    _, source_receipt, _, _, _ = source_inputs(
        config, mechanism_stage, source_stage, scan_stage, source_root)
    check_stage = output_root.resolve() / (
        "vsmt-vm04-relink-physics-check-v1-" + reviewed_code[:12])
    check_receipt, _ = audit._marker(check_stage, "check")
    require(check_receipt["reviewed_code"] == reviewed_code and
            check_receipt["bound_sha256"] == bindings and
            check_receipt["requested_workers"] ==
            check_receipt["actual_workers"] == 2,
            "physics check/code marker changed")
    memory, gpu = base.resource_sample()
    disk = shutil.disk_usage(output_root.resolve()).free
    cpus = base.old_probe.safe_visible_cpu_count()
    source_memory_demand = source_receipt["resource_evidence"][
        "observed_cgroup_demand_bytes"]
    source_gpu_demand = source_receipt["resource_evidence"][
        "observed_gpu_demand_bytes"]
    require(type(source_memory_demand) is int and source_memory_demand > 0 and
            type(source_gpu_demand) is int and source_gpu_demand > 0 and
            cpus >= 2 and
            memory >= max(config["minimum_static_cgroup_headroom_bytes"],
                          config["minimum_cgroup_headroom_to_source_sampled_demand_ratio"]
                          * source_memory_demand) and
            gpu >= max(config["minimum_static_gpu_free_bytes"],
                       config["minimum_gpu_headroom_to_source_sampled_demand_ratio"]
                       * source_gpu_demand) and
            disk >= config["minimum_static_data_disk_free_bytes"],
            "two physics replicas lack fresh sampled/static resource headroom")
    simulator = Path(audit.read_json(audit.ENVIRONMENT_PATH)[
        "environment_separation"]["simulator_process"]["environment_path"]) / "bin/python"
    require(simulator.is_file(), "frozen simulator Python missing")
    stage = output_root.resolve() / ("vsmt-vm04-relink-physics-v1-" +
                                   reviewed_code[:12])
    require(not stage.exists(), "physics stage exists: preserve it")
    (stage / "private").mkdir(parents=True)
    environment = dict(os.environ, PYTHONUNBUFFERED="1", OMP_NUM_THREADS="1",
                       OPENBLAS_NUM_THREADS="1",
                       XDG_RUNTIME_DIR=str(output_root.resolve() / "runtime"))
    Path(environment["XDG_RUNTIME_DIR"]).mkdir(parents=True, exist_ok=True)
    shared = ["--mechanism-stage", str(mechanism_stage.resolve()),
              "--source-stage", str(source_stage.resolve()),
              "--scan-stage", str(scan_stage.resolve()),
              "--source-root", str(source_root.resolve()),
              "--stage", str(stage)]
    children = []
    dispatch_error = None
    started = time.monotonic()
    for replica in range(config["replicas"]):
        log = stage / "private" / ("replica_%02d.log" % replica)
        try:
            with log.open("x", encoding="utf-8") as handle:
                child = subprocess.Popen([str(simulator), "-B",
                    str(Path(__file__).resolve()), "worker", *shared,
                    "--replica", str(replica)], cwd=ROOT,
                    stdout=handle, stderr=subprocess.STDOUT, env=environment)
            children.append((replica, child, log))
        except Exception as error:
            dispatch_error = {"error_type": type(error).__name__,
                              "error": str(error)}
            break
    samples = []
    while any(child.poll() is None for _, child, _ in children):
        try:
            current_memory, current_gpu = base.resource_sample()
            samples.append({"elapsed_seconds": time.monotonic() - started,
                            "cgroup_headroom_bytes": current_memory,
                            "gpu_free_bytes": current_gpu})
            require(current_memory > 4294967296 and
                    current_gpu > 4294967296,
                    "active physics replicas exceeded emergency RAM/GPU protection")
        except Exception as error:
            dispatch_error = {"phase": "active_resource_guard",
                              "error_type": type(error).__name__,
                              "error": str(error)}
            for _, child, _ in children:
                if child.poll() is None:
                    child.terminate()
            break
        time.sleep(0.25)
    exits = []
    for replica, child, log in children:
        code = child.wait()
        print("[replica_%02d] %s" %
              (replica, log.read_text(encoding="utf-8")), end="", flush=True)
        path = stage / "private" / ("replica_%02d.json" % replica)
        exits.append({"replica": replica, "exit_code": code,
                      "private_trial_sha256": audit.sha256(path)
                      if path.is_file() else None,
                      "private_log_sha256": audit.sha256(log)})
    sample_path = stage / "private/resource-samples.json"
    audit.write_new_json(sample_path, {
        "schema_version": "vsmt-vm04-relink-physics-resource-samples-v1",
        "initial_cgroup_headroom_bytes": memory,
        "initial_gpu_free_bytes": gpu, "samples": samples})
    success = dispatch_error is None and len(children) == 2 and all(
        row["exit_code"] == 0 and row["private_trial_sha256"] is not None
        for row in exits)
    receipt = stage / "physics.receipt.json"
    audit.write_new_json(receipt, {
        "schema_version": "vsmt-vm04-relink-physics-receipt-v1",
        "reviewed_code": reviewed_code, "bound_sha256": bindings,
        "source_mechanism_receipt_sha256":
            config["source_mechanism_receipt_sha256"],
        "check_receipt_sha256": audit.sha256(
            check_stage / "check.receipt.json"),
        "requested_workers": 2, "actual_workers": len(children),
        "worker_exits": exits, "dispatch_error": dispatch_error,
        "deterministic_merge_order": [0, 1],
        "resource_evidence": {"visible_cpu_count": cpus,
            "initial_cgroup_headroom_bytes": memory,
            "initial_gpu_free_bytes": gpu,
            "initial_data_disk_free_bytes": disk,
            "source_sampled_cgroup_demand_bytes": source_memory_demand,
            "source_sampled_gpu_demand_bytes": source_gpu_demand,
            "private_samples_sha256": audit.sha256(sample_path)},
        "wall_seconds": time.monotonic() - started,
        "episodes_generated": 0, "training_steps": 0,
        "semantic_positive_labels_issued": 0, "success": success})
    if success:
        audit.write_new_json(stage / "physics.success.json", {
            "schema_version": "vsmt-vm04-relink-physics-success-v1",
            "receipt_sha256": audit.sha256(receipt), "success": True})
    print("RELINK_PHYSICS_%s stage=%s workers=%s" %
          ("OK" if success else "FAILED", stage, len(children)), flush=True)
    require(success, "physics diagnostic incomplete: preserve stage")


def position_delta(position, requested):
    return {axis: round(float(position[axis]) - float(requested[axis]), 6)
            for axis in ("x", "y", "z")}


def replica_summary(trial):
    requested = trial["registered_request"]["position"]
    steps = trial["manual_physics_steps"]
    deltas = [position_delta(row["target"]["position"], requested)
              for row in steps]
    first_change = next((index for index, row in enumerate(deltas)
                         if any(abs(value) > 0.000001
                                for value in row.values())), None)
    return {"replica": trial["replica"], "status": trial["status"],
            "initial_paused_delta_xyz_m": position_delta(
                trial["immediate_post_intervention"]["position"], requested),
            "manual_step_count": len(steps),
            "first_changed_step_index": first_change,
            "first_step_delta_xyz_m": deltas[0],
            "last_step_delta_xyz_m": deltas[-1],
            "moving_step_count": sum(row["target"]["is_moving"] is True
                                     for row in steps),
            "memory_history_checked": False,
            "robot_path_reachability_verified": False,
            "semantic_positive_label_issued": False}


def export(reviewed_code, stage, mechanism_stage):
    config = load_config()
    bindings = binding_sha256(reviewed_code)
    receipt, _ = audit._marker(stage, "physics")
    require(receipt["reviewed_code"] == reviewed_code and
            receipt["bound_sha256"] == bindings and
            receipt["requested_workers"] == receipt["actual_workers"] == 2 and
            receipt["source_mechanism_receipt_sha256"] ==
            config["source_mechanism_receipt_sha256"] and
            receipt["deterministic_merge_order"] == [0, 1] and
            receipt["episodes_generated"] == receipt["training_steps"] == 0 and
            not EXPORT_PATH.exists(), "physics receipt/code/export changed")
    sample_path = stage / "private/resource-samples.json"
    require(audit.sha256(sample_path) == receipt["resource_evidence"][
            "private_samples_sha256"], "physics resource trace changed")
    summaries = []
    for row in receipt["worker_exits"]:
        path = stage / "private" / ("replica_%02d.json" % row["replica"])
        log = stage / "private" / ("replica_%02d.log" % row["replica"])
        require(row["exit_code"] == 0 and
                audit.sha256(path) == row["private_trial_sha256"] and
                audit.sha256(log) == row["private_log_sha256"],
                "physics private replica/log changed")
        trial = audit.read_json(path)
        require(trial["replica"] == row["replica"] and
                trial["fixed_slot"] == config["fixed_slot"] and
                len(trial["manual_physics_steps"]) == 50 and
                trial["memory_history_checked"] is False and
                trial["semantic_positive_label_issued"] is False,
                "physics replica semantic boundary changed")
        summaries.append(replica_summary(trial))
    source_report = audit.read_json(SOURCE_REPORT_PATH)
    nonforced_path = mechanism_stage / "private/same_request_nonforced.json"
    mechanism_receipt, _ = audit._marker(mechanism_stage, "mechanism")
    row = next(item for item in mechanism_receipt["worker_exits"]
               if item["mode"] == "same_request_nonforced")
    require(audit.sha256(nonforced_path) == row["private_trial_sha256"] and
            audit.sha256(mechanism_stage / "mechanism.receipt.json") ==
            config["source_mechanism_receipt_sha256"],
            "source nonforced collision diagnostic changed")
    nonforced = audit.read_json(nonforced_path)
    message = nonforced["immediate_post_intervention"]["error_message"] or ""
    collision_reported = (" is colliding with " in message and
                          " after teleport." in message and
                          nonforced["intervention_diagnostic"][
                              "last_action_success"] is False)
    require(collision_reported,
            "nonforced rejection has no explicit simulator collision message")
    original = next(item for item in source_report["trials"]
                    if item["mode"] == "registered_forced")
    audit.write_new_json(EXPORT_PATH, {
        "schema_version": "vsmt-vm04-relink-physics-attribution-report-v1",
        "status": "one_fixed_slot_manual_physics_collision_diagnostic",
        "reviewed_code": reviewed_code,
        "physics_receipt_sha256": audit.sha256(stage / "physics.receipt.json"),
        "source_mechanism_receipt_sha256":
            config["source_mechanism_receipt_sha256"],
        "source_mechanism_public_report_sha256":
            config["source_mechanism_public_report_sha256"],
        "source_original_forced_immediate_delta_xyz_m":
            original["immediate_delta_xyz_m"],
        "simulator_nonforced_rejection_category":
            "explicit_object_collision_after_teleport",
        "simulator_final_pose_collision_reported": True,
        "collider_geometry_independently_verified": False,
        "robot_path_reachability_verified": False,
        "simulator_collision_counterpart_identity_exported": False,
        "manual_physics_replicas": summaries,
        "requested_workers": 2, "actual_workers": 2,
        "resource_evidence": receipt["resource_evidence"],
        "private_ids_exported": False,
        "memory_history_checked": False,
        "semantic_positive_labels_issued": 0,
        "episodes_generated": 0, "training_steps": 0})
    print("RELINK_PHYSICS_EXPORT_OK report=%s" % EXPORT_PATH, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=("contract", "check", "run", "worker",
                                         "export"))
    parser.add_argument("--reviewed-code")
    parser.add_argument("--mechanism-stage", type=Path)
    parser.add_argument("--source-stage", type=Path)
    parser.add_argument("--scan-stage", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--stage", type=Path)
    parser.add_argument("--replica", type=int)
    args = parser.parse_args()
    if args.step == "contract":
        config = load_config()
        print("RELINK_PHYSICS_CONTRACT_OK status=%s generation=false training=false" %
              config["status"])
    elif args.step == "check":
        check(args.reviewed_code, args.output_root)
    elif args.step == "run":
        run(args.reviewed_code, args.mechanism_stage, args.source_stage,
            args.scan_stage, args.source_root, args.output_root)
    elif args.step == "worker":
        run_worker(args)
    else:
        export(args.reviewed_code, args.stage, args.mechanism_stage)


if __name__ == "__main__":
    main()
