"""Retry the sealed R4 reader check with registered float clock tolerance."""

import importlib.util
from pathlib import Path
import platform
import resource
import sys
import traceback

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "ops/spatial_history/r4_learning_data_check_v1.py"
SPEC = importlib.util.spec_from_file_location("r4_learning_data_check_v1", SOURCE)
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)

check.CONFIG = ROOT / "configs/spatial_history/r4_learning_data_check_v4.json"
check.RUN = Path("/root/autodl-tmp/spatial-history/sh05-r4-learning-data-check-v4")
check.REPORT = ROOT / "results/spatial_history_r4_learning_data_v4.json"
check.STAGE = "SH-05-R4-learning-data-check-v4"
check.CONFIG_VERSION = "sh05-r4-learning-data-check-v4"
check.BOUND = tuple(name for name in check.BOUND
                    if name != "configs/spatial_history/r4_learning_data_check_v1.json") + (
    "configs/spatial_history/r4_learning_data_check_v4.json",
    "src/spatial_world_model/r4_public_v2.py",
    "ops/spatial_history/r4_learning_data_check_v4.py",
)


if __name__ == "__main__":
    try:
        check.require(platform.system() == "Linux" and Path("/root/autodl-tmp").is_mount(),
                      "server data disk required")
        config = check.read(check.CONFIG)
        check.require(config["version"] == check.CONFIG_VERSION, "config version")
        limit = config["limits"]["process_as_bytes"]
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        check.run()
    except BaseException:
        if (check.RUN.exists() and not (check.RUN / "failure.json").exists()
                and not (check.RUN / "receipt.json").exists()):
            check.save(check.RUN / "failure.json", {"error": traceback.format_exc()})
        traceback.print_exc()
        sys.exit(1)
