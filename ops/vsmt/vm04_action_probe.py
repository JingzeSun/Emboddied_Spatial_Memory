#!/usr/bin/env python3
"""Review-gated, fixed-two-house action capability probe; generation stays closed."""

from __future__ import annotations

import argparse
import re
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import vm04_two_house_audit as audit  # noqa: E402
import vm04_two_house_worker as generator  # noqa: E402
from vsmt.two_house_audit import validate_episode_plans  # noqa: E402
from vsmt.vm04_target_eligibility import authored_asset_ids  # noqa: E402

CONFIG_PATH = PROJECT_ROOT / "configs/vsmt/vm04_action_capability_probe_proposal_v1.json"
SCAN_REPORT_PATH = PROJECT_ROOT / "results/vsmt_vm04_viewpoint_scan_v1.json"
EXPORT_PATH = PROJECT_ROOT / "results/vsmt_vm04_action_capability_probe_v1.json"
BOUND_FILES = (
    "configs/vsmt/vm04_action_capability_probe_proposal_v1.json",
    "ops/vsmt/vm04_action_probe.py",
    "ops/vsmt/vm04_action_probe_worker.py",
    "ops/vsmt/vm04_two_house_worker.py",
    "src/vsmt/vm04_target_eligibility.py",
    "tests/test_vm04_action_probe.py",
    "tests/test_vm04_target_eligibility.py",
)
CHECK_GROUPS = (
    ("contract", (
        "test_proposed_contract_and_run_gate",
        "test_approved_status_requires_reviewed_commit",
        "test_scan_live_target_mismatch_stops_without_intervention",
    )),
    ("actions", (
        "test_setup_action_failure_keeps_simulator_diagnostic",
        "test_relink_missing_true_position_is_recorded_without_teleport",
        "test_retract_replays_registered_yaw_before_frame_22",
    )),
    ("timing_and_public", (
        "test_reactivate_frame_16_failure_preserves_phase_and_code",
        "test_replace_keeps_secondary_setup_and_enable_target",
        "test_public_report_contains_counts_and_hash_not_private_ids",
    )),
    ("source_boundary", (
        "tests.test_vm04_target_eligibility.TargetBoundaryTests.test_author_house_hierarchy_excludes_architecture_and_keeps_children",
        "tests.test_vm04_target_eligibility.TargetBoundaryTests.test_profiles_preserve_geometry_rank_and_ignore_object_class_text",
        "tests.test_vm04_target_eligibility.TargetBoundaryTests.test_missing_real_position_and_duplicate_rank_are_rejected",
    )),
)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def validate_config(value):
    require(value.get("version") == "vsmt-vm04-action-capability-probe-proposal-v1",
            "wrong action-probe contract version")
    require(value["minimum_position_spacing_m"] == 1.0 and
            value["target_repeat_policy"] ==
            "report_only_no_pose_target_or_house_reselection", "frozen D/target policy changed")
    require(value["source_scan_reviewed_code"] ==
            "67099f2597cc863b58029fcaec2c5165266e2633" and
            value["source_scan_receipt_sha256"] ==
            "044fd705e998b1dea9bc62bdd730ff2fc583f9880901131f8927aefb10bb9fd5" and
            value["source_scan_report_sha256"] ==
            "575d34d084864009bc847e4b91ba144279408dc6a28f0a3e8e1433157a089f32" and
            value["planning_selection_receipt_sha256"] ==
            "7aa29f63f0f71d04fa3cc2613867afb08f22559d7fbe1282225d23030e5f62b9",
            "fixed source scan/planning binding changed")
    require(value["source_public_episode_manifest_sha256"] ==
            "403a7039cea8d8097fca1344d0041bc021ee6a231cfbede38066e690ab1bf406" and
            value["source_private_episode_manifest_sha256"] ==
            "cb8e05aea4da7f92b9463adf411986e0183f8a6660217a4bd08f6b5ac36ecaa4",
            "frozen source episode plans changed")
    require(value["fixed_family_ids"] == ["audit-family:00", "audit-family:01"] and
            value["fixed_source_house_ids"] == ["train:004270", "train:008243"],
            "fixed families/houses changed")
    require(value["target_source"] ==
            "digest_verified_private_scan_spaced_top_18_checked_against_live_masks" and
            value["program_source"] ==
            "frozen_private_episode_plan_same_zero_based_family_slot" and
            value["probe_policy"] ==
            "fresh_controller_per_fixed_slot_registered_actions_until_last_intervention_no_frame_capture" and
            value["required_check_receipt_before_probe"] is True and
            value["failure_policy"] ==
            "record_each_fixed_slot_no_retry_no_replacement_no_result_driven_threshold" and
            value["no_intervention_programs"] ==
            ["NOOP", "BIND", "SPLIT", "MERGE"] and
            value["intervention_programs"] ==
            ["BIRTH", "REACTIVATE", "RELINK", "RETRACT", "REPLACE"],
            "probe target/program/action/failure scope changed")
    require(value["generation_authorized"] is False and
            value["training_authorized"] is False,
            "action probe must never authorize generation or training")
    require(value["implementation_authorized"] is True,
            "probe implementation must be reviewed independently")
    if value["status"] in ("approved_for_implementation_not_executable",
                            "blocked_invalid_v2_scan_targets"):
        require(value["probe_execution_authorized"] is False and
                value["expected_reviewed_probe_code"] is None,
                "closed proposed probe has an executable field")
        if value["status"] == "blocked_invalid_v2_scan_targets":
            require(value["blocking_reason"] ==
                    "70_of_72_v2_scan_top2_are_not_author_house_objects_assets",
                    "blocked invalid-scan reason changed")
    elif value["status"] == "frozen_executable":
        require(value["probe_execution_authorized"] is True and
                isinstance(value["expected_reviewed_probe_code"], str) and
                re.fullmatch(r"[0-9a-f]{40}",
                             value["expected_reviewed_probe_code"]) is not None,
                "executable probe requires an exact reviewed commit")
    else:
        raise RuntimeError("unknown action-probe status")
    resources = value["worker_policy"]
    require(resources["requested_family_workers"] == 2 and
            resources["minimum_visible_cpu_count"] == 2 and
            resources["minimum_cgroup_memory_headroom_bytes"] == 8589934592 and
            resources["minimum_free_gpu_bytes"] == 8589934592 and
            resources["minimum_free_data_disk_bytes"] == 8589934592 and
            resources["maximum_worker_address_space_bytes"] == 42949672960 and
            resources["maximum_private_slot_json_bytes"] == 1048576 and
            resources["no_wall_clock_failure_limit"] is True,
            "fixed two-family resource/concurrency policy changed")
    return value


