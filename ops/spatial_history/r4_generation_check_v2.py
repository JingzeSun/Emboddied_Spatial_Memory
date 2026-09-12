"""R4-2 fixed check/run/verify/export delivery. Linux server only.

The run subcommand explicitly records the user's code/resource release. There
is no command for other families, confirmation, learning or downloading assets.
"""
import argparse
import ast
from contextlib import contextmanager
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import signal
import subprocess
import sys
import time
import threading
import traceback
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from spatial_world_model.pair_contract import require
from spatial_world_model.r4_families_v2 import manifest, validate_manifest, family_config, engineering_rows, categorical_shortcut
from spatial_world_model.r4_generation_v2 import save, run_family, verify_family
from spatial_world_model.r4_storage import file_record, inventory
from public_geometry_resources import capacity
from public_geometry_workers import dispatch

CONFIG = "configs/spatial_history/r4_generation_v2.json"
RUN = Path("/root/autodl-tmp/spatial-history/sh04-r4-engineering-subset-v2")
REPORT = ROOT / "results/spatial_history_r4_engineering_subset_v2.json"
STAGE = "SH-04-R4-2-engineering-subset-v2"
STAGE_CONFIG_DIGEST = "c8a3c6ae3938aed65e66ac9f62ae1c955ade5d74a522dd0ec2f6ed6ef906c170"
TESTS = ("test_r4_families_v2", "test_r4_public_v2", "test_r4_storage", "test_r4_generation_v2", "test_r4_generation_ops_v2")
BOUND = (
    CONFIG, "configs/spatial_history/r4_repair_proposal_v2.json", "configs/spatial_history/two_gate_engineering_v1.json",
    "configs/spatial_history/r4_family_design_v2.json",
    "configs/spatial_history/r4_family_design_v1.json",
    "configs/spatial_history/public_geometry_parallel_v1.json", "configs/spatial_history/physics_v1.xml",
    "src/spatial_world_model/__init__.py", "src/spatial_world_model/pair_contract.py",
    "src/spatial_world_model/two_gate_contract.py", "src/spatial_world_model/two_gate_physics.py",
    "src/spatial_world_model/two_gate_engineering.py", "src/spatial_world_model/r4_query_v2.py",
    "src/spatial_world_model/r4_scoring_v2.py", "src/spatial_world_model/public_geometry.py",
    "src/spatial_world_model/public_geometry_audit.py",
    "src/spatial_world_model/r4_trajectory.py",
    *[f"src/spatial_world_model/{name}.py" for name in
      ("r4_families_v2", "r4_public_v2", "r4_trajectory_v2", "r4_physics_v2", "r4_storage", "r4_generation_v2", "r4_families")],
    *[f"tests/spatial_world_model/{name}.py" for name in TESTS],
    "tests/spatial_world_model/test_two_gate_contract.py",
    "ops/spatial_history/r4_generation_check_v2.py", "ops/spatial_history/public_geometry_resources.py",
    "ops/spatial_history/public_geometry_workers.py", "ops/spatial_history/requirements-physics.txt",
    "results/spatial_history_r4_contract_v1.json", "results/spatial_history_public_geometry_parallel_v1.json",
    "results/spatial_history_r4_engineering_subset_v1.json", "results/spatial_history_r4_failure_diagnostics_v1.json",
    "docs/METHOD.md", "docs/DATA.md")
# Contract receipt is consumed in place after the single stage sync.
import r4_contract_check_v2 as contract_ops
BOUND = tuple(dict.fromkeys((*BOUND, *contract_ops.BOUND)))


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def binding():
    return {p: file_record(ROOT / p) for p in BOUND}


def configuration():
    c = read(ROOT / CONFIG)
    require(c["version"] == "sh04-r4-engineering-subset-v2" and c["tests"] == list(TESTS), "wrong stage config")
    require(all(c[k] is False for k in ("generation_authorized", "training_authorized", "weight_download_authorized",
                                       "confirmation_authorized", "remaining_inventory_executable", "confirmation_executable")),
            "base config cannot silently grant execution")
    from spatial_world_model.r4_families_v2 import digest
    require(digest(c) == STAGE_CONFIG_DIGEST, "registered v2 stage config changed")
    require(file_record(ROOT / c["protocol"])["sha256"] == c["source_proposal_sha256"], "accepted proposal bytes changed")
    return c


