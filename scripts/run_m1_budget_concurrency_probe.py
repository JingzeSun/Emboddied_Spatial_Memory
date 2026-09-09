#!/usr/bin/env python3
"""Bounded AutoDL runtime comparison using existing train-only profile paths.

The pool threads only launch fresh Python processes. They never train models
in shared Python/Torch state. No scope fix, new data or hyperparameter search.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from cpmt.m1_scope_rebuild import feasible_layouts, runtime_recommendation
from cpmt.m1_s5_training import read_json, require, write_json
from cpmt.run_provenance import capture_run_provenance, file_sha256, source_tree_sha256


def hardware():
    affinity = len(os.sched_getaffinity(0))
    cpu_limits = [float(affinity)]
    memory_limits = []
    cgroups = {}
    # Inspect the current cgroup and every visible ancestor, not host CPU count.
    relative = next((line.split(":", 2)[2] for line in Path("/proc/self/cgroup").read_text().splitlines()
                     if line.startswith("0::")), "/")
    mount = Path("/sys/fs/cgroup")
    current = (mount / relative.lstrip("/")).resolve()
    paths = [mount]
    if current.is_relative_to(mount) and current.exists():
        paths += [current, *[p for p in current.parents if p.is_relative_to(mount)]]
    for folder in sorted(set(paths)):
        cpu = folder / "cpu.max"
        if cpu.exists():
            quota, period = cpu.read_text().split()
            cgroups[str(cpu)] = [quota, period]
            if quota != "max":
                cpu_limits.append(int(quota) / int(period))
        limit, used = folder / "memory.max", folder / "memory.current"
        if limit.exists() and used.exists() and limit.read_text().strip() != "max":
            memory_limits.append(max(0, int(limit.read_text()) - int(used.read_text())) / 2**30)
    # cgroup v1 fallback used by some older container hosts.
    quota = mount / "cpu/cpu.cfs_quota_us"
    period = mount / "cpu/cpu.cfs_period_us"
    if quota.exists() and period.exists() and int(quota.read_text()) > 0:
        cpu_limits.append(int(quota.read_text()) / int(period.read_text()))
    v1_limit = mount / "memory/memory.limit_in_bytes"
    v1_used = mount / "memory/memory.usage_in_bytes"
    if v1_limit.exists() and v1_used.exists():
        memory_limits.append(max(0, int(v1_limit.read_text())-int(v1_used.read_text())) / 2**30)
    mem = {line.split(":")[0]: int(line.split()[1]) for line in Path("/proc/meminfo").read_text().splitlines()
           if line.startswith("MemAvailable:")}
    memory_limits.append(mem["MemAvailable"] / 2**20)
    lines = subprocess.check_output(["nvidia-smi", "--query-gpu=index,uuid,name,memory.total,memory.free",
                                     "--format=csv,noheader,nounits"], text=True).strip().splitlines()
    require(len(lines) == 1, "runtime probe requires one visible physical GPU; inspect multi-GPU placement first")
    index, uuid, name, total, free = [x.strip() for x in lines[0].split(",")]
    return {"cpu_affinity_count": affinity, "cpu_capacity": min(cpu_limits), "cgroup_cpu_limits": cgroups,
            "host_available_gib": min(memory_limits), "gpu_index": index, "gpu_uuid": uuid,
            "gpu_name": name, "gpu_total_gib": float(total)/1024, "gpu_free_gib": float(free)/1024}


def run(out):
    require(sys.platform == "linux", "AutoDL only; no local heavy workload")
    plan_path = PROJECT / "configs/m1_scope_rebuild_plan.json"
    plan = read_json(plan_path)
    require(plan["concurrency"]["benchmark_steps_per_model"] == 300, "profile budget changed")
    require(not subprocess.check_output(["git", "status", "--porcelain"], cwd=PROJECT).strip(), "clean checkout required")
    changed = subprocess.check_output(["git", "diff", "--name-only", "05bc12902d6d54ecbeaa670b4dee52b3b67901f1",
                                      "HEAD", "--", "src", "scripts", "configs"], cwd=PROJECT, text=True).splitlines()
    require(set(changed) <= {"configs/m1_scope_rebuild_plan.json", "src/cpmt/m1_scope_rebuild.py",
                            "scripts/run_m1_budget_concurrency_probe.py"}, "historical profiling science changed")
    probe_path = PROJECT / "results/m1_v6_d047_endpoint_probe.json"
    require(file_sha256(probe_path) == "d15831b42057f1591dacba8b27fa85f2d944761b29ead466d6de724a0750b058", "probe export changed")
    train = Path(read_json(probe_path)["endpoint_probe"]["input_arrays"]["path"])
    require(train.is_file(), "original train arrays missing; no automatic generation")
    for entry in (out / "diagnostic_report.json", out / "failure.json", out / "benchmark_started.json"):
        require(not entry.exists(), "existing benchmark attempt requires review/reuse: " + str(entry))
    machine = hardware()
    layouts, skipped = feasible_layouts(plan, cpu_capacity=machine["cpu_capacity"],
                                        gpu_free_gib=machine["gpu_free_gib"], host_available_gib=machine["host_available_gib"])
    require(any(x == {"workers": 1, "threads": 1} for x in layouts), "insufficient capacity even for serial profile")
    provenance = capture_run_provenance(PROJECT, component="m1_budget_concurrency_probe", entrypoint=Path(__file__))
    binding = {"plan_sha256": file_sha256(plan_path), "source_tree_sha256": provenance["source_tree_sha256"],
               "train_path": str(train), "train_file_sha256": file_sha256(train),
               "train_manifest_sha256": file_sha256(train.with_suffix(".manifest.json"))}
    write_json(out / "benchmark_started.json", {"binding": binding, "hardware": machine,
                                                 "layouts": layouts, "skipped": skipped, "provenance": provenance})
    print("CONCURRENCY_HARDWARE " + json.dumps(machine), flush=True)
    print("CONCURRENCY_LAYOUTS " + json.dumps({"run": layouts, "skipped": skipped}), flush=True)
    results = []
    tasks = plan["concurrency"]["benchmark_tasks"]
    require(tasks == ["transformer_0", "mlp_0", "transformer_1", "mlp_1"], "fixed task set changed")
    for layout in layouts:
        workers, threads = layout["workers"], layout["threads"]
        directory = out / f"workers_{workers}_threads_{threads}"
        directory.mkdir()
        print(f"CONCURRENCY_LAYOUT_BEGIN workers={workers} threads={threads} tasks=4", flush=True)
        def execute(task):
            architecture = "cross_candidate_set_transformer_v1" if task.startswith("transformer") else "shared_candidate_mlp_v1"
            destination = directory / task
            destination.mkdir()
            env = dict(os.environ, OMP_NUM_THREADS=str(threads), MKL_NUM_THREADS=str(threads),
                       OPENBLAS_NUM_THREADS=str(threads), CUDA_VISIBLE_DEVICES=machine["gpu_uuid"])
            command = [sys.executable, "scripts/run_m1_train_inner_dev_budget.py", "--train", str(train),
                       "--out-dir", str(destination), "--architecture", architecture, "--device", "cuda",
                       "--threads", str(threads), "--runtime-profile-only"]
            before = time.monotonic()
            with (destination / "worker.log").open("w", encoding="utf-8") as log:
                completed = subprocess.run(command, cwd=PROJECT, env=env, stdout=log, stderr=subprocess.STDOUT)
            write_json(destination / "exit.json", {"exit_code": completed.returncode, "command": command,
                                                   "elapsed_seconds": time.monotonic()-before})
            require(completed.returncode == 0, f"profile failed: {destination}/worker.log")
            profile_path = destination / "runtime_profile.json"
            profile = read_json(profile_path)
            require(profile["profile"]["steps"] == 300 and profile["architecture"] == architecture, "wrong profile work")
            require(all(profile[k] is False for k in ["formal_run", "selection_performed", "scientific_metrics_exported",
                                                       "validation_arrays_read", "test_access"]), "profile boundary violation")
            print(f"CONCURRENCY_TASK_OK workers={workers} threads={threads} task={task}", flush=True)
            return {"task": task, "runtime_profile": profile, "sha256": file_sha256(profile_path),
                    "elapsed_seconds": time.monotonic()-before}
        before = time.monotonic()
        # These threads only supervise subprocesses; no Torch objects are shared.
        with ThreadPoolExecutor(max_workers=workers) as pool:
            jobs = list(pool.map(execute, tasks))
        record = dict(layout, elapsed_seconds=time.monotonic()-before, tasks=jobs)
        write_json(directory / "layout.json", record)
        results.append(record)
        print(f"CONCURRENCY_LAYOUT_OK workers={workers} threads={threads} elapsed_seconds={record['elapsed_seconds']:.3f}", flush=True)
    require(file_sha256(train) == binding["train_file_sha256"], "train file changed during benchmark")
    require(file_sha256(train.with_suffix(".manifest.json")) == binding["train_manifest_sha256"], "manifest changed")
    require(source_tree_sha256(PROJECT) == binding["source_tree_sha256"], "source changed during benchmark")
    baseline = next(r for r in results if r["workers"] == r["threads"] == 1)
    for r in results:
        r["speedup_vs_1_process_1_thread"] = baseline["elapsed_seconds"] / r["elapsed_seconds"]
    report = {"schema_version": "cpmt-budget-concurrency-probe-v1", "binding": binding,
              "diagnostic_provenance": provenance, "hardware": machine, "skipped_layouts": skipped,
              "layouts": results, "recommendation": runtime_recommendation(results),
              "training_source": "old_train_arrays_only_runtime_probe", "validation_read": False,
              "test_access": False, "hyperparameters_selected": False, "production_scope_changed": False,
              "full_budget_parallel_runner_implemented": False,
              "limitations": ["Short cold-process workload; not full-grid wall time or formal latency.",
                              "Runtime profiles do not establish numerical equivalence of a future parallel budget runner.",
                              "Resource admission uses conservative estimates, not a guarantee against OOM.",
                              "Selected scheduling is provisional; corrected data require a resource and equivalence check."]}
    write_json(out / "diagnostic_report.json", report)
    print("CONCURRENCY_PROBE_COMPLETE " + json.dumps(report["recommendation"]), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    try:
        run(args.out_dir)
    except BaseException as error:
        path = args.out_dir / "failure.json"
        if not path.exists():
            write_json(path, {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()})
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
