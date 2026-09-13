"""Checked, resumable-by-family D-114 execution for M-SIMPLE and M-PHYS.

The public phase reads only registered public histories.  The evaluation phase
starts only after every public prediction is sealed and is the first code path
that opens labels.  Confirmation family IDs are rejected from both phases.
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
except ImportError:  # Local Windows contract tests never enter a server worker.
    resource = None
import shutil
import signal
import subprocess
import sys
import time
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
from spatial_world_model.pair_contract import require
from spatial_world_model.r4_families_v2 import ACTIONS
from spatial_world_model.r4_storage import file_record


CONFIG_PATH = "configs/spatial_history/r4_dual_m_stage_v1.json"
CONFIG = json.loads((ROOT / CONFIG_PATH).read_text(encoding="utf-8"))
RUN = Path(CONFIG["run_directory"])
ENVIRONMENT = Path(CONFIG["environment"])
REPORT = ROOT / CONFIG["report"]
STAGE = "SH-05-R4-dual-M-v1"
TESTS = (
    "tests.spatial_world_model.test_r4_continuous_geometry",
    "tests.spatial_world_model.test_r4_continuous_map",
    "tests.spatial_world_model.test_r4_continuous_shapes",
    "tests.spatial_world_model.test_r4_simple_dynamics",
    "tests.spatial_world_model.test_r4_reconstructed_mujoco",
    "tests.spatial_world_model.test_r4_dual_m_stage",
)
BOUND = (
    CONFIG_PATH,
    "configs/spatial_history/learning_contract_r4_v2.json",
    "configs/spatial_history/r4_family_design_v2.json",
    "ops/spatial_history/requirements-r4-map.txt",
    "ops/spatial_history/r4_dual_m_stage_v1.py",
    "src/spatial_world_model/r4_continuous_geometry.py",
    "src/spatial_world_model/r4_continuous_map.py",
    "src/spatial_world_model/r4_continuous_shapes.py",
    "src/spatial_world_model/r4_continuous_readout.py",
    "src/spatial_world_model/r4_simple_dynamics.py",
    "src/spatial_world_model/r4_reconstructed_mujoco.py",
    "src/spatial_world_model/r4_object_association.py",
    "src/spatial_world_model/r4_object_surfaces.py",
    "src/spatial_world_model/r4_observed_map_v2.py",
    "src/spatial_world_model/r4_query_v2.py",
    "src/spatial_world_model/r4_scoring_v2.py",
    "tests/spatial_world_model/test_r4_continuous_geometry.py",
    "tests/spatial_world_model/test_r4_continuous_map.py",
    "tests/spatial_world_model/test_r4_continuous_shapes.py",
    "tests/spatial_world_model/test_r4_simple_dynamics.py",
    "tests/spatial_world_model/test_r4_reconstructed_mujoco.py",
    "tests/spatial_world_model/test_r4_dual_m_stage.py",
    "docs/DECISIONS.md",
    "docs/METHOD.md",
    "docs/DATA.md",
)


def read(path):
    path = Path(path)
    with (gzip.open(path, "rt") if path.suffix == ".gz" else path.open(encoding="utf-8")) as handle:
        return json.load(handle)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode()


def write(path, value):
    path = Path(path)
    raw = encode(value)
    if path.suffix == ".gz":
        raw = gzip.compress(raw, mtime=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
    return file_record(path)


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def binding():
    return {name: file_record(ROOT / name) for name in BOUND}


def used(path=RUN):
    path = Path(path)
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file()) \
        if path.exists() else 0


def configuration():
    config = read(ROOT / CONFIG_PATH)
    require(config["version"] == "sh05-r4-dual-m-stage-v1", "wrong stage config")
    require(Path(config["run_directory"]) == RUN and Path(config["environment"]) == ENVIRONMENT,
            "stage path changed")
    require(ROOT / config["report"] == REPORT, "report path changed")
    require(all(config[key] is False for key in
                ("implementation_review_complete", "effect_run_authorized",
                 "training_authorized", "confirmation_authorized")),
            "review candidate cannot silently authorize execution")
    for name in ("design", "learning_contract"):
        require(file_record(ROOT / config[name])["sha256"] == config[name + "_sha256"],
                name + " digest changed")
    design = read(ROOT / config["design"])
    families = [row for row in design["rows"] if row["split"] in config["allowed_splits"]]
    require(len(families) == config["counts"]["families"], "development family census")
    require(not any(row["split"] in config["forbidden_splits"] for row in families),
            "confirmation family included")
    require(len(ACTIONS) == config["counts"]["candidates_per_world"], "candidate census")
    return config, families


def create_environment():
    config, _ = configuration()
    marker = ENVIRONMENT / "environment.json"
    requirement = file_record(ROOT / "ops/spatial_history/requirements-r4-map.txt")
    if marker.exists():
        value = read(marker)
        require(value["exit_code"] == 0 and value["requirements"] == requirement,
                "environment marker changed")
        freeze = subprocess.check_output(
            [str(ENVIRONMENT / "bin/python"), "-m", "pip", "freeze", "--all"], text=True).splitlines()
        require(freeze == value["freeze"], "environment freeze changed")
        print(f"{STAGE} ENVIRONMENT REUSED exit=0", flush=True)
        return
    require(not ENVIRONMENT.exists(), "unmarked environment exists")
    subprocess.check_call([sys.executable, "-m", "venv", str(ENVIRONMENT)])
    python = ENVIRONMENT / "bin/python"
    subprocess.check_call([str(python), "-m", "pip", "install", "-r",
                           str(ROOT / "ops/spatial_history/requirements-r4-map.txt")])
    freeze = subprocess.check_output([str(python), "-m", "pip", "freeze", "--all"],
                                     text=True).splitlines()
    write(marker, {"exit_code": 0, "requirements": requirement, "freeze": freeze,
                   "created_utc": datetime.now(timezone.utc).isoformat()})
    print(f"{STAGE} ENVIRONMENT CREATED exit=0", flush=True)


def require_environment():
    require(Path(sys.prefix).resolve() == ENVIRONMENT.resolve(),
            "run this step with the registered dual-M environment Python")
    import mujoco
    import numpy
    import shapely
    require((mujoco.__version__, numpy.__version__, shapely.__version__)
            == ("3.3.7", "2.2.6", "2.1.2"), "dependency version mismatch")
    marker = read(ENVIRONMENT / "environment.json")
    freeze = subprocess.check_output([sys.executable, "-m", "pip", "freeze", "--all"],
                                     text=True).splitlines()
    require(freeze == marker["freeze"], "environment freeze changed")
    return {"prefix": sys.prefix, "marker": file_record(ENVIRONMENT / "environment.json")}


def loaded_tests():
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(name))
                               for name in TESTS)
    return suite


def check():
    config, families = configuration()
    require_environment()
    require(not RUN.exists(), "dual-M stage already started")
    require(not git("status", "--porcelain", "--", *BOUND), "bound sources must be committed")
    began = time.monotonic()
    suite = loaded_tests()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    require(result.wasSuccessful() and not result.skipped and not result.expectedFailures,
            "dual-M checks failed")
    require(time.monotonic() - began <= config["limits"]["check_wall_s"], "check wall limit")
    RUN.mkdir(parents=True)
    write(RUN / "check_receipt.json", {
        "stage": STAGE, "exit_code": 0, "commit": git("rev-parse", "HEAD"),
        "binding": binding(), "environment": require_environment(),
        "tests_run": result.testsRun, "family_count": len(families),
        "elapsed_s": time.monotonic() - began,
    })
    print(f"{STAGE} CHECKED tests={result.testsRun} exit=0", flush=True)


def verify_check():
    receipt = read(RUN / "check_receipt.json")
    require(receipt["exit_code"] == 0 and receipt["binding"] == binding(),
            "check binding changed")
    require(receipt["environment"] == require_environment(), "check environment changed")
    return receipt


def source_root(family_id, existing_ids):
    base = Path(CONFIG["existing_stage"] if family_id in existing_ids else CONFIG["generated_stage"])
    path = base / "execution" / family_id / "data"
    require(path.is_dir(), "source family missing: " + family_id)
    verified = path.parent / "verified.json"
    require(verified.is_file() and read(verified)["accepted"], "source family not verified: " + family_id)
    return path


def source_file(data, channel, name):
    manifest_path = data / (channel + "_manifest.json")
    manifest = read(manifest_path)
    require(name in manifest, "unregistered source file: " + name)
    path = data / channel / name
    require(path.resolve().is_relative_to((data / channel).resolve()), "source path escape")
    require(file_record(path) == manifest[name], "source file changed: " + name)
    return path


def _public_family(family_id, split, existing_ids):
    from spatial_world_model import r4_continuous_map as maps
    from spatial_world_model import r4_continuous_readout as task_readout
    from spatial_world_model import r4_object_association as objects
    from spatial_world_model import r4_observed_map_v2 as nominal_maps
    from spatial_world_model import r4_reconstructed_mujoco as physical
    from spatial_world_model import r4_simple_dynamics as simple
    from spatial_world_model.r4_query_v2 import domain_spec
    data = source_root(family_id, existing_ids)
    destination = RUN / "public" / family_id
    destination.mkdir(parents=True)
    files = {}
    systems_complete = {"M-SIMPLE": 0, "M-PHYS": 0}
    certificates = {"M-SIMPLE": 0, "M-PHYS": 0}
    for world in ("LL", "LR", "RL", "RR"):
        value = read(source_file(data, "public", world + ".json.gz"))
        require(len(value["history"]) == 121 and len(value["actions"]) == 9,
                "public query census")
        frames = [{key: frame[key] for key in objects.FIELDS.split()}
                  for frame in value["history"]]
        for index, frame in enumerate(frames):
            frame["time_s"] = (index - 120) / 10
        mapped = maps.build_map(
            {"schema_version": nominal_maps.HISTORY_VERSION, "frames": frames},
            objects.sensor_spec(), objects.common_shape_spec(), domain_spec(),
            nominal_maps.parameters(), maps.parameters(), history_mode="full")
        require(mapped["current_object"] is not None and
                mapped["current_object"]["status"] == "association_ready", "map association")
        files[f"{world}/map.json.gz"] = write(destination / world / "map.json.gz", mapped)
        for action, rows in zip(ACTIONS, value["actions"]):
            controls = {name: [row[name] for row in rows]
                        for name in ("ee_velocity_mps", "duration_s")}
            simple_value = simple.predict(mapped, controls, value["goal"], domain_spec(),
                                          simple.parameters(), task_readout.parameters())
            physical_value = physical.predict(mapped, controls, value["goal"], domain_spec(),
                                               physical.parameters(), task_readout.parameters())
            for result in (simple_value, physical_value):
                require(result["status"] == "complete" and result["prediction"] is not None,
                        f"{result['system']} incomplete")
                require(len(result["trajectory"]) == 10001 and
                        len(result["prediction"]["object_position_m"]) == 200,
                        f"{result['system']} output census")
                systems_complete[result["system"]] += 1
                certificates[result["system"]] += int(
                    result["certificate"]["complete_sweep_contained"])
            relative = f"{world}/{action}.json.gz"
            files[relative] = write(destination / relative, {
                "family_id": family_id, "split": split, "world": world,
                "action": action, "M-SIMPLE": simple_value, "M-PHYS": physical_value,
                "private_truth_read": False,
            })
            print(STAGE, family_id, world, action, "PUBLIC COMPLETE", flush=True)
    write(destination / "manifest.json", {"family_id": family_id, "split": split,
          "files": files, "systems_complete": systems_complete,
          "certificates_complete": certificates, "private_truth_read": False})


def _worker(family_id):
    config, families = configuration()
    checked = verify_check()
    release = read(RUN / "release.json")
    require(release["reviewed_code"] == checked["commit"], "review binding changed")
    by_id = {row["family_id"]: row for row in families}
    require(family_id in by_id, "worker family outside development release")
    require(resource is not None, "server resource limits unavailable")
    resource.setrlimit(resource.RLIMIT_AS,
                       (config["limits"]["process_as_bytes"], config["limits"]["process_as_bytes"]))
    existing_ids = set(read(ROOT / "configs/spatial_history/r4_development_generation_v2.json")
                       ["existing_family_ids"])
    _public_family(family_id, by_id[family_id]["split"], existing_ids)
    require(used(RUN / "public" / family_id) <= config["limits"]["family_bytes"],
            "family output byte limit")


def _tree_rss():
    total = 0
    selected = {os.getpid()}
    values = {}
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        try:
            fields = dict(line.split(":", 1) for line in
                          (path / "status").read_text().splitlines() if ":" in line)
            values[int(path.name)] = (int(fields["PPid"]),
                                      int(fields.get("VmHWM", "0 kB").split()[0]) * 1024)
        except (OSError, ValueError, KeyError):
            pass
    while True:
        extended = selected | {pid for pid, (parent, _) in values.items() if parent in selected}
        if extended == selected:
            break
        selected = extended
    for pid in selected:
        total += values.get(pid, (0, 0))[1]
    return total


def run(reviewed_code, workers):
    config, families = configuration()
    checked = verify_check()
    require(reviewed_code == checked["commit"], "reviewed code must equal checked commit")
    require(workers in config["limits"]["workers_allowed"], "worker count not registered")
    require(not (RUN / "release.json").exists(), "public execution already released")
    require(shutil.disk_usage(RUN.parent).free >=
            config["limits"]["stage_bytes"] + config["limits"]["data_disk_reserve_bytes"],
            "insufficient stage disk plus reserve")
    # These exact mechanical receipts must exist before public M predictions.
    require((Path(config["generated_stage"]) / "verify_receipt.json").is_file(),
            "48-family generation is not verified")
    write(RUN / "release.json", {
        "reviewed_code": reviewed_code, "workers": workers,
        "family_ids": [row["family_id"] for row in families],
        "confirmation_authorized": False, "private_truth_read": False,
        "time_utc": datetime.now(timezone.utc).isoformat(),
    })
    pending = [row["family_id"] for row in families]
    active = {}
    exits = []
    began = time.monotonic()
    try:
        while pending or active:
            while pending and len(active) < workers:
                family_id = pending.pop(0)
                log = (RUN / "logs" / (family_id + ".log"))
                log.parent.mkdir(parents=True, exist_ok=True)
                handle = log.open("x")
                child = subprocess.Popen(
                    [sys.executable, "-B", str(Path(__file__).resolve()), "_worker",
                     "--family", family_id], cwd=ROOT, stdout=handle,
                    stderr=subprocess.STDOUT, start_new_session=True,
                    env=dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1"))
                handle.close()
                active[family_id] = child
            time.sleep(1)
            for family_id, child in list(active.items()):
                if child.poll() is not None:
                    exits.append({"family_id": family_id, "exit_code": child.returncode})
                    del active[family_id]
                    require(child.returncode == 0, "family worker failed: " + family_id)
            require(time.monotonic() - began <= config["limits"]["run_wall_s"], "run wall limit")
            require(_tree_rss() <= config["limits"]["tree_rss_bytes"], "tree RSS limit")
            require(shutil.disk_usage(RUN.parent).free >= config["limits"]["data_disk_reserve_bytes"],
                    "disk reserve crossed")
    except BaseException as error:
        for child in active.values():
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
        write(RUN / "failure.json", {"error": f"{type(error).__name__}: {error}",
              "exits": exits, "not_started": pending, "active": list(active)})
        raise
    manifests = {row["family_id"]: file_record(RUN / "public" / row["family_id"] / "manifest.json")
                 for row in families}
    write(RUN / "public_receipt.json", {
        "exit_code": 0, "commit": checked["commit"], "binding": checked["binding"],
        "families": manifests, "exits": exits, "elapsed_s": time.monotonic() - began,
        "private_truth_read": False, "confirmation_read": False,
    })
    print(f"{STAGE} PUBLIC COMPLETE families={len(families)} exit=0", flush=True)


def verify_public():
    config, families = configuration()
    receipt = read(RUN / "public_receipt.json")
    require(receipt["exit_code"] == 0 and receipt["binding"] == binding(),
            "public receipt binding")
    from spatial_world_model.r4_query_v2 import validate_prediction
    counts = {"M-SIMPLE": 0, "M-PHYS": 0}
    for row in families:
        family_id = row["family_id"]
        manifest_path = RUN / "public" / family_id / "manifest.json"
        require(receipt["families"][family_id] == file_record(manifest_path),
                "family manifest changed")
        manifest = read(manifest_path)
        for relative, expected in manifest["files"].items():
            path = RUN / "public" / family_id / relative
            require(file_record(path) == expected, "public output changed")
            if relative.endswith(".json.gz") and not relative.endswith("map.json.gz"):
                value = read(path)
                require(value["private_truth_read"] is False, "public truth flag")
                for system in counts:
                    validate_prediction(value[system]["prediction"])
                    counts[system] += 1
    expected = len(families) * 4 * len(ACTIONS)
    require(counts == {"M-SIMPLE": expected, "M-PHYS": expected}, "public census")
    write(RUN / "verify_receipt.json", {"exit_code": 0, "public_receipt": file_record(
          RUN / "public_receipt.json"), "counts": counts})
    print(f"{STAGE} VERIFIED branches={expected} systems=2 exit=0", flush=True)


def _mean(values):
    return sum(values) / len(values) if values else None


def evaluate():
    config, families = configuration()
    require((RUN / "verify_receipt.json").is_file(), "public predictions not verified")
    require(not (RUN / "evaluation").exists(), "evaluation already started")
    from spatial_world_model.r4_scoring_v2 import score_world
    existing_ids = set(read(ROOT / "configs/spatial_history/r4_development_generation_v2.json")
                       ["existing_family_ids"])
    began = time.monotonic()
    metrics = {system: {"family_regret": [], "position": [], "contact_brier": [],
                        "success_brier": [], "valid_worlds": 0}
               for system in ("M-SIMPLE", "M-PHYS")}
    certificate_counts = {system: 0 for system in metrics}
    total_branches = 0
    for row in families:
        family_id = row["family_id"]
        data = source_root(family_id, existing_ids)
        family_scores = {system: [] for system in metrics}
        output = {"family_id": family_id, "split": row["split"], "worlds": []}
        for world in ("LL", "LR", "RL", "RR"):
            labels = [read(source_file(data, "labels", f"{world}-{action}.json.gz"))["labels"]
                      for action in ACTIONS]
            values = [read(RUN / "public" / family_id / world / f"{action}.json.gz")
                      for action in ACTIONS]
            world_row = {"world": world}
            for system in metrics:
                predictions = [value[system]["prediction"] for value in values]
                score = score_world(predictions, labels)
                world_row[system] = score
                metrics[system]["valid_worlds"] += int(score["valid"])
                if score["valid"]:
                    family_scores[system].append(score["selection_regret"])
                    for candidate in score["candidate_scores"]:
                        metrics[system]["position"].append(candidate["position_mean_error_m"])
                        metrics[system]["contact_brier"].append(candidate["contact_brier"])
                        metrics[system]["success_brier"].append(candidate["success_brier"])
                certificate_counts[system] += sum(int(value[system]["certificate"]
                                                      ["complete_sweep_contained"])
                                                  for value in values)
            total_branches += len(ACTIONS)
            output["worlds"].append(world_row)
        for system in metrics:
            metrics[system]["family_regret"].append(_mean(family_scores[system]))
        write(RUN / "evaluation" / (family_id + ".json.gz"), output)
        require(time.monotonic() - began <= config["limits"]["evaluation_wall_s"],
                "evaluation wall limit")
    summary = {
        "stage": STAGE,
        "family_count": len(families), "world_count": len(families) * 4,
        "branch_count": total_branches,
        "systems": {system: {
            "valid_worlds": values["valid_worlds"],
            "family_mean_regret": _mean(values["family_regret"]),
            "branch_mean_position_error_m": _mean(values["position"]),
            "branch_mean_contact_brier": _mean(values["contact_brier"]),
            "branch_mean_success_brier": _mean(values["success_brier"]),
            "complete_sweep_certificates": certificate_counts[system],
        } for system, values in metrics.items()},
        "confirmation_read": False, "elapsed_s": time.monotonic() - began,
    }
    write(RUN / "evaluation" / "summary.json", summary)
    write(RUN / "evaluation_receipt.json", {"exit_code": 0,
          "summary": file_record(RUN / "evaluation" / "summary.json"),
          "public_receipt": file_record(RUN / "public_receipt.json")})
    print(f"{STAGE} EVALUATED branches={total_branches} exit=0", flush=True)


def export():
    summary = read(RUN / "evaluation" / "summary.json")
    receipt = read(RUN / "evaluation_receipt.json")
    require(receipt["exit_code"] == 0 and
            receipt["summary"] == file_record(RUN / "evaluation" / "summary.json"),
            "evaluation receipt changed")
    require(not REPORT.exists(), "report exists")
    value = {"stage": STAGE, "status": "completed",
             "summary": summary, "check_receipt": read(RUN / "check_receipt.json"),
             "public_receipt": read(RUN / "public_receipt.json"),
             "verify_receipt": read(RUN / "verify_receipt.json"),
             "evaluation_receipt": receipt,
             "run_directory": str(RUN), "confirmation_read": False}
    raw = encode(value)
    require(len(raw) <= CONFIG["limits"]["report_bytes"], "report byte limit")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("xb") as handle:
        handle.write(raw)
    print(f"{STAGE} EXPORTED {REPORT} exit=0", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("environment", "check", "run", "_worker",
                                             "verify", "evaluate", "export"))
    parser.add_argument("--reviewed-code")
    parser.add_argument("--workers", type=int, default=CONFIG["limits"]["workers_default"])
    parser.add_argument("--family")
    args = parser.parse_args()
    if args.command == "environment":
        create_environment()
    elif args.command == "check":
        check()
    elif args.command == "run":
        require(args.reviewed_code is not None, "reviewed code required")
        run(args.reviewed_code, args.workers)
    elif args.command == "_worker":
        require(args.family is not None, "worker family required")
        _worker(args.family)
    elif args.command == "verify":
        verify_public()
    elif args.command == "evaluate":
        evaluate()
    else:
        export()


if __name__ == "__main__":
    main()
