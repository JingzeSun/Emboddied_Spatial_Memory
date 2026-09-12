"""One fixed R4 engineering family: real histories, branches, replays and gates.

Caller owns source binding, resource supervision, release and exit receipts.
This module has no authority to choose a family or expand the inventory.
"""
import gzip
import json
from pathlib import Path

from .pair_contract import require
from .r4_families_v2 import controls, encode, digest, ACTIONS, validate_family_config
from .r4_storage import array_summary, file_record, inventory, read_json, write_json, compressed_writer
from .r4_public_v2 import VERSION, make_public, model_input, audit_family, validate_public
from .two_gate_engineering import observation_checks, compare_replay

NAMES = ("LL", "LR", "RL", "RR")


def save(path, value, progress=None):
    path = Path(path)
    raw = encode(value)
    if progress:
        progress({"phase": "write", "file": path.name, "reserve_bytes": len(raw)})
    with path.open("xb") as stream:
        stream.write(raw)


def contact_summary(samples, threshold):
    """Count positive-contact time steps per geom pair, not solver contacts."""
    pairs = {}
    count = 0
    first = last = None
    for sample in samples:
        require(sample['step_index'] == count, 'trace step order changed')
        count += 1
        state = {key: sample[key] for key in ('step_index', 'time_s', 'object_position_m',
                 'pusher_position_m', 'actuator_force_n')}
        if first is None:
            first = state
        last = state
        positive = {}
        for contact in sample['contacts']:
            names = tuple(sorted(contact['geoms']))
            if not {'object', 'pusher'}.intersection(names):
                continue
            if contact['distance_m'] > 0 or contact['normal_force_n'] <= threshold:
                continue
            # Several solver points in one step count once. Peak is a
            # single-point normal force, not total pair force.
            positive[names] = max(positive.get(names, 0), contact['normal_force_n'])
        for names, force in positive.items():
            if names not in pairs:
                pairs[names] = {'geoms': list(names), 'positive_steps': 0,
                                'first': state, 'peak_point_normal_force_n': -1}
            item = pairs[names]
            item['positive_steps'] += 1
            item['last'] = state
            if force > item['peak_point_normal_force_n']:
                item.update(peak_point_normal_force_n=force, peak=state)
    require(count == 10001, f'incomplete trace: {count} rows')
    return {'trace_rows': count, 'initial': first, 'terminal': last,
            'positive_contact_pairs': [pairs[key] for key in sorted(pairs)]}


def _history(root, config, reference, world, progress):
    from .r4_physics_v2 import R4SceneV2, build_xml
    from .two_gate_physics import save_png
    import numpy as np
    private = root / "audit" / world
    private.mkdir()
    xml = build_xml(reference, config, world)
    with (private / "world.xml").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(xml)
    scene = R4SceneV2(xml, config)
    try:
        with compressed_writer(private / "history_prefix.jsonl.gz", progress) as stream:
            def captured(record):
                stream.write(encode(record))
                stream.flush()
            history, visible = scene.history(progress=progress, frame_sink=captured)
        snapshot = scene.snapshot()
        scene.observe()
        scene.visibility()
        evidence = {"visibility": visible, "observation_preserves_integration": snapshot == scene.snapshot()}
        # Preserve sensor values before any validator can reject them.
        write_json(root / "public" / f"{world}.json.gz",
                   {"schema_version": VERSION, "history": history,
                    "actions": list(controls(config).values()), "goal": config["task_success"]}, progress)
        save(private / "snapshot.json", snapshot, progress)
        save(private / "observation.json", evidence, progress)
        public = make_public(history, config)
        from .r4_query_v2 import from_public_query
        # V2 value boundary; all candidate rows also pass validate_public.
        from_public_query(model_input(public, 0))
        for name, index in {"first": 0, "near": config["observation"]["fixed_view_frame_indices"]["A"],
                            "far": config["observation"]["fixed_view_frame_indices"]["B"], "recent": 120}.items():
            row = history[index]
            save_png(private / f"{name}.png", np.asarray(row["rgb"], dtype=np.uint8).reshape(80, 80, 3), progress=progress)
        return public, snapshot, evidence
    except BaseException as error:
        save(private / "history_failure.json", {"error": f"{type(error).__name__}: {error}",
                                               "actual_snapshot": scene.snapshot()})
        raise
    finally:
        scene.close()


