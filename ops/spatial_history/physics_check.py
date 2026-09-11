"""SH-02 setup/run/verify/export. Parent process is standard-library only.

The isolated Linux child runs the real simulation/tests. Failures and signals
retain partial artifacts and exit evidence; export also supports failed runs.
"""
import argparse
import ast
import base64
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback
import unittest

from contract_check import ROOT, encode, git, require, sha, write_new


DISK = Path("/root/autodl-tmp")
ENV = DISK / "spatial-history-venv-v1"
RUN = DISK / "spatial-history/sh02-engineering-v2-flat-pusher"
REPORT = ROOT / "results/spatial_history_physics_v2_flat_pusher.json"
REQUIREMENTS = "ops/spatial_history/requirements-physics.txt"
TESTS = ("tests/spatial_world_model/test_pair_contract.py", "tests/spatial_world_model/test_physics_fixture.py")
BOUND = ("src/spatial_world_model/__init__.py", "src/spatial_world_model/pair_contract.py",
         "src/spatial_world_model/physics_fixture.py", *TESTS, "data/fixtures/spatial_history/manual_pair.json",
         "configs/spatial_history/physics_v1.json", "configs/spatial_history/physics_v1.xml",
         "ops/spatial_history/contract_check.py", "ops/spatial_history/physics_check.py",
         "ops/spatial_history/contact_diagnose.py", REQUIREMENTS,
         "docs/METHOD.md", "docs/DATA.md", "results/spatial_history_contract_v1.json")


def now():
    return datetime.now(timezone.utc).isoformat()


def binding():
    return {p: sha((ROOT / p).read_bytes()) for p in BOUND}


def test_names():
    names = []
    for filename in TESTS:
        tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
        for cls in (n for n in tree.body if isinstance(n, ast.ClassDef)):
            names.extend(f"{Path(filename).stem}.{cls.name}.{n.name}" for n in cls.body
                         if isinstance(n, ast.FunctionDef) and n.name.startswith("test_"))
    require(names and len(names) == len(set(names)), "empty/duplicate test inventory")
    return sorted(names)


def stream(command, log_path, env=None):
    with log_path.open("x", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in process.stdout:
            print(line, end="", flush=True)
            log.write(line)
            log.flush()
        return process.wait()


def freeze(python):
    return subprocess.check_output([str(python), "-m", "pip", "freeze", "--all"], text=True).splitlines()


def environment():
    saved = json.loads((ENV / "sh02-environment.json").read_text())
    require(saved["exit_code"] == 0 and saved["requirements_sha256"] == sha((ROOT / REQUIREMENTS).read_bytes()),
            "environment setup absent/failed or requirements changed")
    require(saved["freeze"] == freeze(ENV / "bin/python"), "isolated environment packages changed")
    return saved


def setup():
    require(not git("status", "--porcelain", "--", REQUIREMENTS), "requirements must be committed and clean")
    if ENV.exists():
        environment()
        print(f"SH-02 ENV VERIFIED {ENV} exit=0", flush=True)
        return
    require(platform.system() == "Linux" and (3, 11) <= sys.version_info[:2] < (3, 13), "Linux Python 3.11/3.12 server required")
    require(DISK.is_mount(), "verified data disk mount missing; do not create on system disk")
    ENV.mkdir(exist_ok=False)
    write_new(ENV / "sh02-started.json", {"started": now(), "requirements_sha256": sha((ROOT / REQUIREMENTS).read_bytes())})
    code = stream([sys.executable, "-m", "venv", str(ENV)], ENV / "sh02-venv.log")
    if code == 0:
        code = stream([str(ENV / "bin/python"), "-m", "pip", "install", "--no-cache-dir", "-r", str(ROOT / REQUIREMENTS)], ENV / "sh02-install.log")
    saved = {"exit_code": code, "finished": now(), "requirements_sha256": sha((ROOT / REQUIREMENTS).read_bytes()),
             "freeze": freeze(ENV / "bin/python") if code == 0 else None}
    write_new(ENV / "sh02-environment.json", saved)
    require(code == 0, f"environment setup failed exit={code}; directory retained")
    print(f"SH-02 ENV READY {ENV} exit=0", flush=True)


def worker(directory):
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "tests/spatial_world_model"))
    suite = unittest.TestSuite()
    for filename in TESTS:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(Path(filename).stem)))
    def flatten(item):
        return [n for child in item for n in flatten(child)] if isinstance(item, unittest.TestSuite) else [item.id()]
    names = sorted(flatten(suite))
    require(names == test_names(), "runtime/static test inventory mismatch")
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    success = (result.wasSuccessful() and result.testsRun == len(names) and not result.skipped and not result.expectedFailures)
    write_new(directory / "tests-result.json", {"test_names": names, "tests_run": result.testsRun,
              "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
              "exit_code": 0 if success else 1})
    return 0 if success else 1


def artifacts(directory):
    return {str(p.relative_to(directory)).replace(os.sep, "/"): sha(p.read_bytes())
            for p in sorted(directory.rglob("*")) if p.is_file() and p.name != "receipt.json"}


def verify(directory, allow_failed=False):
    receipt = json.loads((directory / "receipt.json").read_text())
    require(receipt["stage"] == "SH-02" and receipt["binding"] == binding(), "SH-02 code/contract binding mismatch")
    require(receipt["artifacts"] == artifacts(directory), "artifact manifest changed")
    require(receipt["test_names"] == test_names(), "test inventory changed")
    success = receipt["exit_code"] == 0
    if success:
        result = json.loads((directory / "tests-result.json").read_text())
        require(result["exit_code"] == 0 and result["test_names"] == test_names()
                and result["tests_run"] == len(test_names()) and result["failures"] == result["errors"] == result["skipped"] == 0,
                "incomplete test result")
        for required in ("fixture/pair.json", "fixture/evidence.json", "tests.log", "environment.json"):
            require(required in receipt["artifacts"], f"missing required artifact {required}")
    require(success or allow_failed, f"SH-02 failed exit={receipt['exit_code']}; preserved at {directory}; export for diagnosis")
    print(f"SH-02 {'VERIFIED' if success else 'FAILURE-VERIFIED'} tests={len(test_names())} original_commit={receipt['commit']} exit={receipt['exit_code']}", flush=True)
    return receipt


