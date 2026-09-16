#!/usr/bin/env python3
"""Review-gated 36-slot VM-04 raw stage with terminal failure retention."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import vm04_two_house_audit as audit  # noqa: E402
import vm04_target_action_probe as resource_probe  # noqa: E402
import vm04_fixed_slot_raw_manifest as manifest  # noqa: E402
import vm04_fixed_slot_raw_worker as worker  # noqa: E402
import vm04_fixed_slot_raw_verify as raw_verify  # noqa: E402

CONFIG = ROOT / "configs/vsmt/vm04_fixed_slot_raw_stage_v1.json"
STAGE_PREFIX = "vsmt-vm04-fixed-slot-raw-v1-"


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def stage_path(output_root, reviewed_code):
    return Path(output_root).resolve() / (STAGE_PREFIX + reviewed_code[:12])


def bound_code(reviewed_code):
    head, _ = audit.verify_checkout(reviewed_code)
    return {relative: audit.sha256(ROOT / relative) for relative in (
        "configs/vsmt/vm04_fixed_slot_raw_stage_v1.json",
        "ops/vsmt/vm04_fixed_slot_raw_worker.py",
        "ops/vsmt/vm04_fixed_slot_raw_manifest.py",
        "ops/vsmt/vm04_fixed_slot_raw_stage.py",
        "ops/vsmt/vm04_fixed_slot_raw_verify.py",
        "src/vsmt/vm04_target_selection_v3.py",
        "configs/vsmt/vm04_target_boundary_proposal_v3.json",
        "configs/vsmt/vm04_l1_environment_v1.json",
        "tests/test_vm04_fixed_slot_raw_worker.py",
        "tests/test_vm04_fixed_slot_raw_manifest.py",
        "tests/test_vm04_fixed_slot_raw_stage.py",
        "tests/test_vm04_fixed_slot_raw_verify.py",
    )}


def check(reviewed_code, output_root):
    bindings = bound_code(reviewed_code)
    config = audit.read_json(CONFIG)
    require(type(config["run_authorized"]) is bool and
            config["run_authorized"] == config["generation_authorized"],
            "fixed slot generation gate is inconsistent")
    stage = stage_path(output_root, reviewed_code)
    require(not stage.exists(), "fixed slot stage exists; verify, do not redo")
    (stage / "check").mkdir(parents=True)
    groups = [
        ("raw_file_boundary", ["tests.test_vm04_fixed_slot_raw_worker",
                                "tests.test_vm04_fixed_slot_raw_manifest",
                                "tests.test_vm04_fixed_slot_raw_stage",
                                "tests.test_vm04_fixed_slot_raw_verify",
                                "tests.test_vsmt_two_house_ops"]),
        ("target_and_endpoint", ["tests.test_vm04_target_selection_v3",
                                 "tests.test_vm04_relink_endpoint_two_house_probe"]),
    ]
    children = []
    for name, tests in groups:
        log = stage / "check" / (name + ".log")
        handle = log.open("x", encoding="utf-8")
        child = subprocess.Popen(
            [sys.executable, "-B", "-m", "unittest", *tests, "-q"],
            cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT,
            start_new_session=True)
        handle.close()
        children.append((name, child, log))
    exits = []
    for name, child, log in children:
        code = child.wait()
        print("[%s] %s" % (name, log.read_text(encoding="utf-8")),
              end="", flush=True)
        exits.append({"group": name, "exit_code": code,
                      "log_sha256": audit.sha256(log)})
    success = len(exits) == 2 and all(row["exit_code"] == 0 for row in exits)
    receipt = stage / "check.receipt.json"
    audit.write_new_json(receipt, {
        "schema_version": "vsmt-vm04-fixed-slot-check-v1",
        "reviewed_code": reviewed_code, "bound_sha256": bindings,
        "requested_workers": 2, "actual_workers": len(children),
        "worker_exits": exits, "success": success,
        "episode_generation_performed": False})
    if success:
        audit.write_new_json(stage / "check.success.json", {
            "receipt_sha256": audit.sha256(receipt), "success": True})
    require(success, "fixed slot pure check failed; preserve logs")
    print("VM04_FIXED_SLOT_CHECK_OK stage=%s" % stage, flush=True)


def safe_worker_count(cpu_count, memory_headroom, memory_demand,
                      gpu_free, gpu_demand, emergency_memory,
                      emergency_gpu, empirical_cap):
    """Maximum safe slot workers from one actual sealed-slot benchmark."""
    require(cpu_count >= 1 and memory_demand > 0 and gpu_demand > 0 and
            empirical_cap >= 1, "fresh single-worker demand is missing")
    memory_capacity = max(0, memory_headroom - emergency_memory) // memory_demand
    gpu_capacity = max(0, gpu_free - emergency_gpu) // gpu_demand
    return max(0, min(cpu_count, memory_capacity, gpu_capacity,
                      empirical_cap))


def verify_simulator_environment(simulator, contract):
    """Read installed versions from the exact isolated Python before scene IO."""
    script = ("import json,sys,importlib.metadata as m;"
              "print(json.dumps({'python':sys.version.split()[0],"
              "'ai2thor':m.version('ai2thor'),"
              "'procthor':m.version('procthor')}))")
    installed = json.loads(subprocess.check_output(
        [str(simulator), "-c", script], text=True, cwd=ROOT))
    expected = contract["environment_separation"]["simulator_process"]
    require(installed == {"python": expected["python"],
                          **expected["packages"]},
            "isolated simulator Python/package versions differ from D-135")
    return installed


def episode_path(stage, task):
    return (stage / "execution" /
            task["family_id"].replace(":", "_") / "episodes" /
            task["episode_id"].replace(":", "_"))


def not_started(stage, task, reason):
    episode = episode_path(stage, task)
    require(not episode.exists(), "cannot mark attempted episode not started")
    audit.write_new_json(episode / "raw.not_started.json", {
        "schema_version": "vsmt-vm04-fixed-slot-not-started-v1",
        "family_id": task["family_id"], "slot": task["slot"],
        "episode_id": task["episode_id"], "attempted": False,
        "raw_complete": False, "constructed": False,
        "reason": reason, "task_sha256": audit.canonical_sha256(task),
        "source_record_sha256": task["source_record_sha256"],
        "fixed_pose_sha256": audit.canonical_sha256(task["fixed_pose"]),
        "family_viewpoints_sha256": task["family_viewpoints_sha256"],
        "relink_coverage_gap": task["program"] == "RELINK",
        "relink_collision_observed_this_run": False,
        "relink_collision_evidence_source": (
            "registered_D173_nonforced_endpoint_receipt"
            if task["program"] == "RELINK" else None),
        "semantic_positive_label_issued": False})


def _worker_command(task, task_path, source_root, episode, simulator,
                    family_limit):
    return [str(simulator), "-B", str(ROOT /
            "ops/vsmt/vm04_fixed_slot_raw_worker.py"),
            "--task", str(task_path),
            "--task-sha256", audit.sha256(task_path),
            "--source-root", str(source_root),
            "--episode-root", str(episode),
            "--family-byte-limit", str(family_limit)]


def _terminal_after_exit(episode, task, exit_code):
    receipt = episode / "raw.receipt.json"
    failure = episode / "raw.failure.json"
    if receipt.is_file() or failure.is_file():
        require(not (receipt.is_file() and failure.is_file()),
                "slot has two terminal records")
        return receipt if receipt.is_file() else failure
    # The started slot and private log stay intact, even if Python/Unity died.
    public_prefix = sorted((episode / "public").glob("frame_*/camera.json"))
    private_prefix = sorted((episode / "private").glob(
        "frame_*/mapping.json"))
    audit.write_new_json(failure, {
        "schema_version": "vsmt-vm04-fixed-slot-process-failure-v1",
        "family_id": task["family_id"], "slot": task["slot"],
        "episode_id": task["episode_id"], "attempted": True,
        "raw_complete": False, "constructed": False,
        "reason": "worker_process_exited_without_terminal",
        "exit_code": exit_code,
        "task_sha256": audit.canonical_sha256(task),
        "source_record_sha256": task["source_record_sha256"],
        "fixed_pose_sha256": audit.canonical_sha256(task["fixed_pose"]),
        "family_viewpoints_sha256": task["family_viewpoints_sha256"],
        "public_prefix_frame_count": len(public_prefix),
        "public_prefix_camera_sha256": [audit.sha256(path)
                                        for path in public_prefix],
        "private_prefix_mapping_receipts": [
            {"frame_index": int(path.parent.name[6:]),
             "private_mapping_sha256": audit.sha256(path)}
            for path in private_prefix],
        "relink_coverage_gap": task["program"] == "RELINK",
        "relink_collision_observed_this_run": False,
        "relink_collision_evidence_source": (
            "registered_D173_nonforced_endpoint_receipt"
            if task["program"] == "RELINK" else None),
        "semantic_positive_label_issued": False})
    return failure


def _launch(stage, task, task_path, source_root, simulator, family_limit, env):
    episode = episode_path(stage, task)
    require(not episode.exists(), "sealed slot exists; no relaunch")
    log = (stage / "private/logs" /
           ("%s_slot_%02d.log" % (task["family_id"].replace(":", "_"),
                                  task["slot"])))
    log.parent.mkdir(parents=True, exist_ok=True)
    handle = log.open("x", encoding="utf-8")
    child = subprocess.Popen(_worker_command(
        task, task_path, source_root, episode, simulator, family_limit),
        cwd=ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT,
        start_new_session=True)
    handle.close()
    try:
        audit.write_new_json(log.with_suffix(".launched.json"), {
            "family_id": task["family_id"], "slot": task["slot"],
            "pid": child.pid, "private_task_sha256": audit.sha256(task_path)})
    except Exception:
        child.terminate()
        child.wait()
        raise
    return child, log


def run(reviewed_code, scan_stage, endpoint_stage, source_root, output_root):
    bindings = bound_code(reviewed_code)
    config = audit.read_json(CONFIG)
    review_ref = config["expected_reviewed_code"]
    require(config["run_authorized"] is True and
            config["generation_authorized"] is True and
            config["status"] == "frozen_reviewed_generation" and
            type(review_ref) is str and len(review_ref) == 40 and
            config["semantic_positive_labels_allowed"] is False and
            config["training_authorized"] is False,
            "D-059 reviewed code and fixed generation gate remain closed")
    # The gate change itself creates a later commit. It may only change the
    # config/docs; reviewed implementation bytes must match the approved ref.
    subprocess.check_call(["git", "merge-base", "--is-ancestor",
                           review_ref, reviewed_code], cwd=ROOT)
    for relative in ("ops/vsmt/vm04_fixed_slot_raw_worker.py",
                     "ops/vsmt/vm04_fixed_slot_raw_manifest.py",
                     "ops/vsmt/vm04_fixed_slot_raw_stage.py",
                     "ops/vsmt/vm04_fixed_slot_raw_verify.py",
                     "src/vsmt/vm04_target_selection_v3.py",
                     "configs/vsmt/vm04_target_boundary_proposal_v3.json",
                     "tests/test_vm04_fixed_slot_raw_worker.py",
                     "tests/test_vm04_fixed_slot_raw_manifest.py",
                     "tests/test_vm04_fixed_slot_raw_stage.py",
                     "tests/test_vm04_fixed_slot_raw_verify.py"):
        approved = subprocess.check_output(
            ["git", "show", "%s:%s" % (review_ref, relative)], cwd=ROOT)
        require(hashlib.sha256(approved).hexdigest() ==
                audit.sha256(ROOT / relative),
                "science source changed since reviewed code: " + relative)
    stage = stage_path(output_root, reviewed_code)
    checked, _ = audit._marker(stage, "check")
    require(checked["reviewed_code"] == reviewed_code and
            checked["bound_sha256"] == bindings and
            checked["requested_workers"] ==
            checked["actual_workers"] == 2 and
            not (stage / "run.receipt.json").exists() and
            not (stage / "execution").exists(),
            "review check changed or stage already attempted")
    tasks, sources = manifest.frozen_tasks(
        scan_stage.resolve(), endpoint_stage.resolve(), source_root.resolve())
    manifest.seal(tasks, sources, stage / "tasks")
    simulator = Path(audit.read_json(audit.ENVIRONMENT_PATH)[
        "environment_separation"]["simulator_process"][
            "environment_path"]) / "bin/python"
    require(simulator.is_file(), "pinned simulator Python missing")
    require(audit.sha256(audit.ENVIRONMENT_PATH) ==
            config["source_simulator_environment_contract_sha256"],
            "D-135 isolated simulator environment contract changed")
    simulator_versions = verify_simulator_environment(
        simulator, audit.read_json(audit.ENVIRONMENT_PATH))
    initial_memory = audit._cgroup_memory_headroom_bytes()
    initial_gpu_devices = resource_probe.gpu_free_bytes_by_device()
    initial_disk = shutil.disk_usage(output_root).free
    cpu = resource_probe.safe_visible_cpu_count()
    require(type(initial_memory) is int and initial_memory >
            config["emergency_cgroup_headroom_bytes"] and
            min(initial_gpu_devices) > config["emergency_gpu_free_bytes"] and
            initial_disk >= config["minimum_initial_data_disk_free_bytes"] and
            cpu >= 1, "fresh CPU/RAM/GPU/disk capacity insufficient")
    env = dict(os.environ, PYTHONUNBUFFERED="1", OMP_NUM_THREADS="1",
               OPENBLAS_NUM_THREADS="1",
               XDG_RUNTIME_DIR=str(Path(output_root).resolve() / "runtime"))
    Path(env["XDG_RUNTIME_DIR"]).mkdir(parents=True, exist_ok=True)
    (stage / "execution").mkdir()
    family_limit = int(config["maximum_stage_bytes"])
    private_manifest = audit.read_json(stage / "tasks/private/task-manifest.json")
    task_paths = {(row["family_id"], row["slot"]):
                  stage / "tasks" / row["private_task_path"]
                  for row in private_manifest["rows"]}
    task_by_key = {(task["family_id"], task["slot"]): task for task in tasks}
    started = time.monotonic()
    exits, samples = [], []
    stop_reason = None

    def record_exit(task, child, log):
        code = child.wait()
        episode = episode_path(stage, task)
        terminal = _terminal_after_exit(episode, task, code)
        row = {"family_id": task["family_id"], "slot": task["slot"],
               "exit_code": code,
               "private_log_sha256": audit.sha256(log),
               "terminal_sha256": audit.sha256(terminal),
               "terminal_kind": terminal.name}
        audit.write_new_json(log.with_suffix(".exit.json"), row)
        exits.append(row)
        print("[%s:%02d] %s" % (task["family_id"], task["slot"],
              log.read_text(encoding="utf-8")), end="", flush=True)
        return code

    benchmark = tasks[0]
    key = (benchmark["family_id"], benchmark["slot"])
    child, log = _launch(stage, benchmark, task_paths[key], source_root,
                         simulator, family_limit, env)
    min_memory, min_gpu = initial_memory, list(initial_gpu_devices)
    peak_rss = 0
    benchmark_abort = None
    try:
        while child.poll() is None:
            memory = audit._cgroup_memory_headroom_bytes()
            gpu = resource_probe.gpu_free_bytes_by_device()
            peak_rss = max(peak_rss,
                           audit._linux_process_tree_rss_bytes([child.pid]))
            require(type(memory) is int and len(gpu) == len(min_gpu),
                    "benchmark resource observation disappeared")
            min_memory = min(min_memory, memory)
            min_gpu = [min(a, b) for a, b in zip(min_gpu, gpu)]
            if (memory < config["emergency_cgroup_headroom_bytes"] or
                    min(gpu) < config["emergency_gpu_free_bytes"] or
                    shutil.disk_usage(output_root).free <
                    config["emergency_data_disk_free_bytes"] or
                    audit._directory_bytes(stage) > config["maximum_stage_bytes"]):
                benchmark_abort = "benchmark_emergency_resource_guard"
                child.terminate()
            time.sleep(0.25)
    except Exception:
        benchmark_abort = "benchmark_resource_monitor_failed"
        if child.poll() is None:
            child.terminate()
    benchmark_code = record_exit(benchmark, child, log)
    observed_memory_demand = max(initial_memory - min_memory, peak_rss)
    observed_gpu_demand = max(a - b for a, b in
                              zip(initial_gpu_devices, min_gpu))
    current_memory = audit._cgroup_memory_headroom_bytes()
    current_gpu = resource_probe.gpu_free_bytes_by_device()
    requested = 0
    if (benchmark_abort is None and benchmark_code == 0 and
            audit._directory_bytes(stage) <= config["maximum_stage_bytes"] and
            observed_memory_demand > 0 and
            observed_gpu_demand > 0 and type(current_memory) is int):
        requested = safe_worker_count(
            cpu, current_memory, observed_memory_demand,
            min(current_gpu), observed_gpu_demand,
            int(config["emergency_cgroup_headroom_bytes"]),
            int(config["emergency_gpu_free_bytes"]),
            int(config["maximum_registered_simulator_concurrency"]))
    if requested == 0:
        stop_reason = (benchmark_abort or
                       "benchmark_or_resource_demand_insufficient")
    elif requested == 1:
        print("VM04_FIXED_SLOT_SINGLE_WORKER evidence=sampled_RAM_GPU_capacity "
              "estimated_remaining_slots=35", flush=True)
    active = []
    remaining = tasks[1:]
    peak_active = 0
    while remaining or active:
        while remaining and len(active) < requested and stop_reason is None:
            task = remaining.pop(0)
            key = (task["family_id"], task["slot"])
            try:
                launched, launched_log = _launch(
                    stage, task, task_paths[key], source_root,
                    simulator, family_limit, env)
            except Exception:
                stop_reason = "worker_launch_failed"
                episode = episode_path(stage, task)
                if episode.exists():
                    _terminal_after_exit(episode, task, -1)
                else:
                    not_started(stage, task, stop_reason)
                break
            active.append((task, launched, launched_log))
            peak_active = max(peak_active, len(active))
        if not active:
            break
        memory = audit._cgroup_memory_headroom_bytes()
        gpu = resource_probe.gpu_free_bytes_by_device()
        disk = shutil.disk_usage(output_root).free
        stage_bytes = audit._directory_bytes(stage)
        samples.append({"memory_headroom_bytes": memory,
                        "gpu_free_bytes_by_device": gpu,
                        "disk_free_bytes": disk,
                        "stage_bytes": stage_bytes,
                        "active_workers": len(active)})
        if (type(memory) is not int or
                memory < config["emergency_cgroup_headroom_bytes"] or
                min(gpu) < config["emergency_gpu_free_bytes"] or
                disk < config["emergency_data_disk_free_bytes"] or
                stage_bytes > config["maximum_stage_bytes"]):
            stop_reason = "emergency_resource_guard"
            for _, running, _ in active:
                if running.poll() is None:
                    running.terminate()
        for task, running, running_log in list(active):
            if running.poll() is None:
                continue
            code = record_exit(task, running, running_log)
            active.remove((task, running, running_log))
            if code != 0 and stop_reason is None:
                stop_reason = "worker_process_failure"
        if active:
            time.sleep(0.25)
    for task in remaining:
        not_started(stage, task, stop_reason or "dispatch_not_started")
    ordered = []
    for task in tasks:
        episode = episode_path(stage, task)
        candidates = [episode / name for name in (
            "raw.receipt.json", "raw.failure.json", "raw.not_started.json")]
        present = [path for path in candidates if path.is_file()]
        require(len(present) == 1, "original fixed slot has no unique terminal")
        terminal = audit.read_json(present[0])
        require(terminal["family_id"] == task["family_id"] and
                terminal["slot"] == task["slot"] and
                terminal["episode_id"] == task["episode_id"] and
                terminal["constructed"] is False and
                terminal["task_sha256"] == audit.canonical_sha256(task),
                "terminal slot identity or construction boundary changed")
        ordered.append({"family_id": task["family_id"],
                        "slot": task["slot"], "program": task["program"],
                        "kind": present[0].name,
                        "terminal_sha256": audit.sha256(present[0])})
    audit.write_new_json(stage / "private/resource-samples.json", {
        "initial_memory_headroom_bytes": initial_memory,
        "initial_gpu_free_bytes_by_device": initial_gpu_devices,
        "initial_disk_free_bytes": initial_disk,
        "benchmark_memory_demand_bytes": observed_memory_demand,
        "benchmark_gpu_demand_bytes": observed_gpu_demand,
        "benchmark_peak_rss_bytes": peak_rss,
        "samples": samples})
    receipt = stage / "run.receipt.json"
    audit.write_new_json(receipt, {
        "schema_version": "vsmt-vm04-fixed-slot-raw-stage-receipt-v1",
        "reviewed_code": reviewed_code, "bound_sha256": bindings,
        "simulator_versions": simulator_versions,
        "check_receipt_sha256": audit.sha256(stage / "check.receipt.json"),
        "private_task_manifest_sha256": audit.sha256(
            stage / "tasks/private/task-manifest.json"),
        "private_resource_samples_sha256": audit.sha256(
            stage / "private/resource-samples.json"),
        "requested_workers": requested,
        "actual_peak_workers": peak_active,
        "benchmark_worker_count": 1,
        "benchmark_slot": [benchmark["family_id"], benchmark["slot"]],
        "task_partition": [{"family_id": row["family_id"],
                            "slot": row["slot"]} for row in ordered],
        "worker_exits": sorted(exits,
                               key=lambda row: (row["family_id"], row["slot"])),
        "deterministic_merge_order": ordered,
        "terminal_slot_count": 36,
        "terminal_complete": True,
        "stop_reason": stop_reason,
        "wall_seconds": time.monotonic() - started,
        "constructed_count": 0,
        "construction_assessment_pending": True,
        "semantic_positive_labels_issued": 0,
        "new_relink_collision_actions_executed": 0,
        "memory_history_checked": False,
        "training_steps": 0,
        "success": stop_reason is None})
    if stop_reason is None:
        audit.write_new_json(stage / "run.success.json", {
            "receipt_sha256": audit.sha256(receipt), "success": True})
    print("VM04_FIXED_SLOT_RUN_TERMINAL stage=%s slots=36 workers=%s "
          "stop=%s" % (stage, requested, stop_reason), flush=True)
    require(stop_reason is None, "fixed stage stopped; preserve all slot outputs")


def verify(reviewed_code, output_root, *, record=True):
    """Read every sealed slot in parallel before exporting an anonymous report."""
    stage = stage_path(output_root, reviewed_code)
    require((stage / "verify.receipt.json").exists() != record,
            "fixed slot verification marker state changed")
    receipt_path = stage / "run.receipt.json"
    receipt = audit.read_json(receipt_path)
    ordered = receipt["deterministic_merge_order"]
    require(receipt["reviewed_code"] == reviewed_code and
            receipt["terminal_slot_count"] == len(ordered) == 36 and
            audit.sha256(stage / "tasks/private/task-manifest.json") ==
            receipt["private_task_manifest_sha256"],
            "run or private task manifest changed before verification")
    private_rows = audit.read_json(
        stage / "tasks/private/task-manifest.json")["rows"]
    public_rows = audit.read_json(
        stage / "tasks/public/task-manifest.json")["rows"]
    require(len(private_rows) == len(public_rows) == 36 and
            [{"family_id": row["family_id"], "slot": row["slot"],
              "episode_id": row["episode_id"]} for row in private_rows] ==
            public_rows, "sealed public/private slot order changed")
    tasks = {}
    for row in private_rows:
        task_path = stage / "tasks" / row["private_task_path"]
        require(audit.sha256(task_path) == row["private_task_sha256"],
                "sealed private task bytes changed")
        tasks[(row["family_id"], row["slot"])] = audit.read_json(task_path)
    require(len(tasks) == 36, "sealed slot key repeated")
    memory = audit._cgroup_memory_headroom_bytes()
    cpu = resource_probe.safe_visible_cpu_count()
    disk = shutil.disk_usage(output_root).free
    config = audit.read_json(CONFIG)
    reserve = config["emergency_cgroup_headroom_bytes"]
    # SHA reads one 1-MiB block at a time; 64 MiB per I/O thread is a
    # conservative RAM allowance. There is one independent task per slot.
    requested = (min(36, cpu, (memory - reserve) // (64 * 1024 * 1024))
                 if type(memory) is int and type(cpu) is int else 0)
    require(requested >= 1 and
            disk >= config["emergency_data_disk_free_bytes"],
            "CPU/RAM/disk capacity insufficient for fixed raw verification")
    if requested == 1:
        print("VM04_FIXED_SLOT_VERIFY_SINGLE_WORKER evidence=sampled_CPU_RAM "
              "estimated_slots=36", flush=True)

    def one(row):
        key = (row["family_id"], row["slot"])
        task = tasks[key]
        require(row["program"] == task["program"],
                "merge order program differs from sealed task")
        episode = episode_path(stage, task)
        result = raw_verify.verify_slot(
            episode, task, episode / row["kind"], row["terminal_sha256"])
        return {"family_id": row["family_id"], "slot": row["slot"],
                **result}

    results, failures = {}, []
    with ThreadPoolExecutor(max_workers=requested) as pool:
        future_rows = {pool.submit(one, row): row for row in ordered}
        for future in as_completed(future_rows):
            row = future_rows[future]
            key = (row["family_id"], row["slot"])
            try:
                results[key] = future.result()
            except Exception as error:
                failures.append({"family_id": key[0], "slot": key[1],
                                 "error_type": type(error).__name__,
                                 "private_reason": str(error)})
    success = not failures and len(results) == 36
    verified_slots = [results[(row["family_id"], row["slot"])]
                      for row in ordered if
                      (row["family_id"], row["slot"]) in results]
    if not record:
        if failures:
            audit.write_new_json(
                stage / "private/export-verify-failures.json",
                {"failures": sorted(
                    failures, key=lambda row: (row["family_id"],
                                               row["slot"]))})
        require(success, "raw bytes changed after verify; preserve failure")
        prior, _ = audit._marker(stage, "verify")
        require(prior["verified_slots"] == verified_slots,
                "raw slot verification changed before export")
        print("VM04_FIXED_SLOT_EXPORT_REVERIFIED slots=36 workers=%s" %
              requested, flush=True)
        return
    private_failure_sha256 = None
    if failures:
        private_failure_path = stage / "private/raw-verify-failures.json"
        audit.write_new_json(private_failure_path, {"failures": sorted(
            failures, key=lambda row: (row["family_id"], row["slot"]))})
        private_failure_sha256 = audit.sha256(private_failure_path)
    verify_receipt = stage / "verify.receipt.json"
    audit.write_new_json(verify_receipt, {
        "schema_version": "vsmt-vm04-fixed-slot-raw-verify-v1",
        "reviewed_code": reviewed_code,
        "run_receipt_sha256": audit.sha256(receipt_path),
        "private_task_manifest_sha256":
            receipt["private_task_manifest_sha256"],
        "requested_workers": requested, "actual_workers": requested,
        "resource_basis": {"visible_cpu": cpu,
                           "cgroup_memory_headroom_bytes": memory,
                           "disk_free_bytes": disk,
                           "sha_block_bytes": 1024 * 1024,
                           "ram_allowance_per_worker_bytes": 64 * 1024 * 1024,
                           "io_policy": "one_read_only_stream_per_worker"},
        "verified_slots": verified_slots,
        "failures": [{"family_id": row["family_id"], "slot": row["slot"],
                      "error_type": row["error_type"],
                      "reason": "digest_or_file_boundary_failed"}
                     for row in sorted(
                         failures, key=lambda row: (row["family_id"],
                                                  row["slot"]))],
        "private_failure_sha256": private_failure_sha256,
        "semantic_positive_labels_issued": 0,
        "private_semantics_evaluated": False,
        "success": success})
    if success:
        audit.write_new_json(stage / "verify.success.json", {
            "receipt_sha256": audit.sha256(verify_receipt), "success": True})
    print("VM04_FIXED_SLOT_VERIFY_TERMINAL stage=%s slots=%s workers=%s "
          "success=%s" % (stage, len(results), requested, success), flush=True)
    require(success, "fixed raw digest verification failed; preserve receipt")


def export(reviewed_code, output_root, report):
    stage = stage_path(output_root, reviewed_code)
    receipt = audit.read_json(stage / "run.receipt.json")
    verified, _ = audit._marker(stage, "verify")
    require(verified["reviewed_code"] == reviewed_code and
            verified["run_receipt_sha256"] ==
            audit.sha256(stage / "run.receipt.json") and
            len(verified["verified_slots"]) == 36 and
            verified["private_semantics_evaluated"] is False,
            "raw verification changed before export")
    require(receipt["reviewed_code"] == reviewed_code and
            receipt["terminal_slot_count"] == 36 and
            not Path(report).exists(), "fixed stage/report identity changed")
    verify(reviewed_code, output_root, record=False)
    counts = {}
    for row in receipt["deterministic_merge_order"]:
        task = {"family_id": row["family_id"], "slot": row["slot"],
                "episode_id": next(item["episode_id"] for item in
                    audit.read_json(stage / "tasks/public/task-manifest.json")[
                        "rows"] if item["family_id"] == row["family_id"] and
                        item["slot"] == row["slot"])}
        terminal = episode_path(stage, task) / row["kind"]
        require(audit.sha256(terminal) == row["terminal_sha256"],
                "terminal bytes changed before export")
        key = (row["family_id"], row["program"], row["kind"])
        counts[key] = counts.get(key, 0) + 1
    audit.write_new_json(Path(report), {
        "schema_version": "vsmt-vm04-fixed-slot-raw-public-report-v1",
        "reviewed_code": reviewed_code,
        "run_receipt_sha256": audit.sha256(stage / "run.receipt.json"),
        "raw_verify_receipt_sha256": audit.sha256(
            stage / "verify.receipt.json"),
        "raw_file_digests_verified": True,
        "terminal_slot_count": 36,
        "terminal_complete": True,
        "counts_by_family_program_kind": [
            {"family_id": family, "program": program,
             "terminal_kind": kind, "count": count}
            for (family, program, kind), count in sorted(counts.items())],
        "relink_coverage_gap_count": sum(count for (family, program, kind),
                                         count in counts.items()
                                         if program == "RELINK" and
                                         kind != "raw.receipt.json"),
        "relink_collision_evidence_source":
            "registered_D173_nonforced_endpoint_receipt",
        "source_endpoint_receipt_sha256": audit.read_json(CONFIG)[
            "source_d173_endpoint_receipt_sha256"],
        "new_relink_collision_actions_executed": 0,
        "memory_history_checked": False,
        "requested_workers": receipt["requested_workers"],
        "actual_peak_workers": receipt["actual_peak_workers"],
        "stop_reason": receipt["stop_reason"],
        "constructed_count": 0,
        "construction_assessment_pending": True,
        "candidate_miss_count": None,
        "private_ids_exported": False,
        "semantic_positive_labels_issued": 0,
        "training_steps": 0})
    print("VM04_FIXED_SLOT_EXPORTED report=%s" % report, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=("check", "run", "verify", "export"))
    parser.add_argument("--reviewed-code", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--scan-stage", type=Path)
    parser.add_argument("--endpoint-stage", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.step == "check":
        check(args.reviewed_code, args.output_root)
    elif args.step == "run":
        require(all((args.scan_stage, args.endpoint_stage, args.source_root)),
                "run needs exact frozen scan/endpoint/source paths")
        run(args.reviewed_code, args.scan_stage, args.endpoint_stage,
            args.source_root, args.output_root)
    elif args.step == "verify":
        verify(args.reviewed_code, args.output_root)
    else:
        require(args.report is not None, "export needs a precise report path")
        export(args.reviewed_code, args.output_root, args.report)


if __name__ == "__main__":
    main()
