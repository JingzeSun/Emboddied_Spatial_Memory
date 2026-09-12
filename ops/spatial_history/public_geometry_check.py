"""E0: fixed read-only public recovery, sealed predictions, private evaluation.

Linux server only; standard library, no simulation, learning, or downloads.
Workers receive role-specific requests. This is an API boundary, not an OS jail.
"""
import argparse
import ast
import fcntl
import importlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import threading
import time
import traceback
import unittest

sys.dont_write_bytecode = True
from contract_check import ROOT, encode, git, require, sha
import public_input_check as reader_ops
from public_geometry_workers import dispatch
from public_geometry_resources import capacity


STAGE = "SH-04-R3-E0-public-geometry-parallel-v1"
SERIAL_RUN = Path("/root/autodl-tmp/spatial-history/sh04-r3-e0-public-geometry-v1")
RUN = Path("/root/autodl-tmp/spatial-history/sh04-r3-e0-public-geometry-parallel-v1")
SOURCE = reader_ops.SOURCE
REPORT = ROOT / "results/spatial_history_public_geometry_parallel_v1.json"
CONFIG = "configs/spatial_history/public_geometry_parallel_v1.json"
SERIAL_CONFIG = "configs/spatial_history/public_geometry_v1.json"
SERIAL_COMMIT = "0b1640fe92d1c3452f7e9dde4652d38fd13446ac"
PROPOSAL = "configs/spatial_history/public_geometry_proposal_v1.json"
PROPOSAL_COMMIT = "e64afa64239f82bd659a59df069b8f670b21ddcf"
PROPOSAL_SHA = "935ecaf6556ea58cde2c0f3d7c90fa0b74f8ef21c61122dc67b727c9fe1406b5"
R3_REPORT = "results/spatial_history_public_input_v1.json"
R3_COMMIT = "88c42b7ffeabbeba1e4c1b5cb297ae03194e125e"
R3_SHA = "6db21359a5e1c6e09701bf9d7e23d4630dcf9c1aae8513b137cbea48bd612754"
TESTS = ("tests/spatial_world_model/test_public_geometry.py",
         "tests/spatial_world_model/test_public_geometry_audit.py",
         "tests/spatial_world_model/test_public_geometry_ops.py",
         "tests/spatial_world_model/test_public_geometry_workers.py",
         "tests/spatial_world_model/test_public_geometry_resources.py")
BOUND = ("src/spatial_world_model/__init__.py", "src/spatial_world_model/pair_contract.py",
         "src/spatial_world_model/two_gate_contract.py", "src/spatial_world_model/public_reader.py",
         "src/spatial_world_model/public_geometry.py", "src/spatial_world_model/public_geometry_audit.py",
         "ops/spatial_history/contract_check.py", "ops/spatial_history/public_input_check.py",
         "ops/spatial_history/public_geometry_check.py", "ops/spatial_history/public_geometry_workers.py",
         "ops/spatial_history/public_geometry_resources.py", *TESTS, CONFIG, SERIAL_CONFIG, PROPOSAL,
         reader_ops.R2_REPORT, R3_REPORT, "docs/METHOD.md", "docs/DATA.md")
LIMIT_S = 1800
LIMIT_BYTES = 64 * 1024 * 1024
PROCESS_LIMIT = 512 * 1024 * 1024
DEFAULT_WORKERS = 4
MAX_WORKERS = 16
LIMIT_RSS = (DEFAULT_WORKERS + 1) * PROCESS_LIMIT
PARALLEL_SPEC = {"default_workers": DEFAULT_WORKERS, "minimum_workers": 1, "maximum_workers": MAX_WORKERS,
                 "process_as_limit_bytes": PROCESS_LIMIT, "memory_reserve_bytes": PROCESS_LIMIT,
                 "tree_rss_limit_rule": "(workers + 1) * process_as_limit_bytes",
                 "parallel_scope": "public_queries_only", "capacity_policy": "reject_insufficient_no_silent_downshift",
                 "failure_policy": "stop_dispatch_kill_live_groups_preserve_every_started_exit",
                 "aggregation_order": "registered_query_id", "artifact_writes": "process_shared_flock"}
RESERVE = 1024 * 1024
CLOSEOUT_S = 1.0
COMMAND_BEGIN = None
MONITOR = {"sampled_live_rss_peak_bytes": 0, "conservative_live_hwm_peak_bytes": 0, "error": None}
read = reader_ops.read
no_links = reader_ops.no_links
file_sha = reader_ops.file_sha
original_binding = reader_ops.original_binding
manifest = reader_ops.manifest


def configuration():
    proposal_raw = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{PROPOSAL_COMMIT}:{PROPOSAL}"])
    require(sha(proposal_raw) == PROPOSAL_SHA and (ROOT / PROPOSAL).read_bytes() == proposal_raw,
            "proposal source bytes changed")
    serial_expected = json.loads(proposal_raw)
    serial_expected.update(version="sh04-r3-e0-public-geometry-v1", status="frozen_read_only_engineering",
                    decision="D-077", numeric_protocol_approved=True, implementation_run_authorized=True,
                    proposal_source=PROPOSAL, proposal_commit=PROPOSAL_COMMIT, proposal_sha256=PROPOSAL_SHA)
    serial_raw = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{SERIAL_COMMIT}:{SERIAL_CONFIG}"])
    require((ROOT / SERIAL_CONFIG).read_bytes() == serial_raw and encode(json.loads(serial_raw)) == encode(serial_expected),
            "original serial registration changed")
    expected = json.loads(serial_raw)
    expected.update(version="sh04-r3-e0-public-geometry-parallel-v1", decision="D-078",
                    serial_registration_source=SERIAL_CONFIG, serial_registration_commit=SERIAL_COMMIT,
                    serial_registration_sha256=sha(serial_raw), parallel_execution=PARALLEL_SPEC)
    expected["budget_proposal"]["peak_rss_limit_bytes"] = (MAX_WORKERS + 1) * PROCESS_LIMIT
    actual = read(ROOT / CONFIG)
    require(encode(actual) == encode(expected), "active configuration differs from approved proposal")
    return actual


