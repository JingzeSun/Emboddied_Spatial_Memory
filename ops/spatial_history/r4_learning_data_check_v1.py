"""Read one real sealed R4 branch through the training-data boundary; no training."""

import hashlib
import json
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
import traceback

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from spatial_world_model.pair_contract import require
from spatial_world_model.r4_learning_data import branch_index, load_branch
from spatial_world_model.r4_storage import file_record, inventory

CONFIG = ROOT / "configs/spatial_history/r4_learning_data_check_v1.json"
RUN = Path("/root/autodl-tmp/spatial-history/sh05-r4-learning-data-check-v1")
REPORT = ROOT / "results/spatial_history_r4_learning_data_v1.json"
STAGE = "SH-05-R4-learning-data-check-v1"
CONFIG_VERSION = "sh05-r4-learning-data-check-v1"
BOUND = (
    "configs/spatial_history/r4_learning_data_check_v1.json",
    "configs/spatial_history/learning_contract_r4_v2.json",
    "src/spatial_world_model/r4_learning_data.py",
    "src/spatial_world_model/r4_query_v2.py",
    "src/spatial_world_model/r4_scoring_v2.py",
    "src/spatial_world_model/r4_storage.py",
    "src/spatial_world_model/r4_generation_v2.py",
    "tests/spatial_world_model/test_r4_learning_data.py",
    "ops/spatial_history/r4_learning_data_check_v1.py",
    "docs/DECISIONS.md", "docs/METHOD.md", "docs/DATA.md",
    "results/spatial_history_r4_engineering_subset_v2.json",
)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    with path.open("xb") as handle:
        handle.write(raw)
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def binding():
    return {name: file_record(ROOT / name) for name in BOUND}


def expected_seals(source_inventory, families):
    result = {}
    for family_id in families:
        prefix = f"execution/{family_id}/data/"
        result[family_id] = {
            "public_manifest": source_inventory[prefix + "public_manifest.json"],
            "labels_manifest": source_inventory[prefix + "labels_manifest.json"],
            "audit_manifest": source_inventory[prefix + "audit_manifest.json"],
            "family_result": source_inventory[prefix + "audit/family_result.json"],
        }
    return result


def run():
    config = read(CONFIG)
    require(config["version"] == CONFIG_VERSION, "config version")
    require(not RUN.exists() and not REPORT.exists(), "refuse overwrite/retry")
    require(not git("status", "--porcelain", "--", *BOUND), "bound files must be committed")
    require(file_record(ROOT / config["source_report"])["sha256"] == config["source_report_sha256"],
            "source report changed")
    source = Path(config["source_stage"])
    source_report = read(ROOT / config["source_report"])
    RUN.mkdir()
    save(RUN / "started.json", {
        "stage": STAGE, "commit": git("rev-parse", "HEAD"), "binding": binding(),
        "source_report": file_record(ROOT / config["source_report"]),
    })
    before = inventory(source)
    require(before == source_report["source_inventory"], "source stage inventory changed")
    roots = {family_id: source / "execution" / family_id / "data" for family_id in config["families"]}
    seals = expected_seals(before, config["families"])
    began = time.monotonic()
    index = branch_index(roots, seals)
    require(len(index["rows"]) == 144, "four-family branch index count")
    sample = config["sample"]
    without = load_branch(index, **sample, include_auxiliary_rgbd=False)
    with_aux = load_branch(index, **sample, include_auxiliary_rgbd=True)
    require(without["model_input"] == with_aux["model_input"] and without["targets"] == with_aux["targets"],
            "auxiliary permission changed main values")
    require(without["auxiliary_targets"] is None, "L/R path read future RGBD")
    auxiliary = with_aux["auxiliary_targets"]
    require(auxiliary["future_rgb"].shape == (200, 80, 80, 3)
            and auxiliary["future_depth_m"].shape == auxiliary["future_depth_valid"].shape == (200, 80, 80),
            "auxiliary future shape")
    require(str(auxiliary["future_rgb"].dtype) == "uint8"
            and str(auxiliary["future_depth_m"].dtype) == "float64"
            and str(auxiliary["future_depth_valid"].dtype) == "bool", "auxiliary dtype")
    require(len(without["model_input"]["history"]["time_s"]) == 121
            and len(without["model_input"]["controls"]["duration_s"]) == 200
            and len(without["targets"]["object_position_m"]) == 200, "main sequence lengths")
    require(set(without["model_input"]) == {"schema_version", "history", "controls", "goal", "domain_spec"},
            "model input fields changed")
    require(not without["audit"]["actual_future_robot_motion_returned"]
            and not without["audit"]["integration_state_returned"], "forbidden future state returned")
    after = inventory(source)
    require(after == before, "source files changed during read")
    elapsed = time.monotonic() - began
    require(elapsed <= config["limits"]["wall_s"], "check wall limit")
    commit = git("rev-parse", "HEAD")
    receipt = {
        "stage": STAGE, "exit_code": 0, "commit": commit, "binding": binding(),
        "elapsed_s": elapsed, "source_files_verified": len(before), "family_count": 4,
        "indexed_branches": 144, "sample": sample, "checks": [
            "external_manifest_seals", "complete_family_census", "public_query_121x200",
            "label_trajectory_binding", "auxiliary_toggle_main_invariance", "future_rgbd_1_through_200",
            "sensor_time_and_step_alignment", "no_integration_or_future_robot_return",
            "source_inventory_unchanged",
        ],
        "array_shapes": {key: list(value.shape) for key, value in auxiliary.items()},
        "array_dtypes": {key: str(value.dtype) for key, value in auxiliary.items()},
        "new_simulation_steps": 0, "new_training_steps": 0, "confirmation_read": False,
    }
    receipt_file = save(RUN / "receipt.json", receipt)
    report = {"stage": STAGE, "receipt": receipt, "receipt_file": receipt_file,
              "source_report": file_record(ROOT / config["source_report"]),
              "training_data_reader_ready": True, "training_runner_ready": False}
    record = save(REPORT, report)
    require(record["bytes"] <= config["limits"]["report_bytes"], "report byte limit")
    print(json.dumps({"report": str(REPORT), **record, "checks": len(receipt["checks"]), "exit_code": 0}))


if __name__ == "__main__":
    try:
        require(platform.system() == "Linux" and Path("/root/autodl-tmp").is_mount(), "server data disk required")
        config = read(CONFIG)
        limit = config["limits"]["process_as_bytes"]
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        run()
    except BaseException:
        if RUN.exists() and not (RUN / "failure.json").exists() and not (RUN / "receipt.json").exists():
            save(RUN / "failure.json", {"error": traceback.format_exc()})
        traceback.print_exc()
        sys.exit(1)