def _geometry(root, publics, config, e0, progress):
    from .public_geometry import recover_openings
    destination = root / "audit" / "geometry"
    destination.mkdir()
    indices = config["observation"]["fixed_view_frame_indices"]
    modes = {"full": list(range(121)), "view_a": [indices["A"]], "view_b": [indices["B"]], "recent": [119, 120]}
    predictions = {}
    for world in NAMES:
        for mode, selected in modes.items():
            progress({"phase": "geometry_public", "world": world, "mode": mode})
            history = [publics[world]["history"][i] for i in selected]
            prediction = recover_openings(history, e0["public_sensor_spec"], e0["extractor"])
            identifier = f"{world}-{mode}"
            write_json(destination / f"{identifier}.json.gz", prediction, progress)
            predictions[identifier] = {"file": f"{identifier}.json.gz", "indices": selected,
                                       **file_record(destination / f"{identifier}.json.gz")}
    seal = {"predictions": predictions, "public_complete": True}
    save(destination / "public_seal.json", seal, progress)
    # Only after all public outputs are saved and bound does private evaluation
    # parse XML. Extractor receives no expected count, semantic index or target.
    from .public_geometry_audit import targets_from_xml, assess_geometry
    rows = []
    for world in NAMES:
        targets = targets_from_xml((root / "audit" / world / "world.xml").read_text(encoding="utf-8"))
        for mode in modes:
            record = predictions[f"{world}-{mode}"]
            path = destination / record["file"]
            require(file_record(path) == {k: record[k] for k in ("bytes", "sha256")}, "public E0 seal changed")
            subset = targets if mode == "full" else ([] if mode == "recent" else [targets[0 if mode == "view_a" else 1]])
            prediction = read_json(path)
            assessment = assess_geometry(prediction, subset, e0["evaluation_only"])
            rows.append({"world": world, "mode": mode, "assessment": assessment,
                         "rejected_counts": prediction["rejected_counts"],
                         "candidate_count": len(prediction["candidates"]),
                         "incomplete_count": len(prediction["incomplete_observations"]),
                         "conflict_count": len(prediction["conflicts"])})
    result = {"rows": rows, "accepted": all(r["assessment"]["accepted"] for r in rows),
              "public_seal": file_record(destination / "public_seal.json")}
    save(destination / "evaluation.json", result, progress)
    return result


def run_family(root, config, reference, e0, progress):
    """Never skip a branch because a physical/information/E0 gate is false."""
    from .r4_physics_v2 import R4SceneV2
    from .r4_trajectory_v2 import assess_trajectory
    from .r4_scoring_v2 import labels_from_trajectory
    validate_family_config(config)
    root = Path(root)
    require(not root.exists(), "family directory exists: never rerun or overwrite")
    root.mkdir()
    for channel in ("public", "labels", "audit"):
        (root / channel).mkdir()
    save(root / "audit" / "config.json", config, progress)
    publics, snapshots, evidence = {}, {}, {}
    results, replays, storage, contacts = {}, {}, {}, {}
    for world in NAMES:
        progress({"phase": "history_start", "world": world})
        publics[world], snapshots[world], evidence[world] = _history(root, config, reference, world, progress)
        save(root / "audit" / world / "history_complete.json", {"snapshot": file_record(root / "audit" / world / "snapshot.json"),
             "public": file_record(root / "public" / f"{world}.json.gz")}, progress)
    geometry = _geometry(root, publics, config, e0, progress)
    for kind, worlds in (("primary", NAMES), ("replay", tuple(reversed(NAMES)))):
        for world in worlds:
            actions = ACTIONS if kind == "primary" else tuple(reversed(ACTIONS))
            for action in actions:
                progress({"phase": "branch_start", "kind": kind, "world": world, "action": action})
                xml = (root / "audit" / world / "world.xml").read_text(encoding="utf-8")
                directory = root / "audit" / world / f"{kind}-{action}"
                scene = R4SceneV2(xml, config)  # Every branch/replay is a fresh simulator instance.
                try:
                    result = scene.rollout(snapshots[world], controls(config)[action], directory,
                                           world_name=world, assessor=assess_trajectory, progress=progress)
                finally:
                    scene.close()
                summaries = {p.name: array_summary(p) for p in sorted(directory.glob("*.npy.gz"))}
                require(len(summaries) == 5, "incomplete array inventory")
                storage[f"{kind}-{world}-{action}"] = summaries
                if kind == "primary":
                    results[world, action] = result
                    with gzip.open(directory / "trajectory.jsonl.gz", "rb") as stream:
                        samples = [json.loads(line) for line in stream]
                    assessment = {k: result["assessment"][k] for k in ("physics_valid", "visibility_valid", "task_success")}
                    labels = labels_from_trajectory(samples, assessment)
                    write_json(root / "labels" / f"{world}-{action}.json.gz",
                               {"labels": labels, "trajectory": file_record(directory / "trajectory.jsonl.gz")}, progress)
                    contacts[world, action] = contact_summary(samples, config["engineering_audit"]["contact_force_min_n"])
                    del samples
                else:
                    replays[world, action] = compare_replay(results[world, action], result)
                save(directory / "complete.json", {"exit_code": 0, "rollout": file_record(directory / "rollout.json"),
                                                   "arrays": summaries}, progress)
    checks = observation_checks(publics, evidence, snapshots, config)
    outcomes = {w: {a: results[w, a]["assessment"]["raw_task_success"] for a in ACTIONS} for w in NAMES}
    information = audit_family(publics, outcomes, config)
    checks.update({f"information_{k}": v for k, v in information["checks"].items()})
    information["valid_physical_evidence"] = all(r["assessment"]["physics_valid"] for r in results.values())
    checks.update(physics=all(r["assessment"]["physics_valid"] for r in results.values()),
                  critical_hidden=all(r["assessment"]["visibility_valid"] for r in results.values()),
                  replay_equal=all(r["equal"] for r in replays.values()),
                  actual_gate_contact=any(r["assessment"]["gate_contact_steps"] > 0 for r in results.values()),
                  public_geometry=geometry["accepted"])
    result = {"schema_version": "sh04-r4-family-result-v2", "accepted": all(checks.values()), "checks": checks,
              "failed_checks": [k for k, v in checks.items() if not v], "success_matrix": outcomes,
              "information_audit": information, "geometry": geometry,
              "branches": [{"world": w, "action": a, "assessment": results[w, a]["assessment"],
                             "replay": replays[w, a], "contacts": contacts[w, a]} for w in NAMES for a in ACTIONS],
              "array_storage": storage, "unique_branches": 36, "independent_replays": 36,
              "histories": 4, "model_experiment_run": False, "training_steps": 0, "weight_download_bytes": 0}
    result["storage_bytes_before_manifests"] = sum(r["bytes"] for r in inventory(root).values())
    result["array_raw_bytes"] = sum(a["raw_bytes"] for v in storage.values() for a in v.values())
    save(root / "audit" / "family_result.json", result, progress)
    for channel in ("public", "labels", "audit"):
        save(root / f"{channel}_manifest.json", inventory(root / channel), progress)
    return result