def binding():
    return {name: file_sha(ROOT / name) for name in BOUND}


def execution_spec(workers):
    require(type(workers) is int and 1 <= workers <= MAX_WORKERS, "workers must be an integer in 1..16")
    return {"workers": workers, "process_as_limit_bytes": PROCESS_LIMIT,
            "tree_rss_limit_bytes": (workers + 1) * PROCESS_LIMIT}


def configure_execution(directory, requested_workers=None):
    global LIMIT_RSS
    started = directory / "started.json"
    if started.exists():
        recorded = read(started)["execution"]
        expected = execution_spec(recorded["workers"])
        require(recorded == expected, "recorded execution limits changed")
        require(requested_workers is None or requested_workers == recorded["workers"],
                "existing stage uses a different worker count; preserved")
    else:
        expected = execution_spec(DEFAULT_WORKERS if requested_workers is None else requested_workers)
    LIMIT_RSS = expected["tree_rss_limit_bytes"]
    return expected


def capacity_options():
    """Report feasible counts without creating a stage or measuring speed."""
    observed = capacity(1, PROCESS_LIMIT, PROCESS_LIMIT)
    feasible = [n for n in range(1, MAX_WORKERS + 1)
                if observed["cpu_capacity"] >= n and observed["available_memory_bytes"] >= (n + 2) * PROCESS_LIMIT]
    require(feasible, "no worker count fits the visible resources")
    return {"cpu_capacity": observed["cpu_capacity"],
            "available_memory_gib": observed["available_memory_bytes"] / (1024 ** 3),
            "feasible_workers": feasible, "maximum_feasible_workers": max(feasible),
            "recommended_initial_workers": min(DEFAULT_WORKERS, max(feasible)),
            "minimum_available_memory_gib": {str(n): (n + 2) * PROCESS_LIMIT / (1024 ** 3)
                                             for n in (1, 4, 8, 16)},
            "scope": "visible CPU affinity/cgroup and RAM limits; no reservation and no speed benchmark",
            "stage_created": False, "tests_or_queries_run": False}


def source_inputs(source):
    public = reader_ops.source_inputs(source)
    r3 = read(ROOT / R3_REPORT)
    require(r3["status"] == "passed" and r3["receipt"]["commit"] == R3_COMMIT
            and r3["receipt_sha256"] == sha(encode(r3["receipt"])) == R3_SHA,
            "accepted R3 report required")
    require(reader_ops.verify(reader_ops.RUN) == r3["receipt"], "R3 server receipt differs from report")
    require(read(reader_ops.RUN / "started.json") == r3["started"]
            and read(reader_ops.RUN / "tests.json") == r3["tests"]
            and read(reader_ops.RUN / "public_audit.json") == r3["public_audit"], "R3 artifacts differ")
    # The reusable reader/helper bytes must still be those exercised by R3.
    for name in ("src/spatial_world_model/public_reader.py", "ops/spatial_history/public_input_check.py",
                 "ops/spatial_history/contract_check.py", "src/spatial_world_model/pair_contract.py",
                 "src/spatial_world_model/two_gate_contract.py"):
        original_binding(R3_COMMIT, {name: file_sha(ROOT / name)})
    r2 = read(ROOT / reader_ops.R2_REPORT)["audit"]
    records = {row["step_id"]: row for row in r2["steps"]}
    xml = {}
    for world in ("LL", "LR", "RL", "RR"):
        entry = records[f"history-{world}"]["artifacts"]["data/world.xml"]
        relative = f"steps/history-{world}/data/world.xml"
        path = source / relative
        no_links(path)
        require(path.stat().st_size == entry["bytes"] and file_sha(path) == entry["sha256"], "R2 XML changed")
        xml[world] = {"relative_path": relative, **entry}
    return {"public": public, "xml": xml, "r3_receipt_sha256": R3_SHA}


def jobs(config, inputs, source):
    rows = []
    for world in config["evaluation_only"]["worlds"]:
        for mode in ("full", "view_a", "view_b", "recent"):
            entry = inputs["public"][world]
            spec = config["evaluation_only"]["query_modes"][mode]
            rows.append({"id": f"query-{len(rows):02d}", "world": world, "mode": mode,
                         "indices": spec["indices"], "expected_candidates": spec["expected_candidates"],
                         "public_path": str(source / entry["relative_path"]),
                         "expected_sha256": entry["sha256"], "expected_bytes": entry["bytes"]})
    require(len(rows) == 16, "wrong fixed census")
    return rows


def test_names(commit=None):
    names = []
    for name in TESTS:
        raw = ((ROOT / name).read_bytes() if commit is None else subprocess.check_output(
            ["git", "-C", str(ROOT), "show", f"{commit}:{name}"]))
        tree = ast.parse(raw)
        names.extend(f"{Path(name).stem}.{cls.name}.{fn.name}" for cls in tree.body
                     if isinstance(cls, ast.ClassDef) for fn in cls.body
                     if isinstance(fn, ast.FunctionDef) and fn.name.startswith("test_"))
    require(names and len(names) == len(set(names)), "invalid test census")
    return sorted(names)


def used_bytes(directory):
    return sum(p.stat().st_size for p in directory.rglob("*") if p.is_file())


def save(directory, relative, value, *, emergency=False):
    path = directory / relative
    no_links(path)
    raw = encode(value)
    lock = directory / ".write.lock"
    no_links(lock)
    # The byte check and complete write share one kernel lock across parent
    # and workers; concurrent writers cannot each spend the same free space.
    with lock.open("a+b") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        used = used_bytes(directory)
        require((used + len(raw) <= LIMIT_BYTES if emergency else 2 * (used + len(raw)) + RESERVE <= LIMIT_BYTES),
                "E0 artifact/export budget reached")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(raw)


