"""Read-only diagnosis of unknown swept cells in the sealed R4 front-end output."""

from __future__ import annotations

import argparse
from collections import Counter, deque
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path


FAMILIES = ("r4-39", "r4-47", "r4-25", "r4-03")
WORLDS = ("LL", "LR", "RL", "RR")
ACTIONS = ("c00", "c01", "c02", "c10", "c11", "c12", "c20", "c21", "c22")
OBJECT_HALF_XY = (0.07, 0.07)
PUSHER_HALF_XY = (0.15, 0.025)
SCHEMA = "spatial-history-r4-map-unknown-diagnostic-v1"


def _read(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def _file_record(path: Path) -> dict:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return {"bytes": size, "sha256": digest.hexdigest()}


def _bounds(previous, current, half, cell):
    values = (
        min(previous[0], current[0]) - half[0],
        max(previous[0], current[0]) + half[0],
        min(previous[1], current[1]) - half[1],
        max(previous[1], current[1]) + half[1],
    )
    return tuple(math.floor(value / cell) for value in values)


def _cells(bounds):
    x0, x1, y0, y1 = bounds
    return {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}


def _dilate(cells):
    return {
        (x + dx, y + dy)
        for x, y in cells
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
    }


def _distance_to_known(known, targets):
    if not targets:
        return {}
    all_cells = known | targets
    x0 = min(x for x, _ in all_cells) - 1
    x1 = max(x for x, _ in all_cells) + 1
    y0 = min(y for _, y in all_cells) - 1
    y1 = max(y for _, y in all_cells) + 1
    queue = deque(known)
    distance = {cell: 0 for cell in known}
    remaining = set(targets)
    found = {}
    while queue and remaining:
        x, y = queue.popleft()
        next_distance = distance[(x, y)] + 1
        for cell in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if cell in distance:
                continue
            if not (x0 <= cell[0] <= x1 and y0 <= cell[1] <= y1):
                continue
            distance[cell] = next_distance
            if cell in remaining:
                found[cell] = next_distance
                remaining.remove(cell)
            queue.append(cell)
    return found


def _variant_summary(bounds_by_step, known):
    cache = {}
    unknown_steps = []
    for step, (object_bounds, pusher_bounds) in enumerate(bounds_by_step, 1):
        valid = True
        for bounds in (object_bounds, pusher_bounds):
            if bounds not in cache:
                cache[bounds] = _cells(bounds).issubset(known)
            valid &= cache[bounds]
        if not valid:
            unknown_steps.append(step)
    return {
        "first_unknown_step": unknown_steps[0] if unknown_steps else None,
        "unknown_sweep_steps": len(unknown_steps),
    }


def _branch(map_data, branch_data):
    proxy = branch_data["proxy"]
    trajectory = proxy["trajectory"]
    if proxy["status"] != "nominal_complete" or len(trajectory) != 10001:
        raise ValueError("sealed proxy trajectory is incomplete")
    cell = map_data["cell_m"]
    if cell != 0.01:
        raise ValueError("unexpected map cell size")
    free = set(map(tuple, map_data["nominal_free_cells"]))
    occupied = set(map(tuple, map_data["occupied_cells"]))
    explicit_unknown = set(map(tuple, map_data["unknown_cells"]))
    floor = set(map(tuple, map_data["floor_cells"]))
    surface = {tuple(item["cell_xy"]) for item in map_data["surface_cells"]}
    known = (free | occupied) - explicit_unknown
    initial = _cells(_bounds(
        trajectory[0]["object_position_m"], trajectory[0]["object_position_m"], OBJECT_HALF_XY, cell
    )) | _cells(_bounds(
        trajectory[0]["robot_position_m"], trajectory[0]["robot_position_m"], PUSHER_HALF_XY, cell
    ))

    bounds_by_step = []
    body_unknown_steps = Counter()
    missing_occurrences = Counter()
    missing_by_body = {"object": set(), "pusher": set()}
    first_detail = None
    for step in range(1, len(trajectory)):
        previous, current = trajectory[step - 1], trajectory[step]
        object_bounds = _bounds(previous["object_position_m"], current["object_position_m"], OBJECT_HALF_XY, cell)
        pusher_bounds = _bounds(previous["robot_position_m"], current["robot_position_m"], PUSHER_HALF_XY, cell)
        bounds_by_step.append((object_bounds, pusher_bounds))
        object_missing = _cells(object_bounds) - known
        pusher_missing = _cells(pusher_bounds) - known
        if object_missing:
            body_unknown_steps["object"] += 1
            missing_by_body["object"].update(object_missing)
        if pusher_missing:
            body_unknown_steps["pusher"] += 1
            missing_by_body["pusher"].update(pusher_missing)
        if object_missing and pusher_missing:
            body_unknown_steps["both"] += 1
        for missing in (object_missing, pusher_missing):
            missing_occurrences.update(missing)
        if first_detail is None and (object_missing or pusher_missing):
            first_detail = {
                "step": step,
                "object_missing_cells": [list(value) for value in sorted(object_missing)],
                "pusher_missing_cells": [list(value) for value in sorted(pusher_missing)],
            }

    missing = set(missing_occurrences)
    distance = _distance_to_known(known, missing)
    base = _variant_summary(bounds_by_step, known)
    reported = {
        "first_unknown_step": proxy["first_unknown_step"],
        "unknown_sweep_steps": proxy["unknown_sweep_steps"],
    }
    if base != reported:
        raise ValueError(f"unknown sweep recomputation differs: {base} != {reported}")
    distance_histogram = Counter(distance.values())
    return {
        "reported_and_recomputed": base,
        "body_unknown_steps": dict(body_unknown_steps),
        "unique_missing_cells": len(missing),
        "missing_cell_occurrences": sum(missing_occurrences.values()),
        "unique_missing_by_body": {key: len(value) for key, value in missing_by_body.items()},
        "missing_cell_classes": {
            "explicit_unknown": len(missing & explicit_unknown),
            "floor_but_not_known": len((missing & floor) - known),
            "surface_but_not_known": len((missing & surface) - known),
            "absent_from_surface_map": len(missing - surface),
            "inside_initial_body_envelope": len(missing & initial),
            "adjacent_to_known_8": len(missing & (_dilate(known) - known)),
        },
        "manhattan_cells_to_nearest_known": {
            str(key): value for key, value in sorted(distance_histogram.items())
        },
        "sensitivity_not_certification": {
            "base": base,
            "add_initial_body_envelopes": _variant_summary(bounds_by_step, known | initial),
            "one_cell_known_dilation": _variant_summary(bounds_by_step, _dilate(known)),
            "initial_plus_one_cell_dilation": _variant_summary(bounds_by_step, _dilate(known | initial)),
        },
        "first_unknown_detail": first_detail,
    }


def run(source: Path, output: Path):
    source = source.resolve(strict=True)
    output = output.resolve()
    if output.exists():
        raise FileExistsError(output)
    expected = []
    for family in FAMILIES:
        for world in WORLDS:
            expected.append(source / "public" / family / world / "map.json.gz")
            expected.extend(source / "public" / family / world / f"{action}.json.gz" for action in ACTIONS)
    if any(not path.is_file() for path in expected):
        raise FileNotFoundError("one or more registered public front-end files are missing")
    before = {str(path.relative_to(source)): _file_record(path) for path in expected}
    rows = []
    for family in FAMILIES:
        for world in WORLDS:
            folder = source / "public" / family / world
            map_data = _read(folder / "map.json.gz")
            for action in ACTIONS:
                rows.append({
                    "family": family,
                    "world": world,
                    "action": action,
                    **_branch(map_data, _read(folder / f"{action}.json.gz")),
                })
    after = {str(path.relative_to(source)): _file_record(path) for path in expected}
    if before != after:
        raise RuntimeError("sealed source files changed during diagnosis")

    aggregate = {
        "branches": len(rows),
        "reported_recomputation_matches": sum(
            row["reported_and_recomputed"] == row["sensitivity_not_certification"]["base"] for row in rows
        ),
        "base_zero_unknown_branches": sum(row["reported_and_recomputed"]["unknown_sweep_steps"] == 0 for row in rows),
    }
    for name in ("add_initial_body_envelopes", "one_cell_known_dilation", "initial_plus_one_cell_dilation"):
        aggregate[f"{name}_zero_unknown_branches"] = sum(
            row["sensitivity_not_certification"][name]["unknown_sweep_steps"] == 0 for row in rows
        )
        aggregate[f"{name}_total_unknown_steps"] = sum(
            row["sensitivity_not_certification"][name]["unknown_sweep_steps"] for row in rows
        )
    result = {
        "schema_version": SCHEMA,
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "read_only": True,
        "uses_private_truth": False,
        "changes_formal_model_ready": False,
        "parameters": {
            "cell_m": 0.01,
            "object_half_xy_m": list(OBJECT_HALF_XY),
            "pusher_half_xy_m": list(PUSHER_HALF_XY),
            "sensitivity_interventions_are_not_observation_certificates": True,
        },
        "source_files": before,
        "aggregate": aggregate,
        "rows": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    output.write_bytes(payload)
    print(json.dumps({"output": str(output), "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), **aggregate}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.source, args.output)


if __name__ == "__main__":
    main()
