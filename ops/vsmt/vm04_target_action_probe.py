#!/usr/bin/env python3
"""Review-gated v3 target action probe over two frozen houses; no episodes."""

from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import vm04_two_house_audit as audit  # noqa: E402
import vm04_two_house_worker as generator  # noqa: E402
from vsmt.two_house_audit import validate_episode_plans  # noqa: E402
from vsmt.vm04_target_contract import validate_target_boundary_proposal  # noqa: E402

CONFIG_PATH = ROOT / "configs/vsmt/vm04_target_action_probe_proposal_v2.json"
TARGET_CONTRACT_PATH = ROOT / "configs/vsmt/vm04_target_boundary_proposal_v3.json"
SCAN_REPORT_PATH = ROOT / "results/vsmt_vm04_viewpoint_scan_v1.json"
EXPORT_PATH = ROOT / "results/vsmt_vm04_target_action_probe_v2.json"
BOUND_FILES = (
    "configs/vsmt/vm04_target_action_probe_proposal_v2.json",
    "configs/vsmt/vm04_target_boundary_proposal_v3.json",
    "ops/vsmt/vm04_target_action_probe.py",
    "ops/vsmt/vm04_target_action_probe_worker.py",
    "ops/vsmt/vm04_two_house_worker.py",
    "src/vsmt/vm04_target_contract.py",
    "src/vsmt/vm04_target_eligibility.py",
    "src/vsmt/vm04_target_selection_v3.py",
    "tests/test_vm04_target_action_probe.py",
    "tests/test_vm04_target_action_probe_worker.py",
    "tests/test_vm04_target_contract.py",
    "tests/test_vm04_target_selection_v3.py",
    "tests/test_vm04_config_digest_shapes.py",
    "tests/test_vm04_target_eligibility.py",
    "tests/test_vm04_action_probe.py",
    "tests/test_vm04_root_cause_audit.py",
    "tests/test_vm04_target_repetition_export.py",
)
CHECK_GROUPS = (
    ("contract_and_eligibility", (
        "tests.test_vm04_target_contract",
        "tests.test_vm04_target_selection_v3",
        "tests.test_vm04_config_digest_shapes",
        "tests.test_vm04_target_eligibility",
    )),
    ("action_and_terminal", (
        "tests.test_vm04_target_action_probe_worker",
        "tests.test_vm04_action_probe",
    )),
    ("stage_and_export", (
        "tests.test_vm04_target_action_probe",
        "tests.test_vm04_root_cause_audit",
        "tests.test_vm04_target_repetition_export",
    )),
)


def require(test, message):
    if not test:
        raise RuntimeError(message)


def load_config():
    value = audit.read_json(CONFIG_PATH)
    target = validate_target_boundary_proposal(audit.read_json(TARGET_CONTRACT_PATH))
    require(value.get("version") == "vsmt-vm04-v3-target-action-probe-proposal-v2",
            "wrong v3 target-probe version")
    require(value["v3_target_contract_sha256"] == audit.sha256(TARGET_CONTRACT_PATH),
            "v3 target contract digest changed")
    for key, expected in (
        ("source_scan_reviewed_code", "67099f2597cc863b58029fcaec2c5165266e2633"),
        ("source_scan_receipt_sha256", target["source_v2_scan_receipt_sha256"]),
        ("source_scan_report_sha256", target["source_v2_scan_report_sha256"]),
        ("planning_selection_receipt_sha256",
         "7aa29f63f0f71d04fa3cc2613867afb08f22559d7fbe1282225d23030e5f62b9"),
        ("source_public_episode_manifest_sha256",
         target["source_public_episode_manifest_sha256"]),
        ("source_private_episode_manifest_sha256",
         target["source_private_episode_manifest_sha256"]),
        ("fixed_source_house_ids", target["fixed_source_house_ids"]),
        ("fixed_family_ids", target["fixed_family_ids"]),
        ("fixed_slots_per_family", target["fixed_slots_per_family"]),
        ("minimum_position_spacing_m", target["minimum_position_spacing_m"]),
        ("target_repeat_policy", "report_only_no_pose_target_or_house_reselection"),
        ("target_source",
         "v3_private_authored_asset_at_frozen_v2_pose_after_scan_live_scene_match"),
        ("program_source", "frozen_private_episode_plan_same_zero_based_family_slot"),
        ("probe_policy",
         "fresh_controller_per_physical_fixed_slot_registered_actions_no_rgbd_capture"),
        ("failure_policy",
         "record_original_fixed_slot_no_retry_no_target_pose_or_house_replacement"),
        ("non_intervention_scope", "no_simulator_action_no_public_region_claim"),
        ("semantic_positive_label_policy", "never_issue_from_action_capability_probe"),
        ("relink_terminal_tolerance_m", 0.005),
        ("relink_force_action_semantic_policy",
         "record_collision_unchecked_not_physical_validity"),
        ("static_lifecycle_memory_history_policy",
         "not_checked_in_probe_no_transaction_positive_label"),
        ("single_worker_resource_benchmark",
         "family00_slot00_scene_create_and_teleport_only_before_two_family_dispatch"),
        ("minimum_memory_headroom_to_peak_rss_ratio_for_two_workers", 4.0),
        ("minimum_memory_headroom_to_sampled_cgroup_demand_ratio_for_two_workers", 4.0),
        ("resource_benchmark_sample_interval_seconds", 0.25),
        ("minimum_gpu_headroom_to_measured_peak_ratio_for_two_workers", 2.0),
    ):
        require(type(value.get(key)) is type(expected) and value[key] == expected,
                "v3 target-probe scope changed: " + key)
    require(value["implementation_authorized"] is True and
            value["generation_authorized"] is False and
            value["training_authorized"] is False,
            "v3 probe cannot open generation/training")
    if value["status"] == "implementation_only_not_executable":
        require(value["probe_execution_authorized"] is False and
                value["expected_reviewed_probe_code"] is None and
                target["status"] == "frozen_target_probe_only" and
                target["target_capability_probe_authorized"] is True and
                target["generation_authorized"] is False,
                "implementation-only v3 probe has an executable field")
    elif value["status"] == "frozen_probe_only":
        require(value["probe_execution_authorized"] is True and
                type(value["expected_reviewed_probe_code"]) is str and
                re.fullmatch(r"[0-9a-f]{40}",
                             value["expected_reviewed_probe_code"]) is not None and
                target["status"] == "frozen_target_probe_only" and
                target["target_capability_probe_authorized"] is True and
                target["generation_authorized"] is False,
                "frozen v3 probe requires reviewed code and target-only gate")
    else:
        raise RuntimeError("unknown v3 target-probe status")
    rules = value["worker_policy"]
    require(rules == {
        "requested_family_workers": 2, "minimum_visible_cpu_count": 2,
        "minimum_cgroup_memory_headroom_bytes": 8589934592,
        "minimum_free_gpu_bytes": 8589934592,
        "minimum_free_data_disk_bytes": 8589934592,
        "maximum_worker_address_space_bytes": 42949672960,
        "maximum_private_slot_json_bytes": 1048576,
        "no_wall_clock_failure_limit": True,
    }, "v3 two-worker resource/safety policy changed")
    return value, target