def load_config():
    return validate_config(audit.read_json(CONFIG_PATH))


def verify_code(reviewed_code):
    require(audit.git("rev-parse", "--show-toplevel") and
            Path(audit.git("rev-parse", "--show-toplevel")).resolve() ==
            PROJECT_ROOT.resolve(), "project checkout root changed")
    require(audit.git("rev-parse", "HEAD") == reviewed_code and
            not audit.git("status", "--porcelain"),
            "reviewed code must be exact HEAD in a clean checkout")
    return {relative: audit.sha256(PROJECT_ROOT / relative) for relative in BOUND_FILES}


def verify_reviewed_implementation(config):
    """A later gate commit may descend from the already reviewed code commit."""
    reviewed = config["expected_reviewed_probe_code"]
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", reviewed,
                               audit.git("rev-parse", "HEAD")], cwd=PROJECT_ROOT)
    require(ancestor.returncode == 0, "reviewed probe code is not an ancestor")
    implementation = ["ops/vsmt/vm04_action_probe.py",
                      "ops/vsmt/vm04_action_probe_worker.py",
                      "src/vsmt/vm04_target_eligibility.py",
                      "tests/test_vm04_action_probe.py",
                      "tests/test_vm04_target_eligibility.py"]
    unchanged = subprocess.run(["git", "diff", "--quiet", reviewed, "HEAD", "--",
                                *implementation], cwd=PROJECT_ROOT)
    require(unchanged.returncode == 0,
            "probe implementation changed after user code review")


