"""SH-04-R2 engineering check/run/verify/export; no learning or simulation logic.

Each child step is sealed before its successor starts. Completed steps are reused;
partial or failed steps are retained and never silently restarted. Only Linux
workers import the new physical adapter. Verification/export read saved evidence.
"""
import argparse
import ast
import base64
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
import traceback
import unittest

from contract_check import ROOT, encode, git, require, sha, write_new
from physics_check import DISK, ENV, REQUIREMENTS, environment, now

STAGE = "SH-04-R2"
CONFIG = "configs/spatial_history/two_gate_engineering_v1.json"
PROPOSAL = "configs/spatial_history/two_gate_engineering_proposal_v1.json"
PROPOSAL_COMMIT = "3c5755eb4f0f38a17c7396e735cb8543eea6c072"
PROPOSAL_SHA = "f1218eca9dbfaa1815b8e86aa64f060868aacb81b707264323b4175d0cdcfe26"
PROPOSAL_REFERENCE_WORKTREE_SHA = "ef06b563e7606278668c668521a97bdae112c9cd49509a4e00fdd272d278d6bb"
PHYSICS_REFERENCE_BLOB_SHA = "9ced1ae1af9d868b0c986dc875a8d1148f649615e9495e398cb4699e654ee51e"
PRIOR = "results/spatial_history_development_audit_v2_wall_clearance.json"
PRIOR_SHA = "6c55d351d7eb0be6768d8992b608a452c677b1f02ac51cedf87443106df1ee5a"
TESTS = tuple(f"tests/spatial_world_model/{name}.py" for name in (
    "test_pair_contract", "test_two_gate_contract", "test_two_gate_physics",
    "test_two_gate_engineering", "test_two_gate_ops"))
BOUND = (CONFIG, PROPOSAL, PRIOR, REQUIREMENTS, *TESTS,
         "src/spatial_world_model/__init__.py", "src/spatial_world_model/pair_contract.py",
         "src/spatial_world_model/two_gate_contract.py", "src/spatial_world_model/two_gate_physics.py",
         "src/spatial_world_model/two_gate_engineering.py", "data/fixtures/spatial_history/manual_pair.json",
         "configs/spatial_history/physics_v1.xml", "ops/spatial_history/contract_check.py",
         "ops/spatial_history/physics_check.py", "ops/spatial_history/two_gate_check.py")
RUN = DISK / "spatial-history/sh04-r2-two-gate-engineering-v1-lfsha1"
REPORT = ROOT / "results/spatial_history_two_gate_engineering_v1_lfsha1.json"
RESERVE_BYTES = 1024 * 1024  # Preserve room for stop evidence and manifests.


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def files(directory):
    paths = sorted(p for p in directory.rglob("*") if p.is_file())
    require(not any(p.is_symlink() for p in directory.rglob("*")), "artifact symlinks are forbidden")
    return paths


def size(directory):
    return sum(p.stat().st_size for p in files(directory))


def manifest(directory):
    return {p.relative_to(directory).as_posix(): {"sha256": file_sha(p), "bytes": p.stat().st_size}
            for p in files(directory) if p != directory / "receipt.json"}


def binding():
    return {name: file_sha(ROOT / name) for name in BOUND}


def original_binding(commit, bound):
    require(isinstance(commit, str) and len(commit) == 40 and all(c in "0123456789abcdef" for c in commit),
            "invalid source commit")
    for name, digest in bound.items():
        require(not Path(name).is_absolute() and ".." not in Path(name).parts, "invalid bound path")
        original = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{commit}:{name}"])
        require(sha(original) == digest, f"original source binding invalid: {name}")


def validate_frozen_config(value, proposal_bytes):
    """Approval changes metadata only; scientific values remain the reviewed proposal."""
    require(sha(proposal_bytes) == PROPOSAL_SHA == value["proposal_sha256"]
            and value["proposal_source"] == PROPOSAL, "approved numeric proposal digest/path changed")
    require(value["version"] == "sh04-r2-two-gate-engineering-v1-lfsha1"
            and value["status"] == "frozen_engineering_only" and value["approval_decision"] == "D-071",
            "unknown engineering approval")
    metadata = {"version", "status", "numeric_protocol_approved", "generation_authorized",
                "approval_decision", "proposal_source", "proposal_sha256", "physics_reference_sha256"}
    proposal = json.loads(proposal_bytes)
    require(proposal["physics_reference_sha256"] == PROPOSAL_REFERENCE_WORKTREE_SHA
            and value["physics_reference_sha256"] == PHYSICS_REFERENCE_BLOB_SHA,
            "approved physics-reference byte normalization changed")
    require(encode({k: v for k, v in value.items() if k not in metadata})
            == encode({k: v for k, v in proposal.items() if k not in metadata}),
            "scientific configuration differs from reviewed numeric proposal")
    require(value["numeric_protocol_approved"] is True and value["generation_authorized"] is True
            and value["training_authorized"] is False, "reviewed engineering-only generation required")