def verify_code(reviewed_code):
    require(Path(audit.git("rev-parse", "--show-toplevel")).resolve() == ROOT.resolve(),
            "v3 probe checkout root changed")
    require(audit.git("rev-parse", "HEAD") == reviewed_code and
            not audit.git("status", "--porcelain"),
            "v3 probe needs exact clean reviewed checkout")
    return {relative: audit.sha256(ROOT / relative) for relative in BOUND_FILES}


def verify_reviewed_implementation(config):
    reviewed = config["expected_reviewed_probe_code"]
    head = audit.git("rev-parse", "HEAD")
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", reviewed,
                               head], cwd=ROOT)
    require(ancestor.returncode == 0, "reviewed v3 probe code is not an ancestor")
    unchanged = subprocess.run([
        "git", "diff", "--quiet", reviewed, head, "--",
        "ops/vsmt/vm04_target_action_probe.py",
        "ops/vsmt/vm04_target_action_probe_worker.py",
        "ops/vsmt/vm04_two_house_worker.py",
        "src/vsmt/vm04_target_contract.py",
        "src/vsmt/vm04_target_eligibility.py",
        "src/vsmt/vm04_target_selection_v3.py",
        "tests/test_vm04_target_action_probe.py",
        "tests/test_vm04_target_action_probe_worker.py",
    ], cwd=ROOT)
    require(unchanged.returncode == 0,
            "v3 probe implementation changed after user code review")


def scan_inputs(config, scan_stage, source_root):
    """Verify source/pose/plan bytes; v2 architectural top2 is diagnostic only."""
    scan = scan_stage.resolve()
    receipt, _ = audit._marker(scan, "scan")
    report = audit.read_json(SCAN_REPORT_PATH)
    require(audit.sha256(SCAN_REPORT_PATH) ==
            config["source_scan_report_sha256"] and
            receipt["reviewed_code"] == config["source_scan_reviewed_code"] ==
            report["source_scan_reviewed_code"] and
            audit.sha256(scan / "scan.receipt.json") ==
            config["source_scan_receipt_sha256"] == report["scan_receipt_sha256"],
            "frozen v2 scan source/report receipt changed")
    require(receipt["planning_selection_receipt_sha256"] ==
            config["planning_selection_receipt_sha256"] ==
            report["planning_selection_receipt_sha256"] and
            receipt["minimum_position_spacing_m"] == 1.0 and
            receipt["episode_generation_performed"] is False,
            "frozen v2 selection/D/zero-episode scope changed")
    require(receipt["worker_code_sha256"] ==
            audit.sha256(ROOT / "ops/vsmt/vm04_two_house_worker.py"),
            "scanned generator action code changed")
    for relative, digest in report["bound_sha256"].items():
        require(audit.sha256(ROOT / relative) == digest,
                "scan bound source changed: " + relative)
    plans = validate_episode_plans({
        "public": audit.read_json(scan / "public/episode_plan.json"),
        "private": audit.read_json(scan / "private/episode_plan.json"),
    })
    require(len(plans["public"]["episodes"]) == 36 and
            plans["public"]["manifest_sha256"] ==
            config["source_public_episode_manifest_sha256"] and
            plans["private"]["manifest_sha256"] ==
            config["source_private_episode_manifest_sha256"],
            "frozen episode plan digests changed")
    families = sorted(receipt["families"], key=lambda row: row["family_id"])
    require([row["family_id"] for row in families] ==
            config["fixed_family_ids"] and
            [row["source_house_id"] for row in families] ==
            config["fixed_source_house_ids"] and
            all(not (scan / "execution" / row["family_id"] / "episodes").exists()
                for row in families), "frozen family/house or zero-episode scope changed")
    for family in families:
        root = scan / "execution" / family["family_id"]
        for relative, key in (
            ("scan.worker.receipt.json", "worker_receipt_sha256"),
            ("initial_viewpoints.json", "family_viewpoints_sha256"),
            ("private/viewpoint-target-audit.json",
             "private_viewpoint_target_audit_sha256"),
        ):
            require(audit.sha256(root / relative) == family[key],
                    "frozen scan family artifact changed: " + relative)
        public = audit.read_json(root / "initial_viewpoints.json")
        private = audit.read_json(root / "private/viewpoint-target-audit.json")
        require(public["selected_pose_count"] == 18 and
                public["minimum_pose_separation_m"] == 1.0 and
                [row["rank_index"] for row in private["spaced_top_18"]] ==
                public["selected_pose_rank_indices"],
                "frozen scan pose/rank pairing changed")
    inventory = audit.validate_source_inventory(
        audit.read_json(scan / "private/inventory.json"))
    selection = audit.validate_house_selection(
        audit.read_json(scan / "selection.json"), inventory=inventory)
    source_cfg = audit.load_config()["source_inventory_proposal"]
    require(inventory["source_manifest_sha256"] ==
            source_cfg["source_manifest_sha256"] and
            selection["selection_sha256"] ==
            audit.load_config()["planning_stage_binding"]["selection_sha256"] and
            selection["audit_house_ids"] == config["fixed_source_house_ids"] and
            audit.git("rev-parse", "HEAD", cwd=source_root.resolve()) ==
            source_cfg["data_release_commit"],
            "frozen inventory/selection/source checkout changed")
    for family in families:
        row = next(item for item in inventory["houses"]
                   if item["house_id"] == family["source_house_id"])
        locator = row["source_locator"]
        file = (source_root.resolve() / locator["relative_path"]).resolve()
        require(source_root.resolve() in file.parents and
                audit.sha256(file) == row["source_file_sha256"],
                "frozen author source file changed")
        house = generator.load_source_record(source_root.resolve(), locator)
        require(generator.canonical_sha256(house) ==
                row["source_record_sha256"],
                "frozen author house record changed")
    return receipt, families


