"""D-082 deterministic v2 design. No simulator, files or outcome selection.

The private base template pins unchanged D-071 physics and audit constants.
Only numerical controls reach queries; band pairs and family indices do not.
Chinese explanation: docs/METHOD.md and docs/DATA.md, R4 v2 sections.
"""
from copy import deepcopy
import hashlib

from .pair_contract import require
from .r4_families import encode, digest, parameter_word, SPLITS, COUNTS
from .r4_families import camera_design as old_camera_design

VERSION = "sh04-r4-family-design-v2"
FAMILY_VERSION = "sh04-r4-family-v2"
PROPOSAL_DIGEST = "a9d7e237a3df8b9e5b399e88b8dd3ef1d10b431e28a0117b5f689f45c965db44"
BASE_DIGEST = "8cd74699923b2760b0d2b0b778e28ecc4583d8ff20ed7450def8c9049fc4c31b"
NAMES = ("LL", "LR", "RL", "RR")
ACTIONS = tuple(f"c{near}{far}" for near in range(3) for far in range(3))
BANDS = (-0.12, 0, 0.12)
PAIRS = ((0, 1), (0, 2), (1, 2))
RANGES = {
    "gate_near_y_m": [0.56, 0.64], "gate_far_y_m": [2.16, 2.24],
    "gate_near_bias_x_m": [-0.005, 0.005], "gate_far_bias_x_m": [-0.005, 0.005],
    "gate_near_L_jitter_x_m": [-0.01, 0.01], "gate_near_R_jitter_x_m": [-0.01, 0.01],
    "gate_far_L_jitter_x_m": [-0.01, 0.01], "gate_far_R_jitter_x_m": [-0.01, 0.01],
    "gate_near_clear_width_m": [0.38, 0.40], "gate_far_clear_width_m": [0.38, 0.40],
    "global_translation_x_m": [-0.12, 0.12],
    "control_near_scale": [0.95, 1.05], "control_far_scale": [0.95, 1.05],
}


def parameters(index):
    return {k: low + (high - low) * (parameter_word(index, k) / (2**64 - 1))
            for k, (low, high) in RANGES.items()}


def band_pairs(index):
    return {which: list(PAIRS[parameter_word(index, f"gate_{which}_band_pair") % 3])
            for which in ("near", "far")}


def camera_design(index):
    camera = old_camera_design(index)
    for segment in camera["segments"]:
        segment["y_m"] = [-0.2 if y == -0.1 else y for y in segment["y_m"]]
    return camera


def manifest(proposal):
    require(digest(proposal) == PROPOSAL_DIGEST, "accepted D-082 proposal changed")
    order = sorted(range(64), key=lambda i: (hashlib.sha256(f"sh04-r4-v1:split:{i}".encode()).digest(), i))
    rows, offset = [], 0
    for split, count in zip(SPLITS, COUNTS):
        for rank, index in enumerate(order[offset:offset + count]):
            p, pairs, camera = parameters(index), band_pairs(index), camera_design(index)
            normalized = {k: v for k, v in p.items() if k != "global_translation_x_m"}
            rows.append({"family_id": f"r4-{index:02d}", "index": index, "split": split,
                         "split_rank": rank, "parameters": p, "band_pairs": pairs, "camera": camera,
                         "normalized_design_sha256": digest({"parameters": normalized, "band_pairs": pairs, "camera": camera})})
        offset += count
    require(len({r["normalized_design_sha256"] for r in rows}) == 64, "duplicate normalized design")
    return {"version": VERSION, "protocol_sha256": digest(proposal), "rows": rows,
            "engineering_family_ids": [r["family_id"] for r in rows[:4]],
            "confirmation_observations_generated": False}


def validate_manifest(value, proposal):
    require(value == manifest(proposal), "manifest differs from deterministic D-082 inventory")


def engineering_rows(value):
    require(value["version"] == VERSION, "v2 design required")
    rows = value["rows"][:4]
    ids = ["r4-39", "r4-47", "r4-25", "r4-03"]
    require([r["family_id"] for r in rows] == value["engineering_family_ids"] == ids,
            "fixed first four families only")
    require(all(r["split"] == "model_train" and r["split_rank"] == i for i, r in enumerate(rows)), "split changed")
    return deepcopy(rows)


def control_phases(near_scale, far_scale):
    """Only two independent control draws enter this function, no geometry."""
    require(type(near_scale) in (int, float) and 0.95 <= near_scale <= 1.05
            and type(far_scale) in (int, float) and 0.95 <= far_scale <= 1.05, "control scale range")
    result = {}
    for near in range(3):
        for far in range(3):
            qn, qf = BANDS[near] * near_scale, BANDS[far] * far_scale
            result[f"c{near}{far}"] = [0, .02 * qn / .12, .04 * qn / .12, .02 * qn / .12, 0,
                                       .02 * (qf - qn) / .24, .04 * (qf - qn) / .24,
                                       .02 * (qf - qn) / .24, 0, 0]
    return result


