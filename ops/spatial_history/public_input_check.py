"""SH-04-R3 public-file boundary: fixed server check, read, verify and export.

Standard library only. The trusted parent verifies R2 provenance; the actual
reader receives just one public path and its approved digest/size. No geometry
recovery, simulation, weight download, training or future-label loading.
"""
import argparse
import ast
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
import traceback
import unittest
from datetime import datetime, timezone

sys.dont_write_bytecode = True
from contract_check import ROOT, Tee, encode, git, require, sha, write_new


STAGE = "SH-04-R3-public-input-v1"
RUN = Path("/root/autodl-tmp/spatial-history/sh04-r3-public-input-v1")
SOURCE = Path("/root/autodl-tmp/spatial-history/sh04-r2-two-gate-engineering-v1-lfsha1")
R2_REPORT = "results/spatial_history_two_gate_engineering_v1_lfsha1.json"
R2_AUDIT_SHA = "acd203d21bef24cdca913fa9861bcc899c0e92cae88f8d07d36c37bfd2b0911e"
R2_COMMIT = "9c044fca7738e2b294024d073ffbbb96902ef130"
REPORT = ROOT / "results/spatial_history_public_input_v1.json"
TESTS = ("tests/spatial_world_model/test_public_reader.py",
         "tests/spatial_world_model/test_public_input_ops.py")
LIMIT_S = 1800
LIMIT_BYTES = 8 * 1024 * 1024
BOUND = (
    "src/spatial_world_model/__init__.py", "src/spatial_world_model/pair_contract.py",
    "src/spatial_world_model/two_gate_contract.py", "src/spatial_world_model/public_reader.py",
    *TESTS, "tests/spatial_world_model/test_two_gate_contract.py",
    "configs/spatial_history/two_gate_engineering_proposal_v1.json",
    "ops/spatial_history/contract_check.py", "ops/spatial_history/public_input_check.py",
    R2_REPORT, "docs/METHOD.md", "docs/DATA.md",
)


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def no_links(path):
    require(not any(p.is_symlink() for p in (path, *path.parents)), "symlink path rejected")


def binding():
    return {name: file_sha(ROOT / name) for name in BOUND}


def original_binding(commit, values):
    require(len(commit) == 40 and all(c in "0123456789abcdef" for c in commit), "invalid commit")
    for name, digest in values.items():
        require(not Path(name).is_absolute() and ".." not in Path(name).parts, "invalid source path")
        raw = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{commit}:{name}"])
        require(sha(raw) == digest, f"source differs from original Git blob: {name}")


def source_inputs(source):
    """Read provenance and public-file references, never raw private physics."""
    no_links(source)
    report = read(ROOT / R2_REPORT)
    audit = report["audit"]
    require(sha(encode(audit)) == report["audit_sha256"] == R2_AUDIT_SHA, "R2 audit changed")
    require(audit["status"] == "passed" and audit["started"]["commit"] == R2_COMMIT,
            "accepted R2 run required")
    original_binding(R2_COMMIT, audit["started"]["binding"])
    for name, expected in (("started.json", audit["started"]), ("completion.json", audit["completion"])):
        path = source / name
        no_links(path)
        require(read(path) == expected, f"R2 {name} differs from approved report")
    inputs = {}
    records = {s["step_id"]: s for s in audit["steps"]}
    for world in ("LL", "LR", "RL", "RR"):
        record = records[f"history-{world}"]
        unit = source / "steps" / f"history-{world}"
        no_links(unit / "receipt.json")
        require(read(unit / "receipt.json") == record["receipt"], "R2 history receipt changed")
        relative = f"steps/history-{world}/data/public.json"
        entry = record["artifacts"]["data/public.json"]
        path = source / relative
        no_links(path)
        require(path.stat().st_size == entry["bytes"] and file_sha(path) == entry["sha256"],
                f"R2 public artifact changed: {world}")
        inputs[world] = {"relative_path": relative, **entry}
    return inputs