def environment():
    import hashlib
    env = Path("/root/autodl-tmp/spatial-history-venv-v1")
    saved = read(env / "sh02-environment.json")
    require(saved["exit_code"] == 0, "existing isolated environment has no successful setup")
    require(saved["requirements_sha256"] == hashlib.sha256((ROOT / "ops/spatial_history/requirements-physics.txt").read_bytes()).hexdigest(),
            "environment requirements changed")
    freeze = subprocess.check_output([sys.executable, "-m", "pip", "freeze", "--all"], text=True).splitlines()
    require(freeze == saved["freeze"], "existing environment dependency lock changed")
    return {"python": sys.version, "prefix": sys.prefix, "freeze": freeze,
            "setup_marker": file_record(env / "sh02-environment.json")}


def old_prereqs():
    """Verify imported reports against original Git blobs, never rerun R4-1/E0."""
    import hashlib
    verified = []
    for name in ("spatial_history_r4_contract_v1.json", "spatial_history_public_geometry_parallel_v1.json"):
        report = read(ROOT / "results" / name)
        receipt = report["receipt"]
        require(receipt["exit_code"] == 0, "failed prerequisite receipt")
        # These existing receipts use the original 2-space JSON encoding.
        raw = (json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        require(hashlib.sha256(raw).hexdigest() == report["receipt_sha256"], "prerequisite receipt digest")
        for path, expected in receipt["binding"].items():
            blob = subprocess.check_output(["git", "-C", str(ROOT), "show", f'{receipt["commit"]}:{path}'])
            require(hashlib.sha256(blob).hexdigest() == expected, "original prerequisite source mismatch: " + path)
        verified.append({"report": name, "file": file_record(ROOT / "results" / name), "commit": receipt["commit"]})
    return verified


def prereqs():
    c = configuration()
    verified = old_prereqs()
    contract = contract_ops.verify(contract_ops.RUN)
    require(contract["commit"] == git("rev-parse", "HEAD"), "v2 contract must be checked at this stage commit")
    verified.append({"stage": contract_ops.STAGE, "receipt": file_record(contract_ops.RUN / "receipt.json"),
                     "commit": contract["commit"]})
    retained = c["retained_v1"]
    for key in ("report", "diagnostic_report"):
        record = file_record(ROOT / retained[key])
        require(record["sha256"] == retained[key + "_sha256"], "retained v1 report changed")
    report = read(ROOT / retained["report"])
    old_stage = Path(retained["stage"])
    require(old_stage.is_dir() and inventory(old_stage) == report["source_inventory"], "retained v1 inventory changed/missing")
    bytes_used = used(old_stage) + used(ROOT / retained["report"]) + used(ROOT / retained["diagnostic_report"])
    require(bytes_used <= c["limits_proposed"]["retained_v1_reserved_from_shared_pool_bytes"], "retained v1 exceeds reserved shared pool")
    consumed = report["export_resources"]["run_plus_export_s_upper"]
    require(consumed == c["limits_proposed"]["v1_run_and_first_export_consumed_s_upper"], "v1 consumed-time ledger changed")
    verified.append({"retained_v1_bytes": bytes_used, "v1_consumed_s_upper": consumed,
                     "report": file_record(ROOT / retained["report"]),
                     "diagnostic_report": file_record(ROOT / retained["diagnostic_report"])})
    return verified


def used(path):
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.exists() else 0


def tree_memory():
    processes = {}
    for p in Path("/proc").iterdir():
        if p.name.isdigit():
            try:
                fields = dict(line.split(":", 1) for line in (p / "status").read_text().splitlines() if ":" in line)
                processes[int(p.name)] = (int(fields["PPid"]), int(fields.get("VmHWM", "0 kB").split()[0]) * 1024)
            except (OSError, ValueError, KeyError):
                continue
    require(os.getpid() in processes, "cannot inspect process memory")
    selected = {os.getpid()}
    while True:
        extended = selected | {pid for pid, (parent, _) in processes.items() if parent in selected}
        if extended == selected:
            return sum(processes[p][1] for p in selected)
        selected = extended


@contextmanager
def guarded_command(seconds):
    """Bound parent finalization/export as well as silent worker processes."""
    limits = configuration()["limits_proposed"]
    began, stop, errors = time.monotonic(), threading.Event(), []
    def exceeded(signum, frame):
        raise KeyboardInterrupt(errors[0] if errors else "resource guard interruption")
    previous = signal.signal(signal.SIGUSR1, exceeded)
    def watch():
        next_notice = began + 30
        while not stop.wait(0.1):
            try:
                require(time.monotonic() - began < seconds, "command time limit")
                peak = tree_memory()
                require(peak <= limits["tree_rss_bytes"], "command process-tree RSS limit")
                require(used(RUN) + used(REPORT) <= limits["stage_and_report_bytes"], "command disk limit")
                if time.monotonic() >= next_notice:
                    print(f"{STAGE} elapsed={time.monotonic()-began:.1f}s tree_hwm_mib={peak/1024**2:.1f}", flush=True)
                    next_notice = time.monotonic() + 30
            except BaseException as error:
                errors.append(str(error))
                os.kill(os.getpid(), signal.SIGUSR1)
                return
    # The watcher must not receive the signal intended for the main thread.
    watched = {signal.SIGINT, signal.SIGTERM, signal.SIGUSR1}
    prior_mask = signal.pthread_sigmask(signal.SIG_BLOCK, watched)
    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    signal.pthread_sigmask(signal.SIG_SETMASK, prior_mask)
    try:
        yield
        require(not errors, errors[0] if errors else "guard failed")
        require(time.monotonic() - began <= seconds, "command finalization time limit")
    finally:
        stop.set()
        thread.join(timeout=1)
        signal.signal(signal.SIGUSR1, previous)


def capacity_report(workers):
    c = configuration()
    limits = c["limits_proposed"]
    require(workers in limits["workers_allowed"], "engineering subset permits 1..4 workers")
    cap = capacity(workers, limits["process_as_bytes"], limits["capacity_reserve_bytes"])
    cap.update(data_disk_free_bytes=shutil.disk_usage(RUN.parent).free,
               proposed_subset_bytes=limits["stage_and_report_bytes"],
               quota_verified=False, quota_note="df is not the rental quota; run requires explicit remaining new-data allowance")
    return cap


def test_census():
    names = []
    for module in TESTS:
        tree = ast.parse((ROOT / f"tests/spatial_world_model/{module}.py").read_bytes())
        for cls in tree.body:
            if isinstance(cls, ast.ClassDef):
                names.extend(f"{module}.{cls.name}.{fn.name}" for fn in cls.body
                             if isinstance(fn, ast.FunctionDef) and fn.name.startswith("test_"))
    require(names and len(names) == len(set(names)), "bad test census")
    return sorted(names)


def supervise(tasks, workers, directory, seconds, byte_limit):
    began, peak = time.monotonic(), 0
    launched, exits, readers = [], [], {}
    def checkpoint():
        nonlocal peak
        peak = max(peak, tree_memory())
        require(time.monotonic() - began < seconds - 1, "stage wall-clock limit")
        require(peak <= configuration()["limits_proposed"]["tree_rss_bytes"], "stage RSS limit")
        require(used(RUN) + used(REPORT.parent / REPORT.name) <= byte_limit - 1024**2, "stage disk limit")
        for identifier, reader in readers.items():
            output = reader.read(8192)
            if output:
                print(f"[{identifier}] {output}", end="", flush=True)
    def launch(task):
        unit = directory / task["id"]
        unit.mkdir()
        log = (unit / "run.log").open("x")
        try:
            child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "_worker", "--role", task["id"]],
                                     cwd=ROOT, env=dict(os.environ, MUJOCO_GL="egl", OPENBLAS_NUM_THREADS="1",
                                     OMP_NUM_THREADS="1", PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1"),
                                     stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        finally:
            log.close()
        try:
            launched.append({"id": task["id"], "pid": child.pid})
            readers[task["id"]] = (unit / "run.log").open(errors="replace")
            save(unit / "launched.json", {"pid": child.pid, "id": task["id"]})
        except BaseException:
            abort(child)
            raise
        return child
    def abort(child):
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=5)
    def completed(task, child, error):
        entry = {"id": task["id"], "pid": child.pid, "exit_code": child.returncode, "parent_error": error}
        exits.append(entry)
        save(directory / task["id"] / "exit.json", entry)
        require(child.returncode == 0 and error is None, "child failed: " + task["id"])
        return entry
    try:
        dispatch(tasks, workers, launch, completed, checkpoint, abort)
        checkpoint()
    finally:
        for reader in readers.values():
            rest = reader.read()
            if rest:
                print(rest, end="", flush=True)
            reader.close()
        save(directory / "processes.json", {"launched": launched, "exits": exits,
             "not_started": [t["id"] for t in tasks if t["id"] not in {e["id"] for e in launched}],
             "missing_exit": [e["id"] for e in launched if e["id"] not in {r["id"] for r in exits}],
             "elapsed_s": time.monotonic() - began, "peak_tree_hwm_bytes": peak})