def tree_memory():
    """Live RSS and conservative sum of live-process high-water marks, bytes."""
    processes = {}
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            fields = dict(line.split(":", 1) for line in (p / "status").read_text().splitlines() if ":" in line)
            processes[int(p.name)] = (int(fields["PPid"]), int(fields.get("VmRSS", "0 kB").split()[0]) * 1024,
                                      int(fields.get("VmHWM", "0 kB").split()[0]) * 1024)
        except (OSError, ValueError, KeyError):
            continue  # Processes can exit between enumeration and read.
    require(os.getpid() in processes and processes[os.getpid()][1] > 0,
            "cannot measure parent RSS from /proc")
    selected = {os.getpid()}
    while True:
        enlarged = selected | {pid for pid, (parent, _, _) in processes.items() if parent in selected}
        if enlarged == selected:
            break
        selected = enlarged
    return tuple(sum(processes.get(pid, (0, 0, 0))[i] for pid in selected) for i in (1, 2))


def watch_command(stop):
    """Cover preflight, source rechecks, verification and export as well as workers."""
    while not stop.is_set():
        try:
            rss, bound = tree_memory()
            MONITOR["sampled_live_rss_peak_bytes"] = max(MONITOR["sampled_live_rss_peak_bytes"], rss)
            MONITOR["conservative_live_hwm_peak_bytes"] = max(MONITOR["conservative_live_hwm_peak_bytes"], bound)
            require(bound <= LIMIT_RSS, "whole-command live-process-tree memory limit")
        except BaseException as exc:
            MONITOR["error"] = f"{type(exc).__name__}: {exc}"
            stop.set()
            os.kill(os.getpid(), signal.SIGUSR1)
            return
        stop.wait(0.05)


def watch_thread(stop):
    blocked = {signal.SIGTERM, signal.SIGINT, signal.SIGALRM, signal.SIGUSR1}
    # This dedicated thread keeps its mask until it exits, so it cannot take
    # a pending signal while the main thread registers a newly spawned child.
    signal.pthread_sigmask(signal.SIG_BLOCK, blocked)
    watch_command(stop)


def run_children(directory, tasks, workers, begin, ledger, launched_children=None):
    """One parent owns dispatch/receipts; workers write only their own outputs."""
    parent_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    measured = {"rss": 0, "bound": parent_peak}
    launched_children = [] if launched_children is None else launched_children

    def checkpoint():
        rss, hwm = tree_memory()
        measured["rss"], measured["bound"] = max(measured["rss"], rss), max(measured["bound"], hwm)
        require(time.monotonic() - begin <= LIMIT_S, "stage wall-clock limit")
        require(hwm <= LIMIT_RSS and MONITOR["error"] is None, "live process-tree memory limit")
        require(2 * used_bytes(directory) + RESERVE <= LIMIT_BYTES, "artifact/export limit")

    def launch(task):
        identifier, role = task["id"], task["role"]
        save(directory, f"requests/{identifier}.json", task["request"])
        env = {**os.environ, "E0_CHILD_DIR": str(directory), "E0_CHILD_ID": identifier,
               "E0_CHILD_AS_BYTES": str(PROCESS_LIMIT)}
        cmd = [sys.executable, "-B", str(Path(__file__).resolve()), "_worker", "--role", role, "--id", identifier]
        child = subprocess.Popen(cmd, env=env, start_new_session=True)
        launched_children.append({"id": identifier, "role": role, "pid": child.pid})
        return child

    def abort(child):
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            if child.poll() is None:
                child.kill()
        except OSError:
            child.kill()
        child.wait(timeout=5)

    def completed(task, child, error):
        identifier = task["id"]
        stats, stats_error = None, None
        try:
            stats_path = directory / f"worker/{identifier}.json"
            stats = read(stats_path) if stats_path.exists() else None
            if stats is not None:
                require(isinstance(stats, dict) and set(stats) == {"id", "role", "completed", "error", "peak_rss_bytes"}
                        and stats["id"] == identifier and stats["role"] == task["role"]
                        and type(stats["completed"]) is bool and type(stats["peak_rss_bytes"]) is int
                        and 0 < stats["peak_rss_bytes"] <= PROCESS_LIMIT
                        and (stats["error"] is None if stats["completed"] else isinstance(stats["error"], str)),
                        "malformed worker completion evidence")
        except (OSError, ValueError, KeyError, TypeError):
            stats_error = traceback.format_exc()
            stats = None
        bound = max(measured["bound"], parent_peak + (stats["peak_rss_bytes"] if stats else 0))
        row = {"id": identifier, "role": task["role"], "exit_code": child.returncode,
               "error": error or stats_error, "sampled_live_rss_peak_bytes": measured["rss"],
               "conservative_live_hwm_peak_bytes": bound, "worker": stats}
        ledger.append(row)
        save(directory, f"exits/{identifier}.json", row, emergency=error is not None or child.returncode != 0 or stats_error is not None)
        if error is None:
            require(stats_error is None and child.returncode == 0 and stats is not None
                    and stats["completed"] and bound <= LIMIT_RSS, f"{identifier} failed; preserved")
        return row

    return dispatch(tasks, workers, launch, completed, checkpoint, abort)


def run_child(directory, role, identifier, request, begin, ledger, launched_children=None):
    return run_children(directory, [{"id": identifier, "role": role, "request": request}], 1, begin, ledger, launched_children)