def run(directory):
    if directory.exists():
        return verify(directory)
    require(platform.system() == "Linux" and DISK.is_mount(), "Linux server/data mount required")
    env_receipt = environment()
    require(Path(sys.prefix).resolve() == ENV.resolve(), f"run with {ENV}/bin/python")
    require(not git("status", "--porcelain", "--", *BOUND), "bound files must be committed and clean")
    sh01 = json.loads((ROOT / "results/spatial_history_contract_v1.json").read_text())
    require(sh01["receipt"]["exit_code"] == 0 and sh01["receipt"]["tests_run"] == 20
            and sh01["receipt_sha256"] == sha(encode(sh01["receipt"]))
            == "e33be9053ca01a75623953c7eb996cda7d162de3db503f1bf85aa2f724bc5d76", "SH-01 exported prerequisite invalid")
    for name, digest in sh01["receipt"]["binding"].items():
        if not name.startswith("docs/"):
            require(sha((ROOT / name).read_bytes()) == digest, f"approved SH-01 implementation changed: {name}")
    before = binding()
    commit = git("rev-parse", "HEAD")
    directory.mkdir(parents=True, exist_ok=False)
    started, timer = now(), time.monotonic()
    write_new(directory / "started.json", {"stage": "SH-02", "started": started, "commit": commit, "binding": before})
    write_new(directory / "environment.json", {"setup": env_receipt, "python": sys.version, "platform": platform.platform(),
              "executable": sys.executable, "MUJOCO_GL": "egl", "repository": str(ROOT)})
    child_env = dict(os.environ, MUJOCO_GL="egl", PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1",
                     OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", SH02_ARTIFACT_DIR=str(directory))
    code = 1
    try:
        code = stream([sys.executable, str(Path(__file__).resolve()), "_worker", "--run-dir", str(directory)], directory / "tests.log", child_env)
    except Exception:
        with (directory / "parent-error.txt").open("x") as handle:
            traceback.print_exc(file=handle)
    if before != binding() or commit != git("rev-parse", "HEAD"):
        code = 1
    receipt = {"stage": "SH-02", "commit": commit, "binding": before,
               "started": started, "finished": now(), "elapsed_s": time.monotonic()-timer,
               "exit_code": code, "test_names": test_names(), "artifacts": artifacts(directory),
               "engineering_fixture_count": 1, "model_experiment_run": False,
               "physics_and_visibility_verified": code == 0}
    write_new(directory / "receipt.json", receipt)
    print(f"SH-02 RUN FINISHED exit={code} directory={directory}", flush=True)
    return verify(directory)


def export(directory, report):
    receipt = verify(directory, allow_failed=True)
    value = {"kind": "engineering_physics_check", "receipt": receipt,
             "receipt_sha256": sha((directory / "receipt.json").read_bytes()), "diagnostics": {}, "previews_png_base64": {}}
    for name in ("fixture/evidence.json", "tests-result.json", "environment.json"):
        if (directory / name).exists():
            value["diagnostics"][name] = json.loads((directory / name).read_text())
    for path in sorted((directory / "fixture").glob("*.png")):
        value["previews_png_base64"][path.name] = base64.b64encode(path.read_bytes()).decode()
    # Include already-recorded contact/robot motion in the normal export.
    # This avoids another export-only code update if the fixture fails again.
    from contact_diagnose import summarize
    value["contact_process_by_branch"] = {}
    for path in sorted((directory / "fixture").glob("world-*-action-*-trace.json")):
        if "-replay-" in path.name:
            continue
        relative = str(path.relative_to(directory)).replace(os.sep, "/")
        require(relative in receipt["artifacts"], "unbound contact trace")
        summary = summarize(json.loads(path.read_text()))
        summary["object_pusher_episode_count"] = len(summary.pop("object_pusher_episodes"))
        value["contact_process_by_branch"][relative] = {
            "trace_sha256": receipt["artifacts"][relative], **summary}
    if receipt["exit_code"] != 0:
        value["failure_log_tail"] = (directory / "tests.log").read_text()[-16000:]
    if report.exists():
        require(report.read_bytes() == encode(value), "different existing report; not overwritten")
    else:
        write_new(report, value)
    print(f"SH-02 EXPORTED status={'passed' if receipt['exit_code'] == 0 else 'failed'} {report} exit=0", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("setup", "run", "verify", "export", "_worker"))
    parser.add_argument("--run-dir", type=Path, default=RUN)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    directory, report = args.run_dir.resolve(), args.report.resolve()
    require(directory.is_relative_to((DISK / "spatial-history").resolve()) and directory != (DISK / "spatial-history").resolve(), "run directory must be a named child of data disk spatial-history")
    require(report.parent == (ROOT / "results").resolve() and report.suffix == ".json", "report must be JSON directly in results")
    if args.step == "_worker":
        require(platform.system() == "Linux" and os.environ.get("SH02_ARTIFACT_DIR") == str(directory), "worker requires server stage launcher")
        return worker(directory)
    if args.step == "setup":
        setup()
    elif args.step == "export":
        export(directory, report)
    else:
        {"run": run, "verify": verify}[args.step](directory)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"SH-02 FAILED exit=1: {error}", file=sys.stderr, flush=True)
        sys.exit(1)