def resource_evidence(config, output_root):
    rules = config["worker_policy"]
    cpus = safe_visible_cpu_count()
    memory = audit._cgroup_memory_headroom_bytes()
    disk = shutil.disk_usage(output_root.resolve()).free
    gpu_free = gpu_free_bytes_by_device()
    gpu = max(gpu_free)
    require(cpus >= rules["minimum_visible_cpu_count"] and
            memory is not None and
            memory >= rules["minimum_cgroup_memory_headroom_bytes"] and
            disk >= rules["minimum_free_data_disk_bytes"] and
            gpu >= rules["minimum_free_gpu_bytes"],
            "two v3 family workers lack fresh CPU/RAM/disk/GPU headroom")
    return {"visible_cpu_count": cpus,
            "cgroup_memory_headroom_bytes": memory,
            "free_data_disk_bytes": disk,
            "visible_gpu_count": len(gpu_free),
            "free_gpu_bytes_by_device": gpu_free,
            "free_gpu_bytes_on_one_device": gpu,
            "prior_two_family_scan_receipt_sha256":
                config["source_scan_receipt_sha256"]}


def gpu_free_bytes_by_device():
    lines = subprocess.check_output([
        "nvidia-smi", "--query-gpu=memory.free",
        "--format=csv,noheader,nounits",
    ], text=True).splitlines()
    require(lines, "v3 probe requires a visible simulator GPU")
    values = [int(line.strip()) * 1024 * 1024 for line in lines]
    require(all(value >= 0 for value in values), "invalid GPU free memory")
    return values


def measured_gpu_sufficient(initial_free, minimum_free, final_free,
                            minimum_static_free, ratio):
    """Bound two family workers by sampled single-worker GPU demand."""
    if not (len(initial_free) == len(minimum_free) == len(final_free) and
            initial_free):
        return False, None, None
    demand = [max(0, before - trough) for before, trough in
              zip(initial_free, minimum_free)]
    selected_device = max(range(len(demand)), key=lambda index: demand[index])
    if demand[selected_device] == 0:
        return False, None, 0
    needed = max(minimum_static_free, ratio * demand[selected_device])
    return (final_free[selected_device] >= needed,
            selected_device, demand[selected_device])


def safe_visible_cpu_count():
    """Take the smaller of affinity, cgroup quota, and host-reported CPUs."""
    counts = [os.cpu_count() or 0]
    if hasattr(os, "sched_getaffinity"):
        counts.append(len(os.sched_getaffinity(0)))
    quota_file = Path("/sys/fs/cgroup/cpu.max")
    if quota_file.is_file():
        quota, period = quota_file.read_text(encoding="utf-8").split()[:2]
        if quota != "max":
            counts.append(max(1, math.floor(int(quota) / int(period))))
    return min(counts)


def memory_sufficient_for_two_workers(peak_rss_kib, headroom_bytes, ratio):
    """Auxiliary Python RSS gate; the cgroup gate also covers simulator children."""
    return (type(peak_rss_kib) is int and peak_rss_kib > 0 and
            type(headroom_bytes) is int and
            headroom_bytes >= peak_rss_kib * 1024 * ratio)


def sampled_cgroup_demand_sufficient(baseline_headroom_bytes,
                                      minimum_headroom_bytes,
                                      dispatch_headroom_bytes, ratio):
    """Fail closed unless sampled descendant-inclusive demand fits at dispatch."""
    if not (all(type(value) is int and value > 0 for value in (
            baseline_headroom_bytes, minimum_headroom_bytes,
            dispatch_headroom_bytes)) and type(ratio) is float and ratio >= 1):
        return False, 0
    demand = max(0, baseline_headroom_bytes - minimum_headroom_bytes)
    return demand > 0 and dispatch_headroom_bytes >= ratio * demand, demand