def worker_tests(directory, request):
    sys.path.insert(0, str(ROOT / "tests/spatial_world_model"))
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(Path(p).stem))
                               for p in TESTS)
    def flatten(item):
        return [n for child in item for n in flatten(child)] if isinstance(item, unittest.TestSuite) else [item.id()]
    names = sorted(flatten(suite))
    require(names == request["test_names"] == test_names(), "test census changed")
    class Stream:
        def __init__(self, handle):
            self.handle = handle
        def write(self, text):
            require(2 * (used_bytes(directory) + len(text.encode("utf-8"))) + RESERVE <= LIMIT_BYTES, "test log budget")
            sys.stdout.write(text)
            self.handle.write(text)
            self.handle.flush()
        def flush(self):
            sys.stdout.flush()
            self.handle.flush()
    with (directory / "tests.log").open("x", encoding="utf-8") as log:
        result = unittest.TextTestRunner(stream=Stream(log), verbosity=2).run(suite)
    counts = {"test_names": names, "tests_run": result.testsRun, "failures": len(result.failures),
              "errors": len(result.errors), "skipped": len(result.skipped),
              "expected_failures": len(result.expectedFailures), "unexpected_successes": len(result.unexpectedSuccesses)}
    save(directory, "tests.json", counts)
    require(result.wasSuccessful() and result.testsRun == len(names) and not result.skipped
            and not result.expectedFailures, "E0 tests failed")


def public_request(job, config):
    return {"public_path": job["public_path"], "expected_sha256": job["expected_sha256"],
            "expected_bytes": job["expected_bytes"], "history_indices": job["indices"],
            "public_sensor_spec": config["public_sensor_spec"], "extractor": config["extractor"]}


def worker_public(directory, identifier, request):
    require(set(request) == {"public_path", "expected_sha256", "expected_bytes", "history_indices",
                             "public_sensor_spec", "extractor"}, "private/public request boundary")
    from spatial_world_model.public_reader import load_query
    from spatial_world_model.public_geometry import recover_openings
    query = load_query(request["public_path"], expected_sha256=request["expected_sha256"],
                       expected_bytes=request["expected_bytes"], action_name="LL",
                       history_indices=request["history_indices"])
    history = query.pop("history")
    del query  # Neither goal nor numeric controls reach geometry recovery.
    prediction = recover_openings(history, request["public_sensor_spec"], request["extractor"])
    save(directory, f"predictions/{identifier}.json", {"prediction": prediction,
         "prediction_sha256": sha(encode(prediction)), "public_file_sha256": request["expected_sha256"],
         "history_sha256": sha(encode(history)), "history_frames": len(history)})
    print(f"{STAGE} PUBLIC {identifier} frames={len(history)} candidates={len(prediction['candidates'])}", flush=True)


def verify_seal(directory, seal):
    require(set(seal) == {"predictions", "public_complete"} and seal["public_complete"] is True, "invalid public seal")
    expected = {f"predictions/query-{i:02d}.json" for i in range(16)}
    require(set(seal["predictions"]) == expected, "incomplete sealed prediction census")
    for name, entry in seal["predictions"].items():
        path = directory / name
        no_links(path)
        require(path.stat().st_size == entry["bytes"] and file_sha(path) == entry["sha256"], "sealed prediction changed")


def evaluate_predictions(directory, request, *, progress=False):
    from spatial_world_model.public_geometry_audit import targets_from_xml, assess_geometry
    seal = read(directory / "public_seal.json")
    verify_seal(directory, seal)
    require(request["public_seal_sha256"] == file_sha(directory / "public_seal.json"), "seal source mismatch")
    rows = []
    targets_by_world, xml_evidence = {}, {}
    for world, entry in request["xml"].items():
        path = SOURCE / entry["relative_path"]
        no_links(path)
        raw = path.read_bytes()
        require(len(raw) == entry["bytes"] and sha(raw) == entry["sha256"], "private XML changed")
        targets_by_world[world] = targets_from_xml(raw.decode("utf-8"))
        xml_evidence[world] = {**entry, "xml_text": raw.decode("utf-8"), "targets": targets_by_world[world]}
    for job in request["jobs"]:
        record = read(directory / f"predictions/{job['id']}.json")
        pred = record["prediction"]
        require(record["prediction_sha256"] == sha(encode(pred)), "prediction content digest differs")
        all_targets = targets_by_world[job["world"]]
        mode = job["mode"]
        targets = (all_targets if mode == "full" else all_targets[:1] if mode == "view_a"
                   else all_targets[1:] if mode == "view_b" else [])
        result = assess_geometry(pred, targets, request["evaluation_only"])
        result["registered_count_matches"] = len(pred["candidates"]) == job["expected_candidates"]
        result["accepted"] = result["accepted"] and result["registered_count_matches"]
        rows.append({"id": job["id"], "world": job["world"], "mode": mode, "assessment": result})
        if progress:
            print(f"{STAGE} EVALUATE {job['world']}/{mode} accepted={result['accepted']}", flush=True)
    verify_seal(directory, seal)
    return {"rows": rows, "accepted": all(r["assessment"]["accepted"] for r in rows),
            "private_xml_evidence": xml_evidence,
            "public_seal_sha256": request["public_seal_sha256"]}


def worker_evaluate(directory, request):
    save(directory, "evaluation.json", evaluate_predictions(directory, request, progress=True))


