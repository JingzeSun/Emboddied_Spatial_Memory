#!/usr/bin/env python3
"""Check all four frozen VM04 RELINK endpoints without force or substitution."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace

try:
    import resource
except ImportError:  # Pure local checks run on Windows.
    resource = None

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import vm04_two_house_audit as audit  # noqa: E402
import vm04_two_house_worker as generator  # noqa: E402
import vm04_target_action_probe as old_probe  # noqa: E402
import vm04_relink_mechanism_probe as mechanism  # noqa: E402
import vm04_physical_relink_action as physical  # noqa: E402

CONFIG_PATH = ROOT / "configs/vsmt/vm04_relink_endpoint_two_house_probe_v1.json"
ENDPOINT_PATH = ROOT / "configs/vsmt/vm04_physical_relink_endpoint_contract_v1.json"
OLD_REPORT_PATH = ROOT / "results/vsmt_vm04_target_action_probe_v1.json"
PHYSICS_REPORT_PATH = ROOT / "results/vsmt_vm04_relink_physics_step_probe_v1.json"
EXPORT_PATH = ROOT / "results/vsmt_vm04_relink_endpoint_two_house_probe_v1.json"
BOUND_FILES = (
    "configs/vsmt/vm04_relink_endpoint_two_house_probe_v1.json",
    "configs/vsmt/vm04_physical_relink_endpoint_contract_v1.json",
    "ops/vsmt/vm04_relink_endpoint_two_house_probe.py",
    "ops/vsmt/vm04_physical_relink_action.py",
    "ops/vsmt/vm04_relink_mechanism_probe.py",
    "ops/vsmt/vm04_two_house_worker.py",
    "src/vsmt/vm04_target_selection_v3.py",
    "tests/test_vm04_relink_endpoint_two_house_probe.py",
    "tests/test_vm04_physical_relink_action.py",
)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def load_config():
    config = audit.read_json(CONFIG_PATH)
    endpoint = physical.validate_contract(audit.read_json(ENDPOINT_PATH))
    require(config["version"] == "vsmt-vm04-relink-endpoint-two-house-probe-v1" and
            config["status"] ==
            "frozen_fixed_two_house_nonforced_endpoint_diagnostic_only" and
            config["authorized_endpoint_probe"] is True and
            config["generation_authorized"] is False and
            config["training_authorized"] is False and
            config["source_v1_action_probe_receipt_sha256"] ==
            "b328caa335857a8e85fe26ac994c069115ba5baa218c2f9a4bee41a87b424333" and
            config["source_v2_scan_receipt_sha256"] ==
            "044fd705e998b1dea9bc62bdd730ff2fc583f9880901131f8927aefb10bb9fd5" and
            config["source_v1_action_public_report_sha256"] ==
            audit.sha256(OLD_REPORT_PATH) and
            config["source_physics_attribution_public_report_sha256"] ==
            audit.sha256(PHYSICS_REPORT_PATH) and
            config["physical_endpoint_contract_sha256"] ==
            audit.sha256(ENDPOINT_PATH) and
            config["fixed_house_ids"] == endpoint["fixed_house_ids"] and
            config["fixed_family_ids"] == endpoint["fixed_family_ids"] and
            config["all_original_relink_slots_per_family"] == 2 and
            config["requested_independent_slot_workers"] == 4 and
            config["failure_policy"] ==
            "original_slot_diagnosis_no_target_pose_destination_house_reselection" and
            config["resource_policy"] ==
            "four_slot_workers_only_if_fresh_headroom_covers_four_times_source_sampled_demand" and
            config["minimum_cgroup_headroom_to_four_source_workers_ratio"] == 4.0 and
            config["minimum_gpu_headroom_to_four_source_workers_ratio"] == 2.0 and
            config["minimum_static_cgroup_headroom_bytes"] == 8589934592 and
            config["minimum_static_gpu_free_bytes"] == 8589934592 and
            config["minimum_static_data_disk_free_bytes"] == 8589934592 and
            config["maximum_worker_address_space_bytes"] == 42949672960 and
            config["no_wall_clock_failure_limit"] is True,
            "four RELINK endpoint scope/gate/source changed")
    for key in ("source_v1_action_probe_receipt_sha256",
                "source_v2_scan_receipt_sha256",
                "source_v1_action_public_report_sha256",
                "source_physics_attribution_public_report_sha256",
                "physical_endpoint_contract_sha256"):
        require(re.fullmatch(r"[0-9a-f]{64}", config[key]) is not None,
                "invalid RELINK endpoint provenance digest")
    return config, endpoint


def binding_sha256(reviewed_code):
    require(audit.git("rev-parse", "HEAD") == reviewed_code and
            not audit.git("status", "--porcelain") and
            Path(audit.git("rev-parse", "--show-toplevel")).resolve() == ROOT,
            "endpoint probe requires exact clean checkout")
    return {relative: audit.sha256(ROOT / relative) for relative in BOUND_FILES}


def original_tasks(config, source_stage, scan_stage, source_root,
                   mechanism_stage):
    receipt, _ = audit._marker(source_stage, "probe")
    require(audit.sha256(source_stage / "probe.receipt.json") ==
            config["source_v1_action_probe_receipt_sha256"] and
            audit.sha256(scan_stage / "scan.receipt.json") ==
            config["source_v2_scan_receipt_sha256"] and
            receipt["requested_workers"] == receipt["actual_workers"] == 2 and
            receipt["episodes_generated"] == receipt["training_steps"] == 0,
            "original two-house source probe/scan changed")
    source_config, _ = old_probe.load_config()
    old_probe.scan_inputs(source_config, scan_stage, source_root)
    physics = audit.read_json(PHYSICS_REPORT_PATH)
    mechanism_receipt, _ = audit._marker(mechanism_stage, "mechanism")
    require(physics["source_mechanism_receipt_sha256"] ==
            audit.sha256(mechanism_stage / "mechanism.receipt.json") and
            mechanism_receipt["source_action_probe_receipt_sha256"] ==
            config["source_v1_action_probe_receipt_sha256"],
            "collision attribution source chain changed")
    tasks = []
    for index, family_id in enumerate(config["fixed_family_ids"]):
        root = source_stage / "execution" / family_id
        worker_path = root / "private/worker.receipt.json"
        registered = next(row["sha256"] for row in
                          receipt["family_worker_receipts"]
                          if row["family_id"] == family_id)
        require(audit.sha256(worker_path) == registered,
                "original family worker receipt changed")
        worker = audit.read_json(worker_path)
        require(worker["fixed_slot_count"] == 18 and
                [row["slot"] for row in worker["slots"]] == list(range(18)),
                "original family slots changed")
        slots = [row for row in worker["slots"] if row["program"] == "RELINK"]
        require(len(slots) == config["all_original_relink_slots_per_family"],
                "expected exactly two original RELINK slots per family")
        for row in slots:
            slot = row["slot"]
            private_path = root / "private" / ("slot_%02d.json" % slot)
            require(audit.sha256(private_path) == row["private_slot_sha256"],
                    "original RELINK private slot changed")
            original = audit.read_json(private_path)
            require(original["slot"] == slot and original["program"] == "RELINK" and
                    len(original["v3_target_instance_ids"]) == 1 and
                    original["status"] in (
                        "relink_forced_action_terminal_verified_collision_unchecked",
                        "terminal_poststate_mismatch"),
                    "original RELINK source diagnosis changed")
            tasks.append({"family_id": family_id, "source_house_id":
                          config["fixed_house_ids"][index], "slot": slot,
                          "private_source_sha256": row["private_slot_sha256"]})
    require(len(tasks) == 4 and tasks == sorted(tasks,
            key=lambda row: (row["family_id"], row["slot"])),
            "original four-slot deterministic order changed")
    return tasks, mechanism_receipt


def event_from_snapshot(snapshot, object_id):
    if snapshot is None:
        return None
    return SimpleNamespace(metadata={
        "lastActionSuccess": snapshot.get("last_action_success"),
        "errorMessage": snapshot.get("error_message"),
        "objects": [{"objectId": object_id,
                     "position": snapshot.get("position"),
                     "isMoving": snapshot.get("is_moving")}]})


def endpoint_record(trial, endpoint):
    if (trial["registered_request"] is None or
            trial["attempted_request"] is None):
        return {"status": "original_scene_or_asset_precondition_failed",
                "source_trial_status": trial["status"],
                "memory_history_checked": False,
                "semantic_positive_label_issued": False}
    before = dict(trial["pre_intervention"])
    frozen_source = dict(trial["registered_request"]["position"])
    frozen_source["x"] = float(frozen_source["x"]) - 0.5
    before["position"] = frozen_source
    expected = physical.nonforced_original_request(
        trial["registered_request"], before, endpoint)
    require(trial["attempted_request"] == expected,
            "endpoint probe changed more than forceAction")
    object_id = trial["target_object_id"]
    return physical.endpoint_verdict(
        trial["registered_request"],
        event_from_snapshot(trial["immediate_post_intervention"], object_id),
        event_from_snapshot(trial["terminal_poststate"], object_id), endpoint)


def run_worker(args):
    config, endpoint = load_config()
    require(resource is not None, "Linux simulator worker resource limit required")
    resource.setrlimit(resource.RLIMIT_AS, (
        config["maximum_worker_address_space_bytes"],
        config["maximum_worker_address_space_bytes"]))
    tasks, _ = original_tasks(config, args.source_stage, args.scan_stage,
                              args.source_root, args.mechanism_stage)
    task = next((row for row in tasks if row["family_id"] == args.family_id and
                 row["slot"] == args.slot), None)
    require(task is not None, "unregistered original RELINK task")
    original_path = (args.source_stage / "execution" / args.family_id /
                     "private" / ("slot_%02d.json" % args.slot))
    require(audit.sha256(original_path) == task["private_source_sha256"],
            "assigned original slot digest changed")
    original = audit.read_json(original_path)
    scan_receipt = audit.read_json(args.scan_stage / "scan.receipt.json")
    scan_family = args.scan_stage / "execution" / args.family_id
    family = next(row for row in scan_receipt["families"]
                  if row["family_id"] == args.family_id)
    viewpoints = audit.read_json(scan_family / "initial_viewpoints.json")
    pose = viewpoints["ranked_poses"][viewpoints[
        "selected_pose_rank_indices"][args.slot]]
    private_scan = audit.read_json(scan_family /
        "private/viewpoint-target-audit.json")["spaced_top_18"]
    scan_top2 = private_scan[args.slot]["target_instance_ids"][:2]
    inventory = audit.read_json(args.scan_stage / "private/inventory.json")
    house_row = next(row for row in inventory["houses"]
                     if row["house_id"] == task["source_house_id"])
    house = generator.load_source_record(
        args.source_root, house_row["source_locator"])
    require(generator.canonical_sha256(house) ==
            house_row["source_record_sha256"] and
            audit.sha256(scan_family / "initial_viewpoints.json") ==
            family["family_viewpoints_sha256"] and
            scan_top2 == original["scan_top2_instance_ids"],
            "endpoint house/pose/scan target changed")
    _, target_contract = mechanism.load_config()
    trial = mechanism.execute_trial(
        house, pose, original, scan_top2, target_contract,
        "same_request_nonforced")
    verdict = endpoint_record(trial, endpoint)
    result = {"schema_version": "vsmt-vm04-private-relink-endpoint-slot-v1",
              "family_id": args.family_id, "slot": args.slot,
              "source_private_slot_sha256": task["private_source_sha256"],
              "original_forced_status": original["status"],
              "trial": trial, "endpoint_verdict": verdict,
              "memory_history_checked": False,
              "semantic_positive_label_issued": False}
    path = (args.stage / "private" / args.family_id /
            ("slot_%02d.json" % args.slot))
    audit.write_new_json(path, result)
    print("RELINK_ENDPOINT_WORKER family=%s slot=%s status=%s" %
          (args.family_id, args.slot, verdict["status"]), flush=True)
    require(trial["status"] not in (
        "reproduction_failed_before_conclusion", "controller_stop_failed"),
        "fixed RELINK endpoint replay incomplete: preserve original slot")


def check(reviewed_code, output_root):
    config, _ = load_config()
    bindings = binding_sha256(reviewed_code)
    require(old_probe.safe_visible_cpu_count() >= 2,
            "two independent endpoint pure checks need two CPUs")
    stage = output_root.resolve() / ("vsmt-vm04-relink-endpoint-check-v1-" +
                                   reviewed_code[:12])
    require(not stage.exists(), "endpoint check stage exists")
    stage.mkdir(parents=True)
    groups = (("endpoint", "tests.test_vm04_relink_endpoint_two_house_probe"),
              ("action", "tests.test_vm04_physical_relink_action"))
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
        "schema_version": "vsmt-vm04-relink-endpoint-check-v1",
        "reviewed_code": reviewed_code, "bound_sha256": bindings,
        "config_status": config["status"],
        "requested_workers": 2, "actual_workers": len(children),
        "worker_exits": exits, "deterministic_merge_order":
        [name for name, _ in groups], "simulator_started": False,
        "episodes_generated": 0, "training_steps": 0, "success": success})
    if success:
        audit.write_new_json(stage / "check.success.json", {
            "schema_version": "vsmt-vm04-relink-endpoint-check-success-v1",
            "receipt_sha256": audit.sha256(receipt), "success": True})
    require(success, "endpoint pure check failed")
    print("RELINK_ENDPOINT_CHECK_OK workers=2 stage=%s" % stage, flush=True)


def run(reviewed_code, source_stage, scan_stage, source_root,
        mechanism_stage, output_root):
    config, _ = load_config()
    bindings = binding_sha256(reviewed_code)
    tasks, mechanism_receipt = original_tasks(
        config, source_stage, scan_stage, source_root, mechanism_stage)
    check_stage = output_root.resolve() / (
        "vsmt-vm04-relink-endpoint-check-v1-" + reviewed_code[:12])
    check_receipt, _ = audit._marker(check_stage, "check")
    require(check_receipt["reviewed_code"] == reviewed_code and
            check_receipt["bound_sha256"] == bindings and
            check_receipt["requested_workers"] ==
            check_receipt["actual_workers"] == 2,
            "endpoint pure check/code marker changed")
    memory, gpu = mechanism.resource_sample()
    disk = shutil.disk_usage(output_root.resolve()).free
    cpus = old_probe.safe_visible_cpu_count()
    source_memory_demand = mechanism_receipt["resource_evidence"][
        "observed_cgroup_demand_bytes"]
    source_gpu_demand = mechanism_receipt["resource_evidence"][
        "observed_gpu_demand_bytes"]
    require(cpus >= 4 and memory >= max(
                config["minimum_static_cgroup_headroom_bytes"],
                config["minimum_cgroup_headroom_to_four_source_workers_ratio"]
                * 4 * source_memory_demand) and
            gpu >= max(config["minimum_static_gpu_free_bytes"],
                       config["minimum_gpu_headroom_to_four_source_workers_ratio"]
                       * 4 * source_gpu_demand) and
            disk >= config["minimum_static_data_disk_free_bytes"],
            "four independent endpoint workers lack fresh resource headroom")
    simulator = Path(audit.read_json(audit.ENVIRONMENT_PATH)[
        "environment_separation"]["simulator_process"]["environment_path"]) / "bin/python"
    require(simulator.is_file(), "frozen simulator Python missing")
    stage = output_root.resolve() / ("vsmt-vm04-relink-endpoint-v1-" +
                                   reviewed_code[:12])
    require(not stage.exists(), "endpoint stage exists: preserve it")
    (stage / "private").mkdir(parents=True)
    environment = dict(os.environ, PYTHONUNBUFFERED="1", OMP_NUM_THREADS="1",
                       OPENBLAS_NUM_THREADS="1",
                       XDG_RUNTIME_DIR=str(output_root.resolve() / "runtime"))
    Path(environment["XDG_RUNTIME_DIR"]).mkdir(parents=True, exist_ok=True)
    shared = ["--source-stage", str(source_stage.resolve()),
              "--scan-stage", str(scan_stage.resolve()),
              "--source-root", str(source_root.resolve()),
              "--mechanism-stage", str(mechanism_stage.resolve()),
              "--stage", str(stage)]
    children = []
    dispatch_error = None
    started = time.monotonic()
    for task in tasks:
        family_id, slot = task["family_id"], task["slot"]
        private_root = stage / "private" / family_id
        private_root.mkdir(parents=True, exist_ok=True)
        log = private_root / ("slot_%02d.log" % slot)
        try:
            with log.open("x", encoding="utf-8") as handle:
                child = subprocess.Popen([str(simulator), "-B",
                    str(Path(__file__).resolve()), "worker", *shared,
                    "--family-id", family_id, "--slot", str(slot)],
                    cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT,
                    env=environment)
            children.append((task, child, log))
        except Exception as error:
            dispatch_error = {"phase": "worker_dispatch",
                              "error_type": type(error).__name__,
                              "error": str(error)}
            break
    samples = []
    while any(child.poll() is None for _, child, _ in children):
        try:
            current_memory, current_gpu = mechanism.resource_sample()
            samples.append({"elapsed_seconds": time.monotonic() - started,
                            "cgroup_headroom_bytes": current_memory,
                            "gpu_free_bytes": current_gpu})
            require(current_memory > 4294967296 and current_gpu > 4294967296,
                    "active endpoint workers exceeded emergency RAM/GPU protection")
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
    for task, child, log in children:
        code = child.wait()
        print("[%s:%02d] %s" % (task["family_id"], task["slot"],
              log.read_text(encoding="utf-8")), end="", flush=True)
        private_path = (stage / "private" / task["family_id"] /
                        ("slot_%02d.json" % task["slot"]))
        exits.append({"family_id": task["family_id"], "slot": task["slot"],
                      "exit_code": code,
                      "private_slot_sha256": audit.sha256(private_path)
                      if private_path.is_file() else None,
                      "private_log_sha256": audit.sha256(log)})
    sample_path = stage / "private/resource-samples.json"
    audit.write_new_json(sample_path, {
        "schema_version": "vsmt-vm04-relink-endpoint-resource-samples-v1",
        "initial_cgroup_headroom_bytes": memory,
        "initial_gpu_free_bytes": gpu, "samples": samples})
    success = dispatch_error is None and len(children) == 4 and all(
        row["exit_code"] == 0 and row["private_slot_sha256"] is not None
        for row in exits)
    receipt = stage / "endpoint.receipt.json"
    audit.write_new_json(receipt, {
        "schema_version": "vsmt-vm04-relink-endpoint-receipt-v1",
        "reviewed_code": reviewed_code, "bound_sha256": bindings,
        "source_v1_action_probe_receipt_sha256":
            config["source_v1_action_probe_receipt_sha256"],
        "source_v2_scan_receipt_sha256":
            config["source_v2_scan_receipt_sha256"],
        "source_physics_public_report_sha256":
            config["source_physics_attribution_public_report_sha256"],
        "check_receipt_sha256": audit.sha256(
            check_stage / "check.receipt.json"),
        "requested_workers": 4, "actual_workers": len(children),
        "worker_exits": exits, "dispatch_error": dispatch_error,
        "deterministic_merge_order": [{"family_id": row["family_id"],
                                        "slot": row["slot"]} for row in tasks],
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
        audit.write_new_json(stage / "endpoint.success.json", {
            "schema_version": "vsmt-vm04-relink-endpoint-success-v1",
            "receipt_sha256": audit.sha256(receipt), "success": True})
    print("RELINK_ENDPOINT_%s stage=%s workers=%s" %
          ("OK" if success else "FAILED", stage, len(children)), flush=True)
    require(success, "four original RELINK endpoint diagnoses incomplete")


def export(reviewed_code, stage):
    config, _ = load_config()
    bindings = binding_sha256(reviewed_code)
    receipt, _ = audit._marker(stage, "endpoint")
    require(receipt["reviewed_code"] == reviewed_code and
            receipt["bound_sha256"] == bindings and
            receipt["requested_workers"] == receipt["actual_workers"] == 4 and
            receipt["source_v1_action_probe_receipt_sha256"] ==
            config["source_v1_action_probe_receipt_sha256"] and
            receipt["source_v2_scan_receipt_sha256"] ==
            config["source_v2_scan_receipt_sha256"] and
            receipt["episodes_generated"] == receipt["training_steps"] == 0 and
            not EXPORT_PATH.exists(), "endpoint receipt/code/export changed")
    sample_path = stage / "private/resource-samples.json"
    require(audit.sha256(sample_path) == receipt["resource_evidence"][
            "private_samples_sha256"], "endpoint resource trace changed")
    counts = {}
    for row in receipt["worker_exits"]:
        family_id, slot = row["family_id"], row["slot"]
        private_path = (stage / "private" / family_id /
                        ("slot_%02d.json" % slot))
        log = (stage / "private" / family_id /
               ("slot_%02d.log" % slot))
        require(row["exit_code"] == 0 and
                audit.sha256(private_path) == row["private_slot_sha256"] and
                audit.sha256(log) == row["private_log_sha256"],
                "private endpoint original slot/log changed")
        private = audit.read_json(private_path)
        require(private["family_id"] == family_id and private["slot"] == slot and
                private["trial"]["target_object_id"] ==
                private["trial"]["registered_request"]["objectId"] and
                private["memory_history_checked"] is False and
                private["semantic_positive_label_issued"] is False,
                "endpoint original identity/semantic boundary changed")
        status = private["endpoint_verdict"]["status"]
        key = (family_id, status)
        counts[key] = counts.get(key, 0) + 1
    require(sum(counts.values()) == 4,
            "all four original RELINK slots must be represented")
    rows = [{"family_id": family, "status": status, "count": count}
            for (family, status), count in sorted(counts.items())]
    audit.write_new_json(EXPORT_PATH, {
        "schema_version": "vsmt-vm04-relink-endpoint-two-house-public-report-v1",
        "status": "all_four_original_relink_endpoint_diagnostic_only",
        "reviewed_code": reviewed_code,
        "endpoint_receipt_sha256": audit.sha256(stage / "endpoint.receipt.json"),
        "source_v1_probe_receipt_sha256":
            config["source_v1_action_probe_receipt_sha256"],
        "source_v2_scan_receipt_sha256":
            config["source_v2_scan_receipt_sha256"],
        "source_physics_attribution_public_report_sha256":
            config["source_physics_attribution_public_report_sha256"],
        "counts_by_family_status": rows,
        "requested_workers": 4, "actual_workers": 4,
        "resource_evidence": receipt["resource_evidence"],
        "private_ids_exported": False,
        "robot_manipulation_path_reachability_checked": False,
        "memory_history_checked": False,
        "semantic_positive_labels_issued": 0,
        "episodes_generated": 0, "training_steps": 0})
    print("RELINK_ENDPOINT_EXPORT_OK report=%s slots=4" % EXPORT_PATH,
          flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=("contract", "check", "run", "worker",
                                         "export"))
    parser.add_argument("--reviewed-code")
    parser.add_argument("--source-stage", type=Path)
    parser.add_argument("--scan-stage", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--mechanism-stage", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--stage", type=Path)
    parser.add_argument("--family-id")
    parser.add_argument("--slot", type=int)
    args = parser.parse_args()
    if args.step == "contract":
        config, _ = load_config()
        print("RELINK_ENDPOINT_CONTRACT_OK status=%s generation=false training=false" %
              config["status"])
    elif args.step == "check":
        check(args.reviewed_code, args.output_root)
    elif args.step == "run":
        run(args.reviewed_code, args.source_stage, args.scan_stage,
            args.source_root, args.mechanism_stage, args.output_root)
    elif args.step == "worker":
        run_worker(args)
    else:
        export(args.reviewed_code, args.stage)


if __name__ == "__main__":
    main()