def scan_inputs(config, scan_stage, source_root):
    """Read-only verification before a probe stage or simulator is created."""
    scan = scan_stage.resolve()
    receipt, _ = audit._marker(scan, "scan")
    report = audit.read_json(SCAN_REPORT_PATH)
    require(audit.sha256(SCAN_REPORT_PATH) ==
            config["source_scan_report_sha256"],
            "source scan public report digest changed")
    require(receipt["reviewed_code"] == config["source_scan_reviewed_code"] ==
            report["source_scan_reviewed_code"] and
            audit.sha256(scan / "scan.receipt.json") ==
            config["source_scan_receipt_sha256"] == report["scan_receipt_sha256"],
            "source scan reviewed code or receipt hash changed")
    require(receipt["planning_selection_receipt_sha256"] ==
            config["planning_selection_receipt_sha256"] ==
            report["planning_selection_receipt_sha256"],
            "source planning selection hash changed")
    require(receipt["minimum_position_spacing_m"] ==
            config["minimum_position_spacing_m"] and
            receipt["episode_generation_performed"] is False,
            "source scan D or generation boundary changed")
    require(receipt["worker_code_sha256"] ==
            audit.sha256(PROJECT_ROOT / "ops/vsmt/vm04_two_house_worker.py"),
            "generator action semantics differ from scanned source")
    for relative, digest in report["bound_sha256"].items():
        require(audit.sha256(PROJECT_ROOT / relative) == digest,
                "scanned source binding changed: " + relative)
    plans = validate_episode_plans({
        "public": audit.read_json(scan / "public/episode_plan.json"),
        "private": audit.read_json(scan / "private/episode_plan.json"),
    })
    require(len(plans["public"]["episodes"]) == 36 and
            plans["public"]["manifest_sha256"] ==
            config["source_public_episode_manifest_sha256"] and
            plans["private"]["manifest_sha256"] ==
            config["source_private_episode_manifest_sha256"],
            "source scan episode plans changed")
    require(all(not (scan / "execution" / family / "episodes").exists()
                for family in config["fixed_family_ids"]),
            "source scan has unexpected episode artifacts")
    families = sorted(receipt["families"], key=lambda row: row["family_id"])
    require([row["family_id"] for row in families] ==
            config["fixed_family_ids"] and
            [row["source_house_id"] for row in families] ==
            config["fixed_source_house_ids"], "scan families/houses changed")
    for family in families:
        root = scan / "execution" / family["family_id"]
        for relative, field in (
            ("scan.worker.receipt.json", "worker_receipt_sha256"),
            ("initial_viewpoints.json", "family_viewpoints_sha256"),
            ("private/viewpoint-target-audit.json",
             "private_viewpoint_target_audit_sha256"),
        ):
            require(audit.sha256(root / relative) == family[field],
                    "scan family artifact hash changed: " + relative)
        public = audit.read_json(root / "initial_viewpoints.json")
        private = audit.read_json(root / "private/viewpoint-target-audit.json")
        require(public["selected_pose_count"] == 18 and
                public["minimum_pose_separation_m"] == 1.0 and
                [row["rank_index"] for row in private["spaced_top_18"]] ==
                public["selected_pose_rank_indices"],
                "scan selected pose/target rule changed")
    inventory = audit.validate_source_inventory(
        audit.read_json(scan / "private/inventory.json")
    )
    selection = audit.validate_house_selection(
        audit.read_json(scan / "selection.json"), inventory=inventory
    )
    source_config = audit.load_config()["source_inventory_proposal"]
    require(inventory["source_manifest_sha256"] ==
            source_config["source_manifest_sha256"] and
            selection["selection_sha256"] ==
            audit.load_config()["planning_stage_binding"]["selection_sha256"],
            "source inventory/selection changed")
    require(selection["audit_house_ids"] == config["fixed_source_house_ids"],
            "source selection changed")
    require(audit.git("rev-parse", "HEAD", cwd=source_root.resolve()) ==
            source_config["data_release_commit"],
            "source checkout release commit changed")
    for family in families:
        house_id = family["source_house_id"]
        source_row = next(row for row in inventory["houses"]
                          if row["house_id"] == house_id)
        locator = source_row["source_locator"]
        source_file = (source_root.resolve() / locator["relative_path"]).resolve()
        require(source_root.resolve() in source_file.parents and
                audit.sha256(source_file) == source_row["source_file_sha256"],
                "frozen source asset file changed")
        house = generator.load_source_record(source_root, locator)
        require(generator.canonical_sha256(house) ==
                source_row["source_record_sha256"],
                "frozen source asset record changed")
        asset_ids = authored_asset_ids(house)
        private_rows = audit.read_json(
            scan / "execution" / family["family_id"] /
            "private/viewpoint-target-audit.json"
        )["spaced_top_18"]
        require(all(target_id in asset_ids for row in private_rows
                    for target_id in row["target_instance_ids"][:2]),
                "v2 scan top2 includes architecture: action probe is blocked")
    return receipt, families


