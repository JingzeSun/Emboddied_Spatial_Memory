"""Real public reachable-position scan and per-step route reachability (D-207).

Before this module the route search had a schema and a pure core but no real
source of reachable points: the pose graph was handed to it already built.  The
D-207 blocker asks for two things at once, and they are the same thing seen
from both ends.

* A *scan* receipt: the public ``GetReachablePositions`` grid of one house,
  seal-checked against the frozen 0.25 m move magnitude so that one planned
  grid step really does equal one registered action.
* A *per-step* guarantee: every planned translation lands on a verified cell of
  that grid **before** the route is sealed.  This is the yield guard for the
  64-step place layer.  Route acceptance compares the actual pose to the
  planned pose at three anchors only and does not accumulate, so a longer route
  is not less accurate; it simply has more chances for one action to be
  blocked.  Rejecting blocked steps at planning time is the only mitigation
  that does not relax a tolerance, and D-207 forbids relaxing one.

Nothing here reads private identity, program outcome or any action result: the
scan is a pre-intervention public query and the planned poses are pure
kinematics over the frozen action request templates.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from cpmt.hashing import clone_json

from .vm04_observation_runner import (
    _hex64,
    _pose,
    _require,
    _sha,
    validate_approved_contract,
    validate_registered_action_request_templates,
    validate_route_plan,
)
from .vm04_odometry import PITCH_ACTIONS, TRANSLATION_ACTIONS, YAW_ACTIONS


REACHABLE_SCAN_SCHEMA = "vsmt-vm04-public-reachable-scan-v1"
STEP_VERIFICATION_SCHEMA = "vsmt-vm04-route-step-reachability-v1"
SCAN_SOURCE_ACTION = "GetReachablePositions"
SCAN_PHASE = "pre_intervention_public_reachable_scan"

#: Lattice snap tolerance, matching the 0.01 m tolerance the earlier two-house
#: reachable-grid reader already used against the same simulator query.
GRID_TOLERANCE_M = 0.01
#: A heading counts as axis aligned within this many degrees of a right angle.
AXIS_ALIGNED_TOLERANCE_DEG = 1e-6


def _self_sha(record: Mapping[str, Any], digest_field: str) -> str:
    """Digest a record over every field except its own digest slot.

    The shared ``_payload_sha`` strips a fixed list of digest names, so these
    two new record kinds carry their own helper instead of widening that list
    and disturbing digests that are already pinned elsewhere.
    """

    payload = {key: value for key, value in dict(record).items()
               if key != digest_field}
    return _sha(payload)


def registered_grid_size_m(contract: Mapping[str, Any]) -> float:
    """Return the grid step the frozen move templates commit the route to.

    The value is derived from the contract rather than hardcoded so that a
    future move magnitude cannot silently disagree with the scan grid.
    """

    approved = validate_approved_contract(contract)
    templates = validate_registered_action_request_templates(
        approved["observation_trajectory"]["registered_action_request_templates"]
    )
    magnitudes = {
        float(templates[name]["moveMagnitude"]) for name in TRANSLATION_ACTIONS
    }
    _require(len(magnitudes) == 1,
             "the four registered move actions must share one magnitude for a "
             "planned grid step to equal one registered action")
    magnitude = magnitudes.pop()
    _require(magnitude > 0.0, "registered move magnitude must be positive")
    return magnitude


def _finite(value: Any, name: str) -> float:
    _require(type(value) in {int, float} and math.isfinite(float(value)),
             f"{name} must be a finite number")
    return float(value)


def _position(row: Any, name: str) -> dict[str, float]:
    _require(type(row) is dict and set(row) == {"x", "y", "z"},
             f"{name} must be an x/y/z simulator position")
    return {axis: _finite(row[axis], f"{name}.{axis}")
            for axis in ("x", "y", "z")}


def seal_public_reachable_scan(
    *, house_id: str, raw_positions: Sequence[Mapping[str, Any]],
    contract: Mapping[str, Any],
    source_action: str = SCAN_SOURCE_ACTION,
    source_action_success: bool = True,
) -> dict[str, Any]:
    """Seal one house's public reachable grid into a replayable receipt.

    ``raw_positions`` is the simulator ``actionReturn`` of a public
    ``GetReachablePositions`` call.  The receipt keeps integer cell keys rather
    than raw floats, so two scans of the same house are byte comparable and a
    later per-step check is exact instead of tolerance chained.
    """

    approved = validate_approved_contract(contract)
    grid = registered_grid_size_m(approved)
    _require(type(house_id) is str and house_id, "house_id must be nonempty")
    _require(source_action == SCAN_SOURCE_ACTION,
             "the reachable scan must come from the registered public query")
    _require(source_action_success is True,
             "a failed reachable query may not be sealed as a scan")
    _require(type(raw_positions) in {list, tuple} and raw_positions,
             "the reachable scan returned no positions")

    positions = sorted(
        (_position(row, "public reachable position") for row in raw_positions),
        key=lambda row: (row["x"], row["y"], row["z"]),
    )
    origin = positions[0]
    cells: dict[tuple[int, int], dict[str, float]] = {}
    for row in positions:
        _require(abs(row["y"] - origin["y"]) <= GRID_TOLERANCE_M,
                 "a multilevel reachable grid needs a separately reviewed route")
        key = (round((row["x"] - origin["x"]) / grid),
               round((row["z"] - origin["z"]) / grid))
        _require(key not in cells, "the reachable scan repeats a grid cell")
        _require(abs(row["x"] - (origin["x"] + key[0] * grid)) <=
                 GRID_TOLERANCE_M and
                 abs(row["z"] - (origin["z"] + key[1] * grid)) <=
                 GRID_TOLERANCE_M,
                 "public reachable points do not lie on one registered grid")
        cells[key] = row

    scan = {
        "schema_version": REACHABLE_SCAN_SCHEMA,
        "house_id": house_id,
        "source_action": SCAN_SOURCE_ACTION,
        "scan_phase": SCAN_PHASE,
        "grid_size_m": grid,
        "origin_x_m": origin["x"],
        "origin_z_m": origin["z"],
        "level_y_m": origin["y"],
        "cell_count": len(cells),
        "cells": [[key[0], key[1]] for key in sorted(cells)],
        "private_identity_used": False,
        "future_or_action_outcome_used": False,
        "positions_chosen_after_a_failure": False,
    }
    scan["reachable_scan_sha256"] = _self_sha(
        scan, "reachable_scan_sha256")
    return scan


def validate_public_reachable_scan(
    scan: Mapping[str, Any], *, contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Re-check a sealed scan against the contract and against its own digest."""

    approved = validate_approved_contract(contract)
    expected = {
        "schema_version", "house_id", "source_action", "scan_phase",
        "grid_size_m", "origin_x_m", "origin_z_m", "level_y_m", "cell_count",
        "cells", "private_identity_used", "future_or_action_outcome_used",
        "positions_chosen_after_a_failure", "reachable_scan_sha256",
    }
    _require(type(scan) is dict and set(scan) == expected,
             "public reachable scan has unexpected fields")
    _require(scan["schema_version"] == REACHABLE_SCAN_SCHEMA,
             "wrong public reachable scan schema")
    _require(scan["source_action"] == SCAN_SOURCE_ACTION,
             "the reachable scan must come from the registered public query")
    _require(scan["scan_phase"] == SCAN_PHASE,
             "the reachable scan must be sealed before the intervention")
    _require(scan["private_identity_used"] is False,
             "the reachable scan may not use private identity")
    _require(scan["future_or_action_outcome_used"] is False,
             "the reachable scan may not use future or action-outcome data")
    _require(scan["positions_chosen_after_a_failure"] is False,
             "reachable positions may not be reselected after a failure")
    _require(type(scan["house_id"]) is str and scan["house_id"],
             "house_id must be nonempty")
    _require(scan["grid_size_m"] == registered_grid_size_m(approved),
             "the scan grid does not match the frozen move magnitude")
    for name in ("origin_x_m", "origin_z_m", "level_y_m"):
        _finite(scan[name], name)
    cells = scan["cells"]
    _require(type(cells) is list and cells, "the reachable scan has no cells")
    _require(all(type(row) is list and len(row) == 2 and
                 all(type(value) is int for value in row) for row in cells),
             "reachable cells must be integer grid keys")
    keys = [tuple(row) for row in cells]
    _require(keys == sorted(set(keys)),
             "reachable cells must be unique and canonically ordered")
    _require(scan["cell_count"] == len(keys), "reachable cell count mismatch")
    _hex64(scan["reachable_scan_sha256"], "reachable_scan_sha256")
    _require(scan["reachable_scan_sha256"] ==
             _self_sha(scan, "reachable_scan_sha256"),
             "reachable scan digest mismatch")
    return clone_json(dict(scan))