def validate_cgroup_trace(trace, evidence):
    """Recompute the sampled summary from the private trace before export."""
    samples = trace["samples"]
    running_gap = max((right["elapsed_seconds"] - left["elapsed_seconds"]
                       for left, right in zip(samples, samples[1:-1])),
                      default=0.0)
    require(len(samples) >= 3 and samples[0]["phase"] == "baseline" and
            samples[-1]["phase"] == "after_benchmark" and
            all(sample["phase"] == "running" for sample in samples[1:-1]) and
            all(type(sample["headroom_bytes"]) is int and
                sample["headroom_bytes"] > 0 and
                type(sample["elapsed_seconds"]) in (float, int)
                for sample in samples) and
            all(left["elapsed_seconds"] <= right["elapsed_seconds"]
                for left, right in zip(samples, samples[1:])) and
            samples[0]["headroom_bytes"] ==
                evidence["pre_benchmark_cgroup_memory_headroom_bytes"] and
            samples[-1]["headroom_bytes"] ==
                evidence["post_benchmark_cgroup_memory_headroom_bytes"] and
            min(sample["headroom_bytes"] for sample in samples) ==
                evidence["benchmark_min_cgroup_memory_headroom_bytes"] and
            len(samples) - 2 == trace["running_sample_count"] ==
                evidence["benchmark_cgroup_sample_count"] and
            trace["maximum_running_sample_gap_seconds"] ==
                evidence["benchmark_maximum_cgroup_sample_gap_seconds"] and
            abs(running_gap - trace[
                "maximum_running_sample_gap_seconds"]) < 0.000001,
            "v3 private cgroup trace/summary changed")


def check(reviewed_code, output_root):
    """Run independent pure test groups in parallel; no simulator actions."""
    config, _ = load_config()
    bindings = verify_code(reviewed_code)
    cpus = safe_visible_cpu_count()
    memory = audit._cgroup_memory_headroom_bytes()
    disk = shutil.disk_usage(output_root.resolve()).free
    require(cpus >= 3 and memory is not None and memory >= 4294967296 and
            disk >= 1073741824,
            "v3 pure check lacks three safe independent test workers")
    stage = output_root.resolve() / ("vsmt-vm04-v3-target-probe-check-v2-" +
                                   reviewed_code[:12])
    require(not stage.exists(), "v3 check stage exists: preserve it")
    stage.mkdir(parents=True)
    started = time.monotonic()
    children = []
    dispatch_error = None
    for group, modules in CHECK_GROUPS:
        log_path = stage / (group + ".log")
        try:
            with log_path.open("x", encoding="utf-8") as handle:
                child = subprocess.Popen([
                    sys.executable, "-B", "-m", "unittest", "-v", *modules,
                ], cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT)
            children.append((group, child, log_path))
        except Exception as error:
            dispatch_error = {"group": group,
                              "error_type": type(error).__name__,
                              "error": str(error)}
            break
    exits = []
    for group, child, log_path in children:
        code = child.wait()
        output = log_path.read_text(encoding="utf-8")
        print("[%s] %s" % (group, output), end="", flush=True)
        match = re.search(r"Ran (\d+) tests?", output)
        passed = (int(match.group(1)) if match is not None and code == 0 and
                  "FAILED" not in output else 0)
        exits.append({"group": group, "exit_code": code,
                      "log_sha256": audit.sha256(log_path),
                      "passed_test_count": passed})
    success = (dispatch_error is None and len(exits) == len(CHECK_GROUPS) and
               all(row["exit_code"] == 0 and row["passed_test_count"] > 0
                   for row in exits))
    receipt_path = stage / "check.receipt.json"
    audit.write_new_json(receipt_path, {
        "schema_version": "vsmt-vm04-v3-target-probe-check-receipt-v2",
        "reviewed_code": reviewed_code, "bound_sha256": bindings,
        "config_status": config["status"],
        "requested_workers": len(CHECK_GROUPS),
        "actual_workers": len(children), "worker_exits": exits,
        "dispatch_error": dispatch_error,
        "resource_evidence": {"visible_cpu_count": cpus,
                              "cgroup_memory_headroom_bytes": memory,
                              "free_data_disk_bytes": disk},
        "deterministic_merge_order": [group for group, _ in CHECK_GROUPS],
        "passed_test_count": sum(row["passed_test_count"] for row in exits),
        "wall_seconds": time.monotonic() - started,
        "simulator_started": False, "episodes_generated": 0,
        "success": success,
    })
    if success:
        audit.write_new_json(stage / "check.success.json", {
            "schema_version": "vsmt-vm04-v3-target-probe-check-success-v2",
            "receipt_sha256": audit.sha256(receipt_path), "success": True,
        })
    print("VM04_V3_TARGET_PROBE_CHECK_%s stage=%s workers=%s tests=%s" %
          ("OK" if success else "FAILED", stage, len(children),
           sum(row["passed_test_count"] for row in exits)), flush=True)
    require(success, "v3 probe pure check failed: preserve stage")


