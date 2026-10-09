"""Locations inside the repository and the import path of its frozen code.

The package is used from a clone of the repository: it imports the frozen modules under ``src/`` and reads the
registered values from ``configs/vsmt/`` and ``results/``.  Importing this module puts ``src/`` on ``sys.path`` once.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
CONFIG_DIR = REPO_ROOT / "configs" / "vsmt"
RESULTS_DIR = REPO_ROOT / "results"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def load_json(path: Path) -> Any:
    """Read one JSON file as UTF-8."""

    return json.loads(Path(path).read_text(encoding="utf-8"))