def resource_evidence(config, output_root):
    rules = config["worker_policy"]
    cpus = os.cpu_count() or 0
    disk = shutil.disk_usage(output_root.resolve()).free
    memory_headroom = audit._cgroup_memory_headroom_bytes()
    gpu = subprocess.check_output([
        "nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits",
    ], text=True).splitlines()
    gpu_free = max(int(line.strip()) for line in gpu) * 1024 * 1024
    require(cpus >= rules["minimum_visible_cpu_count"] and
            disk >= rules["minimum_free_data_disk_bytes"] and
            memory_headroom is not None and
            memory_headroom >= rules["minimum_cgroup_memory_headroom_bytes"] and
            gpu_free >= rules["minimum_free_gpu_bytes"],
            "two family workers lack fresh CPU/cgroup/GPU/disk headroom")
    return {"visible_cpu_count": cpus,
            "cgroup_memory_headroom_bytes": memory_headroom,
            "free_gpu_bytes_on_one_device": gpu_free,
            "visible_gpu_count": len(gpu), "free_data_disk_bytes": disk,
            "prior_two_family_scan_receipt_sha256":
                config["source_scan_receipt_sha256"]}


def check(reviewed_code, output_root):
    """Three independent pure test workers; no simulator process."""
    config = load_config()
    bindings = verify_code(reviewed_code)
    cpus = os.cpu_count() or 0
    headroom = audit._cgroup_memory_headroom_bytes()
    free_disk = shutil.disk_usage(output_root.resolve()).free
    require(cpus >= 4 and headroom is not None and headroom >= 4294967296 and
            free_disk >= 1073741824,
            "probe check lacks capacity for three independent test workers")
    stage = output_root.resolve() / ("vsmt-vm04-action-probe-check-v1-" +
                                     reviewed_code[:12])
    require(not stage.exists(), "probe check stage already exists: preserve it")
    stage.mkdir(parents=True)
    started = time.monotonic()
    children = []
    dispatch_error = None
    for group, names in CHECK_GROUPS:
        log_path = stage / (group + ".log")
        command = [sys.executable, "-B", "-m", "unittest", "-v", *[
            name if name.startswith("tests.") else
            "tests.test_vm04_action_probe.ActionProbeTests." + name
            for name in names
        ]]
        try:
            with log_path.open("x", encoding="utf-8") as handle:
                child = subprocess.Popen(command, cwd=PROJECT_ROOT,
                                         stdout=handle, stderr=subprocess.STDOUT)
            children.append((group, child, log_path))
        except Exception as error:
            dispatch_error = {"group": group, "error_type": type(error).__name__,
                              "error": str(error)}
            break
    exits = []
    for group, child, log_path in children:
        code = child.wait()
        output = log_path.read_text(encoding="utf-8")
        print("[%s] %s" % (group, output), end="", flush=True)
        exits.append({"group": group, "exit_code": code,
                      "log_sha256": audit.sha256(log_path),
                      "expected_test_count": 3,
                      "passed_test_count": 3 if code == 0 and
                      "Ran 3 tests" in output and "FAILED" not in output else 0})
    success = (dispatch_error is None and len(exits) == 4 and
               all(row["passed_test_count"] == 3 for row in exits))
    receipt_path = stage / "check.receipt.json"
    audit.write_new_json(receipt_path, {
        "schema_version": "vsmt-vm04-action-probe-check-receipt-v1",
        "reviewed_code": reviewed_code, "bound_sha256": bindings,
        "config_status": config["status"],
        "requested_workers": 4, "actual_workers": len(children),
        "worker_exits": exits, "dispatch_error": dispatch_error,
        "resource_evidence": {"visible_cpu_count": cpus,
                              "cgroup_memory_headroom_bytes": headroom,
                              "free_data_disk_bytes": free_disk},
        "deterministic_merge_order": [row[0] for row in CHECK_GROUPS],
        "expected_test_count": 12,
        "passed_test_count": sum(row["passed_test_count"] for row in exits),
        "wall_seconds": time.monotonic() - started,
        "simulator_started": False, "episodes_generated": 0,
        "success": success,
    })
    if success:
        audit.write_new_json(stage / "check.success.json", {
            "schema_version": "vsmt-vm04-action-probe-check-success-v1",
            "receipt_sha256": audit.sha256(receipt_path), "success": True,
        })
    print("VM04_ACTION_PROBE_CHECK_%s stage=%s workers=%s tests=%s/12" %
          ("OK" if success else "FAILED", stage, len(children),
           sum(row["passed_test_count"] for row in exits)), flush=True)
    require(success, "probe check failed: preserve check stage")