def test_names(commit=None):
    names = []
    for filename in TESTS:
        raw = ((ROOT / filename).read_bytes() if commit is None else subprocess.check_output(
            ["git", "-C", str(ROOT), "show", f"{commit}:{filename}"]))
        tree = ast.parse(raw)
        names.extend(f"{Path(filename).stem}.{cls.name}.{fn.name}" for cls in tree.body
                     if isinstance(cls, ast.ClassDef) for fn in cls.body
                     if isinstance(fn, ast.FunctionDef) and fn.name.startswith("test_"))
    require(names and len(names) == len(set(names)), "invalid test inventory")
    return sorted(names)


def manifest(directory):
    result = {}
    for path in sorted(directory.rglob("*")):
        require(not path.is_symlink(), "output symlink rejected")
        if path.is_file() and path != directory / "receipt.json":
            result[path.relative_to(directory).as_posix()] = {"bytes": path.stat().st_size, "sha256": file_sha(path)}
    return result


def audit_queries(source, inputs):
    from spatial_world_model.public_reader import load_query
    rows = []
    for world, entry in inputs.items():
        for action in ("LL", "LR", "RL", "RR"):
            for mode, indices in (("full", None), ("recent", [119, 120])):
                try:
                    query = load_query(source / entry["relative_path"], expected_sha256=entry["sha256"],
                                       expected_bytes=entry["bytes"], action_name=action, history_indices=indices)
                except (ValueError, OSError, KeyError, TypeError) as exc:
                    raise ValueError(f"public query {world}/{action}/{mode}: {exc}") from exc
                require(set(query) == {"history", "controls", "goal"}, "query allowlist changed")
                frames = query["history"]
                require(len(frames) == (121 if mode == "full" else 2) and len(query["controls"]) == 200,
                        "registered public shape changed")
                require(all(f["height"] == f["width"] == 64 for f in frames), "registered resolution changed")
                rows.append({"world": world, "action": action, "mode": mode,
                             "query_sha256": sha(encode(query)), "history_sha256": sha(encode(frames)),
                             "controls_sha256": sha(encode(query["controls"])),
                             "goal_sha256": sha(encode(query["goal"])), "history_frames": len(frames),
                             "control_steps": len(query["controls"]), "query_keys": sorted(query),
                             "first_time_s": frames[0]["time_s"], "last_time_s": frames[-1]["time_s"]})
                print(f"{STAGE} READ {world}/{action}/{mode} frames={len(frames)} controls=200", flush=True)
    checks = query_checks(rows)
    return {"checks": checks, "accepted": all(checks.values()), "queries": rows,
            "row_identifiers_are_audit_only": True, "geometry_recovery_run": False,
            "model_experiment_run": False, "new_training_steps": 0}


def query_checks(rows):
    expected = {(w, act, mode) for w in ("LL", "LR", "RL", "RR")
                for act in ("LL", "LR", "RL", "RR") for mode in ("full", "recent")}
    return {
        "complete_32_query_inventory": len(rows) == 32 and {(r["world"], r["action"], r["mode"]) for r in rows} == expected,
        "registered_shapes_and_keys": all(r["history_frames"] == (121 if r["mode"] == "full" else 2)
                                          and r["control_steps"] == 200
                                          and r["query_keys"] == ["controls", "goal", "history"] for r in rows),
        "same_goal": len({r["goal_sha256"] for r in rows}) == 1,
        "same_recent_history": len({r["history_sha256"] for r in rows if r["mode"] == "recent"}) == 1,
        "four_distinct_full_histories": len({r["history_sha256"] for r in rows if r["mode"] == "full"}) == 4,
        "common_controls_per_action": all(len({r["controls_sha256"] for r in rows if r["action"] == act}) == 1
                                          for act in ("LL", "LR", "RL", "RR")),
        "same_recent_query_per_action": all(len({r["query_sha256"] for r in rows
                                                 if r["action"] == act and r["mode"] == "recent"}) == 1
                                            for act in ("LL", "LR", "RL", "RR")),
    }