def config():
    sys.path.insert(0, str(ROOT / "src"))
    from spatial_world_model.two_gate_contract import validate_config
    value = read(ROOT / CONFIG)
    validate_config(value)
    proposal_bytes = (ROOT / PROPOSAL).read_bytes()
    validate_frozen_config(value, proposal_bytes)
    original = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{PROPOSAL_COMMIT}:{PROPOSAL}"])
    require(original == proposal_bytes and sha(original) == PROPOSAL_SHA, "original approved proposal source invalid")
    require(file_sha(ROOT / value["physics_reference"]) == value["physics_reference_sha256"],
            "physics reference checkout bytes changed")
    return value


def step_ids(value):
    sys.path.insert(0, str(ROOT / "src"))
    from spatial_world_model.two_gate_engineering import step_ids as inventory
    return inventory(value)


def test_names():
    result = []
    for filename in TESTS:
        tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
        for cls in (n for n in tree.body if isinstance(n, ast.ClassDef)):
            result.extend(f"{Path(filename).stem}.{cls.name}.{n.name}" for n in cls.body
                          if isinstance(n, ast.FunctionDef) and n.name.startswith("test_"))
    require(result and len(result) == len(set(result)), "empty/duplicate test inventory")
    return sorted(result)


def prerequisites():
    prior = read(ROOT / PRIOR)
    audit = prior["audit"]
    require(sha(encode(audit)) == prior["audit_sha256"] == PRIOR_SHA, "approved SH-03 digest mismatch")
    require(audit["status"] == "passed" and audit["tests"]["exit_code"] == 0
            and len(audit["cases"]) == 16 and all(c["status"] == "passed" for c in audit["cases"]),
            "complete successful SH-03 evidence required")
    original_binding(audit["started"]["commit"], audit["started"]["binding"])


def server():
    require(platform.system() == "Linux" and DISK.is_mount(), "Linux server/data mount required")
    require(Path(sys.prefix).resolve() == ENV.resolve(), f"use {ENV}/bin/python")
    return environment()


def current_source(started):
    require(started["binding"] == binding(), "bound source/configuration changed")
    require(not git("status", "--porcelain", "--", *BOUND), "bound files must be committed and clean")
    require(git("rev-parse", "HEAD") == started["commit"], "checkout changed; no new computation")


def stage(directory, historical=False):
    require((directory / "started.json").is_file(), "check required first; partial root preserved")
    started = read(directory / "started.json")
    require(started["stage"] == STAGE and started["model_training_steps"] == 0, "wrong stage")
    require(set(started["binding"]) == set(BOUND), "source binding inventory incomplete")
    require(file_sha(directory / "environment.json") == started["environment_sha256"], "environment record changed")
    require(sha(encode(started["config"])) == started["config_sha256"], "saved config changed")
    require(started["step_ids"] == step_ids(started["config"]), "registered step plan changed")
    if historical:
        original_binding(started["commit"], started["binding"])
        original_config = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{started['commit']}:{CONFIG}"])
        require(json.loads(original_config) == started["config"], "saved config differs from original commit")
    else:
        current_source(started)
        require(started["config"] == config(), "registered configuration changed")
    return started


class Budget:
    """Wall-clock plus incremental disk checks, also called before child writes."""
    def __init__(self, directory, maximum_bytes, maximum_seconds, reserve_bytes=RESERVE_BYTES):
        self.directory, self.maximum_bytes = directory, maximum_bytes
        self.maximum_seconds, self.reserve_bytes = maximum_seconds, reserve_bytes
        self.began = time.monotonic()

    def check(self, *, reserve_bytes=0):
        require(isinstance(reserve_bytes, int) and reserve_bytes >= 0, "invalid write reservation")
        require(time.monotonic() - self.began < self.maximum_seconds, "wall-clock budget reached; retained")
        require(size(self.directory) + reserve_bytes + self.reserve_bytes <= self.maximum_bytes,
                "output budget reached; retained")