def check():
    c = configuration()
    if RUN.exists():
        return verify_check()
    require(not git("status", "--porcelain", "--", *BOUND), "commit bound files before checking")
    dependencies, env = prereqs(), environment()
    before, commit = binding(), git("rev-parse", "HEAD")
    # Versions are inspected in child tests; no simulation or rendering in check.
    RUN.mkdir()
    save(RUN / "started.json", {"stage": STAGE, "commit": commit, "binding": before,
         "prerequisites": dependencies, "environment": env,
         "started": datetime.now(timezone.utc).isoformat(), "config": c})
    design = read(ROOT / "configs/spatial_history/r4_family_design_v2.json")
    validate_manifest(design, read(ROOT / c["protocol"]))
    save(RUN / "design.json", design)
    folder = RUN / "check"
    folder.mkdir()
    supervise([{"id": "tests"}], 1, folder, c["limits_proposed"]["check_wall_s"], c["limits_proposed"]["stage_and_report_bytes"])
    require(binding() == before, "source changed during check")
    result = read(folder / "tests" / "result.json")
    require(result["names"] == test_census() and result["passed"], "incomplete check")
    save(RUN / "check_receipt.json", {"commit": commit, "binding": before, "exit_code": 0,
         "design": file_record(RUN / "design.json"), "artifacts": inventory(folder), "tests": result})
    return verify_check()