def worker(directory, source):
    started = read(directory / "started.json")
    require(started["binding"] == binding() and started["commit"] == git("rev-parse", "HEAD"),
            "source changed before worker")
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "tests/spatial_world_model"))
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(Path(p).stem))
                               for p in TESTS)

    def flatten(item):
        return [name for child in item for name in flatten(child)] if isinstance(item, unittest.TestSuite) else [item.id()]

    names = sorted(flatten(suite))
    require(names == started["test_names"] == test_names(), "test inventory changed")
    with (directory / "tests.log").open("x", encoding="utf-8") as log:
        result = unittest.TextTestRunner(stream=Tee(log), verbosity=2).run(suite)
    test_result = {"test_names": names, "tests_run": result.testsRun, "failures": len(result.failures),
                   "errors": len(result.errors), "skipped": len(result.skipped),
                   "expected_failures": len(result.expectedFailures),
                   "unexpected_successes": len(result.unexpectedSuccesses)}
    write_new(directory / "tests.json", test_result)
    require(result.wasSuccessful() and result.testsRun == len(names) and not result.skipped
            and not result.expectedFailures, "new reader checks failed; preserved")
    audit = audit_queries(source, started["public_inputs"])
    audit["peak_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    write_new(directory / "public_audit.json", audit)
    require(audit["accepted"], "public input engineering audit failed")


def verify(directory, *, require_success=True):
    no_links(directory)
    started = read(directory / "started.json")
    saved = read(directory / "receipt.json")
    require(started["stage"] == saved["stage"] == STAGE, "wrong stage")
    require(saved["commit"] == started["commit"] and saved["binding"] == started["binding"], "receipt source mismatch")
    require(set(saved["binding"]) == set(BOUND), "source binding inventory changed")
    original_binding(saved["commit"], saved["binding"])
    require(saved["artifacts"] == manifest(directory), "saved artifacts changed")
    require(saved["artifact_bytes"] == sum(m["bytes"] for m in saved["artifacts"].values()), "artifact size mismatch")
    require(started["r2_audit_sha256"] == R2_AUDIT_SHA, "wrong R2 evidence")
    require(started["test_names"] == test_names(saved["commit"]), "original test inventory differs")
    if saved["exit_code"] == 0:
        tests = read(directory / "tests.json")
        audit = read(directory / "public_audit.json")
        require(set(saved["artifacts"]) == {"started.json", "tests.log", "tests.json", "public_audit.json"},
                "incomplete successful artifact set")
        require(tests["test_names"] == started["test_names"] and tests["tests_run"] == len(started["test_names"])
                and all(tests[k] == 0 for k in ("errors", "failures", "skipped", "expected_failures", "unexpected_successes")),
                "incomplete test evidence")
        require(audit["checks"] == query_checks(audit["queries"]) and audit["accepted"] is True
                and all(v is True for v in audit["checks"].values()), "incomplete public audit")
        require(audit["geometry_recovery_run"] is False and audit["model_experiment_run"] is False
                and audit["new_training_steps"] == 0 and audit["row_identifiers_are_audit_only"] is True,
                "engineering-only boundary changed")
        require(saved["elapsed_s"] <= LIMIT_S and saved["artifact_bytes"] <= LIMIT_BYTES
                and saved["child_exit_code"] == 0 and saved["error"] is None
                and saved["source_unchanged"] and saved["input_unchanged"], "budget/source guard failed")
    if require_success:
        require(saved["exit_code"] == 0, "failed run preserved; export diagnosis")
        print(f"{STAGE} VERIFIED tests={len(started['test_names'])} queries=32 exit=0", flush=True)
    return saved


def run(directory, source):
    if directory.exists():
        verify(directory)
        return
    require(platform.system() == "Linux" and (3, 11) <= sys.version_info[:2] < (3, 13), "Linux Python 3.11/3.12 required")
    require(not git("status", "--porcelain", "--", *BOUND), "bound files must be committed and clean")
    inputs = source_inputs(source)
    before, commit = binding(), git("rev-parse", "HEAD")
    original_binding(commit, before)
    directory.mkdir(parents=True, exist_ok=False)
    started = {"stage": STAGE, "commit": commit, "binding": before, "started": now(),
               "public_inputs": inputs, "source_directory": str(source), "r2_audit_sha256": R2_AUDIT_SHA,
               "test_names": test_names(), "limits": {"elapsed_s": LIMIT_S, "artifact_bytes": LIMIT_BYTES},
               "python": sys.version, "repository": str(ROOT), "model_training_steps": 0,
               "new_weight_download_bytes": 0, "new_simulation_steps": 0}
    write_new(directory / "started.json", started)
    begin = time.monotonic()
    error, code, same_input = None, 1, False
    try:
        child_env = {**os.environ, "SH04_R3_CHILD_DIR": str(directory)}
        child = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "_worker",
                                "--run-dir", str(directory), "--source-dir", str(source)],
                               timeout=LIMIT_S, env=child_env)
        code = child.returncode
        same_input = source_inputs(source) == inputs
    except (subprocess.SubprocessError, OSError, ValueError, KeyError) as exc:
        error = f"{type(exc).__name__}: {exc}"
    artifacts = manifest(directory)
    elapsed = time.monotonic() - begin
    same_source = binding() == before and git("rev-parse", "HEAD") == commit
    used = sum(m["bytes"] for m in artifacts.values())
    success = code == 0 and error is None and same_source and same_input and elapsed <= LIMIT_S and used + 65536 <= LIMIT_BYTES
    saved = {"stage": STAGE, "commit": commit, "binding": before, "finished": now(),
             "elapsed_s": elapsed, "child_exit_code": code, "error": error,
             "source_unchanged": same_source, "input_unchanged": same_input,
             "artifacts": artifacts, "artifact_bytes": used, "exit_code": 0 if success else 1}
    write_new(directory / "receipt.json", saved)
    require(success, f"{STAGE} failed; outputs preserved, export diagnosis")
    verify(directory)