def stop_process(process):
    if process.poll() is None:
        try:
            if platform.system() == "Linux":
                os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
        except ProcessLookupError:
            pass  # The child may have exited between poll and signal.
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if platform.system() == "Linux":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            process.wait(timeout=5)


def bounded_stream(command, log_path, child_env, budget):
    """Poll a real log file so a silent/hung child cannot block the watchdog."""
    process = None
    try:
        with log_path.open("x", encoding="utf-8") as log:
            process = subprocess.Popen(command, cwd=ROOT, env=child_env, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=platform.system() == "Linux")
            with log_path.open(encoding="utf-8", errors="replace") as reader:
                while True:
                    output = reader.read(8192)
                    if output:
                        print(output, end="", flush=True)
                    budget.check()
                    code = process.poll()
                    if code is not None:
                        rest = reader.read()
                        if rest:
                            print(rest, end="", flush=True)
                        return code
                    time.sleep(0.2)
    finally:
        if process is not None:
            stop_process(process)


def sealed(unit, started):
    require((unit / "receipt.json").is_file(), f"partial step preserved at {unit}; no automatic retry")
    receipt = read(unit / "receipt.json")
    require(receipt["stage"] == STAGE and receipt["commit"] == started["commit"]
            and receipt["binding"] == started["binding"], "step source mismatch")
    require(receipt["step_id"] == unit.name and receipt["artifacts"] == manifest(unit), "step artifacts changed")
    return receipt


def launch(directory, started, step_id, remaining_seconds):
    unit = directory / ("check" if step_id == "check" else f"steps/{step_id}")
    unit.mkdir(parents=True, exist_ok=False)
    write_new(unit / "started.json", {"stage": STAGE, "step_id": step_id, "started": now()})
    limits = started["config"]["budget_proposal"]
    budget = Budget(directory, limits["new_output_limit_bytes"], remaining_seconds)
    child_env = dict(os.environ, MUJOCO_GL="egl", PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1",
                     OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", SH04_CHILD_DIR=str(unit),
                     SH04_REMAINING_SECONDS=str(remaining_seconds),
                     SH04R2_TEST_ARTIFACT_DIR=str(unit / "artifacts/physics"))
    command = [sys.executable, str(Path(__file__).resolve()), "_worker", "--run-dir", str(directory),
               "--step-id", step_id]
    timer, code, error = time.monotonic(), 1, None
    try:
        code = bounded_stream(command, unit / "run.log", child_env, budget)
    except BaseException as exception:
        code = 130 if isinstance(exception, KeyboardInterrupt) else 1
        error = f"{type(exception).__name__}: {exception}"
        with (unit / "parent-error.txt").open("x", encoding="utf-8") as handle:
            traceback.print_exc(file=handle)
    unchanged = binding() == started["binding"] and git("rev-parse", "HEAD") == started["commit"]
    code = code if unchanged else 1
    write_new(unit / "receipt.json", {"stage": STAGE, "step_id": step_id, "commit": started["commit"],
              "binding": started["binding"], "finished": now(), "elapsed_s": time.monotonic() - timer,
              "generation_budget_used_s": (0 if step_id == "check" else
                  limits["generation_wall_clock_limit_s"] - remaining_seconds + time.monotonic() - timer),
              "exit_code": code, "source_unchanged": unchanged, "parent_error": error,
              "artifacts": manifest(unit)})
    print(f"{STAGE} STEP FINISHED step={step_id} exit={code}", flush=True)
    return sealed(unit, started)


def completed_tests(directory, started):
    receipt = sealed(directory / "check", started)
    require(receipt["exit_code"] == 0, "check failed; export diagnosis")
    result = read(directory / "check/result.json")
    require(result["test_names"] == started["test_names"] and result["tests_run"] == len(started["test_names"])
            and result["exit_code"] == 0 and result["failures"] == result["errors"] == result["skipped"] == 0,
            "incomplete test receipt")
    require(result["egl"]["status"] == "passed", "EGL context verification missing")
    return result