def _derive(base, index):
    require(digest(base) == BASE_DIGEST, "unchanged D-071 base required")
    p, pairs, camera = parameters(index), band_pairs(index), camera_design(index)
    value = deepcopy(base)
    value.update(version=FAMILY_VERSION, status="review_only", numeric_protocol_approved=False,
                 generation_authorized=False, training_authorized=False, approval_decision="D-084",
                 registration={"index": index, "base_template": deepcopy(base)})
    g, o = value["geometry"], value["observation"]
    tx = p["global_translation_x_m"]
    g["gate_y_m"] = [p[f"gate_{which}_y_m"] for which in ("near", "far")]
    g["gate_centers_x_m"] = [
        {side: tx + BANDS[pairs[which][i]] + p[f"gate_{which}_bias_x_m"] + p[f"gate_{which}_{side}_jitter_x_m"]
         for i, side in enumerate(("L", "R"))} for which in ("near", "far")]
    g["gate_widths_m"] = [p[f"gate_{which}_clear_width_m"] for which in ("near", "far")]
    del g["gate_center_x_m"], g["gate_clear_width_m"]
    for key in ("cross_wall_outer_x_m", "side_wall_inner_x_m"):
        g[key] = [v + tx for v in g[key]]
    for key in ("object_initial_position_m", "pusher_initial_position_m"):
        g[key][0] += tx
    o.update(resolution=[80, 80], camera_fovy_degrees=42, camera_height_m=1.4,
             camera_x_m=o["camera_x_m"] + tx, future_camera_y_m=-0.2,
             camera_segments=camera["segments"], fixed_view_frame_indices=camera["view_frame_indices"])
    value["controls"].update(phase_duration_s=[1.6, .2, 2.8, .2, .8, .2, 5.8, .2, 3.0, 5.2],
                             phase_vy_mps=[.1, .2, .2, .2, .2, .2, .2, .2, .2, 0], phase_vz_mps=[0] * 10,
                             phase_vx_mps=control_phases(p["control_near_scale"], p["control_far_scale"]))
    task = value["task_success"]
    task["goal_center_xy_m"][0] += tx
    task["goal_x_bounds_m"] = [v + tx for v in task["goal_x_bounds_m"]]
    value["budget_proposal"].update(unique_control_branches=36, independent_replay_branches=36,
                                    new_output_limit_bytes=384 * 1024**2, generation_wall_clock_limit_s=7200)
    return value


def family_config(base, row):
    index = row["index"]
    require(row["parameters"] == parameters(index) and row["camera"] == camera_design(index)
            and row["band_pairs"] == band_pairs(index), "registered row changed")
    return _derive(base, index)


def validate_family_config(value):
    require(isinstance(value, dict) and value.get("version") == FAMILY_VERSION, "v2 family config required")
    registration = value["registration"]
    expected = _derive(registration["base_template"], registration["index"])
    require(encode(value) == encode(expected), "config differs from exact registered v2 derivation")


def xml_template_view(config):
    """Intermediate XML scaffold only; caller replaces both gate wall pairs.

    Not a public, scoring or old-test compatibility contract. No controls are
    changed, and the final physical scene retains the complete v2 config.
    """
    value = deepcopy(config)
    g = value["geometry"]
    g["gate_center_x_m"] = g.pop("gate_centers_x_m")[0]
    g["gate_clear_width_m"] = g.pop("gate_widths_m")[0]
    return value


def controls(config):
    validate_family_config(config)
    c = config["controls"]
    result = {}
    for action in ACTIONS:
        expanded = []
        for duration, vx, vy, vz in zip(c["phase_duration_s"], c["phase_vx_mps"][action], c["phase_vy_mps"], c["phase_vz_mps"]):
            expanded.extend({"duration_s": .1, "ee_velocity_mps": [vx, vy, vz]} for _ in range(round(duration / .1)))
        require(len(expanded) == 200, "registered control count")
        result[action] = expanded
    require(len({digest(v) for v in result.values()}) == 9, "duplicate numerical candidates")
    return result


def categorical_shortcut(matrices):
    require(bool(matrices), "no development matrices")
    intersections = {w: set(range(9)) for w in NAMES}
    for matrix in matrices:
        require(set(matrix) == set(NAMES), "incomplete worlds")
        for world in NAMES:
            require(set(matrix[world]) == set(ACTIONS) and all(type(v) is bool for v in matrix[world].values()), "invalid nine-action matrix")
            best = max(matrix[world].values())
            intersections[world] &= {i for i, a in enumerate(ACTIONS) if matrix[world][a] == best}
    return {"optimal_index_intersections": {w: sorted(v) for w, v in intersections.items()},
            "categorical_shortcut_unexcluded": all(intersections.values()), "development_family_count": len(matrices)}
