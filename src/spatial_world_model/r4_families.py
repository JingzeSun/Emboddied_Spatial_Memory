"""D-079 deterministic design only: no simulator, files, labels or sampling.

The 64 design rows include sealed confirmation assignments, not observations.
Only the first four model_train rows may be used by the engineering runner.
Chinese field definitions and examples: docs/DATA.md#r4-data.
"""
from copy import deepcopy
import hashlib
import json

from .pair_contract import require
from .two_gate_contract import validate_config as validate_base, expand_controls

VERSION = "sh04-r4-family-design-v1"
SPLITS = ("model_train", "model_validation", "model_confirmation",
          "probe_train", "probe_validation", "probe_confirmation")
COUNTS = (32, 8, 8, 8, 4, 4)
RANGES = {
    "gate_near_y_m": [0.56, 0.64], "gate_far_y_m": [2.16, 2.24],
    "gate_near_bias_x_m": [-0.02, 0.02], "gate_far_bias_x_m": [-0.02, 0.02],
    "gate_near_half_separation_m": [0.10, 0.16], "gate_far_half_separation_m": [0.10, 0.16],
    "gate_near_clear_width_m": [0.34, 0.42], "gate_far_clear_width_m": [0.34, 0.42],
    "global_translation_x_m": [-0.12, 0.12],
    "control_near_scale": [0.8, 1.2], "control_far_scale": [0.8, 1.2],
}


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def parameter_word(index, key):
    require(type(index) is int and 0 <= index < 64, "family index must be 0..63")
    raw = f"sh04-r4-v1:param:{index}:{key}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def parameters(index):
    return {key: low + (high - low) * (parameter_word(index, key) / (2**64 - 1))
            for key, (low, high) in RANGES.items()}


def camera_design(index):
    order = parameter_word(index, "camera_order") % 2
    centers = [base + (-0.3, 0.0, 0.3)[parameter_word(index, key) % 3]
               for base, key in zip((2.5, 6.5), ("camera_dwell_1", "camera_dwell_2"))]
    views = [0.6, 2.2] if order == 0 else [2.2, 0.6]
    c1, c2 = centers
    boundaries = [0, c1 - 0.5, c1 + 0.5, c2 - 0.5, c2 + 0.5, 11, 12]
    positions = [-0.1, views[0], views[0], views[1], views[1], -0.1, -0.1]
    segments = [{"time_s": [a, b], "y_m": [y0, y1]}
                for a, b, y0, y1 in zip(boundaries, boundaries[1:], positions, positions[1:])]
    indices = {"A": round(centers[order] * 10), "B": round(centers[1 - order] * 10)}
    checkpoints = sorted({round(t * 10) for c in centers for t in (c, c + 0.5, c + 1.4)} | {101, 120})
    return {"order": "near_first" if order == 0 else "far_first", "dwell_centers_s": centers,
            "segments": segments, "view_frame_indices": indices, "probe_prefix_indices": checkpoints}


def manifest(protocol):
    data = protocol["dataset"]
    require(protocol["version"] == "sh04-r4-comparison-contract-v1", "R4 version")
    require(data["ranges"] == RANGES and data["family_count"] == 64, "registered ranges changed")
    require(data["split_order"] == list(SPLITS) and data["split_counts"] == list(COUNTS), "split changed")
    order = sorted(range(64), key=lambda i: (hashlib.sha256(f"sh04-r4-v1:split:{i}".encode()).digest(), i))
    rows, offset = [], 0
    for split, count in zip(SPLITS, COUNTS):
        for rank, index in enumerate(order[offset:offset + count]):
            p = parameters(index)
            # Remove translation in parameter space, before floating-point
            # addition/subtraction can make exact duplicates appear different.
            normalized = {k: v for k, v in p.items() if k != "global_translation_x_m"}
            camera = camera_design(index)
            rows.append({"family_id": f"r4-{index:02d}", "index": index, "split": split,
                         "split_rank": rank, "parameters": p, "camera": camera,
                         "normalized_design_sha256": digest({"parameters": normalized, "camera": camera})})
        offset += count
    require(len({row["normalized_design_sha256"] for row in rows}) == 64,
            "duplicate geometry/control/observation design: reject complete inventory")
    return {"version": VERSION, "protocol_sha256": digest(protocol), "rows": rows,
            "engineering_family_ids": [r["family_id"] for r in rows[:4]],
            "confirmation_observations_generated": False}