def export(directory, report):
    saved = verify(directory, require_success=False)
    value = {"kind": "public_input_engineering_only", "receipt": saved,
             "receipt_sha256": file_sha(directory / "receipt.json"), "started": read(directory / "started.json"),
             "status": "passed" if saved["exit_code"] == 0 else "failed"}
    for name in ("tests", "public_audit", "worker_error"):
        path = directory / f"{name}.json"
        if path.exists():
            value[name] = read(path)
    if saved["exit_code"] != 0 and (directory / "tests.log").exists():
        value["test_log_tail"] = (directory / "tests.log").read_text(encoding="utf-8")[-16000:]
    if report.exists():
        require(report.read_bytes() == encode(value), "different report already exists; preserved")
    else:
        write_new(report, value)
    print(f"{STAGE} EXPORTED status={value['status']} {report} exit=0", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("run", "verify", "export", "_worker"))
    parser.add_argument("--run-dir", type=Path, default=RUN)
    parser.add_argument("--source-dir", type=Path, default=SOURCE)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    # Fixed stage paths prevent accidentally writing into an old run or a model dataset.
    require(args.run_dir == RUN and args.source_dir == SOURCE and args.report == REPORT, "unregistered path")
    no_links(args.run_dir)
    os.chdir(ROOT)
    if args.step == "run":
        run(args.run_dir, args.source_dir)
    elif args.step == "verify":
        verify(args.run_dir)
    elif args.step == "export":
        export(args.run_dir, args.report)
    else:
        require(platform.system() == "Linux" and os.environ.get("SH04_R3_CHILD_DIR") == str(args.run_dir)
                and (args.run_dir / "started.json").is_file()
                and not (args.run_dir / "receipt.json").exists()
                and not (args.run_dir / "tests.log").exists(), "fresh parent launch required")
        try:
            worker(args.run_dir, args.source_dir)
        except Exception:
            write_new(args.run_dir / "worker_error.json", {"traceback": traceback.format_exc(), "time": now()})
            raise


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f"{STAGE} FAILED exit=1: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)
