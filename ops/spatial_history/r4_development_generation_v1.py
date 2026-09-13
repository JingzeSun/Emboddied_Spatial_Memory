"""Generate the 48 unsealed R4 development families after explicit code review."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import shutil
import subprocess
import sys
import time
import traceback
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = Path(__file__).resolve()
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests/spatial_world_model"))
from spatial_world_model.pair_contract import require
from spatial_world_model.r4_families_v2 import (
    categorical_shortcut, family_config, validate_manifest,
)
from spatial_world_model.r4_generation_v2 import run_family, save, verify_family
from spatial_world_model.r4_storage import file_record, inventory
from public_geometry_workers import dispatch

CONFIG_PATH = "configs/spatial_history/r4_development_generation_v1.json"
RUN = Path("/root/autodl-tmp/spatial-history/sh05-r4-development-generation-v1")
REPORT = ROOT / "results/spatial_history_r4_development_generation_v1.json"
STAGE = "SH-05-R4-development-generation-v1"
CONFIG_VERSION = "sh05-r4-development-generation-v1"
TESTS = (
    "test_r4_families_v2", "test_r4_public_v2", "test_r4_storage",
    "test_r4_generation_v2", "test_r4_generation_ops_v2",
    "test_r4_development_generation_v1",
)
BOUND = (
    CONFIG_PATH,
    "configs/spatial_history/learning_contract_r4_v2.json",
    "configs/spatial_history/r4_family_design_v2.json",
    "configs/spatial_history/r4_generation_v2.json",
    "configs/spatial_history/r4_repair_proposal_v2.json",
    "configs/spatial_history/two_gate_engineering_v1.json",
    "configs/spatial_history/public_geometry_parallel_v1.json",
    "configs/spatial_history/physics_v1.xml",
    "src/spatial_world_model/pair_contract.py",
    "src/spatial_world_model/two_gate_contract.py",
    "src/spatial_world_model/two_gate_physics.py",
    "src/spatial_world_model/two_gate_engineering.py",
    "src/spatial_world_model/public_geometry.py",
    "src/spatial_world_model/public_geometry_audit.py",
    "src/spatial_world_model/r4_query_v2.py",
    "src/spatial_world_model/r4_scoring_v2.py",
    "src/spatial_world_model/r4_families.py",
    "src/spatial_world_model/r4_families_v2.py",
    "src/spatial_world_model/r4_public_v2.py",
    "src/spatial_world_model/r4_trajectory.py",
    "src/spatial_world_model/r4_trajectory_v2.py",
    "src/spatial_world_model/r4_physics_v2.py",
    "src/spatial_world_model/r4_storage.py",
    "src/spatial_world_model/r4_generation_v2.py",
    "ops/spatial_history/public_geometry_workers.py",
    "ops/spatial_history/requirements-physics.txt",
    "ops/spatial_history/r4_development_generation_v1.py",
    "tests/spatial_world_model/test_r4_families_v2.py",
    "tests/spatial_world_model/test_r4_public_v2.py",
    "tests/spatial_world_model/test_r4_storage.py",
    "tests/spatial_world_model/test_r4_generation_v2.py",
    "tests/spatial_world_model/test_r4_generation_ops_v2.py",
    "tests/spatial_world_model/test_r4_development_generation_v1.py",
    "results/spatial_history_r4_engineering_subset_v2.json",
    "docs/DECISIONS.md",
    "docs/METHOD.md",
    "docs/DATA.md",
)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def binding():
    return {path: file_record(ROOT / path) for path in BOUND}


def configuration():
    config = read(ROOT / CONFIG_PATH)
    require(config["version"] == CONFIG_VERSION, "wrong config version")
    require(Path(config["run_directory"]) == RUN and ROOT / config["report"] == REPORT, "stage paths changed")
    require(all(config[key] is False for key in (
        "implementation_review_complete", "generation_authorized", "training_authorized", "confirmation_authorized"
    )), "review candidate config cannot silently authorize execution")
    for key in ("design", "learning_contract", "existing_report"):
        require(file_record(ROOT / config[key])["sha256"] == config[key + "_sha256"], key + " digest changed")
    design = read(ROOT / config["design"])
    contract = read(ROOT / config["learning_contract"])
    validate_manifest(design, read(ROOT / "configs/spatial_history/r4_repair_proposal_v2.json"))
    rows = [row for row in design["rows"] if row["split"] in config["allowed_splits"]]
    expected = [row["family_id"] for row in rows if row["family_id"] not in config["existing_family_ids"]]
    require(expected == config["new_family_ids"] and len(expected) == 48, "development family list changed")
    split_by_id = {row["family_id"]: row["split"] for row in design["rows"]}
    require(not any(split_by_id[family_id] in config["forbidden_splits"] for family_id in config["new_family_ids"]),
            "confirmation family included")
    require(contract["dataset"]["development_families_remaining"] == 48
            and contract["dataset"]["confirmation_families"] == 12, "learning split counts changed")
    return config


def rows_by_id():
    design = read(ROOT / configuration()["design"])
    return {row["family_id"]: row for row in design["rows"]}


def used(path):
    path = Path(path)
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file()) if path.exists() else 0


def tree_memory():
    processes = {}
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        try:
            fields = dict(line.split(":", 1) for line in (path / "status").read_text().splitlines() if ":" in line)
            processes[int(path.name)] = (int(fields["PPid"]), int(fields.get("VmHWM", "0 kB").split()[0]) * 1024)
        except (OSError, ValueError, KeyError):
            pass
    selected = {os.getpid()}
    while True:
        extended = selected | {pid for pid, (parent, _) in processes.items() if parent in selected}
        if extended == selected:
            return sum(processes[pid][1] for pid in selected if pid in processes)
        selected = extended


def prior_stage(config):
    report = read(ROOT / config["existing_report"])
    require(report["stage"] == "SH-04-R4-2-engineering-subset-v2" and report["status"] == "passed", "old subset not accepted")
    require(report["receipt"]["exit_code"] == 0 and report["receipt"]["accepted"], "old subset receipt failed")
    stage = Path(config["existing_stage"])
    require(stage.is_dir(), "old subset stage missing")
    require(inventory(stage) == report["source_inventory"], "old subset files changed")
    summary = report["artifacts_json"]["execution/summary.json"]
    require([row["family_id"] for row in summary["families"]] == config["existing_family_ids"], "old subset identity changed")
    return {
        "stage": str(stage), "report": file_record(ROOT / config["existing_report"]),
        "run_commit": report["receipt"]["commit"], "families": summary["families"],
    }


def environment():
    env = Path("/root/autodl-tmp/spatial-history-venv-v1")
    saved = read(env / "sh02-environment.json")
    requirements = file_record(ROOT / "ops/spatial_history/requirements-physics.txt")
    require(saved["exit_code"] == 0 and saved["requirements_sha256"] == requirements["sha256"], "physics environment marker changed")
    freeze = subprocess.check_output([sys.executable, "-m", "pip", "freeze", "--all"], text=True).splitlines()
    require(freeze == saved["freeze"], "physics environment dependency lock changed")
    return {"prefix": sys.prefix, "requirements": requirements, "freeze": freeze}


def loaded_tests():
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(name)) for name in TESTS)
    names = []
    def visit(item):
        if isinstance(item, unittest.TestSuite):
            for child in item:
                visit(child)
        else:
            names.append(item.id())
    visit(suite)
    return suite, sorted(names)


def check():
    if RUN.exists():
        return verify_check()
    config = configuration()
    require(not git("status", "--porcelain", "--", *BOUND), "commit bound files before check")
    before, commit = binding(), git("rev-parse", "HEAD")
    prior, env = prior_stage(config), environment()
    RUN.mkdir()
    save(RUN / "started.json", {
        "stage": STAGE, "commit": commit, "binding": before, "prior": prior, "environment": env,
        "time_utc": datetime.now(timezone.utc).isoformat(), "config": config,
    })
    suite, names = loaded_tests()
    began = time.monotonic()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    passed = result.wasSuccessful() and not result.skipped and result.testsRun == len(names)
    save(RUN / "check.json", {
        "tests": names, "tests_run": result.testsRun, "failures": len(result.failures),
        "errors": len(result.errors), "skipped": len(result.skipped), "passed": passed,
        "elapsed_s": time.monotonic() - began, "simulation_steps": 0, "training_steps": 0,
    })
    require(passed, "checks failed")
    require(time.monotonic() - began <= config["limits"]["check_wall_s"], "check wall limit")
    require(binding() == before, "source changed during check")
    save(RUN / "check_receipt.json", {
        "exit_code": 0, "commit": commit, "binding": before, "prior": prior,
        "check": file_record(RUN / "check.json"),
    })
    return verify_check()


def verify_check():
    receipt = read(RUN / "check_receipt.json")
    started = read(RUN / "started.json")
    require(receipt["exit_code"] == 0 and receipt["commit"] == started["commit"], "check receipt mismatch")
    require(receipt["binding"] == started["binding"] == binding(), "check source changed")
    require(receipt["check"] == file_record(RUN / "check.json") and read(RUN / "check.json")["passed"], "check artifact changed")
    print(f"{STAGE} CHECKED tests={read(RUN / 'check.json')['tests_run']} exit=0", flush=True)
    return receipt


def capacity(workers):
    config = configuration()
    limits = config["limits"]
    require(workers in limits["workers_allowed"], "worker count outside registered range")
    free = shutil.disk_usage(RUN.parent).free
    return {
        "workers": workers, "visible_cpu_count": os.cpu_count(), "data_disk_free_bytes": free,
        "required_stage_and_reserve_bytes": limits["stage_bytes"] + limits["data_disk_reserve_bytes"],
        "disk_ready": free >= limits["stage_bytes"] + limits["data_disk_reserve_bytes"],
        "tree_rss_limit_bytes": limits["tree_rss_bytes"], "process_as_limit_bytes": limits["process_as_bytes"],
    }


def supervise(family_ids, workers):
    directory = RUN / "execution"
    began, peak = time.monotonic(), 0
    launched, exits, readers = [], [], {}
    config = configuration()
    def checkpoint():
        nonlocal peak
        peak = max(peak, tree_memory())
        require(time.monotonic() - began < config["limits"]["run_wall_s"], "generation wall limit")
        require(peak <= config["limits"]["tree_rss_bytes"], "generation RSS limit")
        require(shutil.disk_usage(RUN.parent).free >= config["limits"]["data_disk_reserve_bytes"], "data disk reserve crossed")
        for key, reader in readers.items():
            output = reader.read(8192)
            if output:
                print(f"[{key}] {output}", end="", flush=True)
    def launch(task):
        unit = directory / task["id"]
        unit.mkdir()
        log = (unit / "run.log").open("x")
        try:
            child = subprocess.Popen(
                [sys.executable, "-B", str(ENTRYPOINT), "_worker", "--family", task["id"]],
                cwd=ROOT, env=dict(os.environ, MUJOCO_GL="egl", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", PYTHONUNBUFFERED="1"),
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
            )
        finally:
            log.close()
        launched.append({"id": task["id"], "pid": child.pid})
        readers[task["id"]] = (unit / "run.log").open(errors="replace")
        save(unit / "launched.json", launched[-1])
        return child
    def abort(child):
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=10)
    def completed(task, child, error):
        row = {"id": task["id"], "pid": child.pid, "exit_code": child.returncode, "parent_error": error}
        exits.append(row)
        save(directory / task["id"] / "exit.json", row)
        require(child.returncode == 0 and error is None, "family worker failed: " + task["id"])
        return row
    try:
        dispatch([{"id": family_id} for family_id in family_ids], workers, launch, completed, checkpoint, abort)
        checkpoint()
    finally:
        for reader in readers.values():
            output = reader.read()
            if output:
                print(output, end="", flush=True)
            reader.close()
        save(directory / "processes.json", {
            "launched": launched, "exits": exits,
            "not_started": [key for key in family_ids if key not in {row["id"] for row in launched}],
            "missing_exit": [row["id"] for row in launched if row["id"] not in {done["id"] for done in exits}],
            "elapsed_s": time.monotonic() - began, "peak_tree_hwm_bytes": peak,
        })


def worker(family_id):
    config = configuration()
    checked = verify_check()
    release = read(RUN / "execution/release.json")
    require(release["reviewed_code"] == checked["commit"], "worker review binding changed")
    require(family_id in config["new_family_ids"], "family outside development release")
    limit = config["limits"]["process_as_bytes"]
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    row = rows_by_id()[family_id]
    base = read(ROOT / config["base"])
    family = RUN / "execution" / family_id
    last = [0.0]
    measured = [used(family), time.monotonic(), 0]
    def progress(event):
        now = time.monotonic()
        if now - measured[1] >= 1:
            measured[:] = [used(family), now, 0]
        reserve = event.get("reserve_bytes", 0)
        require(measured[0] + measured[2] + reserve <= config["limits"]["family_bytes"], "family byte cap")
        if event["phase"] != "allocate":
            measured[2] += reserve
        if now - last[0] > 3 or event["phase"].endswith("start"):
            print(event, flush=True)
            last[0] = now
    reference = (ROOT / base["physics_reference"]).read_bytes()
    require(hashlib.sha256(reference).hexdigest() == base["physics_reference_sha256"], "physics reference changed")
    result = run_family(family / "data", family_config(base, row), reference.decode(), read(ROOT / config["e0"]), progress)
    verified = verify_family(family / "data")
    require(result == verified and result["accepted"], "development family engineering gate failed")
    save(family / "verified.json", {
        "family_id": family_id, "accepted": True,
        "public_manifest": file_record(family / "data/public_manifest.json"),
        "labels_manifest": file_record(family / "data/labels_manifest.json"),
        "audit_manifest": file_record(family / "data/audit_manifest.json"),
        "family_result": file_record(family / "data/audit/family_result.json"),
        "bytes": used(family / "data"),
    })
    print(f"FAMILY COMPLETED id={family_id} accepted=True exit=0", flush=True)


def run(reviewed_code, declared_gib, workers):
    config, checked = configuration(), verify_check()
    if (RUN / "execution").exists():
        raise FileExistsError("execution already started; preserve and inspect instead of rerunning")
    require(reviewed_code == checked["commit"], "reviewed code must equal checked source commit")
    require(binding() == checked["binding"], "reviewed bound files changed after check")
    require(subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor",
                            checked["commit"], git("rev-parse", "HEAD")]).returncode == 0,
            "current checkout does not descend from reviewed code")
    require(declared_gib is not None and declared_gib >= config["limits"]["minimum_declared_new_data_gib"], "declare at least 18 GiB new-data allowance")
    require(not git("status", "--porcelain", "--", *BOUND), "bound files changed after check")
    cap = capacity(workers)
    require(cap["disk_ready"], "insufficient disk plus reserve")
    execution = RUN / "execution"
    execution.mkdir()
    save(execution / "release.json", {
        "reviewed_code": reviewed_code, "declared_available_new_data_gib": declared_gib,
        "workers": workers, "capacity": cap, "confirmation_authorized": False, "training_authorized": False,
    })
    began = time.monotonic()
    try:
        supervise(config["new_family_ids"], workers)
        results = [read(execution / family_id / "data/audit/family_result.json") for family_id in config["new_family_ids"]]
        existing = read(ROOT / config["existing_report"])["artifacts_json"]["execution/summary.json"]["families"]
        combined = [row["result"] for row in existing] + results
        shortcut = categorical_shortcut([row["success_matrix"] for row in combined])
        summary = {
            "new_family_count": 48, "existing_family_count": 4, "development_family_count": 52,
            "new_families": [{"family_id": key, "result": value} for key, value in zip(config["new_family_ids"], results)],
            "existing_families": existing, "all_family_gates_passed": all(row["accepted"] for row in combined),
            "categorical_shortcut": shortcut,
            "accepted": all(row["accepted"] for row in combined) and not shortcut["categorical_shortcut_unexcluded"],
            "confirmation_generated": False, "new_training_steps": 0, "new_weight_download_bytes": 0,
        }
        save(execution / "summary.json", summary)
        require(summary["accepted"], "development generation completed but aggregate gate failed")
        total_bytes = used(RUN) + (REPORT.stat().st_size if REPORT.exists() else 0)
        require(total_bytes <= config["limits"]["stage_bytes"], "stage bytes exceeded")
        save(RUN / "run_receipt.json", {
            "exit_code": 0, "commit": checked["commit"], "binding": checked["binding"],
            "elapsed_s": time.monotonic() - began, "workers": workers,
            "summary": file_record(execution / "summary.json"), "processes": file_record(execution / "processes.json"),
            "accepted": True,
        })
    except BaseException as error:
        save(execution / "failure.json", {"error": f"{type(error).__name__}: {error}", "elapsed_s": time.monotonic() - began})
        raise
    print(f"{STAGE} COMPLETED families=48 accepted=True exit=0", flush=True)


def verify():
    config, checked = configuration(), verify_check()
    receipt = read(RUN / "run_receipt.json")
    require(receipt["exit_code"] == 0 and receipt["commit"] == checked["commit"] and receipt["binding"] == checked["binding"], "run receipt mismatch")
    saved_path = RUN / "verify_receipt.json"
    if saved_path.exists():
        saved = read(saved_path)
        require(saved["exit_code"] == 0 and saved["summary"] == file_record(RUN / "execution/summary.json"), "saved verification changed")
        require(list(saved["families"]) == config["new_family_ids"], "saved family verification census changed")
        for family_id, record in saved["families"].items():
            require(record == file_record(RUN / "execution" / family_id / "verified.json"), "family verification record changed")
            verified = read(RUN / "execution" / family_id / "verified.json")
            for name in ("public_manifest", "labels_manifest", "audit_manifest"):
                require(verified[name] == file_record(RUN / "execution" / family_id / "data" / (name.replace("_manifest", "_manifest.json"))),
                        "sealed family manifest changed")
        print(f"{STAGE} VERIFIED reused=true families=48 exit=0", flush=True)
        return
    began = time.monotonic()
    records = {}
    for family_id in config["new_family_ids"]:
        result = verify_family(RUN / "execution" / family_id / "data")
        require(result["accepted"], "family no longer accepted: " + family_id)
        records[family_id] = file_record(RUN / "execution" / family_id / "verified.json")
    require(time.monotonic() - began <= config["limits"]["verify_wall_s"], "verification time limit")
    save(saved_path, {
        "exit_code": 0, "families": records, "elapsed_s": time.monotonic() - began,
        "summary": file_record(RUN / "execution/summary.json"),
    })
    print(f"{STAGE} VERIFIED families=48 accepted=True exit=0", flush=True)


def export():
    config = configuration()
    if REPORT.exists():
        require(read(REPORT)["stage"] == STAGE, "existing report differs")
        print(f"{STAGE} EXPORTED reused=true exit=0")
        return
    verify()
    report = {
        "stage": STAGE, "status": "passed", "source_run": str(RUN),
        "check_receipt": read(RUN / "check_receipt.json"), "run_receipt": read(RUN / "run_receipt.json"),
        "verify_receipt": read(RUN / "verify_receipt.json"), "release": read(RUN / "execution/release.json"),
        "processes": read(RUN / "execution/processes.json"), "summary": read(RUN / "execution/summary.json"),
        "stage_bytes": used(RUN), "confirmation_generated": False, "new_training_steps": 0,
    }
    raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    require(len(raw) <= config["limits"]["report_bytes"], "report byte limit")
    REPORT.write_bytes(raw)
    print(f"{STAGE} EXPORTED path={REPORT} bytes={len(raw)} sha256={hashlib.sha256(raw).hexdigest()} exit=0")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("capacity", "check", "run", "verify", "export", "_worker"))
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--reviewed-code")
    parser.add_argument("--available-new-data-gib", type=float)
    parser.add_argument("--family")
    args = parser.parse_args()
    require(platform.system() == "Linux" and Path("/root/autodl-tmp").is_mount(), "Linux data-disk server required")
    require(Path(sys.prefix) == Path("/root/autodl-tmp/spatial-history-venv-v1"), "use fixed physics environment")
    limit = configuration()["limits"]["process_as_bytes"]
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    if args.command == "_worker":
        worker(args.family)
    elif args.command == "capacity":
        print(json.dumps(capacity(args.workers), indent=2))
    elif args.command == "run":
        run(args.reviewed_code, args.available_new_data_gib, args.workers)
    else:
        {"check": check, "verify": verify, "export": export}[args.command]()


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        traceback.print_exc()
        sys.exit(1)
