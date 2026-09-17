#!/usr/bin/env python3
"""Drive the real public ``GetReachablePositions`` query for one house.

This is the only place that touches a simulator for the D-207 reachable scan.
It is split from the pure sealing core so that the core stays testable without
a controller, and so that the gate is checked *before* the controller is used
rather than after positions are already in hand.

The query is public: it takes no program, no target, no private identity and no
action outcome, and it runs before any intervention.  A failed query is a
refusal, never an empty grid that a later route could quietly plan around.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vsmt.vm04_observation_runner import (  # noqa: E402
    ObservationConstructionError,
    validate_approved_contract,
)
from vsmt.vm04_reachable_scan import (  # noqa: E402
    SCAN_SOURCE_ACTION,
    seal_public_reachable_scan,
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ObservationConstructionError(message)


def require_scan_gate(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Refuse to touch a controller until the trajectory gate is open."""

    approved = validate_approved_contract(contract)
    _require(
        approved["authorization"].get("trajectory_implementation_authorized")
        is True,
        "trajectory_implementation_authorized is not authorized, so the real "
        "reachable scan may not run",
    )
    return approved


def read_public_reachable_positions(controller: Any) -> list[dict[str, Any]]:
    """Return the raw public positions of one ``GetReachablePositions`` event."""

    event = controller.step(action=SCAN_SOURCE_ACTION)
    metadata = getattr(event, "metadata", None)
    _require(type(metadata) is dict, "simulator event metadata is missing")
    _require(metadata.get("lastActionSuccess") is True,
             "the public GetReachablePositions query failed")
    positions = metadata.get("actionReturn")
    _require(type(positions) is list and positions,
             "the public GetReachablePositions query returned no positions")
    return [dict(row) for row in positions]


def run_authorized_reachable_scan(
    controller: Any, *, house_id: str, contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Production entry: check the gate, query the house, seal the scan."""

    approved = require_scan_gate(contract)
    positions = read_public_reachable_positions(controller)
    return seal_public_reachable_scan(
        house_id=house_id, raw_positions=positions, contract=approved,
    )