def check(directory):
    setup = server()
    prerequisites()
    if not directory.exists():
        value = config()
        current = {"binding": binding(), "commit": git("rev-parse", "HEAD")}
        current_source(current)
        require(shutil_free() >= value["budget_proposal"]["new_output_limit_bytes"],
                "insufficient filesystem free space; rental quota must also permit 2 GiB")
        directory.mkdir(parents=True, exist_ok=False)
        record = {"setup": setup, "python": sys.version, "platform": platform.platform(),
                  "executable": sys.executable, "repository": str(ROOT), "MUJOCO_GL": "egl"}
        write_new(directory / "environment.json", record)
        write_new(directory / "started.json", {"stage": STAGE, "started": now(), **current,
                  "config": value, "config_sha256": sha(encode(value)), "step_ids": step_ids(value),
                  "test_names": test_names(), "environment_sha256": sha(encode(record)),
                  "seed": None, "random_sampling": False, "model_training_steps": 0})
    started = stage(directory)
    unit = directory / "check"
    if unit.exists():
        sealed(unit, started)
    else:
        launch(directory, started, "check", started["config"]["budget_proposal"]["generation_wall_clock_limit_s"])
    result = completed_tests(directory, started)
    print(f"{STAGE} CHECK VERIFIED tests={result['tests_run']} renderer={result['egl']['renderer']} exit=0", flush=True)


def shutil_free():
    import shutil
    return shutil.disk_usage(DISK).free


def log_tail(unit):
    result = {}
    for name in ("run.log", "parent-error.txt"):
        path = unit / name
        if path.exists():
            with path.open("rb") as handle:
                handle.seek(max(0, path.stat().st_size - 16000))
                result[name] = handle.read().decode("utf-8", errors="replace")
    return result


def inspect(directory, *, finalizing=False, budget_check=None):
    started = stage(directory, historical=True)
    records = []
    for step_id in ["check", *started["step_ids"]]:
        if budget_check is not None:
            budget_check()
        unit = directory / ("check" if step_id == "check" else f"steps/{step_id}")
        record = {"step_id": step_id, "status": "not_run"}
        if unit.exists():
            if (unit / "receipt.json").exists():
                receipt = sealed(unit, started)
                record.update(receipt=receipt, artifacts=receipt["artifacts"],
                              status="completed" if receipt["exit_code"] == 0 else "runtime_failed")
            else:
                record.update(status="interrupted", artifacts=manifest(unit))
            if (unit / "result.json").exists():
                try:
                    record["result"] = read(unit / "result.json")
                except (ValueError, UnicodeError) as error:
                    record.update(status="invalid_result", result_error=str(error))
            if record["status"] != "completed":
                record["failure_log_tail"] = log_tail(unit)
        records.append(record)
    all_complete = all(r["status"] == "completed" and "result" in r for r in records)
    aggregate = records[-1].get("result") if records[-1]["step_id"] == "audit" else None
    accepted = False
    if all_complete:
        completed_tests(directory, started)
        require(isinstance(aggregate, dict) and isinstance(aggregate.get("accepted"), bool)
                and bool(aggregate.get("checks"))
                and all(type(v) is bool for v in aggregate["checks"].values()), "invalid aggregate audit")
        require(aggregate["accepted"] == all(aggregate["checks"].values())
                and sorted(aggregate["failed_checks"]) == sorted(k for k, v in aggregate["checks"].items() if not v),
                "aggregate acceptance/failed checks disagree")
        accepted = aggregate["accepted"]
    elapsed = max((r.get("receipt", {}).get("generation_budget_used_s", 0) for r in records[1:]), default=0)
    completion = read(directory / "completion.json") if (directory / "completion.json").exists() else None
    if completion is not None:
        require(completion["commit"] == started["commit"] and completion["binding"] == started["binding"],
                "completion source mismatch")
        elapsed = max(elapsed, completion["generation_elapsed_s"])
    count = size(directory)
    limits = started["config"]["budget_proposal"]
    passed = (all_complete and accepted and count <= limits["new_output_limit_bytes"]
              and elapsed <= limits["generation_wall_clock_limit_s"]
              and (finalizing or (completion is not None and completion["exit_code"] == 0)))
    return {"stage": STAGE, "kind": "two_gate_engineering_only", "started": started,
            "environment": read(directory / "environment.json"), "steps": records,
            "status": "passed" if passed else "failed", "artifact_bytes": count, "generation_elapsed_s": elapsed,
            "completion": completion, "aggregate": aggregate, "model_experiment_run": False}


