"""D-121: seal E0-v2 development data while preserving the E0-v1 no-go.

Fifty complete source families are verified in place and referenced by digest.
Only the two interrupted families are generated in this new immutable stage.
No confirmation family or training path is reachable from this entry point.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import importlib
import json
import os
from pathlib import Path
try:
    import resource
except ImportError:  # Windows can inspect and unit-test the protocol only.
    resource = None
import shutil
import signal
import subprocess
import sys
import time
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = Path(__file__).resolve()
sys.path.insert(0, str(ROOT / "src"))

from spatial_world_model.pair_contract import require
from spatial_world_model.r4_families_v2 import categorical_shortcut, family_config, validate_manifest
from spatial_world_model.r4_generation_v2 import run_family, save, verify_family
from spatial_world_model.r4_storage import file_record, inventory, read_json, write_json

CONFIG_PATH = "configs/spatial_history/r4_development_protocol_v3.json"
CONFIG_VERSION = "sh05-r4-development-protocol-v3"
STAGE = "SH-05-R4-development-protocol-v3"
RUN = Path("/root/autodl-tmp/spatial-history/sh05-r4-development-protocol-v3")
REPORT = ROOT / "results/spatial_history_r4_development_protocol_v3.json"
WORLDS = ("LL", "LR", "RL", "RR")
TESTS = (
    "tests.spatial_world_model.test_r4_development_protocol_v3",
    "tests.spatial_world_model.test_public_geometry_v2",
    "tests.spatial_world_model.test_r4_generation_v2",
)
BOUND = (
    CONFIG_PATH,
    "configs/spatial_history/r4_family_design_v2.json",
    "configs/spatial_history/learning_contract_r4_v2.json",
    "configs/spatial_history/public_geometry_boundary_v2.json",
    "configs/spatial_history/r4_e0_boundary_development_v2.json",
    "configs/spatial_history/two_gate_engineering_v1.json",
    "configs/spatial_history/r4_repair_proposal_v2.json",
    "configs/spatial_history/physics_v1.xml",
    "results/spatial_history_r4_e0_boundary_development_v2.json",
    "src/spatial_world_model/pair_contract.py",
    "src/spatial_world_model/public_geometry_v2.py",
    "src/spatial_world_model/public_geometry_audit.py",
    "src/spatial_world_model/r4_families.py",
    "src/spatial_world_model/r4_families_v2.py",
    "src/spatial_world_model/r4_generation_v2.py",
    "src/spatial_world_model/r4_storage.py",
    "src/spatial_world_model/r4_public_v2.py",
    "src/spatial_world_model/r4_query_v2.py",
    "src/spatial_world_model/r4_scoring_v2.py",
    "src/spatial_world_model/r4_physics_v2.py",
    "src/spatial_world_model/r4_trajectory_v2.py",
    "src/spatial_world_model/two_gate_contract.py",
    "src/spatial_world_model/two_gate_physics.py",
    "src/spatial_world_model/two_gate_engineering.py",
    "ops/spatial_history/r4_development_protocol_v3.py",
    "ops/spatial_history/requirements-physics.txt",
    "tests/spatial_world_model/test_r4_development_protocol_v3.py",
    "tests/spatial_world_model/test_public_geometry_v2.py",
    "tests/spatial_world_model/test_r4_generation_v2.py",
    "docs/DECISIONS.md",
    "docs/METHOD.md",
    "docs/DATA.md",
)


def read(path):
    path = Path(path)
    return read_json(path) if path.suffix == ".gz" else json.loads(path.read_text(encoding="utf-8"))


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = encode(value)
    with path.open("xb") as handle:
        handle.write(raw)
    return file_record(path)


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def binding():
    return {name: file_record(ROOT / name) for name in BOUND}


def configuration():
    config = read(ROOT / CONFIG_PATH)
    require(config["version"] == CONFIG_VERSION and config["decision"] == "D-121", "wrong protocol config")
    require(Path(config["run_directory"]) == RUN and ROOT / config["report"] == REPORT, "protocol paths changed")
    require(config["data_completion_authorized"] is True, "data completion scope not authorized")
    require(config["implementation_review_complete"] is False, "review is carried by the explicit commit argument")
    require(all(config[key] is False for key in
                ("dual_m_authorized", "training_authorized", "confirmation_authorized")),
            "downstream authority changed")
    for name in ("design", "learning_contract", "e0_v2", "e0_development_report"):
        require(file_record(ROOT / config[name])["sha256"] == config[name + "_sha256"], name + " digest changed")
    design = read(ROOT / config["design"])
    validate_manifest(design, read(ROOT / "configs/spatial_history/r4_repair_proposal_v2.json"))
    families = [row for row in design["rows"] if row["split"] in config["allowed_splits"]]
    require(len(families) == config["development_family_count"] == 52, "development family census")
    require(not any(row["split"] in config["forbidden_splits"] for row in families), "confirmation family included")
    e0_config = read(ROOT / config["e0_development_config"])
    reused = (e0_config["released_existing_family_ids"] + e0_config["verified_generation_family_ids"]
              + list(e0_config["e0_only_family_status"]))
    require(len(reused) == len(set(reused)) == config["reuse_family_count"] == 50, "reuse census")
    generated = config["generate_family_ids"]
    require(generated == e0_config["excluded_unsealed_family_ids"] == ["r4-23", "r4-58"], "completion identities changed")
    require({row["family_id"] for row in families} == set(reused) | set(generated), "development partition changed")
    trajectory = config["observation_trajectory"]
    require(trajectory["time_varying_axes"] == ["y"] and trajectory["family_constant_x"]
            and trajectory["new_x_motion"] is False, "camera motion scope changed")
    contingency = config["xy_upgrade_contingency"]
    require(contingency["trigger_systems"] == ["D", "F", "W"]
            and contingency["preserve_current_denominator_and_results"]
            and contingency["automatic_release"] is False, "XY contingency changed")
    return config, families, reused


def family_rows():
    return {row["family_id"]: row for row in configuration()[1]}


def source_root(family_id, reused):
    config, _, _ = configuration()
    if family_id in config["generate_family_ids"]:
        return RUN / "execution" / "generated" / family_id / "data"
    e0_config = read(ROOT / config["e0_development_config"])
    existing = set(e0_config["released_existing_family_ids"])
    require(family_id in reused, "family is neither reused nor generated")
    stage = config["source_stages"]["released_existing" if family_id in existing else "stopped_generation"]
    return Path(stage) / family_id / "data"


def _source_manifest(data, channel):
    path = data / f"{channel}_manifest.json"
    manifest = read(path)
    require(manifest == inventory(data / channel), channel + " source manifest changed")
    return path, manifest


def public_file(data, world):
    path, manifest = _source_manifest(data, "public")
    relative = world + ".json.gz"
    require(relative in manifest and file_record(data / "public" / relative) == manifest[relative], "public history changed")
    return data / "public" / relative, file_record(path)


def source_seal(data, family_id, result):
    return {
        "family_id": family_id,
        "data_root": str(data.resolve(strict=True)),
        "public_manifest": file_record(data / "public_manifest.json"),
        "labels_manifest": file_record(data / "labels_manifest.json"),
        "audit_manifest": file_record(data / "audit_manifest.json"),
        "family_result": file_record(data / "audit/family_result.json"),
        "source_accepted": result["accepted"],
        "source_failed_checks": result["failed_checks"],
    }


def source_non_e0_accepted(result, family_id, config):
    failed = set(result["failed_checks"])
    exception = config["source_v1_exception"]
    allowed = set(exception["allowed_failed_checks"]) if family_id == exception["family_id"] else set()
    return failed == allowed and all(value for name, value in result["checks"].items() if name != "public_geometry")


def e0_evidence_by_family(config):
    report = read(ROOT / config["e0_development_report"])
    require(report["status"] == "passed" and report["summary"]["accepted"], "D-120 evidence not accepted")
    grouped = {}
    for row in report["evaluation"]["rows"]:
        grouped.setdefault(row["family_id"], []).append(row)
    require(len(grouped) == config["reuse_family_count"], "D-120 family evidence census")
    for family_id, rows in grouped.items():
        require(len(rows) == 16 and all(row["v2_assessment"]["accepted"] for row in rows),
                "D-120 family E0-v2 evidence failed: " + family_id)
    return grouped


def environment():
    config, _, _ = configuration()
    env = Path(config["environment"])
    marker = read(env / "sh02-environment.json")
    requirements = file_record(ROOT / "ops/spatial_history/requirements-physics.txt")
    require(marker["exit_code"] == 0 and marker["requirements_sha256"] == requirements["sha256"], "environment marker changed")
    freeze = subprocess.check_output([sys.executable, "-m", "pip", "freeze", "--all"], text=True).splitlines()
    require(freeze == marker["freeze"] and Path(sys.prefix).resolve() == env.resolve(), "wrong physics environment")
    return {"prefix": sys.prefix, "requirements": requirements, "marker": file_record(env / "sh02-environment.json")}


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
    require(not RUN.exists(), "new protocol stage already exists")
    config, families, reused = configuration()
    require(not git("status", "--porcelain", "--", *BOUND), "commit bound files before check")
    before = binding()
    suite, names = loaded_tests()
    began = time.monotonic()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    require(result.wasSuccessful() and not result.skipped and result.testsRun == len(names), "checks failed")
    require(time.monotonic() - began <= config["limits"]["check_wall_s"], "check wall limit")
    require(binding() == before, "source changed during check")
    checked_environment = environment()
    RUN.mkdir(parents=True)
    write(RUN / "check_receipt.json", {
        "stage": STAGE, "exit_code": 0, "commit": git("rev-parse", "HEAD"), "binding": before,
        "tests": names, "tests_run": result.testsRun, "families": len(families), "reused": len(reused),
        "generated": config["generate_family_ids"], "environment": checked_environment,
        "elapsed_s": time.monotonic() - began, "simulation_steps": 0, "training_steps": 0,
    })
    print(f"{STAGE} CHECKED tests={result.testsRun} families=52 exit=0", flush=True)


def verify_check():
    receipt = read(RUN / "check_receipt.json")
    require(receipt["exit_code"] == 0 and receipt["binding"] == binding(), "check binding changed")
    require(receipt["environment"] == environment(), "check environment changed")
    return receipt


def _generate_worker(family_id):
    config, _, _ = configuration()
    checked = verify_check()
    release = read(RUN / "execution/release.json")
    require(release["reviewed_code"] == checked["commit"], "review binding changed")
    require(family_id in config["generate_family_ids"], "family outside completion release")
    require(resource is not None, "server resource limits unavailable")
    resource.setrlimit(resource.RLIMIT_AS, (config["limits"]["process_as_bytes"], config["limits"]["process_as_bytes"]))
    base = read(ROOT / config["base"])
    reference = (ROOT / base["physics_reference"]).read_bytes()
    require(hashlib.sha256(reference).hexdigest() == base["physics_reference_sha256"], "physics reference changed")
    unit = RUN / "execution/generated" / family_id
    result = run_family(unit / "data", family_config(base, family_rows()[family_id]), reference.decode(),
                        read(ROOT / config["e0_v2"]), lambda event: print(event, flush=True))
    require(result == verify_family(unit / "data") and result["accepted"], "completed family did not pass E0-v2 data gates")
    require(sum(path.stat().st_size for path in (unit / "data").rglob("*") if path.is_file())
            <= config["limits"]["new_family_bytes"], "new family byte limit")
    write(unit / "verified.json", source_seal(unit / "data", family_id, result))
    print(f"FAMILY COMPLETED id={family_id} accepted=True exit=0", flush=True)


def _run_generation(config, workers):
    pending = list(config["generate_family_ids"])
    active, exits = {}, []
    began = time.monotonic()
    try:
        while pending or active:
            while pending and len(active) < workers:
                family_id = pending.pop(0)
                unit = RUN / "execution/generated" / family_id
                unit.mkdir(parents=True)
                log = (unit / "run.log").open("x")
                child = subprocess.Popen([sys.executable, "-B", str(ENTRYPOINT), "_generate_worker", "--family", family_id],
                                         cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                                         env=dict(os.environ, MUJOCO_GL="egl", PYOPENGL_PLATFORM="egl",
                                                  OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", PYTHONUNBUFFERED="1"))
                log.close()
                active[family_id] = child
                write(unit / "launched.json", {"family_id": family_id, "pid": child.pid})
            time.sleep(1)
            for family_id, child in list(active.items()):
                if child.poll() is not None:
                    exits.append({"family_id": family_id, "exit_code": child.returncode})
                    del active[family_id]
                    require(child.returncode == 0, "family generation failed: " + family_id)
            require(time.monotonic() - began <= config["limits"]["run_wall_s"], "generation wall limit")
            require(shutil.disk_usage(RUN.parent).free >= config["limits"]["data_disk_reserve_bytes"], "data disk reserve crossed")
    except BaseException:
        for child in active.values():
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
        for child in active.values():
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=10)
        write(RUN / "execution/generation_failure.json", {"exits": exits, "not_started": pending,
              "active_at_failure": list(active), "elapsed_s": time.monotonic() - began})
        raise
    write(RUN / "execution/generation_receipt.json", {"exit_code": 0, "families": exits,
          "elapsed_s": time.monotonic() - began, "simulations": config["limits"]["new_family_simulations"]})


def _seal_public_e0(config, families, reused):
    from spatial_world_model.public_geometry_v2 import recover_openings
    e0 = read(ROOT / config["e0_v2"])
    files = {}
    for row in families:
        family_id = row["family_id"]
        data = source_root(family_id, reused)
        for world in WORLDS:
            source, _ = public_file(data, world)
            value = read(source)
            require(len(value["history"]) == 121 and len(value["actions"]) == 9, "public query census")
            prediction = recover_openings(value["history"], e0["public_sensor_spec"], e0["extractor"])
            relative = f"{family_id}/{world}.json.gz"
            destination = RUN / "public_e0" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            write_json(destination, prediction)
            files[relative] = file_record(destination)
    write(RUN / "public_e0_seal.json", {"version": CONFIG_VERSION, "files": files,
          "family_count": len(families), "prediction_count": len(files), "private_truth_used": False})


def _assess_and_index(config, families, reused):
    from spatial_world_model.public_geometry_audit import assess_geometry, targets_from_xml
    evidence = e0_evidence_by_family(config)
    seals, family_rows_out, matrices = {}, [], []
    for row in families:
        family_id = row["family_id"]
        data = source_root(family_id, reused)
        result = verify_family(data)
        matrices.append(result["success_matrix"])
        require(source_non_e0_accepted(result, family_id, config), "non-E0 source gate failed: " + family_id)
        if family_id in reused:
            require(family_id in evidence, "reused family absent from D-120")
        else:
            require(result["accepted"] and not result["failed_checks"], "new family failed internal E0-v2 gate")
        assessments = []
        for world in WORLDS:
            relative = f"{family_id}/{world}.json.gz"
            prediction_path = RUN / "public_e0" / relative
            seal = read(RUN / "public_e0_seal.json")
            require(seal["files"][relative] == file_record(prediction_path), "public E0 output changed")
            targets = targets_from_xml((data / "audit" / world / "world.xml").read_text(encoding="utf-8"))
            assessed = assess_geometry(read(prediction_path), targets, read(ROOT / config["e0_v2"])["evaluation_only"])
            require(assessed["accepted"], "full-history E0-v2 assessment failed: " + family_id + " " + world)
            assessments.append({"world": world, "assessment": assessed, "prediction": file_record(prediction_path)})
        seal = source_seal(data, family_id, result)
        seal.update({"split": row["split"], "protocol_accepted": True,
                     "protocol_e0_v2_full": assessments,
                     "D120_all_four_modes_accepted": family_id in reused})
        seals[family_id] = seal
        family_rows_out.append({"family_id": family_id, "split": row["split"],
                                "source_kind": "reused" if family_id in reused else "new_generation",
                                "source_v1_accepted": result["accepted"], "protocol_accepted": True})
    shortcut = categorical_shortcut(matrices)
    require(not shortcut["categorical_shortcut_unexcluded"], "categorical shortcut gate failed")
    value = {"version": CONFIG_VERSION, "decision": "D-121", "accepted": True,
             "family_count": len(families), "reused_family_count": len(reused),
             "generated_family_ids": config["generate_family_ids"], "families": family_rows_out,
             "seals": seals, "public_e0_seal": file_record(RUN / "public_e0_seal.json"),
             "categorical_shortcut": shortcut, "confirmation_read": False,
             "training_steps": 0, "weight_download_bytes": 0,
             "observation_trajectory": config["observation_trajectory"],
             "xy_upgrade_contingency": config["xy_upgrade_contingency"]}
    write(RUN / "dataset_index.json", value)


def run(reviewed_code, declared_gib, workers):
    config, families, reused = configuration()
    checked = verify_check()
    require(reviewed_code == checked["commit"], "reviewed code must equal checked commit")
    require(workers in config["limits"]["workers_allowed"], "worker count outside registered range")
    require(declared_gib is not None and declared_gib >= config["limits"]["minimum_declared_new_data_gib"], "declare at least 2 GiB")
    require(not (RUN / "execution").exists(), "execution already started; preserve it")
    require(binding() == checked["binding"], "reviewed binding changed")
    require(subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", reviewed_code,
                            git("rev-parse", "HEAD")]).returncode == 0, "checkout does not descend from reviewed code")
    require(shutil.disk_usage(RUN.parent).free >= config["limits"]["stage_bytes"] + config["limits"]["data_disk_reserve_bytes"],
            "insufficient disk plus reserve")
    (RUN / "execution").mkdir()
    write(RUN / "execution/release.json", {"reviewed_code": reviewed_code, "workers": workers,
          "declared_available_new_data_gib": declared_gib, "family_ids": config["generate_family_ids"],
          "training_authorized": False, "confirmation_authorized": False,
          "time_utc": datetime.now(timezone.utc).isoformat()})
    began = time.monotonic()
    try:
        _run_generation(config, workers)
        _seal_public_e0(config, families, reused)
        _assess_and_index(config, families, reused)
        require(sum(path.stat().st_size for path in RUN.rglob("*") if path.is_file()) <= config["limits"]["stage_bytes"],
                "protocol stage byte limit")
        write(RUN / "run_receipt.json", {"exit_code": 0, "commit": checked["commit"], "binding": checked["binding"],
              "dataset_index": file_record(RUN / "dataset_index.json"),
              "public_e0_seal": file_record(RUN / "public_e0_seal.json"),
              "generation_receipt": file_record(RUN / "execution/generation_receipt.json"),
              "elapsed_s": time.monotonic() - began, "accepted": True})
    except BaseException as error:
        write(RUN / "execution/failure.json", {"error": f"{type(error).__name__}: {error}",
              "elapsed_s": time.monotonic() - began})
        raise
    print(f"{STAGE} COMPLETED reused=50 generated=2 families=52 accepted=True exit=0", flush=True)


def verify():
    config, families, reused = configuration()
    receipt = read(RUN / "run_receipt.json")
    require(receipt["exit_code"] == 0 and receipt["accepted"] and receipt["binding"] == binding(), "run receipt changed")
    index = read(RUN / "dataset_index.json")
    require(index["accepted"] and index["family_count"] == len(families) and set(index["seals"]) == {row["family_id"] for row in families},
            "dataset index census")
    began = time.monotonic()
    for row in families:
        family_id = row["family_id"]
        data = source_root(family_id, reused)
        result = verify_family(data)
        expected = index["seals"][family_id]
        current = source_seal(data, family_id, result)
        require(all(expected.get(key) == value for key, value in current.items()), "source seal changed: " + family_id)
        require(expected["protocol_accepted"], "protocol family not accepted")
    require(time.monotonic() - began <= config["limits"]["verify_wall_s"], "verify wall limit")
    write(RUN / "verify_receipt.json", {"exit_code": 0, "dataset_index": file_record(RUN / "dataset_index.json"),
          "families": len(families), "reused": len(reused), "generated": len(config["generate_family_ids"]),
          "elapsed_s": time.monotonic() - began})
    print(f"{STAGE} VERIFIED reused=50 generated=2 families=52 exit=0", flush=True)


def export():
    config, _, _ = configuration()
    receipt = read(RUN / "run_receipt.json")
    verified = read(RUN / "verify_receipt.json")
    require(receipt["accepted"] and verified["exit_code"] == 0
            and verified["dataset_index"] == file_record(RUN / "dataset_index.json"), "protocol not verified")
    require(not REPORT.exists(), "report exists")
    index = read(RUN / "dataset_index.json")
    value = {"version": CONFIG_VERSION, "decision": "D-121", "status": "passed",
             "summary": {key: index[key] for key in
                         ("accepted", "family_count", "reused_family_count", "generated_family_ids",
                          "categorical_shortcut", "confirmation_read", "training_steps", "weight_download_bytes",
                          "observation_trajectory", "xy_upgrade_contingency")},
             "run_directory": str(RUN), "check_receipt": read(RUN / "check_receipt.json"),
             "run_receipt": receipt, "verify_receipt": verified,
             "dataset_index": file_record(RUN / "dataset_index.json")}
    raw = encode(value)
    require(len(raw) <= config["limits"]["report_bytes"], "report byte limit")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("xb") as handle:
        handle.write(raw)
    print(f"{STAGE} EXPORTED {REPORT} exit=0", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "run", "_generate_worker", "verify", "export"))
    parser.add_argument("--reviewed-code")
    parser.add_argument("--declared-available-new-data-gib", type=float)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--family")
    args = parser.parse_args()
    if args.command == "check":
        check()
    elif args.command == "run":
        require(args.reviewed_code is not None, "reviewed code required")
        run(args.reviewed_code, args.declared_available_new_data_gib, args.workers)
    elif args.command == "_generate_worker":
        require(args.family is not None, "family required")
        _generate_worker(args.family)
    elif args.command == "verify":
        verify()
    else:
        export()


if __name__ == "__main__":
    main()