def run(reviewed_code, scan_stage, source_root, output_root):
    config, target = load_config()
    require(config["status"] == "frozen_probe_only" and
            config["probe_execution_authorized"] is True and
            target["status"] == "frozen_target_probe_only" and
            target["target_capability_probe_authorized"] is True,
            "v3 target action probe execution remains closed")
    bindings = verify_code(reviewed_code)
    verify_reviewed_implementation(config)
    check_stage = output_root.resolve() / (
        "vsmt-vm04-v3-target-probe-check-v2-" + reviewed_code[:12])
    check_receipt, _ = audit._marker(check_stage, "check")
    require(check_receipt["reviewed_code"] == reviewed_code and
            check_receipt["bound_sha256"] == bindings and
            check_receipt["requested_workers"] == len(CHECK_GROUPS) and
            check_receipt["actual_workers"] == len(CHECK_GROUPS) and
            check_receipt["deterministic_merge_order"] ==
            [group for group, _ in CHECK_GROUPS] and
            all(row["exit_code"] == 0 and row["passed_test_count"] > 0 and
                audit.sha256(check_stage / (row["group"] + ".log")) ==
                row["log_sha256"] for row in check_receipt["worker_exits"]),
            "v3 probe pure check/code/log chain changed")
    scan_receipt, families = scan_inputs(config, scan_stage, source_root)
    evidence = resource_evidence(config, output_root)
    simulator = Path(audit.read_json(audit.ENVIRONMENT_PATH)[
        "environment_separation"]["simulator_process"]["environment_path"]) / "bin/python"
    require(simulator.is_file(), "frozen simulator Python is missing")
    stage = output_root.resolve() / ("vsmt-vm04-v3-target-probe-v2-" +
                                   reviewed_code[:12])
    require(not stage.exists(), "v3 probe stage exists: preserve it")
    stage.mkdir(parents=True)
    environment = dict(os.environ, PYTHONUNBUFFERED="1", OMP_NUM_THREADS="1",
                       OPENBLAS_NUM_THREADS="1",
                       XDG_RUNTIME_DIR=str(output_root.resolve() / "runtime"))
    Path(environment["XDG_RUNTIME_DIR"]).mkdir(parents=True, exist_ok=True)
    children = []
    dispatch_error = None
    started = time.monotonic()
    base_args = [
        "--scan-stage", str(scan_stage.resolve()),
        "--probe-stage", str(stage),
        "--source-root", str(source_root.resolve()),
        "--maximum-slot-json-bytes",
        str(config["worker_policy"]["maximum_private_slot_json_bytes"]),
        "--maximum-address-space-bytes",
        str(config["worker_policy"]["maximum_worker_address_space_bytes"]),
    ]
    worker_command = [
        str(simulator), "-B",
        str(ROOT / "ops/vsmt/vm04_target_action_probe_worker.py"),
    ]
    benchmark_log = stage / "private/resource-benchmark.worker.log"
    benchmark_log.parent.mkdir(parents=True, exist_ok=True)
    benchmark_exit = None
    benchmark_receipt_sha256 = None
    initial_gpu_free = evidence["free_gpu_bytes_by_device"]
    minimum_gpu_free = list(initial_gpu_free)
    baseline_cgroup_headroom = evidence["cgroup_memory_headroom_bytes"]
    minimum_cgroup_headroom = baseline_cgroup_headroom
    cgroup_sample_count = 0
    sample_started = time.monotonic()
    last_sample = sample_started
    maximum_sample_gap_seconds = 0.0
    cgroup_samples = [{"phase": "baseline", "elapsed_seconds": 0.0,
                       "headroom_bytes": baseline_cgroup_headroom}]
    benchmark = None
    try:
        with benchmark_log.open("x", encoding="utf-8") as handle:
            benchmark = subprocess.Popen([
                *worker_command, *base_args,
                "--family-id", config["fixed_family_ids"][0],
                "--benchmark-only",
            ], stdout=handle, stderr=subprocess.STDOUT, env=environment)
        while True:
            sampled_at = time.monotonic()
            maximum_sample_gap_seconds = max(
                maximum_sample_gap_seconds, sampled_at - last_sample)
            last_sample = sampled_at
            sampled_memory = audit._cgroup_memory_headroom_bytes()
            require(type(sampled_memory) is int and sampled_memory > 0,
                    "cgroup memory unavailable during simulator benchmark")
            minimum_cgroup_headroom = min(minimum_cgroup_headroom,
                                          sampled_memory)
            cgroup_sample_count += 1
            cgroup_samples.append({"phase": "running",
                                   "elapsed_seconds": sampled_at - sample_started,
                                   "headroom_bytes": sampled_memory})
            sample = gpu_free_bytes_by_device()
            require(len(sample) == len(minimum_gpu_free),
                    "visible GPU inventory changed during benchmark")
            minimum_gpu_free = [min(old, new) for old, new in
                                zip(minimum_gpu_free, sample)]
            try:
                benchmark_exit = benchmark.wait(timeout=config[
                    "resource_benchmark_sample_interval_seconds"])
                break
            except subprocess.TimeoutExpired:
                continue
    except Exception as error:
        if benchmark is not None and benchmark_exit is None:
            benchmark_exit = benchmark.wait()
        dispatch_error = {"phase": "single_worker_benchmark",
                          "error_type": type(error).__name__,
                          "error": str(error)}
    benchmark_path = stage / "private/resource-benchmark.json"
    if benchmark_path.is_file():
        benchmark_receipt_sha256 = audit.sha256(benchmark_path)
    if dispatch_error is None:
        if benchmark_exit != 0 or benchmark_receipt_sha256 is None:
            dispatch_error = {"phase": "single_worker_benchmark",
                              "error": "benchmark worker failed or omitted receipt"}
        else:
            try:
                benchmark_result = audit.read_json(benchmark_path)
                peak_kib = benchmark_result["single_worker_peak_RSS_kib"]
                fresh_memory = audit._cgroup_memory_headroom_bytes()
                require(type(fresh_memory) is int and fresh_memory > 0,
                        "cgroup memory unavailable after simulator benchmark")
                minimum_cgroup_headroom = min(minimum_cgroup_headroom,
                                              fresh_memory)
                cgroup_samples.append({"phase": "after_benchmark",
                                       "elapsed_seconds": time.monotonic() - sample_started,
                                       "headroom_bytes": fresh_memory})
                cgroup_safe, observed_cgroup_demand = (
                    sampled_cgroup_demand_sufficient(
                        baseline_cgroup_headroom, minimum_cgroup_headroom,
                        fresh_memory, config[
                            "minimum_memory_headroom_to_sampled_cgroup_demand_ratio_for_two_workers"]))
                final_gpu_free = gpu_free_bytes_by_device()
                gpu_safe, selected_gpu, observed_gpu_peak = measured_gpu_sufficient(
                    initial_gpu_free, minimum_gpu_free, final_gpu_free,
                    config["worker_policy"]["minimum_free_gpu_bytes"],
                    config["minimum_gpu_headroom_to_measured_peak_ratio_for_two_workers"])
                evidence.update({
                    "single_worker_benchmark_peak_RSS_kib": peak_kib,
                    "post_benchmark_cgroup_memory_headroom_bytes": fresh_memory,
                    "pre_benchmark_cgroup_memory_headroom_bytes": baseline_cgroup_headroom,
                    "benchmark_min_cgroup_memory_headroom_bytes": minimum_cgroup_headroom,
                    "benchmark_observed_cgroup_demand_bytes": observed_cgroup_demand,
                    "benchmark_cgroup_sample_count": cgroup_sample_count,
                    "benchmark_cgroup_sample_window_seconds": time.monotonic() - sample_started,
                    "benchmark_maximum_cgroup_sample_gap_seconds": maximum_sample_gap_seconds,
                    "benchmark_cgroup_sampling_interval_seconds": config[
                        "resource_benchmark_sample_interval_seconds"],
                    "minimum_memory_headroom_to_sampled_cgroup_demand_ratio": config[
                        "minimum_memory_headroom_to_sampled_cgroup_demand_ratio_for_two_workers"],
                    "pre_benchmark_gpu_free_bytes_by_device": initial_gpu_free,
                    "benchmark_min_gpu_free_bytes_by_device": minimum_gpu_free,
                    "post_benchmark_gpu_free_bytes_by_device": final_gpu_free,
                    "benchmark_observed_gpu_device_index": selected_gpu,
                    "benchmark_observed_peak_gpu_bytes": observed_gpu_peak,
                    "minimum_gpu_headroom_to_observed_peak_ratio":
                        config["minimum_gpu_headroom_to_measured_peak_ratio_for_two_workers"],
                    "minimum_memory_headroom_to_peak_rss_ratio_for_two_workers":
                        config["minimum_memory_headroom_to_peak_rss_ratio_for_two_workers"],
                })
                if (benchmark_result["success"] is not True or not gpu_safe or
                        not cgroup_safe or
                        not memory_sufficient_for_two_workers(
                            peak_kib, fresh_memory,
                            config["minimum_memory_headroom_to_peak_rss_ratio_for_two_workers"])):
                    dispatch_error = {"phase": "single_worker_benchmark",
                                      "error": "unsafe or unmeasured two-worker RAM/GPU demand"}
                else:
                    evidence["post_benchmark_resource_evidence"] = (
                        resource_evidence(config, output_root))
                    fresh_gpu = evidence["post_benchmark_resource_evidence"][
                        "free_gpu_bytes_by_device"]
                    dispatch_memory = evidence["post_benchmark_resource_evidence"][
                        "cgroup_memory_headroom_bytes"]
                    dispatch_cgroup_safe, _ = sampled_cgroup_demand_sufficient(
                        baseline_cgroup_headroom, minimum_cgroup_headroom,
                        dispatch_memory, config[
                            "minimum_memory_headroom_to_sampled_cgroup_demand_ratio_for_two_workers"])
                    require(dispatch_cgroup_safe,
                            "sampled simulator RAM lost safe headroom before dispatch")
                    require(len(fresh_gpu) == len(initial_gpu_free) and
                            fresh_gpu[selected_gpu] >= max(
                                config["worker_policy"]["minimum_free_gpu_bytes"],
                                config["minimum_gpu_headroom_to_measured_peak_ratio_for_two_workers"]
                                * observed_gpu_peak),
                            "sampled simulator GPU lost safe headroom before dispatch")
            except Exception as error:
                dispatch_error = {"phase": "single_worker_benchmark",
                                  "error_type": type(error).__name__,
                                  "error": str(error)}
    cgroup_samples_path = stage / "private/resource-benchmark.cgroup-samples.json"
    audit.write_new_json(cgroup_samples_path, {
        "schema_version": "vsmt-vm04-v3-target-probe-cgroup-samples-v2",
        "samples": cgroup_samples,
        "running_sample_count": cgroup_sample_count,
        "maximum_running_sample_gap_seconds": maximum_sample_gap_seconds,
    })
    evidence["private_cgroup_samples_sha256"] = audit.sha256(cgroup_samples_path)
    print("VM04_V3_TARGET_PROBE_BENCHMARK exit=%s receipt=%s" %
          (benchmark_exit, benchmark_receipt_sha256 is not None), flush=True)
    if dispatch_error is None:
        for family in families:
            family_id = family["family_id"]
            log_path = stage / "private" / (family_id + ".worker.log")
            try:
                with log_path.open("x", encoding="utf-8") as handle:
                    child = subprocess.Popen([
                        *worker_command, *base_args, "--family-id", family_id,
                    ], stdout=handle, stderr=subprocess.STDOUT,
                       env=environment)
                children.append((family_id, child, log_path))
            except Exception as error:
                dispatch_error = {"family_id": family_id,
                                  "error_type": type(error).__name__,
                                  "error": str(error)}
                break
    completed_count = -1
    while any(child.poll() is None for _, child, _ in children):
        current = sum(len(list((stage / "execution" / family_id / "private").glob(
            "slot_*.json"))) for family_id, _, _ in children)
        if current != completed_count:
            completed_count = current
            print("VM04_V3_TARGET_PROBE_PROGRESS fixed_slots=%s/36" % current,
                  flush=True)
        time.sleep(5)
    exits = [{"family_id": family_id, "exit_code": child.wait(),
              "log_sha256": audit.sha256(log_path)}
             for family_id, child, log_path in children]
    workers = []
    for family_id, _, _ in children:
        path = stage / "execution" / family_id / "private/worker.receipt.json"
        if path.is_file():
            workers.append({"family_id": family_id, "sha256": audit.sha256(path)})
    success = (dispatch_error is None and benchmark_exit == 0 and
               benchmark_receipt_sha256 is not None and len(children) == 2 and
               len(workers) == 2 and all(row["exit_code"] == 0 for row in exits) and
               all(audit.read_json(stage / "execution" / row["family_id"] /
                                       "private/worker.receipt.json")["fixed_slot_count"] == 18
                   for row in workers))
    terminal_path = stage / "probe.receipt.json"
    audit.write_new_json(terminal_path, {
        "schema_version": "vsmt-vm04-v3-target-probe-receipt-v2",
        "reviewed_code": reviewed_code, "bound_sha256": bindings,
        "v3_target_contract_sha256": audit.sha256(TARGET_CONTRACT_PATH),
        "scan_receipt_sha256": audit.sha256(scan_stage / "scan.receipt.json"),
        "check_receipt_sha256": audit.sha256(check_stage / "check.receipt.json"),
        "planning_selection_receipt_sha256":
            scan_receipt["planning_selection_receipt_sha256"],
        "requested_workers": 2, "actual_workers": len(children),
        "resource_evidence": evidence, "worker_exits": exits,
        "single_worker_benchmark": {
            "requested_workers": 1, "actual_workers":
                int(benchmark_exit is not None), "exit_code": benchmark_exit,
            "private_receipt_sha256": benchmark_receipt_sha256,
            "private_log_sha256": (audit.sha256(benchmark_log)
                                   if benchmark_log.is_file() else None),
        },
        "family_worker_receipts": workers, "dispatch_error": dispatch_error,
        "deterministic_merge_order": config["fixed_family_ids"],
        "wall_seconds": time.monotonic() - started,
        "episodes_generated": 0, "frames_captured": 0,
        "semantic_positive_labels_issued": 0,
        "training_steps": 0, "success": success,
    })
    if success:
        audit.write_new_json(stage / "probe.success.json", {
            "schema_version": "vsmt-vm04-v3-target-probe-success-v2",
            "receipt_sha256": audit.sha256(terminal_path), "success": True,
        })
    print("VM04_V3_TARGET_PROBE_%s stage=%s workers=%s episodes=0" %
          ("OK" if success else "FAILED", stage, len(children)), flush=True)
    require(success, "v3 probe failed: preserve original stage and diagnostics")