def run(reviewed_code, scan_stage, source_root, output_root):
    config = load_config()
    require(config["probe_execution_authorized"] is True and
            config["status"] == "frozen_executable",
            "action probe execution is closed pending user code review")
    bindings = verify_code(reviewed_code)
    verify_reviewed_implementation(config)
    check_stage = output_root.resolve() / ("vsmt-vm04-action-probe-check-v1-" +
                                           reviewed_code[:12])
    check_receipt, _ = audit._marker(check_stage, "check")
    require(check_receipt["reviewed_code"] == reviewed_code and
            check_receipt["bound_sha256"] == bindings and
            check_receipt["requested_workers"] == 4 and
            check_receipt["actual_workers"] == 4 and
            check_receipt["passed_test_count"] == 12 and
            check_receipt["deterministic_merge_order"] ==
            [group for group, _ in CHECK_GROUPS] and
            all(row["exit_code"] == 0 and
                audit.sha256(check_stage / (row["group"] + ".log")) ==
                row["log_sha256"] for row in check_receipt["worker_exits"]),
            "probe check receipt/code/log chain changed")
    receipt, families = scan_inputs(config, scan_stage, source_root)
    evidence = resource_evidence(config, output_root)
    simulator = Path(audit.read_json(audit.ENVIRONMENT_PATH)[
        "environment_separation"]["simulator_process"]["environment_path"]) / "bin/python"
    require(simulator.is_file(), "frozen simulator Python is missing")
    stage = output_root.resolve() / ("vsmt-vm04-action-probe-v1-" + reviewed_code[:12])
    require(not stage.exists(), "probe stage already exists: preserve it")
    stage.mkdir(parents=True)
    environment = dict(os.environ, PYTHONUNBUFFERED="1", OMP_NUM_THREADS="1",
                       OPENBLAS_NUM_THREADS="1",
                       XDG_RUNTIME_DIR=str(output_root.resolve() / "runtime"))
    Path(environment["XDG_RUNTIME_DIR"]).mkdir(parents=True, exist_ok=True)
    children = []
    started = time.monotonic()
    dispatch_error = None
    for family in families:
        family_id = family["family_id"]
        log_path = stage / "private" / (family_id + ".worker.log")
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("x", encoding="utf-8") as log:
                completed = subprocess.Popen([
                    str(simulator), "-B",
                    str(PROJECT_ROOT / "ops/vsmt/vm04_action_probe_worker.py"),
                    "--scan-stage", str(scan_stage.resolve()), "--probe-stage", str(stage),
                    "--source-root", str(source_root.resolve()), "--family-id", family_id,
                    "--maximum-slot-json-bytes",
                    str(config["worker_policy"]["maximum_private_slot_json_bytes"]),
                    "--maximum-address-space-bytes",
                    str(config["worker_policy"]["maximum_worker_address_space_bytes"]),
                ], stdout=log, stderr=subprocess.STDOUT, env=environment)
            children.append((family_id, completed, log_path))
        except Exception as error:
            dispatch_error = {"family_id": family_id,
                              "error_type": type(error).__name__, "error": str(error)}
            break
    exits = [{"family_id": family_id, "exit_code": child.wait(),
              "log_sha256": audit.sha256(log_path)}
             for family_id, child, log_path in children]
    worker_receipts = []
    for family_id, _, _ in children:
        path = stage / "execution" / family_id / "private/worker.receipt.json"
        if path.is_file():
            worker_receipts.append({"family_id": family_id,
                                    "sha256": audit.sha256(path)})
    success = (dispatch_error is None and
               all(row["exit_code"] == 0 for row in exits) and
               len(worker_receipts) == 2)
    terminal = stage / "probe.receipt.json"
    audit.write_new_json(terminal, {
        "schema_version": "vsmt-vm04-action-probe-receipt-v1",
        "reviewed_code": reviewed_code, "bound_sha256": bindings,
        "scan_receipt_sha256": audit.sha256(scan_stage / "scan.receipt.json"),
        "check_receipt_sha256": audit.sha256(check_stage / "check.receipt.json"),
        "planning_selection_receipt_sha256": receipt[
            "planning_selection_receipt_sha256"],
        "requested_workers": 2, "actual_workers": len(children),
        "resource_evidence": evidence,
        "worker_exits": exits, "family_worker_receipts": worker_receipts,
        "dispatch_error": dispatch_error,
        "deterministic_merge_order": config["fixed_family_ids"],
        "wall_seconds": time.monotonic() - started,
        "episodes_generated": 0, "frames_captured": 0,
        "training_steps": 0, "success": success,
    })
    if success:
        audit.write_new_json(stage / "probe.success.json", {
            "schema_version": "vsmt-vm04-action-probe-success-v1",
            "receipt_sha256": audit.sha256(terminal), "success": True,
        })
    print("VM04_ACTION_PROBE_%s stage=%s workers=2 exits=%s episodes=0" %
          ("OK" if success else "FAILED", stage,
           [row["exit_code"] for row in exits]), flush=True)
    require(success, "action probe has worker failure; preserve stage for audit")


