"""Frozen SH-04-R2 engineering steps, not a learner or an operations wrapper.

Each step writes only its fresh data directory. The operations parent seals the
result and artifact manifest before calling a dependent step. See METHOD/DATA.
MuJoCo is imported only inside the requested physical step, never for planning.
"""
import hashlib
import json
from pathlib import Path


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _tick(progress, **event):
    if progress is not None:
        progress(event)


def _read(path):
    path = Path(path)
    _require(path.is_file() and not path.is_symlink(), f"missing/unsafe input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path, value, progress):
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    _tick(progress, phase="write", reserve_bytes=len(raw), file=Path(path).name)
    with Path(path).open("xb") as handle:
        handle.write(raw)
    _tick(progress, phase="written", file=Path(path).name)


def _write_text(path, value, progress):
    raw = value.encode("utf-8")
    _tick(progress, phase="write", reserve_bytes=len(raw), file=Path(path).name)
    with Path(path).open("xb") as handle:
        handle.write(raw)


def _load_config(path):
    from .two_gate_contract import validate_config
    config = _read(path)
    validate_config(config)
    _require(config["numeric_protocol_approved"] is True
             and config["generation_authorized"] is True
             and config["training_authorized"] is False,
             "only the approved engineering protocol may execute")
    _require(config["status"] == "frozen_engineering_only", "non-executable protocol")
    return config


def step_ids(config):
    """The fixed inventory: four histories, 16 primary, 16 reverse, audit."""
    worlds = config["worlds"]
    _require(worlds == ["LL", "LR", "RL", "RR"], "unexpected engineering world inventory")
    return ([f"history-{w}" for w in worlds]
            + [f"primary-{w}-{a}" for w in worlds for a in worlds]
            + [f"replay-{w}-{a}" for w in reversed(worlds) for a in reversed(worlds)]
            + ["audit"])


def _unit(stage_directory, step_id):
    return Path(stage_directory) / "steps" / step_id


def _data(stage_directory, step_id):
    return _unit(stage_directory, step_id) / "data"


def _result(stage_directory, step_id):
    return _read(_unit(stage_directory, step_id) / "result.json")


def compare_replay(primary, replay):
    """Compare saved physical values/bytes, without comparing run timestamps."""
    fields = ("base_snapshot_sha256", "control_sha256", "state_spec", "state_shape",
              "sensor_count", "step_count", "files", "end_snapshot", "assessment")
    checks = {key: key in primary and key in replay and primary[key] == replay[key]
              for key in fields}
    return {"equal": all(checks.values()), "checks": checks,
            "different_fields": [key for key, equal in checks.items() if not equal]}


def observation_checks(publics, evidence, snapshots, config):
    """Audit raw rendered visibility independently of outcome labels."""
    worlds = config["worlds"]
    obs = config["observation"]
    count = obs["history_frame_count"]
    near = ("gate_0_left", "gate_0_right")
    far = ("gate_1_left", "gate_1_right")
    minimum = obs["minimum_each_gate_segment_pixels_in_designated_view"]
    checks = {
        "complete_history_evidence": True,
        "registered_sensor_resolution": True,
        "designated_near_view": True,
        "designated_far_view": True,
        "no_single_frame_sees_both_gates": True,
        "recent_object_and_pusher_visible": True,
        "recent_gates_invisible": True,
        "observation_preserves_integration": True,
        "same_nonlayout_integration": True,
    }
    reference = snapshots[worlds[0]]
    for world in worlds:
        item = evidence[world]
        visible = item["visibility"]
        complete = len(visible) == count and len(publics[world]["history"]) == count
        checks["complete_history_evidence"] &= complete
        height, width = obs["resolution"]
        checks["registered_sensor_resolution"] &= complete and all(
            row["height"] == height and row["width"] == width for row in publics[world]["history"])
        checks["observation_preserves_integration"] &= item["observation_preserves_integration"] is True
        checks["same_nonlayout_integration"] &= (
            snapshots[world]["state_spec"] == reference["state_spec"]
            and snapshots[world]["state"] == reference["state"])
        if not complete:
            for key in ("designated_near_view", "designated_far_view",
                        "no_single_frame_sees_both_gates", "recent_object_and_pusher_visible",
                        "recent_gates_invisible"):
                checks[key] = False
            continue
        for record in visible:
            _require(all(type(record.get(name)) is int and record[name] >= 0
                         for name in (*near, *far, "object", "pusher")),
                     "visibility must contain nonnegative actual pixel counts")
            _require(all(type(value) is int and 0 <= value <= height * width for value in record.values())
                     and sum(record.values()) <= height * width,
                     "segmentation geometry counts exceed the registered sensor pixels")
            checks["no_single_frame_sees_both_gates"] &= not (
                sum(record[n] for n in near) > 0 and sum(record[n] for n in far) > 0)
        a = visible[obs["fixed_view_frame_indices"]["A"]]
        b = visible[obs["fixed_view_frame_indices"]["B"]]
        checks["designated_near_view"] &= all(a[n] >= minimum for n in near) and all(a[n] == 0 for n in far)
        checks["designated_far_view"] &= all(b[n] >= minimum for n in far) and all(b[n] == 0 for n in near)
        for record in visible[-obs["recent_frames"]:]:
            checks["recent_object_and_pusher_visible"] &= record["object"] > 0 and record["pusher"] > 0
            checks["recent_gates_invisible"] &= all(record[n] == 0 for n in (*near, *far))
    return checks


def _history_step(directory, config, config_path, world, progress):
    from .two_gate_contract import make_public
    from .two_gate_physics import TwoGateScene, build_xml, save_png
    import numpy as np
    reference_path = Path(config_path).resolve().parents[2] / config["physics_reference"]
    reference = reference_path.read_bytes()
    _require(hashlib.sha256(reference).hexdigest() == config["physics_reference_sha256"],
             "physical reference bytes changed")
    xml = build_xml(reference.decode("utf-8"), config, world)
    directory.mkdir(parents=True, exist_ok=False)
    _write_text(directory / "world.xml", xml, progress)
    scene = TwoGateScene(xml, config)
    try:
        history, visibility = scene.history(progress=progress)
        snapshot = scene.snapshot()
        scene.observe()
        scene.visibility()
        preserves = scene.snapshot() == snapshot
        # Save actual records before public-input validation can reject them.
        _write_json(directory / "history.json", history, progress)
        _write_json(directory / "snapshot.json", snapshot, progress)
        evidence = {"visibility": visibility, "observation_preserves_integration": preserves}
        _write_json(directory / "observation_evidence.json", evidence, progress)
        public = make_public(history, config)
        _write_json(directory / "public.json", public, progress)
        chosen = {"first.png": 0, "view-a.png": config["observation"]["fixed_view_frame_indices"]["A"],
                  "view-b.png": config["observation"]["fixed_view_frame_indices"]["B"],
                  "recent.png": len(history) - 1}
        for name, index in chosen.items():
            row = history[index]
            rgb = np.asarray(row["rgb"], dtype=np.uint8).reshape(row["height"], row["width"], 3)
            save_png(directory / name, rgb, progress=progress)
        return {"kind": "history", "world": world, "history_frames": len(history),
                "observation_preserves_integration": preserves,
                "snapshot_sha256": scene.digest(snapshot),
                "public_schema_version": public["schema_version"]}
    finally:
        scene.close()


def _branch_step(directory, config, stage_directory, kind, world, action, progress):
    from .two_gate_contract import assess_trajectory, expand_controls
    from .two_gate_physics import TwoGateScene
    history_dir = _data(stage_directory, f"history-{world}")
    xml = (history_dir / "world.xml").read_text(encoding="utf-8")
    snapshot = _read(history_dir / "snapshot.json")
    controls = expand_controls(config)[action]
    scene = TwoGateScene(xml, config)
    try:
        result = scene.rollout(snapshot, controls, directory, world_name=world,
                               assessor=assess_trajectory, progress=progress)
    finally:
        scene.close()
    result.update(kind=kind, world=world, action=action)
    if kind == "replay":
        primary = _result(stage_directory, f"primary-{world}-{action}")
        result["replay_comparison"] = compare_replay(primary, result)
    return result


def _audit_step(directory, config, stage_directory, progress):
    from .two_gate_contract import audit_family
    directory.mkdir(parents=True, exist_ok=False)
    publics, visibility, snapshots = {}, {}, {}
    for world in config["worlds"]:
        root = _data(stage_directory, f"history-{world}")
        publics[world] = _read(root / "public.json")
        visibility[world] = _read(root / "observation_evidence.json")
        snapshots[world] = _read(root / "snapshot.json")
        _tick(progress, phase="read_history", world=world)
    checks = observation_checks(publics, visibility, snapshots, config)
    summaries, outcomes = [], {}
    physics_valid, critical_hidden, replay_equal, gate_contact = True, True, True, False
    for world in config["worlds"]:
        outcomes[world] = {}
        for action in config["worlds"]:
            primary = _result(stage_directory, f"primary-{world}-{action}")
            replay = _result(stage_directory, f"replay-{world}-{action}")
            assessment = primary["assessment"]
            comparison = compare_replay(primary, replay)
            physics_valid &= assessment["physics_valid"] is True
            critical_hidden &= assessment["visibility_valid"] is True
            replay_equal &= comparison["equal"]
            outcomes[world][action] = assessment["raw_task_success"]
            gate_contact |= assessment["gate_contact_steps"] > 0
            summaries.append({"world": world, "action": action, "assessment": assessment,
                              "replay_comparison": comparison,
                              "primary_step": f"primary-{world}-{action}",
                              "replay_step": f"replay-{world}-{action}"})
            _tick(progress, phase="read_branch", world=world, action=action)
    checks.update(all_physics_valid=physics_valid, all_critical_interactions_hidden=critical_hidden,
                  all_independent_replays_equal=replay_equal, actual_gate_contact_exists=gate_contact)
    # Even an invalid physical run keeps its raw outcome table for diagnosis.
    # Its information calculation cannot qualify as scientific evidence.
    information = audit_family(publics, outcomes, config)
    checks.update({f"public_information_{key}": value for key, value in information["checks"].items()})
    result = {
        "kind": "audit", "accepted": all(checks.values()), "checks": checks,
        "failed_checks": [key for key, value in checks.items() if not value],
        "success_matrix": outcomes,
        "success_matrix_is_valid_physical_evidence": physics_valid and replay_equal,
        "information_is_valid_physical_evidence": physics_valid and replay_equal,
        "information_audit": information, "branches": summaries,
        "public_geometry_recovery_verified": False,
        "model_experiment_run": False, "long_term_memory_claim_verified": False,
    }
    _write_json(directory / "audit.json", result, progress)
    return result


def run_step(step_id, directory, config_path, stage_directory, progress=None):
    """Execute one step; the caller verifies/seals dependencies and receipts.

    A false audit result is a completed engineering failure, not a runtime
    exception. Exceptions retain partial outputs and must never trigger retry.
    """
    config = _load_config(config_path)
    _require(step_id in step_ids(config), "step outside the approved fixed inventory")
    directory = Path(directory)
    expected = _data(stage_directory, step_id)
    _require(directory.resolve() == expected.resolve(), "step output path does not match its identity")
    _require(not directory.exists(), "partial/completed data already exists; never overwrite")
    _tick(progress, phase="start", step_id=step_id)
    if step_id == "audit":
        return _audit_step(directory, config, stage_directory, progress)
    parts = step_id.split("-")
    if parts[0] == "history":
        return _history_step(directory, config, config_path, parts[1], progress)
    return _branch_step(directory, config, stage_directory, *parts, progress)