class ReachableGrid:
    """Exact membership test for planned poses against one sealed scan."""

    def __init__(
        self, scan: Mapping[str, Any], *, contract: Mapping[str, Any],
    ) -> None:
        self.contract = validate_approved_contract(contract)
        self.scan = validate_public_reachable_scan(scan, contract=self.contract)
        self.grid = float(self.scan["grid_size_m"])
        self.origin_x = float(self.scan["origin_x_m"])
        self.origin_z = float(self.scan["origin_z_m"])
        self.cells = {tuple(row) for row in self.scan["cells"]}

    @property
    def reachable_scan_sha256(self) -> str:
        return self.scan["reachable_scan_sha256"]

    def cell_of(self, x_m: float, z_m: float) -> tuple[int, int] | None:
        """Return the grid cell of a planned position, or ``None`` if off-grid."""

        key = (round((float(x_m) - self.origin_x) / self.grid),
               round((float(z_m) - self.origin_z) / self.grid))
        if (abs(float(x_m) - (self.origin_x + key[0] * self.grid)) >
                GRID_TOLERANCE_M or
                abs(float(z_m) - (self.origin_z + key[1] * self.grid)) >
                GRID_TOLERANCE_M):
            return None
        return key

    def contains(self, x_m: float, z_m: float) -> bool:
        key = self.cell_of(x_m, z_m)
        return key is not None and key in self.cells

    def pose_is_reachable(self, pose: Mapping[str, float]) -> bool:
        return self.contains(pose["x_m"], pose["z_m"])


