"""Validate paired records and expose only observation/control inputs.

This is an interface audit, not a renderer or physics validator. See docs/DATA.md.
No simulator, numerical library, legacy CPMT module, or filesystem is accessed.
"""
from copy import deepcopy
import math


VERSION = "spatial-history-pair-v1"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keys(value, expected, where):
    require(isinstance(value, dict), f"{where}: expected object")
    require(set(value) == set(expected.split()), f"{where}: unexpected/missing fields")


def number(value, where):
    require(type(value) in (int, float), f"{where}: finite number required")
    try:
        require(math.isfinite(value), f"{where}: finite number required")
    except OverflowError as error:
        raise ValueError(f"{where}: number outside supported range") from error


def vector(value, size, where):
    require(isinstance(value, list) and len(value) == size, f"{where}: expected {size} values")
    for item in value:
        number(item, where)


def digest(value, where):
    require(isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value), f"{where}: invalid SHA256")


def label(value, where):
    require(isinstance(value, str) and value.strip(), f"{where}: nonempty string required")


def frame(value, where):
    keys(value, "time_s width height rgb depth_m camera_position_m camera_xyzw "
         "intrinsics ee_position_m ee_velocity_mps previous_velocity_mps", where)
    number(value["time_s"], where)
    require(value["time_s"] >= 0, f"{where}: negative time")
    for dim in ("width", "height"):
        require(type(value[dim]) is int and value[dim] > 0, f"{where}: invalid {dim}")
    pixels = value["width"] * value["height"]
    require(isinstance(value["rgb"], list) and len(value["rgb"]) == pixels * 3,
            f"{where}: RGB shape mismatch")
    require(all(type(v) is int and 0 <= v <= 255 for v in value["rgb"]), f"{where}: invalid RGB")
    vector(value["depth_m"], pixels, where)
    require(all(v >= 0 for v in value["depth_m"]), f"{where}: negative depth")
    for name in ("camera_position_m", "ee_position_m", "ee_velocity_mps", "previous_velocity_mps"):
        vector(value[name], 3, f"{where}.{name}")
    vector(value["camera_xyzw"], 4, where)
    require(abs(sum(v * v for v in value["camera_xyzw"]) - 1) < 1e-6, f"{where}: quaternion norm")
    vector(value["intrinsics"], 4, where)
    require(value["intrinsics"][0] > 0 and value["intrinsics"][1] > 0, f"{where}: focal length")


def actions_valid(actions):
    require(isinstance(actions, list) and len(actions) == 2, "exactly two candidate controls required")
    for action in actions:
        require(isinstance(action, list) and action, "empty control sequence")
        for control in action:
            keys(control, "duration_s ee_velocity_mps", "control")
            number(control["duration_s"], "control.duration_s")
            require(control["duration_s"] > 0, "nonpositive control duration")
            vector(control["ee_velocity_mps"], 3, "control.ee_velocity_mps")
            require(control["ee_velocity_mps"][2] == 0, "first contract is planar")
    require(actions[0] != actions[1], "duplicate candidate controls")
    require([c["duration_s"] for c in actions[0]] == [c["duration_s"] for c in actions[1]],
            "candidates must share sampling times and horizon")


def world_valid(world, actions, where):
    keys(world, "history initial_state hidden_obstacles branches", where)
    history = world["history"]
    require(isinstance(history, list) and history, f"{where}: empty history")
    for index, value in enumerate(history):
        frame(value, f"{where}.history[{index}]")
    require(all(a["time_s"] < b["time_s"] for a, b in zip(history, history[1:])),
            f"{where}: history not strictly chronological")
    require(len({(f["width"], f["height"]) for f in history}) == 1, f"{where}: resolution changed")
    state = world["initial_state"]
    keys(state, "object_position_m object_velocity_mps ee_position_m ee_velocity_mps", where)
    for name, value in state.items():
        vector(value, 3, name)
    for name in ("ee_position_m", "ee_velocity_mps"):
        require(state[name] == history[-1][name], f"{where}: robot state does not match last frame")
    obstacles = world["hidden_obstacles"]
    require(isinstance(obstacles, list) and obstacles, f"{where}: missing hidden layout")
    for bounds in obstacles:
        vector(bounds, 6, "obstacle min_xyz,max_xyz")
        require(all(bounds[i] < bounds[i + 3] for i in range(3)), "invalid obstacle extent")
    branches = world["branches"]
    require(isinstance(branches, list) and len(branches) == len(actions), "missing/extra branches")
    for index, branch in enumerate(branches):
        keys(branch, "action_index base_snapshot_sha256 future", "branch")
        require(type(branch["action_index"]) is int and branch["action_index"] == index,
                "branch action order mismatch")
        digest(branch["base_snapshot_sha256"], "branch.base_snapshot_sha256")
        future = branch["future"]
        require(isinstance(future, list) and len(future) == len(actions[index]), "future length mismatch")
        time = history[-1]["time_s"]
        for control, sample in zip(actions[index], future):
            keys(sample, "time_s object_position_m contact", "future")
            number(sample["time_s"], "future.time_s")
            time += control["duration_s"]
            require(math.isclose(sample["time_s"], time, rel_tol=0, abs_tol=1e-9), "future time mismatch")
            vector(sample["object_position_m"], 3, "future.object_position_m")
            require(type(sample["contact"]) is bool, "contact must be boolean")
    require(len({b["base_snapshot_sha256"] for b in branches}) == 1,
            "branches did not declare the same immutable base")