def public_report_payload(reviewed_code, receipt_sha256, receipt, rows,
                          repetitions):
    require(sum(row["count"] for row in rows) == 36,
            "v3 public probe report needs all 36 fixed slots")
    return {
        "schema_version": "vsmt-vm04-v3-target-action-probe-public-report-v2",
        "status": "fixed_two_house_action_capability_diagnostic_only",
        "reviewed_code": reviewed_code,
        "probe_receipt_sha256": receipt_sha256,
        "scan_receipt_sha256": receipt["scan_receipt_sha256"],
        "v3_target_contract_sha256": receipt["v3_target_contract_sha256"],
        "counts_by_family_program_status": rows,
        "anonymous_target_repetition_by_family": repetitions,
        "requested_workers": receipt["requested_workers"],
        "actual_workers": receipt["actual_workers"],
        "worker_exits": receipt["worker_exits"],
        "resource_evidence": receipt["resource_evidence"],
        "single_worker_benchmark": receipt["single_worker_benchmark"],
        "private_ids_exported": False,
        "semantic_positive_labels_issued": 0,
        "episodes_generated": 0, "frames_captured": 0,
        "training_steps": 0,
    }


def anonymous_target_repeats(private_slots):
    """Use private IDs internally; export only distinct/repeated counts."""
    selected = [slot["v3_target_instance_ids"] for slot in private_slots
                if slot["v3_target_instance_ids"]]
    top1 = [ids[0] for ids in selected]
    sets = [tuple(sorted(ids)) for ids in selected]
    return {"selected_physical_slot_count": len(selected),
            "distinct_top1_count": len(set(top1)),
            "repeated_top1_count": len(top1) - len(set(top1)),
            "distinct_selected_target_set_count": len(set(sets)),
            "repeated_selected_target_set_count": len(sets) - len(set(sets))}


