"""Fixed check/export delivery for accepted corrected train; no algorithm copy."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from cpmt.m1_branch_preflight import fixed_plan, require, summarize
from cpmt.run_provenance import capture_run_provenance, source_tree_sha256
from run_m1_train_branch_preflight import check_generation, file_digest, read_json, write_json

TRAIN_MARKER = Path("/root/autodl-tmp/cpmt_outputs/m1-v7-d051-train-719bb2d494d9/generation.ok.json")
TRAIN_DIGEST = "a1d9f7517feb3c301e856d774369adc9754475a884d236bc49dad43af231136e"
EXPORT_RELATIVE = "results/m1_v7_d051_train_branch_preflight.json"


def artifact_hashes(directory):
    return {p.relative_to(directory).as_posix(): file_digest(p)
            for p in sorted(directory.rglob("*")) if p.is_file()}


def capacity():
    cpu = float(len(os.sched_getaffinity(0)))
    memory = next(int(line.split()[1]) / 2**20 for line in Path("/proc/meminfo").read_text().splitlines()
                  if line.startswith("MemAvailable:"))
    mount = Path("/sys/fs/cgroup")
    relative = next((line.split(":", 2)[2] for line in Path("/proc/self/cgroup").read_text().splitlines()
                     if line.startswith("0::")), "/")
    current = (mount / relative.lstrip("/")).resolve()
    folders = {mount}
    if current.is_relative_to(mount):
        folders.update(p for p in (current, *current.parents) if p.is_relative_to(mount))
    for folder in folders:
        limit = folder / "cpu.max"
        if limit.exists():
            quota, period = limit.read_text().split()
            if quota != "max":
                cpu = min(cpu, int(quota) / int(period))
        limit, used = folder / "memory.max", folder / "memory.current"
        if limit.exists() and used.exists() and limit.read_text().strip() != "max":
            memory = min(memory, max(0, int(limit.read_text()) - int(used.read_text())) / 2**30)
    # A conservative process budget, not an estimate of peak use.
    workers = min(4, int(cpu), int(max(0, memory - 4) / 4))
    require(workers >= 1, "insufficient CPU/RAM headroom; check not started")
    return {"workers": workers, "cpu_capacity": cpu, "available_memory_gib": memory,
            "torch_threads_per_worker": 1, "device": "cpu"}


def verify_completion(stage, binding):
    complete = read_json(stage / "completion.json")
    require(complete["binding"] == binding, "phase source/input binding changed; review required")
    run = stage / "run"
    require(artifact_hashes(run) == complete["files"], "retained preflight files changed")
    report = read_json(run / "report.json") if (run / "report.json").exists() else None
    if report is not None:
        require(report["schema_version"] == "cpmt-train-branch-preflight-report-v1", "wrong report schema")
        require(report["binding"]["plan"] == fixed_plan()
                and report["binding"]["train_arrays_digest"] == TRAIN_DIGEST
                and report["binding"]["generation_marker_sha256"] == binding["generation_marker_sha256"]
                and report["binding"]["source_and_tests_sha256"] == binding["source_and_tests_sha256"],
                "runner report input/source mismatch")
        for name in ("validation_access", "test_access", "training_performed", "model_selection_performed",
                     "scientific_acceptance_gate_changed"):
            require(report[name] is False, "report crossed boundary: " + name)
        require(report["provenance"]["git_dirty"] is False, "dirty check provenance")
        require(report["gate"] == summarize(report["groups"]), "inconsistent engineering gate")
        require(complete["exit_code"] == (0 if report["gate"]["pass"] else 1), "report/exit mismatch")
        for row in report["groups"]:
            directory = run / f"group_{row['group']:06d}"
            require(read_json(directory / "result.json") == {k: v for k, v in row.items() if k != "files"},
                    "group report mismatch")
            require(artifact_hashes(directory) == row["files"], "group file hashes mismatch")
    else:
        require(complete["exit_code"] != 0, "success without a report is invalid")
    return complete, report


def run_check(stage, binding, workers, marker=TRAIN_MARKER):
    if (stage / "completion.json").exists():
        complete, _ = verify_completion(stage, binding)
        print("PREFLIGHT_REUSED exit=" + str(complete["exit_code"]), flush=True)
        return complete["exit_code"]
    require(not (stage / "attempt.json").exists() and not (stage / "run").exists(),
            "interrupted attempt retained; no automatic restart (export diagnostics after review)")
    write_json(stage / "attempt.json", {"binding": binding, "workers": workers})
    command = [sys.executable, "scripts/run_m1_train_branch_preflight.py", "--generation-marker", str(marker),
               "--output", str(stage / "run"), "--workers", str(workers)]
    began = time.monotonic()
    with (stage / "check.log").open("x", encoding="utf-8") as log:
        with subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8", errors="replace", bufsize=1) as process:
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line); log.flush()
            code = process.wait()
    write_json(stage / "completion.json", {"binding": binding, "exit_code": code,
                                           "wall_seconds": time.monotonic() - began,
                                           "files": artifact_hashes(stage / "run")})
    verify_completion(stage, binding)
    return code


def export(stage, binding, generation, target):
    complete, report = verify_completion(stage, binding)
    diagnostics = {}
    for relative in complete["files"]:
        if Path(relative).name in {"failure.json", "failure_snapshot.json", "generation_failure_context.json"}:
            diagnostics[relative] = read_json(stage / "run" / relative)
    scientific = {"schema_version": "cpmt-train-branch-preflight-export-v1", "generation_marker": generation,
                  "phase_completion": complete, "report": report, "failure_diagnostics": diagnostics,
                  "test_access": False, "validation_access": False}
    if (stage / "check.log").exists():
        scientific["check_log_tail"] = (stage / "check.log").read_text(encoding="utf-8").splitlines()[-120:]
    if target.exists():
        payload = read_json(target)
        require(all(payload.get(k) == v for k, v in scientific.items()), "existing export differs; refusing overwrite")
        print("EXPORT_REUSED path=" + str(target), flush=True)
    else:
        payload = {**scientific, "export_provenance": capture_run_provenance(
            ROOT, component="train_branch_preflight_export", entrypoint=Path(__file__))}
        write_json(target, payload)
    require(read_json(target) == payload, "export round-trip verification failed")
    print(f"EXPORT_VERIFIED path={target} sha256={file_digest(target)}", flush=True)
    print("PREFLIGHT_EXPORT_OK engineering_pass=" + str(bool(report and report["gate"]["pass"])).lower(), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "export"))
    args = parser.parse_args()
    require(os.name == "posix", "server phase requires Linux")
    from cpmt.m1_protocol import load_and_validate
    hard = load_and_validate(ROOT / "configs/m1_hard_condition_v7.json")
    # Do not infer a dataset from whichever directory happened to finish last.
    generation = check_generation(ROOT, TRAIN_MARKER, hard)
    require(generation["arrays_digest"] == TRAIN_DIGEST, "not the accepted corrected train arrays")
    source = source_tree_sha256(ROOT, roots=("src", "scripts", "configs", "tests"))
    binding = {"generation_marker_sha256": file_digest(TRAIN_MARKER), "source_and_tests_sha256": source,
               "ops_sha256": file_digest(Path(__file__)), "shell_sha256": file_digest(ROOT / "ops/m1_train_preflight.sh")}
    stage = TRAIN_MARKER.parent.parent / ("m1-v7-d051-branch-preflight-" + source[:12])
    require(stage.parent.is_dir(), "server output parent is absent")
    stage.mkdir(exist_ok=True)
    import fcntl
    with (stage / "phase.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        print(f"PREFLIGHT_STAGE action={args.action} output={stage}", flush=True)
        if args.action == "export":
            export(stage, binding, generation, ROOT / EXPORT_RELATIVE)
            return 0
        require(capture_run_provenance(ROOT, component="preflight_check")["git_dirty"] is False,
                "clean checkout required for check")
        resources = capacity()
        print("PREFLIGHT_RESOURCES=" + json.dumps(resources, sort_keys=True), flush=True)
        code = run_check(stage, binding, resources["workers"])
        print("TRAIN_BRANCH_PREFLIGHT_" + ("OK" if code == 0 else "FAILED"), flush=True)
        print("NEXT=bash ops/m1_train_preflight.sh export (also exports a completed failed check)", flush=True)
        return code


if __name__ == "__main__":
    raise SystemExit(main())