def verify_check():
    r = read(RUN / "check_receipt.json")
    started = read(RUN / "started.json")
    require(started["stage"] == STAGE and r["commit"] == started["commit"]
            and r["binding"] == started["binding"], "check/start provenance mismatch")
    require(r["exit_code"] == 0 and r["binding"] == binding(), "missing/changed check: preserve stage")
    require(r["artifacts"] == inventory(RUN / "check"), "check artifact mismatch")
    require(r["design"] == file_record(RUN / "design.json"), "design digest mismatch")
    validate_manifest(read(RUN / "design.json"), read(ROOT / configuration()["protocol"]))
    require(r["tests"]["passed"] and r["tests"]["names"] == test_census(), "test census mismatch")
    print(f"{STAGE} CHECKED tests={len(r['tests']['names'])} exit=0", flush=True)
    return r


def release_checked(check_receipt, reviewed_code, quota_gib, config):
    require(reviewed_code == check_receipt["commit"], "run requires explicit --reviewed-code equal to checked full commit")
    require(type(quota_gib) in (int, float) and 8 <= quota_gib <= 1000000,
            "declare verified available NEW data quota (GiB), at least 8; df is insufficient")
    return {"reviewed_code": reviewed_code, "declared_available_new_data_gib": quota_gib,
            "engineering_subset_only": True, "approved_limits": config["limits_proposed"],
            "confirmation_authorized": False, "training_authorized": False}


