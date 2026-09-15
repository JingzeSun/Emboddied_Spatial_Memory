#!/usr/bin/env python3
"""Private v3 fixed-slot action capability probe; never constructs an episode."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

try:
    import resource
except ImportError:  # Pure local tests run on Windows; server main requires it.
    resource = None

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import vm04_two_house_worker as generator  # noqa: E402
from vsmt.vm04_target_contract import validate_target_boundary_proposal  # noqa: E402
from vsmt.vm04_target_eligibility import authored_asset_ids  # noqa: E402
from vsmt.vm04_target_selection_v3 import select_private_targets_at_fixed_pose  # noqa: E402
from vsmt.two_house_audit import validate_episode_plans  # noqa: E402

REGISTERED_CAMERA_FRAME_COUNT = 32


def metadata_objects(event):
    return {str(row["objectId"]): dict(row)
            for row in event.metadata.get("objects", [])
            if type(row) is dict and type(row.get("objectId")) is str}


def visible_pixels(event, object_id):
    mask = event.instance_masks.get(object_id)
    if mask is None:
        return 0
    if hasattr(mask, "sum"):
        return int(mask.sum())
    return sum(int(pixel) for row in mask for pixel in row)


def target_poststate(event, targets):
    objects = metadata_objects(event)
    return [{"object_id": object_id,
             "present_in_metadata": object_id in objects,
             "visible_mask_pixels": visible_pixels(event, object_id),
             "position": objects.get(object_id, {}).get("position")}
            for object_id in targets]


def probe_intervention_path(controller, program, replicate, targets, initial_objects):
    """Record every attempted simulator action before reporting any failure."""
    attempts = []
    agent_actions = 0
    last_event = None
    disabled_targets = set()
    for frame_index in [-1] + list(range(REGISTERED_CAMERA_FRAME_COUNT)):
        try:
            edits = generator.intervention_actions(
                program, frame_index, targets, initial_objects)
        except Exception as error:
            return ("missing_action_precondition", attempts, agent_actions,
                    {"frame_index": frame_index, "error_type": type(error).__name__,
                     "error": str(error)}, last_event)
        for edit in edits:
            record = {"phase": "external_intervention", "frame_index": frame_index,
                      "arguments": edit}
            try:
                last_event = controller.step(**edit)
                diagnostic = generator.intervention_event_diagnostic(last_event)
                record["diagnostic"] = diagnostic
                record["target_poststate"] = target_poststate(last_event, targets)
                attempts.append(record)
                if diagnostic["last_action_success"] is not True:
                    return "intervention_rejected", attempts, agent_actions, None, last_event
                if (edit["action"] == "DisableObject" and
                        visible_pixels(last_event, edit["objectId"]) != 0):
                    record["poststate_mismatch"] = (
                        "DisableObject accepted but target mask remains visible")
                    return ("intervention_poststate_mismatch", attempts,
                            agent_actions, None, last_event)
                if edit["action"] == "DisableObject":
                    disabled_targets.add(edit["objectId"])
                elif edit["action"] == "EnableObject":
                    disabled_targets.discard(edit["objectId"])
            except Exception as error:
                record.update(exception_type=type(error).__name__,
                              exception=str(error))
                attempts.append(record)
                return "intervention_exception", attempts, agent_actions, None, last_event
        if frame_index < 0:
            continue
        camera_action, _ = generator.registered_agent_action(replicate, frame_index)
        record = {"phase": "registered_camera_action", "frame_index": frame_index,
                  "arguments": camera_action}
        try:
            last_event = controller.step(**camera_action)
            agent_actions += 1
            diagnostic = generator.intervention_event_diagnostic(last_event)
            record["diagnostic"] = diagnostic
            record["target_poststate"] = target_poststate(last_event, targets)
            attempts.append(record)
            if diagnostic["last_action_success"] is not True:
                return "registered_agent_action_rejected", attempts, agent_actions, None, last_event
            if any(visible_pixels(last_event, object_id) != 0
                   for object_id in disabled_targets):
                record["poststate_mismatch"] = (
                    "disabled target mask reappeared before registered EnableObject")
                return ("disabled_target_reappeared_between_actions",
                        attempts, agent_actions, None, last_event)
        except Exception as error:
            record.update(exception_type=type(error).__name__, exception=str(error))
            attempts.append(record)
            return "registered_agent_action_exception", attempts, agent_actions, None, last_event
    return "actions_accepted", attempts, agent_actions, None, last_event


def terminal_verdict(program, targets, initial_objects, terminal_event, contract,
                     relink_tolerance_m):
    """Verify simulator terminal evidence without asserting memory semantics."""
    if terminal_event is None:
        return "terminal_event_missing", []
    states = target_poststate(terminal_event, targets)
    minimum = contract["minimum_mask_pixels"]
    if program in ("BIRTH", "REACTIVATE"):
        valid = states[0]["present_in_metadata"] and\
            states[0]["visible_mask_pixels"] >= minimum
    elif program == "RETRACT":
        valid = states[0]["visible_mask_pixels"] == 0
    elif program == "REPLACE":
        valid = (states[0]["visible_mask_pixels"] == 0 and
                 states[1]["present_in_metadata"] and
                 states[1]["visible_mask_pixels"] >= minimum)
    elif program == "RELINK":
        before = initial_objects[targets[0]]["position"]
        after = states[0]["position"]
        expected = {"x": float(before["x"]) + 0.5,
                    "y": float(before["y"]), "z": float(before["z"])}
        valid = (states[0]["present_in_metadata"] and type(after) is dict and
                 all(type(after.get(axis)) in (int, float) and
                     abs(float(after[axis]) - expected[axis]) <= relink_tolerance_m
                     for axis in ("x", "y", "z")))
        states[0]["planned_position"] = expected
        states[0]["terminal_position_tolerance_m"] = relink_tolerance_m
        states[0]["collision_or_reachability_checked"] = False
        states[0]["force_action_used_by_registered_action"] = True
    else:
        raise ValueError("terminal verdict requires a physical program")
    if not valid:
        return "terminal_poststate_mismatch", states
    if program == "RELINK":
        return "relink_forced_action_terminal_verified_collision_unchecked", states
    return "visibility_action_terminal_verified_memory_unchecked", states


def probe_slot(house, assignment, pose, scan_top2, contract, *,
               relink_tolerance_m):
    """Probe the original slot at its frozen pose; no target or house fallback."""
    program = assignment["program"]
    result = {
        "schema_version": "vsmt-vm04-private-target-action-probe-slot-v2",
        "episode_id": assignment["episode_id"], "slot": assignment["slot"],
        "program": program, "replicate": assignment["replicate"],
        "scan_top2_instance_ids": scan_top2[:2], "live_scan_top2_instance_ids": [],
        "v3_target_instance_ids": [], "actions": [], "terminal_target_states": [],
        "agent_action_count": 0, "memory_history_checked": False,
        "semantic_positive_label_issued": False, "status": "not_started",
    }
    if program not in contract["physical_intervention_programs"]:
        result["status"] = "non_intervention_public_region_out_of_probe_scope"
        return result
    controller = None
    try:
        controller = generator.make_controller(house)
        initial_event = generator.teleport_to_initial_viewpoint(controller, pose)
        result["initial_teleport_diagnostic"] = (
            generator.intervention_event_diagnostic(initial_event))
        if initial_event.metadata.get("lastActionSuccess") is not True:
            result["status"] = "initial_pose_rejected"
            return result
        initial_objects = metadata_objects(initial_event)
        live_top2 = generator.rank_visible_instance_ids(
            initial_event.instance_masks, set(initial_objects))[:2]
        result["live_scan_top2_instance_ids"] = live_top2
        if live_top2 != scan_top2[:2]:
            result["status"] = "scan_live_scene_mismatch"
            return result
        assets = authored_asset_ids(house)
        try:
            targets = select_private_targets_at_fixed_pose(
                program, initial_event.instance_masks, initial_objects, assets,
                contract=contract)
        except Exception as error:
            result.update(status="fixed_slot_target_eligibility_failed",
                          eligibility_error_type=type(error).__name__,
                          eligibility_error=str(error))
            return result
        result["v3_target_instance_ids"] = targets
        result["metadata_object_capabilities"] = (
            generator.audit_intervention_capabilities(program, targets,
                                                      initial_objects))
        status, attempts, count, failure, terminal_event = probe_intervention_path(
            controller, program, assignment["replicate"], targets, initial_objects)
        result.update(status=status, actions=attempts, agent_action_count=count)
        if failure is not None:
            result["path_failure"] = failure
        if terminal_event is not None:
            result["terminal_target_states"] = target_poststate(terminal_event, targets)
        if status == "actions_accepted":
            verdict, states = terminal_verdict(
                program, targets, initial_objects, terminal_event, contract,
                relink_tolerance_m)
            result.update(status=verdict, terminal_target_states=states)
        return result
    except Exception as error:
        result.update(status="probe_exception", exception_type=type(error).__name__,
                      exception=str(error))
        return result
    finally:
        if controller is not None:
            try:
                controller.stop()
            except Exception as error:
                result["status"] = "controller_stop_exception"
                result["controller_stop_error_type"] = type(error).__name__
                result["controller_stop_error"] = str(error)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-stage", type=Path, required=True)
    parser.add_argument("--probe-stage", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--family-id", required=True)
    parser.add_argument("--maximum-slot-json-bytes", type=int, required=True)
    parser.add_argument("--maximum-address-space-bytes", type=int, required=True)
    parser.add_argument("--benchmark-only", action="store_true")
    args = parser.parse_args()
    generator.require(resource is not None, "v3 probe worker requires Linux resource limits")
    contract_path = ROOT / "configs/vsmt/vm04_target_boundary_proposal_v3.json"
    probe_config_path = ROOT / "configs/vsmt/vm04_target_action_probe_proposal_v2.json"
    contract = validate_target_boundary_proposal(generator.read_json(contract_path))
    probe_config = generator.read_json(probe_config_path)
    generator.require(contract["status"] == "frozen_target_probe_only" and
                      contract["target_capability_probe_authorized"] is True and
                      contract["generation_authorized"] is False and
                      probe_config["status"] == "frozen_probe_only" and
                      probe_config["probe_execution_authorized"] is True and
                      probe_config["generation_authorized"] is False,
                      "v3 target probe worker execution gate is closed")
    generator.require(generator.sha256(contract_path) ==
                      probe_config["v3_target_contract_sha256"],
                      "v3 probe contract digest changed")
    resource.setrlimit(resource.RLIMIT_AS, (
        args.maximum_address_space_bytes, args.maximum_address_space_bytes))
    scan = args.scan_stage.resolve()
    generator.require(generator.sha256(scan / "scan.receipt.json") ==
                      probe_config["source_scan_receipt_sha256"],
                      "frozen scan receipt changed")
    scan_receipt = generator.read_json(scan / "scan.receipt.json")
    generator.require(scan_receipt["worker_code_sha256"] ==
                      generator.sha256(ROOT / "ops/vsmt/vm04_two_house_worker.py"),
                      "registered action code differs from scanned source")
    family_id = args.family_id
    generator.require(family_id in contract["fixed_family_ids"],
                      "unknown fixed family")
    plans = validate_episode_plans({
        "public": generator.read_json(scan / "public/episode_plan.json"),
        "private": generator.read_json(scan / "private/episode_plan.json"),
    })
    public_plan, private_plan = plans["public"], plans["private"]
    generator.require(public_plan["manifest_sha256"] ==
                      probe_config["source_public_episode_manifest_sha256"] and
                      private_plan["manifest_sha256"] ==
                      probe_config["source_private_episode_manifest_sha256"],
                      "frozen private/public episode plan manifests changed")
    rows = sorted((row for row in public_plan["episodes"]
                   if row["family_id"] == family_id), key=lambda row: row["slot"])
    assignments = {row["episode_id"]: row for row in private_plan["assignments"]
                   if row["family_id"] == family_id}
    generator.require(len(rows) == len(assignments) == 18 and
                      [row["slot"] for row in rows] == list(range(18)) and
                      {row["episode_id"] for row in rows} == set(assignments),
                      "v3 probe requires the frozen 18 slots")
    house_ids = {row["source_house_id"] for row in assignments.values()}
    generator.require(len(house_ids) == 1, "one fixed house per family required")
    house_id = next(iter(house_ids))
    generator.require(house_id == contract["fixed_source_house_ids"][
        contract["fixed_family_ids"].index(family_id)],
        "v3 family/source house binding changed")
    inventory = generator.read_json(scan / "private/inventory.json")
    inventory_row = next(row for row in inventory["houses"]
                         if row["house_id"] == house_id)
    locator = inventory_row["source_locator"]
    source = args.source_root.resolve()
    source_file = (source / locator["relative_path"]).resolve()
    generator.require(source in source_file.parents and
                      generator.sha256(source_file) == inventory_row["source_file_sha256"],
                      "frozen source file changed")
    house = generator.load_source_record(source, locator)
    generator.require(generator.canonical_sha256(house) ==
                      inventory_row["source_record_sha256"],
                      "frozen source house changed")
    scan_family = scan / "execution" / family_id
    family_receipt = next(row for row in scan_receipt["families"]
                          if row["family_id"] == family_id)
    generator.require(generator.sha256(scan_family / "initial_viewpoints.json") ==
                      family_receipt["family_viewpoints_sha256"] and
                      generator.sha256(scan_family /
                          "private/viewpoint-target-audit.json") ==
                      family_receipt["private_viewpoint_target_audit_sha256"],
                      "frozen family pose/private scan hashes changed")
    viewpoints = generator.read_json(scan_family / "initial_viewpoints.json")
    private_scan = generator.read_json(
        scan_family / "private/viewpoint-target-audit.json")["spaced_top_18"]
    selected = viewpoints["selected_pose_rank_indices"]
    generator.require(len(selected) == len(private_scan) == 18 and
                      [row["rank_index"] for row in private_scan] == selected and
                      [row["selection_index"] for row in private_scan] ==
                      list(range(18)), "frozen scan pose/target slots changed")
    if args.benchmark_only:
        generator.require(family_id == contract["fixed_family_ids"][0],
                          "single-worker benchmark must use family00")
        started = time.monotonic()
        controller = None
        diagnostic = None
        failure = None
        try:
            controller = generator.make_controller(house)
            event = generator.teleport_to_initial_viewpoint(
                controller, viewpoints["ranked_poses"][selected[0]])
            diagnostic = generator.intervention_event_diagnostic(event)
            generator.require(event.metadata.get("lastActionSuccess") is True,
                              "benchmark frozen slot00 pose rejected")
        except Exception as error:
            failure = {"error_type": type(error).__name__, "error": str(error)}
        finally:
            if controller is not None:
                try:
                    controller.stop()
                except Exception as error:
                    failure = {"error_type": type(error).__name__,
                               "error": str(error), "phase": "controller_stop"}
        path = args.probe_stage / "private/resource-benchmark.json"
        generator.write_new_json(path, {
            "schema_version": "vsmt-vm04-v3-target-probe-resource-benchmark-v2",
            "family_id": family_id, "fixed_slot": 0,
            "initial_pose_diagnostic": diagnostic, "failure": failure,
            "single_worker_peak_RSS_kib":
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "wall_seconds": time.monotonic() - started,
            "external_interventions": 0, "registered_camera_actions": 0,
            "episodes_generated": 0, "success": failure is None,
        })
        print("VM04_V3_TARGET_PROBE_BENCHMARK_%s rss_kib=%s" %
              ("OK" if failure is None else "FAILED",
               resource.getrusage(resource.RUSAGE_SELF).ru_maxrss), flush=True)
        generator.require(failure is None,
                          "v3 single-worker benchmark failed: preserve diagnosis")
        return
    family_root = args.probe_stage / "execution" / family_id
    family_root.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    receipts = []
    for row in rows:
        slot = row["slot"]
        assignment = dict(assignments[row["episode_id"]], slot=slot)
        pose = viewpoints["ranked_poses"][selected[slot]]
        result = probe_slot(
            house, assignment, pose,
            private_scan[slot]["target_instance_ids"], contract,
            relink_tolerance_m=probe_config["relink_terminal_tolerance_m"])
        path = family_root / "private" / ("slot_%02d.json" % slot)
        generator.write_new_json(path, result)
        generator.require(path.stat().st_size <= args.maximum_slot_json_bytes,
                          "private slot record exceeds safety ceiling")
        receipts.append({"slot": slot, "episode_id": row["episode_id"],
                         "program": assignment["program"], "status": result["status"],
                         "private_slot_sha256": generator.sha256(path)})
        print("VM04_V3_TARGET_PROBE_SLOT family=%s slot=%s status=%s" %
              (family_id, slot, result["status"]), flush=True)
    generator.write_new_json(family_root / "private/worker.receipt.json", {
        "schema_version": "vsmt-vm04-v3-target-probe-family-worker-receipt-v2",
        "family_id": family_id, "source_house_id": house_id,
        "v3_target_contract_sha256": generator.sha256(contract_path),
        "scan_family_worker_receipt_sha256": generator.sha256(
            scan_family / "scan.worker.receipt.json"),
        "fixed_slot_count": 18, "slots": receipts,
        "wall_seconds": time.monotonic() - started,
        "worker_max_RSS_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "episodes_generated": 0, "frames_captured": 0,
        "semantic_positive_labels_issued": 0, "training_steps": 0,
        "success": True,
    })
    print("VM04_V3_TARGET_PROBE_FAMILY_OK family=%s slots=18" % family_id,
          flush=True)


if __name__ == "__main__":
    main()