def audit_pair(pair):
    """Return diagnostic booleans; equal outcomes remain valid records.

    Raises ValueError for malformed records or broken pairing. Snapshot hashes
    are declarations here: actual restore/render/replay requires another module.
    """
    keys(pair, "schema_version pair_id family_id split provenance recent_frames "
         "control_kind goal actions worlds", "pair")
    require(pair["schema_version"] == VERSION, "schema version mismatch")
    for name in ("pair_id", "family_id"):
        label(pair[name], name)
    require(pair["split"] == "development", "v1 only admits development records; no test access")
    require(pair["control_kind"] == "ee_velocity_world_mps", "unsupported control semantics")
    provenance = pair["provenance"]
    keys(provenance, "kind simulator seed code_sha256 config_sha256", "provenance")
    require(provenance["kind"] in ("hand_authored_fixture", "simulator_export"), "invalid origin kind")
    label(provenance["simulator"], "simulator")
    require(type(provenance["seed"]) is int and provenance["seed"] >= 0, "invalid seed")
    for name in ("code_sha256", "config_sha256"):
        digest(provenance[name], name)
    keys(pair["goal"], "center_m radius_m", "goal")
    vector(pair["goal"]["center_m"], 3, "goal.center_m")
    number(pair["goal"]["radius_m"], "goal.radius_m")
    require(pair["goal"]["radius_m"] > 0, "invalid goal radius")
    actions_valid(pair["actions"])
    worlds = pair["worlds"]
    require(isinstance(worlds, list) and len(worlds) == 2, "exactly two paired worlds required")
    for index, world in enumerate(worlds):
        world_valid(world, pair["actions"], f"worlds[{index}]")
    left, right = worlds
    n = pair["recent_frames"]
    require(type(n) is int and 0 < n < len(left["history"]), "need early and recent history")
    require(len(left["history"]) == len(right["history"]), "history length shortcut")
    require(left["history"][-n:] == right["history"][-n:], "recent sensor/control inputs differ")
    # Early camera path, timestamps and robot motion must not encode the layout.
    for a, b in zip(left["history"], right["history"]):
        require({k: v for k, v in a.items() if k not in ("rgb", "depth_m")}
                == {k: v for k, v in b.items() if k not in ("rgb", "depth_m")},
                "camera/time/robot metadata shortcut")
    require(left["initial_state"] == right["initial_state"], "non-layout physical state differs")
    require(left["hidden_obstacles"] != right["hidden_obstacles"], "hidden layouts must differ")
    return {
        "pair_id": pair["pair_id"], "contract_valid": True,
        "origin_kind": provenance["kind"],
        "early_visual_evidence_differs": left["history"][:-n] != right["history"][:-n],
        "outcomes_differ_by_action": [a["future"] != b["future"]
                                      for a, b in zip(left["branches"], right["branches"])],
        "physics_and_visibility_verified": False,
    }


def model_input(pair, world_index, action_index, *, recent_only=False):
    """Deep-copy the allowlist. IDs, hashes, initial truth and futures never leave.

    Indices select records in the loader; they are not returned as model features.
    The audit is offline. Deployed models consume this output, not the paired file.
    """
    audit_pair(pair)
    require(type(world_index) is int and world_index in (0, 1), "invalid world index")
    require(type(action_index) is int and action_index in (0, 1), "invalid action index")
    require(type(recent_only) is bool, "recent_only must be boolean")
    history = pair["worlds"][world_index]["history"]
    if recent_only:
        history = history[-pair["recent_frames"]:]
    return deepcopy({"history": history, "controls": pair["actions"][action_index], "goal": pair["goal"]})


def audit_dataset(pairs):
    """Audit all supplied development pairs; never retain only differing outcomes."""
    require(isinstance(pairs, list) and pairs, "empty dataset")
    reports = [audit_pair(pair) for pair in pairs]
    require(len({pair["pair_id"] for pair in pairs}) == len(pairs), "duplicate pair_id")
    return reports