def summary_for(results, rows, config):
    limits = config["limits_proposed"]
    category = categorical_shortcut([r["success_matrix"] for r in results])
    category["valid_physical_evidence"] = all(r["checks"]["physics"] and r["checks"]["replay_equal"] for r in results)
    family_gates = all(r["accepted"] for r in results)
    return {"families": [{"family_id": row["family_id"], "result": result} for row, result in zip(rows, results)],
            "family_gates_passed": family_gates,
            "accepted": family_gates and not category["categorical_shortcut_unexcluded"],
            "categorical_shortcut": category,
            "generation_ledger": {"v1_consumed_s_upper": limits["v1_run_and_first_export_consumed_s_upper"],
                                  "total_limit_s": limits["generation_total_wall_s_including_v1"]},
            "remaining_storage": {"remaining_families": 60, "reserved_worst_case_bytes": 60 * limits["family_bytes"],
                "all_v2_family_caps_bytes": 64 * limits["family_bytes"],
                "retained_v1_reserved_bytes": limits["retained_v1_reserved_from_shared_pool_bytes"],
                "new_features_and_metadata_limit_bytes": limits["new_features_and_metadata_bytes"],
                "data_features_total_limit_bytes": 32 * 1024**3,
                "allocation_within_32gib": 64 * limits["family_bytes"] + limits["retained_v1_reserved_from_shared_pool_bytes"] + limits["new_features_and_metadata_bytes"] <= 32 * 1024**3,
                "remaining_inventory_storage_verified": False},
            "remaining_inventory_executable": False, "confirmation_executable": False,
            "model_experiment_run": False, "new_training_steps": 0, "new_weight_download_bytes": 0}


def run(reviewed_code, quota_gib, workers):
    c, checked = configuration(), verify_check()
    if (RUN / "execution").exists():
        return verify()  # A started failure or partial execution cannot restart.
    require(git("rev-parse", "HEAD") == checked["commit"] and not git("status", "--porcelain", "--", *BOUND), "checked release commit/files changed")
    release = release_checked(checked, reviewed_code, quota_gib, c)
    cap = capacity_report(workers)
    require(cap["data_disk_free_bytes"] >= c["limits_proposed"]["stage_and_report_bytes"], "insufficient disk headroom")
    require(prereqs() == read(RUN / "started.json")["prerequisites"], "prerequisite changed")
    require(environment() == read(RUN / "started.json")["environment"], "environment changed after check")
    execution = RUN / "execution"
    execution.mkdir()
    began = time.monotonic()
    save(execution / "release.json", {**release, "workers": workers, "capacity": cap})
    rows = engineering_rows(read(RUN / "design.json"))
    try:
        supervise([{"id": r["family_id"]} for r in rows], workers, execution,
                  c["limits_proposed"]["run_and_first_export_wall_s"], c["limits_proposed"]["stage_and_report_bytes"])
        results = [verify_family(execution / r["family_id"] / "data") for r in rows]
        summary = summary_for(results, rows, c)
        save(execution / "summary.json", summary)
        require(binding() == checked["binding"], "source changed during generation")
        artifacts = inventory(execution)
        elapsed = time.monotonic() - began
        require(elapsed + 1 <= c["limits_proposed"]["run_and_first_export_wall_s"], "finalization exceeded time budget")
        pending = RUN / "run_receipt.pending.json"
        save(pending, {"exit_code": 0, "accepted": summary["accepted"],
             "commit": checked["commit"], "binding": checked["binding"], "elapsed_s_upper": elapsed + 1,
             "artifacts": artifacts})
        require(time.monotonic() - began <= elapsed + 1, "receipt finalization exceeded reserved second")
        pending.rename(RUN / "run_receipt.json")
    except BaseException as error:
        save(execution / "failure.json", {"error": f"{type(error).__name__}: {error}", "elapsed_s": time.monotonic() - began})
        raise
    print(f"{STAGE} COMPLETED accepted={summary['accepted']} exit=0", flush=True)


def verify():
    checked = verify_check()
    r = read(RUN / "run_receipt.json")
    require(r["exit_code"] == 0 and r["binding"] == checked["binding"] and r["commit"] == checked["commit"], "no completed run")
    require(r["artifacts"] == inventory(RUN / "execution"), "run artifacts changed")
    summary = read(RUN / "execution" / "summary.json")
    require(r["accepted"] == summary["accepted"], "run status changed")
    rows = engineering_rows(read(RUN / "design.json"))
    results = [verify_family(RUN / "execution" / row["family_id"] / "data") for row in rows]
    require(summary == summary_for(results, rows, configuration()), "summary differs from verified family evidence")
    require(r["elapsed_s_upper"] <= configuration()["limits_proposed"]["run_and_first_export_wall_s"], "run budget receipt")
    print(f"{STAGE} VERIFIED accepted={r['accepted']} exit=0", flush=True)
    return r


