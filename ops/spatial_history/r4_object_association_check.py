"""R4-3b server-only artificial object_association checks; run/verify/export once.

No real history, simulator, model, training, download or geometry audit is run.
Existing stages are only verified; failures/interruption are never retried.
"""
import argparse
import ast
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import time
import unittest

sys.dont_write_bytecode = True
from contract_check import ROOT, Tee, encode, git, require, sha

STAGE = "SH-04-R4-3b-object-v1"
RUN = Path("/root/autodl-tmp/spatial-history/sh04-r4-3b-object-v1")
REPORT = ROOT / "results/spatial_history_r4_object_association_v1.json"
CONFIG = "configs/spatial_history/r4_object_association_check_v1.json"
PROPOSAL = "configs/spatial_history/r4_object_association_proposal_v1.json"
PROPOSAL_SHA = "81b50fc5f05de6b568da933f8d9097999f0250ab7f6efd7a2e9e32f350bb4953"
TESTS = ("tests/spatial_world_model/test_r4_object_association.py",
         "tests/spatial_world_model/test_r4_object_association_ops.py")
BOUND = ("src/spatial_world_model/__init__.py", "src/spatial_world_model/pair_contract.py",
         "src/spatial_world_model/r4_coverage.py", "src/spatial_world_model/r4_object_association.py", *TESTS,
         "ops/spatial_history/contract_check.py", "ops/spatial_history/r4_object_association_check.py",
         CONFIG, PROPOSAL, "docs/METHOD.md", "docs/DATA.md")
LIMIT_S, LIMIT_BYTES, LIMIT_RSS = 300, 8 * 1024**2, 512 * 1024**2
CLAIMS = {"real_history_object_association_verified": False, "public_geometry_recovery_verified": False,
          "full_3d_map_verified": False, "physical_predictability_verified": False,
          "model_experiment_run": False, "long_term_memory_claim_verified": False}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def configuration():
    value = read(ROOT / CONFIG)
    expected = {"version": "sh04-r4-object-association-check-v1", "decision": "D-088",
                "scope": "server_only_artificial_depth_object_association_checks",
                "generation_authorized": False, "training_authorized": False,
                "weight_download_authorized": False, "confirmation_authorized": False,
                "tests": list(TESTS), "limits": {"per_command_wall_s": LIMIT_S,
                "stage_plus_report_bytes": LIMIT_BYTES, "process_as_and_rss_bytes": LIMIT_RSS},
                "accepted_proposal_commit": "a9cc59b0458f476ae9c2009946cff42ff07ce176",
                "accepted_proposal_sha256": PROPOSAL_SHA, "claims": CLAIMS}
    require(encode(value) == encode(expected), "object association config changed")
    require(sha((ROOT / PROPOSAL).read_bytes()) == PROPOSAL_SHA, "accepted D-087 proposal changed")
    return value


def binding():
    return {name: sha((ROOT / name).read_bytes()) for name in BOUND}


def test_names():
    names = []
    for name in TESTS:
        tree = ast.parse((ROOT / name).read_bytes())
        names.extend(f"{Path(name).stem}.{cls.name}.{fn.name}" for cls in tree.body
                     if isinstance(cls, ast.ClassDef) for fn in cls.body
                     if isinstance(fn, ast.FunctionDef) and fn.name.startswith("test_"))
    require(names and len(names) == len(set(names)), "test inventory empty/duplicate")
    return sorted(names)


def inventory():
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "tests/spatial_world_model"))
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(
        importlib.import_module(Path(name).stem)) for name in TESTS)
    def flatten(item):
        return [n for child in item for n in flatten(child)] if isinstance(item, unittest.TestSuite) else [item.id()]
    require(sorted(flatten(suite)) == test_names(), "runtime/AST test inventory differs")
    return suite


def used_bytes(directory):
    return sum(p.stat().st_size for p in directory.rglob("*") if p.is_file())


def write_new(directory, path, value):
    raw = encode(value)
    require(used_bytes(directory) + len(raw) <= LIMIT_BYTES, "stage/report byte limit")
    with path.open("xb") as handle:
        handle.write(raw)


def source_matches_commit(commit, sources):
    require(type(commit) is str and len(commit) == 40
            and all(c in "0123456789abcdef" for c in commit), "full source commit required")
    require(sources == binding(), "current sources differ")
    require(all(sha(subprocess.check_output(["git", "-C", str(ROOT), "show", f"{commit}:{n}"])) == digest
                for n, digest in sources.items()), "source bytes differ from recorded Git commit")


def verify(directory):
    configuration()
    receipt = read(directory / "receipt.json")
    require(receipt["stage"] == STAGE and receipt["exit_code"] == 0, "no successful object_association receipt")
    source_matches_commit(receipt["commit"], receipt["binding"])
    names = test_names()
    require(receipt["test_names"] == names and receipt["tests_run"] == len(names), "test census mismatch")
    require(all(receipt[k] == 0 for k in ("failures", "errors", "skipped", "expected_failures", "unexpected_successes")),
            "incomplete checks")
    require(receipt["claims"] == CLAIMS and receipt["new_simulation_steps"] == receipt["new_training_steps"]
            == receipt["new_weight_download_bytes"] == receipt["real_history_queries"] == 0, "scope/claims changed")
    require(receipt["artifacts"] == {n: sha((directory / n).read_bytes()) for n in ("started.json", "tests.log")},
            "evidence digest changed")
    started = read(directory / "started.json")
    require(all(started[k] == receipt[k] for k in ("stage", "commit", "binding")), "started/receipt mismatch")
    require(set(p.name for p in directory.iterdir()) == {"started.json", "tests.log", "receipt.json"},
            "unexpected or failure artifact")
    require(0 <= receipt["elapsed_s"] <= LIMIT_S and 0 < receipt["peak_rss_bytes"] <= LIMIT_RSS,
            "time/memory receipt invalid")
    require(receipt["stage_bytes"] == used_bytes(directory) <= LIMIT_BYTES, "stage byte count changed")
    print(f"{STAGE} VERIFIED tests={len(names)} exit=0", flush=True)
    return receipt