def run(directory):
    if (directory / "completion.json").exists():
        require(inspect(directory)["status"] == "passed", "completed failed run preserved; export diagnosis")
        print(f"{STAGE} REUSED completed engineering audit exit=0", flush=True)
        return
    server()
    started = stage(directory)
    completed_tests(directory, started)
    existing = inspect(directory)  # Check every saved artifact before starting a successor.
    generation = existing["steps"][1:]
    require(all(r["status"] in ("not_run", "completed") for r in generation),
            "failed/partial step preserved; export diagnosis; no automatic retry")
    require(all(r["status"] != "completed" or "result" in r for r in generation),
            "completed step result missing; preserve before starting dependencies")
    require(not all(r["status"] == "completed" for r in generation),
            "interrupted final sealing preserved; no automatic recertification")
    missing = False
    for record in generation:
        if record["status"] == "not_run":
            missing = True
        else:
            require(not missing, "step order has a gap")
    elapsed, timer = existing["generation_elapsed_s"], time.monotonic()
    for index, step_id in enumerate(started["step_ids"]):
        unit = directory / "steps" / step_id
        if unit.exists():
            receipt = sealed(unit, started)
            require(receipt["exit_code"] == 0, "failed step preserved")
            print(f"{STAGE} REUSED {step_id} exit=0", flush=True)
            continue
        current_source(started)
        remaining = (started["config"]["budget_proposal"]["generation_wall_clock_limit_s"]
                     - elapsed - (time.monotonic() - timer))
        if remaining <= 0:
            write_new(directory / "completion.json", {"stage": STAGE, "commit": started["commit"],
                      "binding": started["binding"], "finished": now(),
                      "generation_elapsed_s": elapsed + time.monotonic() - timer, "exit_code": 1,
                      "error": "generation wall-clock budget exhausted before next step", "model_training_steps": 0})
            raise ValueError("generation wall-clock budget exhausted; preserved")
        print(f"{STAGE} STEP {index + 1}/{len(started['step_ids'])} {step_id}", flush=True)
        receipt = launch(directory, started, step_id, remaining)
        require(receipt["exit_code"] == 0, f"runtime failure at {step_id}; successors not started; export diagnosis")
    limits = started["config"]["budget_proposal"]
    final_error, value = None, None
    def final_budget():
        require(elapsed + time.monotonic() - timer < limits["generation_wall_clock_limit_s"],
                "generation wall-clock budget reached during final verification")
        require(size(directory) + RESERVE_BYTES <= limits["new_output_limit_bytes"], "output budget reached at final sealing")
    try:
        value = inspect(directory, finalizing=True, budget_check=final_budget)
        final_budget()
    except Exception as error:
        final_error = f"{type(error).__name__}: {error}"
    total = elapsed + time.monotonic() - timer
    success = value is not None and value["status"] == "passed" and final_error is None
    write_new(directory / "completion.json", {"stage": STAGE, "commit": started["commit"], "binding": started["binding"],
              "finished": now(), "generation_elapsed_s": total, "exit_code": 0 if success else 1,
              "error": final_error, "model_training_steps": 0})
    require(success, "engineering audit/budget failed; fixed census retained; export diagnosis")
    print(f"{STAGE} VERIFIED unique_branches=16 replay_branches=16 exit=0", flush=True)


def export(directory, report):
    value = inspect(directory)
    value["history_observation_evidence"] = {}
    for path in sorted(directory.glob("steps/history-*/data/observation_evidence.json")):
        try:
            evidence = read(path)
        except (ValueError, UnicodeError) as error:
            evidence = {"parse_error": str(error), "partial_evidence_sha256": file_sha(path)}
        value["history_observation_evidence"][path.relative_to(directory).as_posix()] = evidence
    previews = []
    previews.extend(p for pattern in ("steps/history-*/data/view-a.png", "steps/history-*/data/view-b.png",
                                     "steps/history-*/data/recent.png", "steps/primary-*/data/final_ego.png")
                    for p in directory.glob(pattern))
    value["previews_png_base64"] = {p.relative_to(directory).as_posix(): base64.b64encode(p.read_bytes()).decode()
                                    for p in sorted(previews)}
    private = list(directory.glob("steps/primary-*/data/private_overview.png"))
    if value["status"] != "passed":
        private.extend((directory / "check").rglob("*.png"))
        value["aggregate_failure_log_tail"] = log_tail(directory / "steps/audit")
    value["private_review_previews"] = {"purpose": "review_only_not_model_input",
        "png_base64": {p.relative_to(directory).as_posix(): base64.b64encode(p.read_bytes()).decode()
                       for p in sorted(private)}}
    payload = {"audit": value, "audit_sha256": sha(encode(value))}
    if report.exists():
        require(report.read_bytes() == encode(payload), "different report exists; preserved; choose a new report name")
    else:
        write_new(report, payload)
    print(f"{STAGE} EXPORTED status={value['status']} {report} exit=0", flush=True)