def export(reviewed_code, stage):
    config, target = load_config()
    require(config["status"] == "frozen_probe_only" and
            config["probe_execution_authorized"] is True and
            target["status"] == "frozen_target_probe_only" and
            target["generation_authorized"] is False,
            "v3 target probe export remains closed")
    bindings = verify_code(reviewed_code)
    verify_reviewed_implementation(config)
    stage = stage.resolve()
    receipt, _ = audit._marker(stage, "probe")
    require(receipt["reviewed_code"] == reviewed_code and
            receipt["bound_sha256"] == bindings and
            receipt["v3_target_contract_sha256"] ==
            audit.sha256(TARGET_CONTRACT_PATH) and
            receipt["scan_receipt_sha256"] ==
            config["source_scan_receipt_sha256"] and
            receipt["requested_workers"] == receipt["actual_workers"] == 2 and
            receipt["deterministic_merge_order"] == config["fixed_family_ids"],
            "v3 probe receipt/code/source/concurrency changed")
    check_stage = stage.parent / ("vsmt-vm04-v3-target-probe-check-v2-" +
                                  reviewed_code[:12])
    check_receipt, _ = audit._marker(check_stage, "check")
    require(check_receipt["reviewed_code"] == reviewed_code and
            audit.sha256(check_stage / "check.receipt.json") ==
            receipt["check_receipt_sha256"],
            "v3 probe pure check binding changed")
    require(not EXPORT_PATH.exists(), "v3 probe export exists: preserve it")
    benchmark = receipt["single_worker_benchmark"]
    benchmark_path = stage / "private/resource-benchmark.json"
    benchmark_log = stage / "private/resource-benchmark.worker.log"
    require(benchmark["requested_workers"] == benchmark["actual_workers"] == 1 and
            benchmark["exit_code"] == 0 and
            audit.sha256(benchmark_path) == benchmark["private_receipt_sha256"] and
            audit.sha256(benchmark_log) == benchmark["private_log_sha256"],
            "v3 resource benchmark receipt/log changed")
    benchmark_private = audit.read_json(benchmark_path)
    memory_evidence = receipt["resource_evidence"]
    samples_path = stage / "private/resource-benchmark.cgroup-samples.json"
    require(audit.sha256(samples_path) ==
            memory_evidence["private_cgroup_samples_sha256"],
            "v3 private cgroup sampling trace changed")
    trace = audit.read_json(samples_path)
    validate_cgroup_trace(trace, memory_evidence)
    sampled_safe, sampled_demand = sampled_cgroup_demand_sufficient(
        memory_evidence["pre_benchmark_cgroup_memory_headroom_bytes"],
        memory_evidence["benchmark_min_cgroup_memory_headroom_bytes"],
        memory_evidence["post_benchmark_resource_evidence"][
            "cgroup_memory_headroom_bytes"],
        config["minimum_memory_headroom_to_sampled_cgroup_demand_ratio_for_two_workers"])
    require(benchmark_private["success"] is True and
            benchmark_private["external_interventions"] == 0 and
            benchmark_private["episodes_generated"] == 0 and
            benchmark_private["single_worker_peak_RSS_kib"] ==
            memory_evidence["single_worker_benchmark_peak_RSS_kib"] and
            memory_evidence["benchmark_cgroup_sample_count"] > 0 and
            memory_evidence["benchmark_cgroup_sampling_interval_seconds"] ==
            config["resource_benchmark_sample_interval_seconds"] and
            memory_evidence["benchmark_observed_cgroup_demand_bytes"] ==
            sampled_demand and sampled_safe,
            "v3 resource benchmark pre-dispatch safety changed")
    aggregate = {}
    repetitions = []
    require([row["family_id"] for row in receipt["family_worker_receipts"]] ==
            config["fixed_family_ids"], "v3 fixed family receipt order changed")
    for family in receipt["family_worker_receipts"]:
        root = stage / "execution" / family["family_id"]
        worker_path = root / "private/worker.receipt.json"
        require(audit.sha256(worker_path) == family["sha256"],
                "v3 private family worker receipt changed")
        worker = audit.read_json(worker_path)
        require(worker["success"] is True and worker["fixed_slot_count"] == 18 and
                [row["slot"] for row in worker["slots"]] == list(range(18)) and
                worker["episodes_generated"] == worker["frames_captured"] == 0 and
                worker["semantic_positive_labels_issued"] == 0,
                "v3 worker slot/capture/label boundary changed")
        private_slots = []
        for row in worker["slots"]:
            path = root / "private" / ("slot_%02d.json" % row["slot"])
            require(audit.sha256(path) == row["private_slot_sha256"],
                    "v3 private slot diagnosis changed")
            slot = audit.read_json(path)
            require(slot["status"] == row["status"] and
                    slot["program"] == row["program"] and
                    slot["slot"] == row["slot"] and
                    slot["semantic_positive_label_issued"] is False,
                    "v3 private slot/worker label disagreement")
            private_slots.append(slot)
            key = (family["family_id"], row["program"], row["status"])
            aggregate[key] = aggregate.get(key, 0) + 1
        repetitions.append({"family_id": family["family_id"],
                            **anonymous_target_repeats(private_slots)})
    rows = [{"family_id": family, "program": program, "status": status,
             "count": count}
            for (family, program, status), count in sorted(aggregate.items())]
    audit.write_new_json(EXPORT_PATH, public_report_payload(
        reviewed_code, audit.sha256(stage / "probe.receipt.json"), receipt,
        rows, repetitions))
    print("VM04_V3_TARGET_PROBE_EXPORT_OK report=%s slots=36" % EXPORT_PATH,
          flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("contract", "check", "run", "export"))
    parser.add_argument("--reviewed-code")
    parser.add_argument("--scan-stage", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--probe-stage", type=Path)
    args = parser.parse_args()
    if args.action == "contract":
        config, target = load_config()
        print("VM04_V3_TARGET_PROBE_CONTRACT_OK status=%s target=%s execution=%s generation=false" %
              (config["status"], target["status"],
               config["probe_execution_authorized"]), flush=True)
    elif args.action == "check":
        require(args.reviewed_code and args.output_root,
                "check needs reviewed code and output root")
        check(args.reviewed_code, args.output_root)
    elif args.action == "run":
        require(all(value is not None for value in (
            args.reviewed_code, args.scan_stage, args.source_root,
            args.output_root)), "run needs reviewed code and frozen paths")
        run(args.reviewed_code, args.scan_stage, args.source_root,
            args.output_root)
    else:
        require(args.reviewed_code and args.probe_stage,
                "export needs reviewed code and probe stage")
        export(args.reviewed_code, args.probe_stage)


if __name__ == "__main__":
    main()