def validate_manifest(value, protocol):
    require(value == manifest(protocol), "manifest differs from deterministic D-079 inventory")


def engineering_rows(value):
    rows = value["rows"][:4]
    require(len(rows) == 4 and all(r["split"] == "model_train" and r["split_rank"] == i
                                  for i, r in enumerate(rows)), "invalid engineering subset")
    require([r["family_id"] for r in rows] == value["engineering_family_ids"], "subset IDs differ")
    return deepcopy(rows)


def family_config(base, row):
    """Derive geometry and controls independently; execution remains unapproved."""
    validate_base(base)
    index, p = row["index"], row["parameters"]
    require(p == parameters(index) and row["camera"] == camera_design(index), "row parameters changed")
    value = deepcopy(base)
    value.update(version="sh04-r4-family-v1", status="review_only",
                 generation_authorized=False, training_authorized=False,
                 numeric_protocol_approved=False, approval_decision="D-081")
    g, o = value["geometry"], value["observation"]
    tx = p["global_translation_x_m"]
    g["gate_y_m"] = [p[f"gate_{which}_y_m"] for which in ("near", "far")]
    g["gate_centers_x_m"] = [
        {side: tx + p[f"gate_{which}_bias_x_m"] + sign * p[f"gate_{which}_half_separation_m"]
         for side, sign in (("L", -1), ("R", 1))} for which in ("near", "far")]
    g["gate_widths_m"] = [p[f"gate_{which}_clear_width_m"] for which in ("near", "far")]
    del g["gate_center_x_m"], g["gate_clear_width_m"]
    for key in ("cross_wall_outer_x_m", "side_wall_inner_x_m"):
        g[key] = [v + tx for v in g[key]]
    for key in ("object_initial_position_m", "pusher_initial_position_m"):
        g[key][0] += tx
    o["camera_x_m"] += tx
    o["camera_segments"] = deepcopy(row["camera"]["segments"])
    o["fixed_view_frame_indices"] = deepcopy(row["camera"]["view_frame_indices"])
    for action, phases in value["controls"]["phase_vx_mps"].items():
        value["controls"]["phase_vx_mps"][action] = [v * p["control_near_scale" if i < 5 else "control_far_scale"]
                                                     for i, v in enumerate(phases)]
    task = value["task_success"]
    task["goal_center_xy_m"][0] += tx
    task["goal_x_bounds_m"] = [v + tx for v in task["goal_x_bounds_m"]]
    validate_family_config(value)
    return value


def legacy_view(config):
    """Numerical adapter for old helpers that do not consume gate geometry.

    Never pass this representative-gate view to a physical assessor or XML
    builder for R4. It exists only for public schema, clocks and control expansion.
    """
    value = deepcopy(config)
    g = value["geometry"]
    g["gate_center_x_m"] = g.pop("gate_centers_x_m")[0]
    g["gate_clear_width_m"] = g.pop("gate_widths_m")[0]
    return value


def validate_family_config(value):
    require(value["version"] == "sh04-r4-family-v1", "R4 family version")
    g = value["geometry"]
    require(len(g["gate_centers_x_m"]) == len(g["gate_widths_m"]) == 2, "two independent gates required")
    for centers, width in zip(g["gate_centers_x_m"], g["gate_widths_m"]):
        require(set(centers) == {"L", "R"} and 0.34 <= width <= 0.42, "gate fields/range")
        require(centers["L"] < centers["R"], "gate sign order")
        for center in centers.values():
            require(g["cross_wall_outer_x_m"][0] < center - width / 2 < center + width / 2
                    < g["cross_wall_outer_x_m"][1], "opening outside walls")
    validate_base(legacy_view(value))


def controls(config):
    validate_family_config(config)
    return expand_controls(legacy_view(config))


def categorical_shortcut(matrices):
    require(bool(matrices), "no development matrices")
    names = ("LL", "LR", "RL", "RR")
    intersections = {w: set(range(4)) for w in names}
    for matrix in matrices:
        require(set(matrix) == set(names), "incomplete worlds")
        for world in names:
            require(set(matrix[world]) == set(names) and all(type(v) is bool for v in matrix[world].values()),
                    "incomplete/invalid actual outcome matrix")
            best = max(matrix[world].values())
            intersections[world] &= {i for i, a in enumerate(names) if matrix[world][a] == best}
    return {"optimal_index_intersections": {w: sorted(v) for w, v in intersections.items()},
            "categorical_shortcut_unexcluded": all(intersections.values()),
            "development_family_count": len(matrices)}