def worker(directory, step_id):
    started = stage(directory)
    unit = directory / ("check" if step_id == "check" else f"steps/{step_id}")
    require(platform.system() == "Linux" and os.environ.get("SH04_CHILD_DIR") == str(unit), "server launcher required")
    budget = Budget(directory, started["config"]["budget_proposal"]["new_output_limit_bytes"],
                    float(os.environ["SH04_REMAINING_SECONDS"]))
    sys.path.insert(0, str(ROOT / "src"))
    if step_id != "check":
        from spatial_world_model.two_gate_engineering import run_step
        last_print = [time.monotonic()]
        def progress(event):
            budget.check(reserve_bytes=event.get("reserve_bytes", 0))
            if "message" in event or time.monotonic() - last_print[0] >= 2:
                shown = {k: v for k, v in event.items() if k != "reserve_bytes"}
                print(f"{STAGE} {step_id} {shown}", flush=True)
                last_print[0] = time.monotonic()
        result = run_step(step_id, directory=unit / "data", config_path=ROOT / CONFIG,
                          stage_directory=directory, progress=progress)
        budget.check(reserve_bytes=len(encode(result)))
        write_new(unit / "result.json", result)
        return 0
    from mujoco.egl import GLContext
    from OpenGL import GL
    context = GLContext(64, 64)
    try:
        context.make_current()
        renderer = GL.glGetString(GL.GL_RENDERER)
        require(bool(renderer), "EGL renderer missing")
        egl = {"status": "passed", "renderer": renderer.decode(errors="replace")}
    finally:
        context.free()
    sys.path.insert(0, str(ROOT / "tests/spatial_world_model"))
    suite = unittest.TestSuite()
    for filename in TESTS:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(Path(filename).stem)))
    def flatten(item):
        return [name for child in item for name in flatten(child)] if isinstance(item, unittest.TestSuite) else [item.id()]
    names = sorted(flatten(suite))
    require(names == started["test_names"] == test_names(), "runtime/static test inventory mismatch")
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    success = (result.wasSuccessful() and result.testsRun == len(names) and not result.skipped and not result.expectedFailures)
    value = {"test_names": names, "tests_run": result.testsRun, "failures": len(result.failures),
             "errors": len(result.errors), "skipped": len(result.skipped), "exit_code": 0 if success else 1, "egl": egl}
    budget.check(reserve_bytes=len(encode(value)))
    write_new(unit / "result.json", value)
    return value["exit_code"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "run", "verify", "export", "_worker"))
    parser.add_argument("--run-dir", type=Path, default=RUN)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--step-id")
    args = parser.parse_args()
    directory, report = args.run_dir.resolve(), args.report.resolve()
    root = (DISK / "spatial-history").resolve()
    require(directory.is_relative_to(root) and directory != root, "named data-disk stage directory required")
    require(report.parent == (ROOT / "results").resolve() and report.suffix == ".json", "JSON report directly in results required")
    if args.command == "_worker":
        require(args.step_id in ["check", *read(directory / "started.json")["step_ids"]], "unknown worker step")
        return worker(directory, args.step_id)
    require(args.step_id is None, "step-id is private to the stage launcher")
    if args.command == "export":
        export(directory, report)
    elif args.command == "verify":
        value = inspect(directory)
        require(value["status"] == "passed", "engineering audit not passed; export available")
        print(f"{STAGE} VERIFIED unique_branches=16 replay_branches=16 exit=0", flush=True)
    else:
        {"check": check, "run": run}[args.command](directory)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"{STAGE} FAILED exit=1: {error}", file=sys.stderr, flush=True)
        sys.exit(1)
