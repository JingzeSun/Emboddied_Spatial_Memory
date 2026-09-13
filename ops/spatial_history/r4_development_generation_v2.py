"""Current-bound retry of the reviewed 48-family development generation stage."""

import importlib.util
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "ops/spatial_history/r4_development_generation_v1.py"
SPEC = importlib.util.spec_from_file_location("r4_development_generation_v1", SOURCE)
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)

stage.CONFIG_PATH = "configs/spatial_history/r4_development_generation_v2.json"
stage.ENTRYPOINT = Path(__file__).resolve()
stage.RUN = Path("/root/autodl-tmp/spatial-history/sh05-r4-development-generation-v2")
stage.REPORT = ROOT / "results/spatial_history_r4_development_generation_v2.json"
stage.STAGE = "SH-05-R4-development-generation-v2"
stage.CONFIG_VERSION = "sh05-r4-development-generation-v2"
stage.BOUND = tuple(name for name in stage.BOUND
                    if name != "configs/spatial_history/r4_development_generation_v1.json") + (
    "configs/spatial_history/r4_development_generation_v2.json",
    "ops/spatial_history/r4_development_generation_v2.py",
)


if __name__ == "__main__":
    stage.main()