def verify_family(root):
    root = Path(root)
    for channel in ("public", "labels", "audit"):
        expected = json.loads((root / f"{channel}_manifest.json").read_text())
        require(expected == inventory(root / channel), f"{channel} manifest mismatch")
    result = json.loads((root / "audit" / "family_result.json").read_text())
    require(result["schema_version"] == "sh04-r4-family-result-v2", "v2 result required")
    config = json.loads((root / "audit" / "config.json").read_text())
    validate_family_config(config)
    registry = controls(config)
    summaries = {(r["world"], r["action"]): r for r in result["branches"]}
    require({p.name for p in (root / "public").glob("*.json.gz")} == {f"{w}.json.gz" for w in NAMES}, "missing public histories")
    require({p.name for p in (root / "labels").glob("*.json.gz")} == {f"{w}-{a}.json.gz" for w in NAMES for a in ACTIONS}, "missing labels")
    from .r4_scoring_v2 import validate_labels
    for world in NAMES:
        public = read_json(root / "public" / f"{world}.json.gz")
        validate_public(public)
        require(public["actions"] == [registry[a] for a in ACTIONS] and public["goal"] == config["task_success"], "public registration mismatch")
        for action in ACTIONS:
            record = read_json(root / "labels" / f"{world}-{action}.json.gz")
            validate_labels(record["labels"])
            require(record["trajectory"] == file_record(root / "audit" / world / f"primary-{action}" / "trajectory.jsonl.gz"), "label trajectory binding")
            directory = root / "audit" / world
            primary = json.loads((directory / f"primary-{action}" / "rollout.json").read_text())
            replay = json.loads((directory / f"replay-{action}" / "rollout.json").read_text())
            require(primary["control_sha256"] == digest(registry[action])
                    and replay["control_sha256"] == digest(registry[action]), "branch-to-control slot binding")
            branch = summaries[world, action]
            require(branch["assessment"] == primary["assessment"] and branch["replay"] == compare_replay(primary, replay), "branch/replay summary changed")
            require(result["success_matrix"][world][action] == primary["assessment"]["raw_task_success"], "outcome slot binding")
            for name in ("physics_valid", "visibility_valid", "task_success"):
                require(record["labels"][name] == primary["assessment"][name], "label/assessment mismatch")
    require(result["unique_branches"] == result["independent_replays"] == 36 and result["histories"] == 4,
            "family counts changed")
    require(set(result["array_storage"]) == {f"{k}-{w}-{a}" for k in ("primary", "replay") for w in NAMES for a in ACTIONS}, "incomplete branch array census")
    require([(r["world"], r["action"]) for r in result["branches"]] == [(w, a) for w in NAMES for a in ACTIONS], "branch order/census")
    for key, expected in result["array_storage"].items():
        kind, world, action = key.split("-")
        directory = root / "audit" / world / f"{kind}-{action}"
        require({p.name: array_summary(p) for p in directory.glob("*.npy.gz")} == expected, "array roundtrip changed")
        shapes = {"rgb.npy.gz": ([201, 80, 80, 3], "|u1"), "depth.npy.gz": ([201, 80, 80], "<f8"),
                  "integration.npy.gz": ([10001, 67], "<f8"), "sensor_times.npy.gz": ([201], "<f8"),
                  "sensor_step_indices.npy.gz": ([201], "<i8")}
        require(set(expected) == set(shapes), "five complete arrays required")
        for name, (shape, dtype) in shapes.items():
            require(expected[name]["shape"] == shape and expected[name]["dtype"] == dtype, "native array dimensions/dtype changed")
        complete = json.loads((directory / "complete.json").read_text())
        require(complete["exit_code"] == 0 and complete["arrays"] == expected
                and complete["rollout"] == file_record(directory / "rollout.json"), "branch completion binding")
    require(result["accepted"] == all(result["checks"].values()), "false accepted flag")
    return result
