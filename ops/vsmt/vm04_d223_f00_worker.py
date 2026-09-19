#!/usr/bin/env python3
"""One-house F-00 worker: query reachability only and seal private topology."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
OPS = Path(__file__).resolve().parent
for item in (SRC, OPS):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.d223_f00_topology_precheck import (  # noqa: E402
    analyze_reachable_topology,
    make_private_failure,
)
import vm04_two_house_worker as source_worker  # noqa: E402


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _make_controller(house: dict[str, Any], config: dict[str, Any]):
    from ai2thor.controller import Controller
    from ai2thor.platform import CloudRendering

    upgraded = source_worker.upgrade_house_schema_v1(
        house, source_worker.load_pinned_asset_id_database())
    query = config["simulator_query"]
    controller = Controller(
        platform=CloudRendering, scene=upgraded, width=224, height=224,
        gridSize=query["grid_size_m"], snapToGrid=True,
        renderDepthImage=False, renderInstanceSegmentation=False,
    )
    if controller.last_event.metadata.get("lastActionSuccess") is not True:
        error = controller.last_event.metadata.get("errorMessage")
        controller.stop()
        raise RuntimeError(f"ProcTHOR scene creation failed: {error}")
    source_worker.bootstrap_house_agent(controller, upgraded)
    return controller


def precheck_house(task: dict[str, Any]) -> dict[str, Any]:
    """Return one sealed private success or immutable failure receipt."""

    row = task["row"]
    controller = None
    try:
        house = source_worker.load_source_record(
            task["source_root"], row["source_locator"])
        if _sha(house) != row["source_record_sha256"]:
            raise RuntimeError("source record digest changed")
        controller = _make_controller(house, task["contract"])
        event = controller.step(action="GetReachablePositions")
        if event.metadata.get("lastActionSuccess") is not True:
            raise RuntimeError("GetReachablePositions failed: " + str(
                event.metadata.get("errorMessage")))
        positions = event.metadata.get("actionReturn")
        if type(positions) is not list or not positions:
            raise RuntimeError("GetReachablePositions returned no positions")
        return analyze_reachable_topology(
            positions, house_slot=row["house_slot"],
            source_house_id=row["source_house_id"],
            source_record_sha256=row["source_record_sha256"])
    except Exception as error:
        return make_private_failure(
            house_slot=row["house_slot"],
            source_house_id=row["source_house_id"],
            source_record_sha256=row["source_record_sha256"],
            error_type=type(error).__name__, message=str(error))
    finally:
        if controller is not None:
            controller.stop()