def public_report_payload(reviewed_code, receipt_sha256, receipt, rows):
    """Only count rows and digest commitments enter the public report."""
    require(sum(row["count"] for row in rows) == 36,
            "public report requires all 36 fixed slots")
    return {
        "schema_version": "vsmt-vm04-action-probe-public-report-v1",
        "reviewed_code": reviewed_code,
        "probe_receipt_sha256": receipt_sha256,
        "scan_receipt_sha256": receipt["scan_receipt_sha256"],
        "counts_by_family_program_status": rows,
        "requested_workers": receipt["requested_workers"],
        "actual_workers": receipt["actual_workers"],
        "worker_exits": receipt["worker_exits"],
        "episodes_generated": 0, "frames_captured": 0,
        "training_steps": 0,
    }


def export(reviewed_code, stage):
    config = load_config()
    require(config["probe_execution_authorized"] and
            config["status"] == "frozen_executable",
            "action probe export is closed pending user code review")
    bindings = verify_code(reviewed_code)
    verify_reviewed_implementation(config)
    stage = stage.resolve()
    receipt, _ = audit._marker(stage, "probe")
    require(receipt["reviewed_code"] == reviewed_code and
            receipt["bound_sha256"] == bindings and
            receipt["scan_receipt_sha256"] ==
            config["source_scan_receipt_sha256"],
            "probe receipt/current code/source scan binding changed")
    check_stage = stage.parent / ("vsmt-vm04-action-probe-check-v1-" +
                                  reviewed_code[:12])
    check_receipt, _ = audit._marker(check_stage, "check")
    require(check_receipt["reviewed_code"] == reviewed_code and
            audit.sha256(check_stage / "check.receipt.json") ==
            receipt["check_receipt_sha256"],
            "probe check receipt binding changed before export")
    require(not EXPORT_PATH.exists(), "probe export already exists: preserve it")
    aggregate = {}
    for family in receipt["family_worker_receipts"]:
        root = stage / "execution" / family["family_id"]
        worker_path = root / "private/worker.receipt.json"
        require(audit.sha256(worker_path) == family["sha256"],
                "probe family receipt changed")
        worker = audit.read_json(worker_path)
        require(worker["fixed_slot_count"] == 18 and
                [row["slot"] for row in worker["slots"]] == list(range(18)) and
                worker["episodes_generated"] == worker["frames_captured"] == 0,
                "probe worker fixed-slot or capture boundary changed")
        for row in worker["slots"]:
            path = root / "private" / ("slot_%02d.json" % row["slot"])
            require(audit.sha256(path) == row["private_slot_sha256"],
                    "private slot diagnosis changed")
            slot = audit.read_json(path)
            require(slot["status"] == row["status"] and
                    slot["program"] == row["program"],
                    "private slot diagnosis/receipt disagreement")
            key = (family["family_id"], row["program"], row["status"])
            aggregate[key] = aggregate.get(key, 0) + 1
    rows = [{"family_id": family, "program": program, "status": status,
             "count": count} for (family, program, status), count in
            sorted(aggregate.items())]
    audit.write_new_json(EXPORT_PATH, public_report_payload(
        reviewed_code, audit.sha256(stage / "probe.receipt.json"), receipt, rows
    ))
    print("VM04_ACTION_PROBE_EXPORT_OK report=%s slots=36" % EXPORT_PATH)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["contract", "check", "run", "export"])
    parser.add_argument("--reviewed-code")
    parser.add_argument("--scan-stage", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--probe-stage", type=Path)
    args = parser.parse_args()
    if args.action == "contract":
        config = load_config()
        print("VM04_ACTION_PROBE_CONTRACT_OK status=%s execution=%s generation=false" %
              (config["status"], config["probe_execution_authorized"]))
    elif args.action == "check":
        require(args.reviewed_code and args.output_root,
                "check needs reviewed code and output root")
        check(args.reviewed_code, args.output_root)
    elif args.action == "run":
        require(all(value is not None for value in
                    (args.reviewed_code, args.scan_stage, args.source_root,
                     args.output_root)), "run needs reviewed code and frozen paths")
        run(args.reviewed_code, args.scan_stage, args.source_root, args.output_root)
    else:
        require(args.reviewed_code and args.probe_stage,
                "export needs reviewed code and probe stage")
        export(args.reviewed_code, args.probe_stage)


if __name__ == "__main__":
    main()