def worker(role, identifier):
    require(os.environ.get("E0_CHILD_DIR") == str(RUN) and os.environ.get("E0_CHILD_ID") == identifier,
            "fresh parent launch required")
    require(not (RUN / "receipt.json").exists(), "closed stage cannot launch workers")
    signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGTERM, signal.SIGINT, signal.SIGALRM, signal.SIGUSR1})
    cap = int(os.environ["E0_CHILD_AS_BYTES"])
    require(cap == PROCESS_LIMIT, "worker process limit differs from registration")
    resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    sys.path.insert(0, str(ROOT / "src"))
    request = read(RUN / f"requests/{identifier}.json")
    completed, error = False, None
    try:
        if role == "tests":
            worker_tests(RUN, request)
        elif role == "public":
            worker_public(RUN, identifier, request)
        else:
            worker_evaluate(RUN, request)
        completed = True
    except BaseException:
        error = traceback.format_exc()
    save(RUN, f"worker/{identifier}.json", {"id": identifier, "role": role, "completed": completed,
         "error": error, "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}, emergency=not completed)
    require(completed, f"worker failed: {error}")


def inventory_checks(directory, registered_jobs, evaluation):
    expected = [f"query-{i:02d}" for i in range(16)]
    records = [read(directory / f"predictions/{identifier}.json") for identifier in expected]
    recent = [r for j, r in zip(registered_jobs, records) if j["mode"] == "recent"]
    return {"complete_16_queries": [r["id"] for r in evaluation["rows"]] == expected,
            "exact_500_frame_consumptions": sum(r["history_frames"] for r in records) == 500,
            "per_query_frame_counts": all(r["history_frames"] == r["prediction"]["history_frames"]
                                          == (121 if j["indices"] is None else len(j["indices"]))
                                          for j, r in zip(registered_jobs, records)),
            "same_recent_geometry": len({r["prediction_sha256"] for r in recent}) == 1,
            "all_geometry_checks": len(evaluation["rows"]) == 16 and all(r["assessment"]["accepted"] for r in evaluation["rows"])}


def success_evidence(directory, saved, started):
    """Rebuild census, input digests, target matching and child evidence."""
    config = configuration()
    require(started["config"] == config, "registered configuration changed")
    execution = execution_spec(started["execution"]["workers"])
    require(saved["execution"] == started["execution"] == execution, "execution registration differs")
    resources = started["resources"]
    require(resources["workers"] == execution["workers"] and resources["cpu_capacity"] >= execution["workers"]
            and resources["tree_rss_limit_bytes"] == execution["tree_rss_limit_bytes"]
            and resources["process_as_limit_bytes"] == PROCESS_LIMIT and resources["reserve_bytes"] == PROCESS_LIMIT
            and resources["available_memory_bytes"] >= execution["tree_rss_limit_bytes"] + PROCESS_LIMIT,
            "original capacity preflight was insufficient")
    # A later documentation change can reuse a receipt. A changed verifier or
    # scientific implementation must use the original checkout to verify it.
    for name in BOUND:
        if name.endswith(".py"):
            require(file_sha(ROOT / name) == saved["binding"][name], "verify using original code checkout: " + name)
    inputs = source_inputs(SOURCE)
    require(started["inputs"] == inputs and started["source_directory"] == str(SOURCE), "original inputs differ")
    registered_jobs = jobs(config, inputs, SOURCE)
    require(started["jobs"] == registered_jobs, "job registration differs")
    ids = ["tests"] + [f"query-{i:02d}" for i in range(16)] + ["evaluate"]
    expected_files = {".write.lock", "started.json", "tests.json", "tests.log", "public_seal.json", "evaluation.json", "audit.json"}
    expected_files |= {f"{sub}/{identifier}.json" for sub in ("requests", "worker", "exits") for identifier in ids}
    expected_files |= {f"predictions/query-{i:02d}.json" for i in range(16)}
    require(set(saved["artifacts"]) == expected_files, "successful artifact census differs")
    require([r["id"] for r in saved["children"]] == ids, "child completion census incomplete")
    require(saved["not_started_ids"] == [] and saved["missing_exit_ids"] == [], "successful child evidence incomplete")
    for row in saved["children"]:
        identifier = row["id"]
        require(row == read(directory / f"exits/{identifier}.json")
                and row["worker"] == read(directory / f"worker/{identifier}.json"), "child receipts differ")
        role = "tests" if identifier == "tests" else "evaluate" if identifier == "evaluate" else "public"
        require(row["role"] == row["worker"]["role"] == role and row["worker"]["id"] == identifier
                and row["exit_code"] == 0 and row["error"] is None and row["worker"]["completed"]
                and row["worker"]["error"] is None
                and row["conservative_live_hwm_peak_bytes"] <= saved["conservative_live_hwm_peak_bytes"],
                "child completion/source guard differs")
    require(read(directory / "requests/tests.json") == {"test_names": started["test_names"]}, "test request changed")
    from spatial_world_model.public_reader import load_query
    # Recheck public history digests, without rerunning recovery. The original
    # reader validates each entire file before any diagnostic slice is taken.
    for world in config["evaluation_only"]["worlds"]:
        world_jobs = [j for j in registered_jobs if j["world"] == world]
        first = world_jobs[0]
        query = load_query(first["public_path"], expected_sha256=first["expected_sha256"],
                           expected_bytes=first["expected_bytes"], action_name="LL")
        history = query["history"]
        for job in world_jobs:
            require(read(directory / f"requests/{job['id']}.json") == public_request(job, config), "public request differs")
            record = read(directory / f"predictions/{job['id']}.json")
            selected = history if job["indices"] is None else [history[i] for i in job["indices"]]
            require(set(record) == {"prediction", "prediction_sha256", "public_file_sha256", "history_sha256", "history_frames"}
                    and record["public_file_sha256"] == job["expected_sha256"]
                    and record["history_sha256"] == sha(encode(selected))
                    and record["history_frames"] == record["prediction"]["history_frames"] == len(selected)
                    and record["prediction_sha256"] == sha(encode(record["prediction"])), "prediction source differs")
        del query, history
    expected_request = {"xml": inputs["xml"], "jobs": registered_jobs, "evaluation_only": config["evaluation_only"],
                        "public_seal_sha256": file_sha(directory / "public_seal.json")}
    require(read(directory / "requests/evaluate.json") == expected_request, "private evaluation request differs")
    expected_evaluation = evaluate_predictions(directory, expected_request)
    require(read(directory / "evaluation.json") == expected_evaluation, "independent geometry recomputation differs")
    audit = read(directory / "audit.json")
    checks = inventory_checks(directory, registered_jobs, expected_evaluation)
    require(audit["checks"] == checks and all(checks.values()) and audit["accepted"] is True
            and audit["public_geometry_recovery_verified"] is True, "geometry audit incomplete")
    require(all(audit[k] is False for k in ("full_3d_map_verified", "physical_predictability_verified", "model_experiment_run"))
            and all(audit[k] == 0 for k in ("new_training_steps", "new_simulation_steps", "new_weight_download_bytes")),
            "claim boundary differs")


def verify(directory, *, require_success=True, pending=None):
    no_links(directory)
    saved, started = (read(directory / "receipt.json") if pending is None else pending), read(directory / "started.json")
    execution = execution_spec(started["execution"]["workers"])
    require(saved["execution"] == started["execution"] == execution, "execution registration differs")
    registered_ids = ["tests"] + [job["id"] for job in started["jobs"]] + ["evaluate"]
    launched_ids = [row["id"] for row in saved["launched_children"]]
    exited_ids = [row["id"] for row in saved["children"]]
    require(launched_ids == registered_ids[:len(launched_ids)]
            and len(exited_ids) == len(set(exited_ids)) and set(exited_ids) <= set(launched_ids)
            and saved["not_started_ids"] == [i for i in registered_ids if i not in launched_ids]
            and saved["missing_exit_ids"] == [i for i in launched_ids if i not in exited_ids],
            "launched, unstarted, and missing-exit census differs")
    require(all(type(row["pid"]) is int and row["pid"] > 0 for row in saved["launched_children"]),
            "invalid launched process evidence")
    require(saved["stage"] == started["stage"] == STAGE, "wrong stage")
    require(saved["commit"] == started["commit"] and saved["binding"] == started["binding"]
            and set(saved["binding"]) == set(BOUND), "source binding mismatch")
    original_binding(saved["commit"], saved["binding"])
    require(saved["artifacts"] == manifest(directory), "E0 artifacts changed")
    require(saved["artifact_bytes"] == sum(v["bytes"] for v in saved["artifacts"].values()), "artifact byte sum differs")
    require(started["test_names"] == test_names(saved["commit"]), "original test census differs")
    if saved["exit_code"] == 0:
        verify_seal(directory, read(directory / "public_seal.json"))
        tests = read(directory / "tests.json")
        require(tests["test_names"] == started["test_names"] and tests["tests_run"] == len(started["test_names"])
                and all(tests[k] == 0 for k in ("failures", "errors", "skipped", "expected_failures", "unexpected_successes")),
                "tests incomplete")
        success_evidence(directory, saved, started)
        require(saved["source_unchanged"] and saved["input_unchanged"] and saved["error"] is None
                and saved["elapsed_s"] <= LIMIT_S
                and saved["conservative_live_hwm_peak_bytes"] <= execution["tree_rss_limit_bytes"]
                and used_bytes(directory) <= LIMIT_BYTES, "resource or source guard failed")
    if require_success:
        require(saved["exit_code"] == 0, "failed run preserved; export diagnosis")
        if pending is None:
            print(f"{STAGE} VERIFIED tests={len(started['test_names'])} queries=16 workers={execution['workers']} exit=0", flush=True)
    return saved


def run(directory, source, *, workers=DEFAULT_WORKERS):
    if directory.exists():
        verify(directory)
        return
    require(platform.system() == "Linux" and (3, 11) <= sys.version_info[:2] < (3, 13), "Linux Python 3.11/3.12 required")
    begin = COMMAND_BEGIN if COMMAND_BEGIN is not None else time.monotonic()
    resource.setrlimit(resource.RLIMIT_AS, (PROCESS_LIMIT, PROCESS_LIMIT))
    no_links(SERIAL_RUN)
    require(not SERIAL_RUN.exists(), "original serial E0 exists; preserve and verify using commit " + SERIAL_COMMIT)
    execution = configure_execution(directory, workers)
    config = configuration()
    require(not git("status", "--porcelain", "--", *BOUND), "bound sources must be clean and committed")
    before, commit = binding(), git("rev-parse", "HEAD")
    original_binding(commit, before)
    resources = capacity(workers, PROCESS_LIMIT, PROCESS_LIMIT)
    print(f"{STAGE} CAPACITY {json.dumps(resources, sort_keys=True)}", flush=True)
    inputs = source_inputs(source)
    registered_jobs = jobs(config, inputs, source)
    directory.mkdir(parents=True, exist_ok=False)
    save(directory, "started.json", {"stage": STAGE, "commit": commit, "binding": before, "config": config,
         "inputs": inputs, "jobs": registered_jobs, "test_names": test_names(), "python": sys.version,
         "repository": str(ROOT), "source_directory": str(source), "started": reader_ops.now(),
         "execution": execution, "resources": resources})
    ledger, launched_children, error, same_input, accepted = [], [], None, False, False
    try:
        run_child(directory, "tests", "tests", {"test_names": test_names()}, begin, ledger, launched_children)
        tasks = [{"id": job["id"], "role": "public", "request": public_request(job, config)} for job in registered_jobs]
        run_children(directory, tasks, workers, begin, ledger, launched_children)
        predictions = {name: entry for name, entry in manifest(directory).items() if name.startswith("predictions/")}
        save(directory, "public_seal.json", {"predictions": predictions, "public_complete": True})
        verify_seal(directory, read(directory / "public_seal.json"))
        run_child(directory, "evaluate", "evaluate", {"xml": inputs["xml"], "jobs": registered_jobs,
                  "evaluation_only": config["evaluation_only"], "public_seal_sha256": file_sha(directory / "public_seal.json")}, begin, ledger, launched_children)
        checks = inventory_checks(directory, registered_jobs, read(directory / "evaluation.json"))
        accepted = all(checks.values())
        save(directory, "audit.json", {"accepted": accepted, "checks": checks,
             "public_geometry_recovery_verified": accepted, "full_3d_map_verified": False,
             "physical_predictability_verified": False, "model_experiment_run": False,
             "new_training_steps": 0, "new_simulation_steps": 0, "new_weight_download_bytes": 0,
             "rgb_invariance_evidence": "new synthetic server tests; no extra real-query rerun"})
    except BaseException:
        error = traceback.format_exc()
    same_source = False
    if error is None:
        try:
            same_input = source_inputs(source) == inputs
            same_source = binding() == before and git("rev-parse", "HEAD") == commit
        except BaseException:
            error = "Input/source recheck: " + traceback.format_exc()
    registered_ids = ["tests"] + [job["id"] for job in registered_jobs] + ["evaluate"]
    ledger.sort(key=lambda row: registered_ids.index(row["id"]))
    artifacts = manifest(directory)
    elapsed = time.monotonic() - begin
    peak = max([resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024]
               + [x["conservative_live_hwm_peak_bytes"] for x in ledger])
    success = accepted and error is None and same_input and same_source and elapsed <= LIMIT_S and peak <= LIMIT_RSS
    saved = {"stage": STAGE, "commit": commit, "binding": before, "finished": reader_ops.now(),
             "launched_children": launched_children,
             "execution": execution, "not_started_ids": [identifier for identifier in registered_ids
                                                          if identifier not in {r["id"] for r in launched_children}],
             "missing_exit_ids": [r["id"] for r in launched_children if r["id"] not in {e["id"] for e in ledger}],
             "children": ledger, "elapsed_s": elapsed, "conservative_live_hwm_peak_bytes": peak,
             "error": error, "source_unchanged": same_source, "input_unchanged": same_input,
             "geometry_accepted": accepted, "artifacts": artifacts,
             "artifact_bytes": sum(v["bytes"] for v in artifacts.values()), "exit_code": 0 if success else 1}
    if success:
        try:
            verify(directory, pending=saved)
        except BaseException:
            saved["error"] = "Final verification: " + traceback.format_exc()
            success = False
    # Conservative closeout allowance includes the final receipt write/check.
    saved["elapsed_s"] = time.monotonic() - begin + CLOSEOUT_S
    saved["elapsed_measurement"] = "through final verification plus 1 s receipt closeout allowance"
    saved["conservative_live_hwm_peak_bytes"] = max(peak, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                                                   MONITOR["conservative_live_hwm_peak_bytes"])
    saved["sampled_live_rss_peak_bytes"] = MONITOR["sampled_live_rss_peak_bytes"]
    success = (success and MONITOR["error"] is None and saved["elapsed_s"] <= LIMIT_S
               and saved["conservative_live_hwm_peak_bytes"] <= LIMIT_RSS)
    saved["exit_code"] = 0 if success else 1
    saved["public_geometry_recovery_verified"] = success
    # Do not publish a reusable success receipt before its write has passed
    # the closeout gates. A killed process leaves only the pending file.
    save(directory, "receipt.pending.json", saved, emergency=True)
    try:
        require(time.monotonic() - begin <= saved["elapsed_s"], "receipt closeout exceeded allowance")
        require(tree_memory()[1] <= LIMIT_RSS and MONITOR["error"] is None, "receipt closeout memory limit")
    except BaseException:
        saved["error"] = "Receipt closeout: " + traceback.format_exc()
        saved["exit_code"], saved["public_geometry_recovery_verified"] = 1, False
        saved["elapsed_s"] = time.monotonic() - begin
        saved["artifacts"] = manifest(directory)
        saved["artifact_bytes"] = sum(v["bytes"] for v in saved["artifacts"].values())
        save(directory, "receipt.json", saved, emergency=True)
        raise
    (directory / "receipt.pending.json").rename(directory / "receipt.json")
    require(success, f"{STAGE} failed; preserved; use export")
    print(f"{STAGE} VERIFIED tests={len(test_names())} queries=16 workers={workers} exit=0", flush=True)


def export_remaining_s(saved, elapsed):
    """Canonical run + first successful export share the registered 1800 s."""
    run_elapsed = saved["elapsed_s"]
    require(type(run_elapsed) in (int, float) and math.isfinite(run_elapsed) and run_elapsed >= 0,
            "invalid run elapsed time")
    remaining = LIMIT_S - run_elapsed - elapsed
    require(remaining > CLOSEOUT_S, "run plus first export wall-clock budget exhausted")
    return remaining


def export(directory, report):
    begin = COMMAND_BEGIN if COMMAND_BEGIN is not None else time.monotonic()
    no_links(report)
    pending_report = report.with_name(report.stem + ".pending.json")
    no_links(pending_report)
    require(not pending_report.exists(), "interrupted export preserved; do not retry or overwrite")
    prior = read(report) if report.exists() else None
    preliminary = read(directory / "receipt.json")
    if preliminary["exit_code"] == 0 and prior is None:
        remaining = export_remaining_s(preliminary, time.monotonic() - begin)
        if COMMAND_BEGIN is not None:
            signal.setitimer(signal.ITIMER_REAL, remaining)
    saved = verify(directory, require_success=False)
    value = {"kind": "public_geometry_engineering_only", "status": "passed" if saved["exit_code"] == 0 else "failed",
             "public_geometry_recovery_verified": saved["exit_code"] == 0,
             "full_3d_map_verified": False, "physical_predictability_verified": False, "model_experiment_run": False,
             "receipt": saved, "receipt_sha256": file_sha(directory / "receipt.json"), "artifacts_json": {}}
    for name in saved["artifacts"]:
        if name.endswith(".json"):
            try:
                value["artifacts_json"][name] = read(directory / name)
            except (ValueError, UnicodeDecodeError):
                require(saved["exit_code"] != 0, "successful stage contains invalid JSON")
                raw_artifact = (directory / name).read_bytes()
                value.setdefault("unparsed_artifacts", {})[name] = {
                    "reason": "interrupted_or_invalid_json_preserved", "bytes": len(raw_artifact),
                    "sha256": sha(raw_artifact), "utf8_prefix": raw_artifact[:16000].decode("utf-8", errors="replace")}
    if saved["exit_code"] and (directory / "tests.log").exists():
        value["tests_log_tail"] = (directory / "tests.log").read_text(encoding="utf-8")[-16000:]
    if prior is not None:
        # Verification/re-export reuses the first export's recorded budget; it
        # cannot replace measurements or silently consume another experiment.
        value["export_resources"] = prior["export_resources"]
    else:
        elapsed_bound = time.monotonic() - begin + CLOSEOUT_S
        if saved["exit_code"] == 0:
            export_remaining_s(saved, elapsed_bound - CLOSEOUT_S)
        value["export_resources"] = {
            "elapsed_s_upper_bound": elapsed_bound,
            "measurement": "through export verification and assembly plus 1 s write closeout allowance",
            "run_plus_export_elapsed_s_upper_bound": saved["elapsed_s"] + elapsed_bound,
            "observed_live_hwm_peak_before_serialization_bytes": max(MONITOR["conservative_live_hwm_peak_bytes"],
                                                                       resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024),
            "enforced_live_tree_rss_upper_bound_bytes": LIMIT_RSS,
            "failed_run_diagnostic_only": saved["exit_code"] != 0}
    resources = value["export_resources"]
    if saved["exit_code"] == 0:
        require(resources["run_plus_export_elapsed_s_upper_bound"] == saved["elapsed_s"] + resources["elapsed_s_upper_bound"]
                and resources["run_plus_export_elapsed_s_upper_bound"] <= LIMIT_S
                and resources["observed_live_hwm_peak_before_serialization_bytes"] <= LIMIT_RSS
                and resources["enforced_live_tree_rss_upper_bound_bytes"] == LIMIT_RSS
                and resources["failed_run_diagnostic_only"] is False, "export resource evidence failed")
    raw = encode(value)
    require(used_bytes(directory) + len(raw) <= LIMIT_BYTES, "combined stage and export budget")
    if report.exists():
        require(report.read_bytes() == raw, "different export exists; preserved")
    else:
        with pending_report.open("xb") as handle:
            handle.write(raw)
        require(time.monotonic() - begin <= resources["elapsed_s_upper_bound"],
                "export closeout exceeded allowance; preserve pending report")
        require(tree_memory()[1] <= LIMIT_RSS and MONITOR["error"] is None, "export closeout memory limit")
        # This final rename publishes the bounded report; no further numerical
        # work is part of the experiment. Pending exports are never reused.
        pending_report.rename(report)
    print(f"{STAGE} EXPORTED status={value['status']} {report} exit=0", flush=True)


def main():
    global COMMAND_BEGIN, LIMIT_RSS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("capacity", "run", "verify", "export", "_worker"))
    parser.add_argument("--role", choices=("tests", "public", "evaluate"))
    parser.add_argument("--id")
    parser.add_argument("--workers", type=int, choices=range(1, MAX_WORKERS + 1),
                        help="public query concurrency for a new run (default: 4)")
    args = parser.parse_args()
    no_links(RUN)
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT / "src"))
    stop, watcher = None, None
    if args.step != "_worker":
        require(platform.system() == "Linux", "server-only command")
        COMMAND_BEGIN = time.monotonic()
        require(args.workers is None or args.step == "run", "--workers is only accepted with run")
        resource.setrlimit(resource.RLIMIT_AS, (PROCESS_LIMIT, PROCESS_LIMIT))
        if args.step == "capacity":
            LIMIT_RSS = PROCESS_LIMIT
        else:
            configure_execution(RUN, args.workers)
        def deadline(signum, frame):
            # Disable the timer for bounded failure-receipt cleanup, not further work.
            signal.setitimer(signal.ITIMER_REAL, 0)
            raise TimeoutError("whole-command wall-clock limit")
        def stopped(signum, frame):
            signal.setitimer(signal.ITIMER_REAL, 0)
            raise KeyboardInterrupt(f"{signal.Signals(signum).name}: preserve interrupted E0 stage")
        def memory_limit(signum, frame):
            signal.setitimer(signal.ITIMER_REAL, 0)
            raise MemoryError(MONITOR["error"] or "whole-command memory guard")
        signal.signal(signal.SIGALRM, deadline)
        signal.signal(signal.SIGTERM, stopped)
        signal.signal(signal.SIGINT, stopped)
        signal.signal(signal.SIGUSR1, memory_limit)
        signal.setitimer(signal.ITIMER_REAL, LIMIT_S)
        stop = threading.Event()
        watcher = threading.Thread(target=watch_thread, args=(stop,), daemon=True)
        watcher.start()
    try:
        if args.step == "capacity":
            print(json.dumps(capacity_options(), ensure_ascii=False, sort_keys=True, indent=2), flush=True)
            print(f"{STAGE} CAPACITY CHECKED exit=0", flush=True)
        elif args.step == "run":
            run(RUN, SOURCE, workers=configure_execution(RUN, args.workers)["workers"])
        elif args.step == "verify":
            verify(RUN)
        elif args.step == "export":
            export(RUN, REPORT)
        else:
            require(args.workers is None and args.role is not None
                    and args.id in ["tests", "evaluate"] + [f"query-{i:02d}" for i in range(16)], "invalid worker")
            worker(args.role, args.id)
    finally:
        if stop is not None:
            signal.setitimer(signal.ITIMER_REAL, 0)
            stop.set()
            watcher.join(timeout=1)
            print(f"{STAGE} COMMAND {args.step} elapsed_s={time.monotonic() - COMMAND_BEGIN:.6f} "
                  f"parent_peak_rss_bytes={resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024} "
                  f"sampled_tree_peak_bytes={MONITOR['sampled_live_rss_peak_bytes']} "
                  f"conservative_tree_peak_bytes={MONITOR['conservative_live_hwm_peak_bytes']}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, MemoryError, KeyboardInterrupt, subprocess.SubprocessError) as exc:
        print(f"{STAGE} FAILED exit=1: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)