def export():
    if REPORT.exists():
        report = read(REPORT)
        require(report["stage"] == STAGE and report["source_inventory"] == inventory(RUN), "existing export differs; no overwrite")
        print(f"{STAGE} EXPORTED reused=true exit=0")
        return
    require(not REPORT.with_suffix(".pending.json").exists(), "unpublished export exists: preserve, no retry")
    began = time.monotonic()
    c = configuration()
    malformed = {}
    def diagnostic_json(path):
        if not path.exists():
            return None
        try:
            return read(path)
        except (ValueError, UnicodeError) as error:
            with path.open("rb") as stream:
                prefix = stream.read(4096).decode(errors="replace")
            malformed[path.relative_to(RUN).as_posix()] = {"file": file_record(path), "error": str(error), "prefix": prefix}
            return None
    receipt = diagnostic_json(RUN / "run_receipt.json")
    status = "failed_or_incomplete"
    verification_error = None
    if receipt is not None:
        try:
            verify()
            status = "passed" if receipt["accepted"] else "failed"
        except (OSError, ValueError, KeyError, TypeError) as error:
            verification_error = f"{type(error).__name__}: {error}"
            status = "integrity_failed"
    budget_receipt = receipt if status in ("passed", "failed") else None
    # Export even failed/partial manifests and logs; never manufacture arrays or exits.
    report = {"stage": STAGE, "status": status, "source_inventory": inventory(RUN), "receipt": receipt,
              "check": diagnostic_json(RUN / "check_receipt.json"),
              "design": diagnostic_json(RUN / "design.json"), "artifacts_json": {}, "log_tails": {},
              "verification_error": verification_error, "malformed_json": malformed,
              "run_receipt_file": file_record(RUN / "run_receipt.json") if (RUN / "run_receipt.json").exists() else None}
    for p in RUN.rglob("*.json"):
        if p.name in ("summary.json", "failure.json", "release.json", "processes.json", "exit.json", "started.json",
                      "public_manifest.json", "labels_manifest.json", "audit_manifest.json", "family_result.json", "history_failure.json"):
            report["artifacts_json"][p.relative_to(RUN).as_posix()] = diagnostic_json(p)
    for p in RUN.rglob("run.log"):
        with p.open("rb") as stream:
            stream.seek(max(0, p.stat().st_size - 8192))
            report["log_tails"][p.relative_to(RUN).as_posix()] = stream.read().decode(errors="replace")
    from spatial_world_model.r4_families_v2 import encode
    elapsed = (budget_receipt["elapsed_s_upper"] if budget_receipt else 0) + time.monotonic() - began + 1
    require(elapsed <= c["limits_proposed"]["run_and_first_export_wall_s"], "export wall limit; preserve failure")
    report["export_resources"] = {"run_plus_export_s_upper": elapsed if budget_receipt else None,
         "diagnostic_export_s_upper": None if budget_receipt else elapsed,
         "generation_budget_verified": budget_receipt is not None, "status_is_engineering_only": True}
    previous_s = c["limits_proposed"]["v1_run_and_first_export_consumed_s_upper"]
    report["export_resources"]["v1_plus_v2_generation_s_upper"] = previous_s + elapsed if budget_receipt else None
    require(budget_receipt is None or previous_s + elapsed <= c["limits_proposed"]["generation_total_wall_s_including_v1"], "aggregate generation budget exceeded")
    # Fixed previews, selected by registration rather than by success/failure.
    import base64
    report["previews"] = {}
    design = report["design"]
    if design is not None:
        first = design["engineering_family_ids"][0]
        for world in ("LL", "RR"):
            for name in ("first.png", "near.png", "far.png", "recent.png"):
                path = RUN / "execution" / first / "data/audit" / world / name
                if path.is_file():
                    report["previews"][f"{first}-{world}-{name}"] = {
                        "source": path.relative_to(RUN).as_posix(), "file": file_record(path),
                        "png_base64": base64.b64encode(path.read_bytes()).decode("ascii")}
    raw = encode(report)
    require(used(RUN) + len(raw) <= c["limits_proposed"]["stage_and_report_bytes"], "export disk limit")
    pending = REPORT.with_suffix(".pending.json")
    save(pending, report)
    require(not REPORT.exists(), "report already exists")
    require((budget_receipt["elapsed_s_upper"] if budget_receipt else 0) + time.monotonic() - began <= elapsed,
            "export finalization timeout: pending preserved")
    pending.rename(REPORT)
    print(f"{STAGE} EXPORTED status={status} path={REPORT} exit=0")


