#!/usr/bin/env python3
"""Isolated AI2-THOR action dry run. Never captures an episode or RGB-D."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

try:
    import resource
except ImportError:  # local Windows pure-function tests; server runner requires it
    resource = None

import vm04_two_house_worker as generator

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from vsmt.vm04_target_eligibility import authored_asset_ids  # noqa: E402


LAST_INTERVENTION_FRAME = {
    "BIRTH": 24, "REACTIVATE": 24, "RELINK": 24,
    "RETRACT": 22, "REPLACE": 24,
}


def probe_intervention_path(controller, program, replicate, targets, initial_objects):
    """Use the registered actions and timing, stopping at the last edit."""
    actions = []
    agent_actions = 0
    for frame_index in [-1] + list(range(LAST_INTERVENTION_FRAME[program] + 1)):
        try:
            frame_actions = generator.intervention_actions(
                program, frame_index, targets, initial_objects
            )
        except Exception as error:
            return "missing_action_precondition", actions, agent_actions, {
                "error_type": type(error).__name__, "error": str(error),
                "frame_index": frame_index,
            }
        for action in frame_actions:
            try:
                event = controller.step(**action)
                diagnostic = generator.intervention_event_diagnostic(event)
                actions.append({
                    "frame_index": frame_index, "arguments": action,
                    "diagnostic": diagnostic,
                })
                if diagnostic["last_action_success"] is not True:
                    return "intervention_rejected", actions, agent_actions, None
            except Exception as error:
                actions.append({
                    "frame_index": frame_index, "arguments": action,
                    "exception_type": type(error).__name__, "exception": str(error),
                })
                return "intervention_exception", actions, agent_actions, None
        if frame_index < 0 or frame_index == LAST_INTERVENTION_FRAME[program]:
            continue
        agent_action, _ = generator.registered_agent_action(replicate, frame_index)
        try:
            event = controller.step(**agent_action)
            agent_actions += 1
            if event.metadata.get("lastActionSuccess") is not True:
                return "registered_agent_action_rejected", actions, agent_actions, {
                    "frame_index": frame_index,
                    "diagnostic": generator.intervention_event_diagnostic(event),
                }
        except Exception as error:
            return "registered_agent_action_exception", actions, agent_actions, {
                "frame_index": frame_index, "error_type": type(error).__name__,
                "error": str(error),
            }
    return "interventions_succeeded", actions, agent_actions, None


def probe_slot(house, assignment, pose, scan_targets):
    """One fresh controller for one fixed family slot; never choose a substitute."""
    controller = None
    result = {
        "schema_version": "vsmt-vm04-private-action-probe-slot-v1",
        "episode_id": assignment["episode_id"], "slot": assignment["slot"],
        "program": assignment["program"], "replicate": assignment["replicate"],
        "scan_target_instance_ids": scan_targets[:2],
        "live_target_instance_ids": [], "actions": [],
        "agent_action_count": 0, "status": "not_started",
    }
    try:
        controller = generator.make_controller(house)
        event = generator.teleport_to_initial_viewpoint(controller, pose)
        result["teleport_diagnostic"] = generator.intervention_event_diagnostic(event)
        if event.metadata.get("lastActionSuccess") is not True:
            result["status"] = "initial_pose_rejected"
            return result
        initial_objects = {
            str(row["objectId"]): dict(row)
            for row in event.metadata.get("objects", [])
            if isinstance(row, dict) and "objectId" in row
        }
        live_targets = generator.rank_visible_instance_ids(
            event.instance_masks, set(initial_objects)
        )[:2]
        result["live_target_instance_ids"] = live_targets
        if live_targets != scan_targets[:2]:
            result["status"] = "scan_live_target_mismatch"
            return result
        program = assignment["program"]
        required = 2 if program in {"SPLIT", "REPLACE"} else 1
        if len(live_targets) < required:
            result["status"] = "insufficient_targets"
            return result
        targets = live_targets[:required]
        result["metadata_object_capabilities"] = generator.audit_intervention_capabilities(
            program, targets, initial_objects
        )
        if program not in LAST_INTERVENTION_FRAME:
            result["status"] = "no_physical_intervention_registered"
            return result
        status, actions, count, failure = probe_intervention_path(
            controller, program, assignment["replicate"], targets, initial_objects
        )
        result.update(status=status, actions=actions, agent_action_count=count)
        last_event = getattr(controller, "last_event", None)
        terminal_objects = (last_event.metadata.get("objects", [])
                            if last_event is not None else [])
        terminal = {
            str(row["objectId"]): row
            for row in terminal_objects
            if isinstance(row, dict) and "objectId" in row
        }
        result["private_terminal_target_metadata"] = [
            {"object_id": object_id,
             "present_in_terminal_metadata": object_id in terminal,
             "position": terminal.get(object_id, {}).get("position")}
            for object_id in targets
        ]
        if failure is not None:
            result["path_failure"] = failure
        return result
    except Exception as error:
        result.update(status="probe_exception", exception_type=type(error).__name__,
                      exception=str(error))
        return result
    finally:
        if controller is not None:
            controller.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-stage", type=Path, required=True)
    parser.add_argument("--probe-stage", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--family-id", required=True)
    parser.add_argument("--maximum-slot-json-bytes", type=int, required=True)
    parser.add_argument("--maximum-address-space-bytes", type=int, required=True)
    arguments = parser.parse_args()
    generator.require(resource is not None, "probe worker requires Linux resource limits")
    resource.setrlimit(resource.RLIMIT_AS, (
        arguments.maximum_address_space_bytes,
        arguments.maximum_address_space_bytes,
    ))
    scan = arguments.scan_stage.resolve()
    family_id = arguments.family_id
    private_plan = generator.read_json(scan / "private/episode_plan.json")
    public_plan = generator.read_json(scan / "public/episode_plan.json")
    assignments = {row["episode_id"]: row for row in private_plan["assignments"]
                   if row["family_id"] == family_id}
    rows = sorted((row for row in public_plan["episodes"]
                   if row["family_id"] == family_id), key=lambda row: row["slot"])
    generator.require(len(rows) == len(assignments) == 18 and
                      [row["slot"] for row in rows] == list(range(18)),
                      "probe worker requires the frozen 18 fixed slots")
    house_ids = {row["source_house_id"] for row in assignments.values()}
    generator.require(len(house_ids) == 1, "probe worker requires one frozen house")
    house_id = next(iter(house_ids))
    inventory = generator.read_json(scan / "private/inventory.json")
    inventory_row = next(row for row in inventory["houses"]
                         if row["house_id"] == house_id)
    locator = inventory_row["source_locator"]
    source_file = (arguments.source_root.resolve() / locator["relative_path"]).resolve()
    generator.require(arguments.source_root.resolve() in source_file.parents
                      and generator.sha256(source_file) == inventory_row["source_file_sha256"],
                      "frozen source locator/file digest mismatch")
    house = generator.load_source_record(arguments.source_root, locator)
    generator.require(generator.canonical_sha256(house) ==
                      inventory_row["source_record_sha256"],
                      "frozen house record digest mismatch")
    asset_ids = authored_asset_ids(house)
    scan_family = scan / "execution" / family_id
    viewpoints = generator.read_json(scan_family / "initial_viewpoints.json")
    private_targets = generator.read_json(
        scan_family / "private/viewpoint-target-audit.json"
    )["spaced_top_18"]
    selected = viewpoints["selected_pose_rank_indices"]
    generator.require(len(selected) == len(private_targets) == 18 and
                      [row["rank_index"] for row in private_targets] == selected and
                      [row["selection_index"] for row in private_targets] == list(range(18)),
                      "frozen scan pose/target slots mismatch")
    generator.require(all(target_id in asset_ids for row in private_targets
                          for target_id in row["target_instance_ids"][:2]),
                      "v2 scan top2 includes architecture: refuse physical actions")
    family_root = arguments.probe_stage / "execution" / family_id
    family_root.mkdir(parents=True, exist_ok=False)
    results = []
    started = time.monotonic()
    for row in rows:
        slot = row["slot"]
        assignment = dict(assignments[row["episode_id"]], slot=slot)
        pose = viewpoints["ranked_poses"][selected[slot]]
        result = probe_slot(house, assignment, pose,
                            private_targets[slot]["target_instance_ids"])
        path = family_root / "private" / ("slot_%02d.json" % slot)
        generator.write_new_json(path, result)
        generator.require(path.stat().st_size <= arguments.maximum_slot_json_bytes,
                          "private slot JSON exceeds registered safety ceiling")
        results.append({"slot": slot, "episode_id": row["episode_id"],
                        "program": assignment["program"], "status": result["status"],
                        "private_slot_sha256": generator.sha256(path)})
        print("VM04_ACTION_PROBE_SLOT family=%s slot=%s status=%s" %
              (family_id, slot, result["status"]), flush=True)
    generator.write_new_json(family_root / "private/worker.receipt.json", {
        "schema_version": "vsmt-vm04-action-probe-family-worker-receipt-v1",
        "family_id": family_id, "source_house_id": house_id,
        "fixed_slot_count": 18, "slots": results,
        "wall_seconds": time.monotonic() - started,
        "worker_max_RSS_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "episodes_generated": 0, "frames_captured": 0,
        "training_steps": 0, "success": True,
    })
    print("VM04_ACTION_PROBE_FAMILY_OK family=%s slots=18" % family_id, flush=True)


if __name__ == "__main__":
    main()
