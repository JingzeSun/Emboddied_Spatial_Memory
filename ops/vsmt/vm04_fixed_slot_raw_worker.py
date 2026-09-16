#!/usr/bin/env python3
"""One frozen VM-04 slot: separate raw public/private files and retain failure."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import vm04_two_house_worker as old  # noqa: E402
from vsmt.vm04_target_eligibility import authored_asset_ids  # noqa: E402
from vsmt.vm04_target_selection_v3 import select_private_targets_at_fixed_pose  # noqa: E402

PHYSICAL = frozenset(("BIRTH", "REACTIVATE", "RETRACT", "REPLACE", "RELINK"))
PUBLIC_STRUCTURE = frozenset(("NOOP", "BIND", "SPLIT", "MERGE"))
ALL_PROGRAMS = PHYSICAL | PUBLIC_STRUCTURE
TARGET_CONTRACT = ROOT / "configs/vsmt/vm04_target_boundary_proposal_v3.json"
STAGE_CONFIG = ROOT / "configs/vsmt/vm04_fixed_slot_raw_stage_v1.json"
ORIGINAL_RELINK_SLOTS = {"audit-family:00": (4, 11),
                         "audit-family:01": (6, 12)}
HOUSE_BY_FAMILY = {"audit-family:00": "train:004270",
                   "audit-family:01": "train:008243"}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def terminal_path(episode_root, kind):
    return Path(episode_root) / ("raw.%s.json" % kind)


def validate_task(task):
    """The parent must seal this private task from the original 36-slot plan."""
    require(task["schema_version"] == "vsmt-vm04-fixed-slot-raw-task-v1" and
            task["family_id"] in ("audit-family:00", "audit-family:01") and
            task["source_house_id"] == HOUSE_BY_FAMILY[task["family_id"]] and
            type(task["slot"]) is int and 0 <= task["slot"] < 18 and
            task["program"] in ALL_PROGRAMS and
            type(task["replicate"]) is int and task["replicate"] in (0, 1) and
            type(task["episode_id"]) is str and task["episode_id"] and
            type(task["fixed_pose"]) is dict and
            type(task["family_viewpoints_sha256"]) is str and
            len(task["family_viewpoints_sha256"]) == 64 and
            type(task["source_record_sha256"]) is str and
            len(task["source_record_sha256"]) == 64 and
            task["target_contract_sha256"] == old.sha256(TARGET_CONTRACT) and
            type(task["source_locator"]) is dict and
            task["semantic_positive_label_issued"] is False,
            "fixed slot task is incomplete or changed")
    if task["program"] == "RELINK":
        evidence = task.get("endpoint_failure_evidence")
        require(task["slot"] in ORIGINAL_RELINK_SLOTS[task["family_id"]] and
                type(evidence) is dict and
                evidence.get("family_id") == task["family_id"] and
                evidence.get("slot") == task["slot"] and
                evidence.get("status") == "simulator_endpoint_collision_rejected" and
                type(evidence.get("target_object_id")) is str and
                evidence["target_object_id"] and
                type(evidence.get("private_slot_sha256")) is str and
                len(evidence["private_slot_sha256"]) == 64 and
                type(evidence.get("endpoint_receipt_sha256")) is str and
                evidence["endpoint_receipt_sha256"] ==
                old.read_json(STAGE_CONFIG)[
                    "source_d173_endpoint_receipt_sha256"],
                "original RELINK slot lacks registered D-173 collision evidence")
    else:
        require(task.get("endpoint_failure_evidence") is None,
                "D-173 evidence may only accompany an original RELINK slot")
        require(task["slot"] not in ORIGINAL_RELINK_SLOTS[task["family_id"]],
                "original RELINK slot cannot be relabeled")
    return task


def private_targets(program, initial, house, contract):
    """Simulator intervention choice; non-interventions have no private target."""
    require(program in ALL_PROGRAMS, "unknown frozen program")
    if program in PUBLIC_STRUCTURE:
        return []
    metadata = {str(row["objectId"]): row
                for row in initial.metadata.get("objects", [])
                if type(row) is dict and type(row.get("objectId")) is str}
    return select_private_targets_at_fixed_pose(
        program, initial.instance_masks, metadata, authored_asset_ids(house),
        contract=contract)


def _actions(program, frame_index, targets, metadata):
    if program in PUBLIC_STRUCTURE or program == "RELINK":
        return []
    return old.intervention_actions(program, frame_index, targets, metadata)


class InterventionPoststateMismatch(RuntimeError):
    """The simulator accepted a lifecycle action but its mask did not change."""


def _target_mask_pixels(event, object_id):
    """Read private target support from the action event, never public output."""
    import numpy as np

    masks = getattr(event, "instance_masks", {}) or {}
    mask = masks.get(object_id)
    return 0 if mask is None else int(np.asarray(mask, dtype=np.bool_).sum())


def _action_record(frame_index, request, event):
    """Record the immediate private lifecycle poststate."""
    diagnostic = old.intervention_event_diagnostic(event)
    record = {"frame_index": frame_index, "request": request,
              "diagnostic": diagnostic}
    if request["action"] in {"DisableObject", "EnableObject"}:
        support = _target_mask_pixels(event, request["objectId"])
        record["target_mask_visible_pixels"] = support
    return record


def _validate_action_poststate(record):
    request = record["request"]
    if request["action"] not in {"DisableObject", "EnableObject"}:
        return
    support = record["target_mask_visible_pixels"]
    expected_visible = request["action"] == "EnableObject"
    if (support > 0) != expected_visible:
        raise InterventionPoststateMismatch(
            "%s returned success but target mask support was %s" %
            (request["action"], support))


def _failure_reason(error):
    if isinstance(error, KnownEndpointFailure):
        return "prior_D173_fixed_endpoint_collision"
    if isinstance(error, InterventionPoststateMismatch):
        return "intervention_poststate_mismatch"
    if isinstance(error, old.ResourceStop):
        return "resource_stop_with_prefix"
    if isinstance(error, ValueError):
        return "fixed_target_or_task_precondition_failed"
    return "simulator_or_raw_construction_failed"


class KnownEndpointFailure(RuntimeError):
    """Original D-173 RELINK endpoint fails; no new action probe is issued."""


def run_slot(house, task, episode_root, family_byte_limit, *,
             make_controller=old.make_controller,
             capture_frame=old.capture_frame):
    """Never replace a failed slot or overwrite a terminal record."""
    validate_task(task)
    require(old.canonical_sha256(house) == task["source_record_sha256"],
            "frozen source house differs from task")
    require(type(family_byte_limit) is int and family_byte_limit > 0,
            "frozen family byte limit required")
    episode_root = Path(episode_root)
    require(not episode_root.exists(), "slot output exists; verify, never rerun")
    task_sha256 = old.canonical_sha256(task)
    fixed_pose_sha256 = old.canonical_sha256(task["fixed_pose"])
    (episode_root / "public").mkdir(parents=True)
    (episode_root / "private").mkdir()
    controller = None
    frames, actions, targets, past_actions = [], [], [], []
    started = time.monotonic()
    initial = None
    stop_error = None
    try:
        controller = make_controller(house)
        initial = old.teleport_to_initial_viewpoint(controller, task["fixed_pose"])
        require(initial.metadata.get("lastActionSuccess") is True,
                "original fixed pose rejected")
        contract = old.read_json(TARGET_CONTRACT)
        targets = private_targets(task["program"], initial, house, contract)
        if task["program"] == "RELINK":
            require(targets == [task["endpoint_failure_evidence"]["target_object_id"]],
                    "new selection differs from the original D-173 target")
        metadata = {str(row["objectId"]): dict(row)
                    for row in initial.metadata.get("objects", [])
                    if type(row) is dict and type(row.get("objectId")) is str}
        event = initial
        for request in _actions(task["program"], -1, targets, metadata):
            event = controller.step(**request)
            actions.append(_action_record(-1, request, event))
            require(event.metadata.get("lastActionSuccess") is True,
                    "registered setup intervention rejected")
            _validate_action_poststate(actions[-1])
        for frame_index in range(32):
            if task["program"] == "RELINK" and frame_index == 24:
                raise KnownEndpointFailure("D-173 fixed endpoint collision")
            frame_actions = _actions(task["program"], frame_index,
                                     targets, metadata)
            for request in frame_actions:
                event = controller.step(**request)
                actions.append(_action_record(frame_index, request, event))
                require(event.metadata.get("lastActionSuccess") is True,
                        "registered intervention rejected")
                _validate_action_poststate(actions[-1])
            agent_action, command = old.registered_agent_action(
                task["replicate"], frame_index)
            event = controller.step(**agent_action)
            require(event.metadata.get("lastActionSuccess") is True,
                    "registered agent motion rejected")
            past_actions.append({"end_time_s": frame_index * 0.3,
                                 "command": command})
            frames.append(capture_frame(
                event, episode_root / "public", episode_root / "private",
                frame_index, frame_actions, targets, past_actions))
            if old.directory_bytes(episode_root.parent) > family_byte_limit:
                raise old.ResourceStop("frozen family byte limit exceeded")
        private_path = episode_root / "private/intervention.json"
        old.write_new_json(private_path, {
            "schema_version": "vsmt-vm04-fixed-slot-private-intervention-v1",
            "episode_id": task["episode_id"], "program": task["program"],
            "target_instance_ids": targets, "actions": actions,
            "public_structure_semantics_checked": False,
            "semantic_positive_label_issued": False})
        receipt = {"schema_version": "vsmt-vm04-fixed-slot-raw-complete-v1",
                   "family_id": task["family_id"], "slot": task["slot"],
                   "episode_id": task["episode_id"],
                   "program": task["program"], "attempted": True,
                   "raw_complete": True, "constructed": False,
                   "construction_assessment_pending": True,
                   "frame_count": len(frames), "frame_receipts": frames,
                   "private_intervention_sha256": old.sha256(private_path),
                   "family_viewpoints_sha256":
                       task["family_viewpoints_sha256"],
                   "source_record_sha256": task["source_record_sha256"],
                   "task_sha256": task_sha256,
                   "fixed_pose_sha256": fixed_pose_sha256,
                   "relink_coverage_gap": False,
                   "semantic_positive_label_issued": False,
                   "wall_seconds": time.monotonic() - started}
        old.write_new_json(terminal_path(episode_root, "receipt"), receipt)
        return receipt
    except Exception as error:
        private_path = episode_root / "private/construction-failure.json"
        old.write_new_json(private_path, {
            "schema_version": "vsmt-vm04-fixed-slot-private-failure-v1",
            "family_id": task["family_id"], "slot": task["slot"],
            "episode_id": task["episode_id"], "program": task["program"],
            "target_instance_ids": targets, "actions": actions,
            "endpoint_failure_evidence": task.get("endpoint_failure_evidence"),
            "error_type": type(error).__name__, "error": str(error),
            "semantic_positive_label_issued": False})
        failure = {"schema_version": "vsmt-vm04-fixed-slot-raw-failure-v1",
                   "family_id": task["family_id"], "slot": task["slot"],
                   "episode_id": task["episode_id"],
                   "program": task["program"], "attempted": True,
                   "raw_complete": False, "constructed": False,
                   "reason": _failure_reason(error),
                   "public_prefix_frame_count": len(frames),
                   "public_prefix_frame_receipts": [
                       {"frame_index": row["frame_index"],
                        "public_camera_sha256": row["public_camera_sha256"],
                        "private_mapping_sha256":
                            row["private_mapping_sha256"]}
                       for row in frames],
                   "private_failure_sha256": old.sha256(private_path),
                   "family_viewpoints_sha256":
                       task["family_viewpoints_sha256"],
                   "source_record_sha256": task["source_record_sha256"],
                   "task_sha256": task_sha256,
                   "fixed_pose_sha256": fixed_pose_sha256,
                   "relink_coverage_gap": task["program"] == "RELINK",
                   "relink_collision_observed_this_run": False,
                   "relink_collision_evidence_source": (
                       "registered_D173_nonforced_endpoint_receipt"
                       if task["program"] == "RELINK" else None),
                   "registered_endpoint_receipt_sha256": (
                       task["endpoint_failure_evidence"]["endpoint_receipt_sha256"]
                       if task["program"] == "RELINK" else None),
                   "semantic_positive_label_issued": False,
                   "wall_seconds": time.monotonic() - started}
        old.write_new_json(terminal_path(episode_root, "failure"), failure)
        return failure
    finally:
        if controller is not None:
            try:
                controller.stop()
            except Exception as error:
                stop_error = error
        if stop_error is not None:
            # The terminal prefix remains. Parent treats stop failure as
            # infrastructure failure and does not silently relaunch this slot.
            raise RuntimeError("controller stop failed after terminal record") from stop_error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--task-sha256", required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--episode-root", type=Path, required=True)
    parser.add_argument("--family-byte-limit", type=int, required=True)
    args = parser.parse_args()
    require(old.sha256(args.task) == args.task_sha256,
            "parent task digest changed before worker start")
    task = validate_task(old.read_json(args.task))
    locator = task["source_locator"]
    house = old.load_source_record(args.source_root, locator)
    result = run_slot(house, task, args.episode_root,
                      args.family_byte_limit)
    print("VM04_FIXED_SLOT_%s family=%s slot=%s prefix=%s" %
          ("RAW" if result["raw_complete"] else "FAILURE",
           task["family_id"], task["slot"],
           result.get("public_prefix_frame_count", result.get("frame_count"))),
          flush=True)


if __name__ == "__main__":
    main()