def run(directory):
    if directory.exists():
        print("Existing stage: verify only; no rerun or overwrite.", flush=True)
        return verify(directory)
    configuration()
    require(not git("status", "--porcelain", "--", *BOUND), "bound sources must be committed and clean")
    before, commit = binding(), git("rev-parse", "HEAD")
    source_matches_commit(commit, before)
    began = time.monotonic()
    directory.mkdir(parents=True, exist_ok=False)
    try:
        write_new(directory, directory / "started.json", {"stage": STAGE, "commit": commit, "binding": before,
                  "started": datetime.now(timezone.utc).isoformat()})
        suite = inventory()
        with (directory / "tests.log").open("x", encoding="utf-8") as log:
            result = unittest.TextTestRunner(stream=Tee(log), verbosity=2).run(suite)
        names = test_names()
        counts = {"failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
                  "expected_failures": len(result.expectedFailures), "unexpected_successes": len(result.unexpectedSuccesses)}
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        elapsed = time.monotonic() - began
        passed = (not any(counts.values()) and result.testsRun == len(names) and before == binding()
                  and elapsed <= LIMIT_S and rss <= LIMIT_RSS)
        receipt = {"stage": STAGE, "commit": commit, "binding": before, "python": sys.version,
                   "platform": platform.platform(), "test_names": names, "tests_run": result.testsRun,
                   **counts, "artifacts": {n: sha((directory / n).read_bytes()) for n in ("started.json", "tests.log")},
                   "elapsed_s": elapsed, "peak_rss_bytes": rss, "stage_bytes": 0,
                   "new_simulation_steps": 0, "new_training_steps": 0, "new_weight_download_bytes": 0, "real_history_queries": 0,
                   "claims": CLAIMS, "exit_code": 0 if passed else 1}
        evidence_bytes = used_bytes(directory)
        for _ in range(10):
            total = evidence_bytes + len(encode(receipt))
            if receipt["stage_bytes"] == total:
                break
            receipt["stage_bytes"] = total
        require(receipt["stage_bytes"] == evidence_bytes + len(encode(receipt)), "receipt size did not settle")
        write_new(directory, directory / "receipt.json", receipt)
        require(passed, "object_association checks failed; preserve stage and export")
        return verify(directory)
    except BaseException as error:
        if not (directory / "receipt.json").exists():
            try:
                write_new(directory, directory / "failure.json", {"stage": STAGE, "exit_code": 1,
                          "error": f"{type(error).__name__}: {error}", "elapsed_s": time.monotonic() - began})
            except (OSError, ValueError, MemoryError):
                print("Could not write failure receipt; incomplete stage preserved.", file=sys.stderr, flush=True)
        raise


def export(directory, report_path):
    configuration()
    require(directory.is_dir(), "no object_association stage to export")
    error, receipt = None, None
    try:
        receipt = verify(directory)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as problem:
        error = f"{type(problem).__name__}: {problem}"
    artifacts = {}
    require(used_bytes(directory) <= LIMIT_BYTES, "stage too large for registered export")
    for name in ("started.json", "tests.log", "receipt.json", "failure.json"):
        path = directory / name
        if path.is_file():
            raw = path.read_bytes()
            artifacts[name] = {"bytes": len(raw), "sha256": sha(raw), "text": raw.decode("utf-8", errors="replace")}
    value = {"kind": "r4_object_association_artificial_engineering_check", "status": "passed" if error is None else "failed_or_incomplete",
             "verification_error": error, "receipt": receipt, "source_artifacts": artifacts,
             "receipt_sha256": artifacts.get("receipt.json", {}).get("sha256"), "claims": CLAIMS}
    raw = encode(value)
    require(used_bytes(directory) + len(raw) <= LIMIT_BYTES, "stage plus report byte limit")
    if report_path.exists():
        require(report_path.read_bytes() == raw, "different existing report; never overwrite")
    else:
        write_new(directory, report_path, value)
    print(f"{STAGE} EXPORTED status={value['status']} path={report_path} exit=0", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("run", "verify", "export"))
    args = parser.parse_args()
    require(platform.system() == "Linux" and (3, 11) <= sys.version_info[:2] < (3, 13), "Linux Python 3.11/3.12 server only")
    require(Path(sys.prefix) == Path("/root/autodl-tmp/spatial-history-venv-v1"), "use existing isolated server environment")
    def timed_out(signum, frame):
        raise KeyboardInterrupt("object_association command exceeded 300 s; preserve stage")
    signal.signal(signal.SIGALRM, timed_out)
    signal.alarm(LIMIT_S)
    resource.setrlimit(resource.RLIMIT_AS, (LIMIT_RSS, LIMIT_RSS))
    resource.setrlimit(resource.RLIMIT_FSIZE, (LIMIT_BYTES, LIMIT_BYTES))
    os.chdir(ROOT)
    {"run": run, "verify": verify, "export": lambda directory: export(directory, REPORT)}[args.step](RUN)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError, KeyboardInterrupt, MemoryError) as error:
        print(f"{STAGE} FAILED exit=1: {error}", file=sys.stderr, flush=True)
        sys.exit(1)