def worker(role):
    c = configuration()
    require(read(RUN / "started.json")["binding"] == binding(), "worker source changed")
    limit = c["limits_proposed"]["process_as_bytes"]
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    if role == "tests":
        sys.path.insert(0, str(ROOT / "tests/spatial_world_model"))
        suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(m)) for m in TESTS)
        def flatten(s):
            return [n for t in s for n in flatten(t)] if isinstance(s, unittest.TestSuite) else [s.id()]
        names = sorted(flatten(suite))
        require(names == test_census(), "loaded test identity differs")
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        passed = result.wasSuccessful() and not result.skipped and result.testsRun == len(names)
        save(RUN / "check/tests/result.json", {"names": names, "passed": passed, "tests_run": result.testsRun,
             "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
             "simulation_steps": 0, "training_steps": 0, "weight_download_bytes": 0})
        require(passed, "checks failed")
        return
    checked = verify_check()
    release = read(RUN / "execution/release.json")
    release_checked(checked, release["reviewed_code"], release["declared_available_new_data_gib"], c)
    rows = engineering_rows(read(RUN / "design.json"))
    require(role in {r["family_id"] for r in rows}, "family outside fixed engineering subset")
    row = next(r for r in rows if r["family_id"] == role)
    family = RUN / "execution" / role
    last = [0.0]
    # Each family has a separate directory and byte cap, so simultaneous family
    # writes cannot spend another family's reservation. Cache disk size between
    # writes, charging actual guarded bytes; refresh for XML/log/JSON writes.
    measured = [used(family), time.monotonic(), 0]
    def progress(event):
        now = time.monotonic()
        if now - measured[1] >= 1:
            measured[:] = [used(family), now, 0]
        reserve = event.get("reserve_bytes", 0)
        require(measured[0] + measured[2] + reserve <= c["limits_proposed"]["family_bytes"] - 1024**2,
                "family storage bound: preserve prefix")
        # Allocation previews are not on-disk writes. All emitted compressed
        # chunks and ordinary JSON/PNG writes are charged before actual write.
        if event["phase"] != "allocate":
            measured[2] += reserve
        if time.monotonic() - last[0] > 2 or event["phase"].endswith("start"):
            print(event, flush=True)
            last[0] = time.monotonic()
    base = read(ROOT / c["base"])
    config = family_config(base, row)
    reference = (ROOT / base["physics_reference"]).read_bytes()
    import hashlib
    require(hashlib.sha256(reference).hexdigest() == base["physics_reference_sha256"], "reference XML digest")
    result = run_family(family / "data", config, reference.decode("utf-8"), read(ROOT / c["e0"]), progress)
    print(f"FAMILY COMPLETED id={role} accepted={result['accepted']} exit=0", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("capacity", "check", "run", "verify", "export", "_worker"))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--reviewed-code")
    parser.add_argument("--available-new-data-gib", type=float)
    parser.add_argument("--role")
    args = parser.parse_args()
    require(platform.system() == "Linux", "server-only; no local computation")
    require(Path("/root/autodl-tmp").is_mount(), "verified data disk mount is missing")
    require(Path(sys.prefix) == Path("/root/autodl-tmp/spatial-history-venv-v1"),
            "use existing isolated physics environment")
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f"signal {signum}")
    signal.signal(signal.SIGTERM, interrupted)
    if args.command == "_worker":
        worker(args.role)
        return
    limits = configuration()["limits_proposed"]
    resource.setrlimit(resource.RLIMIT_AS, (limits["process_as_bytes"], limits["process_as_bytes"]))
    seconds = limits["check_wall_s"] if args.command in ("check", "capacity") else limits["run_and_first_export_wall_s"]
    if args.command == "export" and not REPORT.exists():
        try:
            seconds -= read(RUN / "run_receipt.json")["elapsed_s_upper"]
        except (OSError, ValueError, KeyError, TypeError):
            seconds = limits["check_wall_s"]  # Bounded diagnostic; no aggregate budget certification.
    require(seconds > 0, "no remaining command budget")
    with guarded_command(seconds):
        if args.command == "capacity":
            print(json.dumps(capacity_report(args.workers), indent=2))
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