def _axis_aligned_forward(yaw_deg: float) -> tuple[float, float] | None:
    """Return the integer (x, z) heading unit, or ``None`` when off-axis.

    AI2-THOR's reachable grid is axis aligned while the frozen rotation step is
    30 degrees, so a translation issued from a heading that is not a multiple of
    a right angle leaves the grid by construction.  Returning ``None`` makes
    that a named planning failure instead of a route that only fails once the
    simulator is already running.
    """

    quadrant = yaw_deg / 90.0
    nearest = round(quadrant)
    if abs(quadrant - nearest) * 90.0 > AXIS_ALIGNED_TOLERANCE_DEG:
        return None
    return ((0.0, 1.0), (1.0, 0.0), (0.0, -1.0), (-1.0, 0.0))[int(nearest) % 4]


def nominal_route_poses(
    initial_pose: Mapping[str, Any], action_names: Sequence[str], *,
    contract: Mapping[str, Any],
) -> list[dict[str, float]]:
    """Return N+1 commanded (noise-free) world poses for N registered actions.

    These are *planning* poses.  The public packet still carries only the D-206
    relative noisy estimate and route acceptance still scores the simulator's
    actual pose; this sequence exists so a step can be checked against the
    reachable grid before the route is sealed.
    """

    approved = validate_approved_contract(contract)
    templates = validate_registered_action_request_templates(
        approved["observation_trajectory"]["registered_action_request_templates"]
    )
    pose = _pose(initial_pose, "initial pose")
    poses = [dict(pose)]
    x, z, yaw = pose["x_m"], pose["z_m"], pose["yaw_deg"]
    for step_index, name in enumerate(action_names):
        _require(type(name) is str and name in templates,
                 f"planned step {step_index} is not a registered camera action")
        if name in TRANSLATION_ACTIONS:
            forward = _axis_aligned_forward(yaw)
            _require(forward is not None,
                     f"planned step {step_index} translates from a heading that "
                     f"is not axis aligned, so it cannot land on the grid")
            magnitude = float(templates[name]["moveMagnitude"])
            lateral_unit, forward_unit = TRANSLATION_ACTIONS[name]
            forward_x, forward_z = forward
            right_x, right_z = forward_z, -forward_x
            x += magnitude * (forward_unit * forward_x + lateral_unit * right_x)
            z += magnitude * (forward_unit * forward_z + lateral_unit * right_z)
        elif name in YAW_ACTIONS:
            yaw = ((yaw + float(templates[name]["degrees"]) * YAW_ACTIONS[name] +
                    180.0) % 360.0) - 180.0
        else:
            _require(name in PITCH_ACTIONS,
                     f"planned step {step_index} is not a registered action")
        poses.append({"x_m": x, "y_m": pose["y_m"], "z_m": z, "yaw_deg": yaw})
    return poses


def seal_route_step_reachability(
    *, plan: Mapping[str, Any], scan: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify every planned step of a sealed route lands on a reachable cell.

    Fails closed on the first blocked step.  A route whose step leaves the grid
    is a construction failure of that route; it is not an invitation to move the
    house, the target or the tolerance.
    """

    approved = validate_approved_contract(contract)
    route = validate_route_plan(plan, contract=approved)
    grid = ReachableGrid(scan, contract=approved)
    actions = [row["action"] for row in route["registered_actions"]]
    poses = nominal_route_poses(
        route["initial_pose"], actions, contract=approved,
    )

    rows = []
    for index, pose in enumerate(poses):
        cell = grid.cell_of(pose["x_m"], pose["z_m"])
        _require(cell is not None,
                 f"planned observation {index} is off the reachable grid")
        _require(tuple(cell) in grid.cells,
                 f"planned observation {index} is not a reachable cell")
        rows.append({
            "observation_index": index,
            "action": None if index == 0 else actions[index - 1],
            "cell": [cell[0], cell[1]],
            "reachable": True,
        })

    receipt = {
        "schema_version": STEP_VERIFICATION_SCHEMA,
        "episode_id": route["episode_id"],
        "family_layer": route["family_layer"],
        "route_plan_sha256": route["route_plan_sha256"],
        "reachable_scan_sha256": grid.reachable_scan_sha256,
        "house_id": grid.scan["house_id"],
        "verified_step_count": len(actions),
        "steps": rows,
        "every_planned_step_verified_reachable": True,
        "tolerances_relaxed_to_raise_yield": False,
        "blocked_route_replacement_allowed": False,
    }
    receipt["step_reachability_sha256"] = _self_sha(
        receipt, "step_reachability_sha256")
    return receipt


def validate_route_step_reachability(
    receipt: Mapping[str, Any], *, plan: Mapping[str, Any],
    scan: Mapping[str, Any], contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Recompute the verification and require the sealed receipt to match."""

    rebuilt = seal_route_step_reachability(
        plan=plan, scan=scan, contract=contract,
    )
    _require(type(receipt) is dict and dict(receipt) == rebuilt,
             "route step reachability receipt does not recompute")
    return rebuilt
