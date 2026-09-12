"""Native v2 public histories and nine anonymous numerical candidate slots.

Information audit uses all 121 fixed-frame partitions and actual outcomes;
the audit's private world/action names never enter model features.
"""
from copy import deepcopy
import math

from .pair_contract import frame, keys, require
from .r4_families_v2 import ACTIONS, NAMES, controls, validate_family_config
from .r4_query_v2 import SOURCE_VERSION, _calibration, validate_goal, validate_controls
from .two_gate_contract import _canonical, _sha

VERSION = "spatial-history-r4-public-family-v2"


def _columns(rows):
    require(isinstance(rows, list) and len(rows) == 200, "200 public controls")
    for row in rows:
        keys(row, "duration_s ee_velocity_mps", "control row")
    return {name: [row[name] for row in rows] for name in ("duration_s", "ee_velocity_mps")}


def validate_public(public):
    keys(public, "schema_version history actions goal", "v2 public family")
    require(public["schema_version"] == VERSION, "v2 family envelope required")
    validate_goal(public["goal"])
    history = public["history"]
    require(isinstance(history, list) and len(history) == 121, "121 native history frames")
    for index, row in enumerate(history):
        frame(row, f"history[{index}]")
        require(row["width"] == row["height"] == 80, "native 80 by 80 required")
        require(math.isclose(row["time_s"], .5 + index / 10, rel_tol=0, abs_tol=1e-9), "history clock")
        _calibration(row, index, public["goal"]["goal_center_xy_m"][0])
    require(isinstance(public["actions"], list) and len(public["actions"]) == 9, "nine anonymous candidate slots")
    for rows in public["actions"]:
        validate_controls(_columns(rows))
    require(len({_canonical(rows) for rows in public["actions"]}) == 9, "duplicate public candidates")


def make_public(history, config):
    registry = controls(config)
    public = {"schema_version": VERSION, "history": history,
              "actions": [registry[a] for a in ACTIONS], "goal": deepcopy(config["task_success"])}
    validate_public(public)
    return public


def model_input(public, candidate_index, *, history_mode="full", history_cut_index=None):
    """Validate whole public record, select permitted frames; strip selectors."""
    from .r4_query_v2 import _history_indices
    validate_public(public)
    require(type(candidate_index) is int and 0 <= candidate_index < 9, "candidate slot 0..8")
    indices = _history_indices(history_mode, history_cut_index)
    return deepcopy({"schema_version": SOURCE_VERSION, "history": [public["history"][i] for i in indices],
                     "controls": public["actions"][candidate_index], "goal": public["goal"]})


def audit_family(public_worlds, outcomes, config):
    """Raw success matrix diagnostic; caller separately gates physical validity."""
    validate_family_config(config)
    keys(public_worlds, "LL LR RL RR", "public worlds")
    keys(outcomes, "LL LR RL RR", "outcomes")
    for world in NAMES:
        validate_public(public_worlds[world])
        keys(outcomes[world], " ".join(ACTIONS), "world outcomes")
        require(all(type(v) is bool for v in outcomes[world].values()), "boolean actual outcomes required")
    registry = controls(config)
    checks = {
        "registered_common_actions": all(p["actions"] == [registry[a] for a in ACTIONS] for p in public_worlds.values()),
        "registered_common_goal": all(p["goal"] == config["task_success"] for p in public_worlds.values()),
        "same_recent_public_inputs": len({_canonical(p["history"][-2:]) for p in public_worlds.values()}) == 1,
        "same_history_metadata": True,
        "each_world_has_success": all(sum(outcomes[w].values()) >= config["engineering_audit"]["minimum_successful_actions_each_world"] for w in NAMES),
    }
    for index in range(121):
        metadata = [{k: v for k, v in public_worlds[w]["history"][index].items() if k not in ("rgb", "depth_m")} for w in NAMES]
        checks["same_history_metadata"] &= len({_canonical(v) for v in metadata}) == 1
    bases = {w: _sha({"recent": public_worlds[w]["history"][-2:], "actions": public_worlds[w]["actions"],
                      "goal": public_worlds[w]["goal"]}) for w in NAMES}
    rows = []
    for index in range(121):
        partitions = {}
        for world in NAMES:
            key = (bases[world], _sha(public_worlds[world]["history"][index]))
            partitions.setdefault(key, []).append(world)
        groups, total_regret = [], 0.0
        for group in partitions.values():
            costs = {a: sum(not outcomes[w][a] for w in group) / len(group) for a in ACTIONS}
            oracle = sum(not any(outcomes[w].values()) for w in group) / len(group)
            regret = min(costs.values()) - oracle
            total_regret += len(group) / 4 * regret
            groups.append({"worlds": group, "action_expected_failure_cost": costs,
                           "fully_informed_expected_failure_cost": oracle, "information_regret": regret})
        rows.append({"frame_index": index, "equivalence_groups": groups, "information_regret": total_regret})
    threshold = config["engineering_audit"]["minimum_fixed_single_view_information_regret"]
    checks["every_fixed_single_view_information_regret"] = all(row["information_regret"] >= threshold for row in rows)
    return {"checks": checks, "contract_audit_passed": all(checks.values()), "accepted": all(checks.values()),
            "failed_checks": [k for k, v in checks.items() if not v], "frame_information": rows,
            "fixed_single_view_audit": rows, "minimum_information_regret": min(row["information_regret"] for row in rows),
            "outcomes": deepcopy(outcomes), "physics_and_geometry_recovery_verified": False}
