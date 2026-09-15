#!/usr/bin/env python3
"""Seal the original 36 private VM-04 raw tasks; never select new slots."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import vm04_two_house_audit as audit  # noqa: E402
import vm04_two_house_worker as source_worker  # noqa: E402
import vm04_target_action_probe as target_probe  # noqa: E402
import vm04_fixed_slot_raw_worker as raw_worker  # noqa: E402
from vsmt.two_house_audit import validate_episode_plans  # noqa: E402

CONFIG = ROOT / "configs/vsmt/vm04_fixed_slot_raw_stage_v1.json"
TARGET_PROBE_CONFIG = ROOT / "configs/vsmt/vm04_target_action_probe_proposal_v1.json"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def build_tasks(plans, viewpoints_by_family, inventory, endpoint_by_slot,
                endpoint_receipt_sha256):
    """Pure join of sealed public slots and private program/house assignments."""
    public = plans["public"]["episodes"]
    assignments = {row["episode_id"]: row
                   for row in plans["private"]["assignments"]}
    houses = {row["house_id"]: row for row in inventory["houses"]}
    tasks = []
    seen_relink = set()
    for row in public:
        family, slot = row["family_id"], row["slot"]
        assignment = assignments[row["episode_id"]]
        house_id = assignment["source_house_id"]
        require(house_id == raw_worker.HOUSE_BY_FAMILY[family],
                "private plan source house changed")
        viewpoints, viewpoint_sha = viewpoints_by_family[family]
        require(len(viewpoints["selected_pose_rank_indices"]) == 18 and
                0 <= slot < 18, "original fixed viewpoint list changed")
        rank = viewpoints["selected_pose_rank_indices"][slot]
        pose = viewpoints["ranked_poses"][rank]
        endpoint = endpoint_by_slot.get((family, slot))
        evidence = None
        if assignment["program"] == "RELINK":
            require(endpoint is not None and
                    endpoint["endpoint_verdict"]["status"] ==
                    "simulator_endpoint_collision_rejected" and
                    endpoint["trial"]["target_object_id"] ==
                    endpoint["trial"]["registered_request"]["objectId"] and
                    endpoint["semantic_positive_label_issued"] is False,
                    "original RELINK collision evidence changed")
            evidence = {
                "family_id": family, "slot": slot,
                "status": endpoint["endpoint_verdict"]["status"],
                "target_object_id": endpoint["trial"]["target_object_id"],
                "private_slot_sha256": endpoint["private_slot_sha256"],
                "endpoint_receipt_sha256": endpoint_receipt_sha256,
            }
            seen_relink.add((family, slot))
        else:
            require(endpoint is None, "endpoint evidence assigned to non-RELINK")
        task = {
            "schema_version": "vsmt-vm04-fixed-slot-raw-task-v1",
            "family_id": family, "slot": slot,
            "episode_id": row["episode_id"],
            "source_house_id": house_id,
            "source_locator": houses[house_id]["source_locator"],
            "source_record_sha256": houses[house_id]["source_record_sha256"],
            "program": assignment["program"],
            "replicate": assignment["replicate"],
            "fixed_pose": pose,
            "family_viewpoints_sha256": viewpoint_sha,
            "target_contract_sha256": source_worker.sha256(
                raw_worker.TARGET_CONTRACT),
            "endpoint_failure_evidence": evidence,
            "semantic_positive_label_issued": False,
        }
        raw_worker.validate_task(task)
        tasks.append(task)
    require(len(tasks) == 36 and
            seen_relink == {(family, slot) for family, slots in
                            raw_worker.ORIGINAL_RELINK_SLOTS.items()
                            for slot in slots},
            "36 original slots or four RELINK gaps changed")
    return sorted(tasks, key=lambda task: (task["family_id"], task["slot"]))


def frozen_tasks(scan_stage, endpoint_stage, source_root):
    """Read-only verification precedes any task-file creation."""
    config = audit.read_json(CONFIG)
    require(config["version"] == "vsmt-vm04-fixed-slot-raw-stage-v1" and
            type(config["run_authorized"]) is bool and
            config["run_authorized"] == config["generation_authorized"] and
            config["status"] == (
                "frozen_reviewed_generation" if config["run_authorized"]
                else "fixed_task_worker_and_stage_for_review_execution_closed") and
            config["semantic_positive_labels_allowed"] is False and
            config["fixed_slot_count"] == 36 and
            source_worker.sha256(raw_worker.TARGET_CONTRACT) ==
            config["source_target_contract_sha256"] and
            audit.sha256(scan_stage / "scan.receipt.json") ==
            config["source_v2_scan_receipt_sha256"] and
            audit.sha256(endpoint_stage / "endpoint.receipt.json") ==
            config["source_d173_endpoint_receipt_sha256"],
            "new fixed slot scope or frozen receipt changed")
    probe_config = audit.read_json(TARGET_PROBE_CONFIG)
    scan_receipt, families = target_probe.scan_inputs(
        probe_config, scan_stage, source_root)
    endpoint_receipt, _ = audit._marker(endpoint_stage, "endpoint")
    require(endpoint_receipt["success"] is True and
            endpoint_receipt["source_v2_scan_receipt_sha256"] ==
            config["source_v2_scan_receipt_sha256"] and
            len(endpoint_receipt["worker_exits"]) == 4 and
            endpoint_receipt["episodes_generated"] == 0 and
            endpoint_receipt["semantic_positive_labels_issued"] == 0,
            "D-173 endpoint stage changed")
    plans = validate_episode_plans({
        "public": audit.read_json(scan_stage / "public/episode_plan.json"),
        "private": audit.read_json(scan_stage / "private/episode_plan.json"),
    })
    inventory = audit.read_json(scan_stage / "private/inventory.json")
    viewpoints = {}
    for family in families:
        path = (scan_stage / "execution" / family["family_id"] /
                "initial_viewpoints.json")
        require(audit.sha256(path) == family["family_viewpoints_sha256"],
                "frozen family viewpoints changed")
        viewpoints[family["family_id"]] = (
            audit.read_json(path), family["family_viewpoints_sha256"])
    endpoint = {}
    for row in endpoint_receipt["worker_exits"]:
        key = (row["family_id"], row["slot"])
        path = (endpoint_stage / "private" / row["family_id"] /
                ("slot_%02d.json" % row["slot"]))
        require(row["exit_code"] == 0 and
                audit.sha256(path) == row["private_slot_sha256"] and
                key not in endpoint, "D-173 private slot changed")
        endpoint[key] = dict(audit.read_json(path),
                             private_slot_sha256=row["private_slot_sha256"])
    tasks = build_tasks(plans, viewpoints, inventory, endpoint,
                        audit.sha256(endpoint_stage / "endpoint.receipt.json"))
    return tasks, {
        "source_scan_receipt_sha256": audit.sha256(
            scan_stage / "scan.receipt.json"),
        "source_endpoint_receipt_sha256": audit.sha256(
            endpoint_stage / "endpoint.receipt.json"),
        "public_plan_sha256": audit.sha256(
            scan_stage / "public/episode_plan.json"),
        "private_plan_sha256": audit.sha256(
            scan_stage / "private/episode_plan.json"),
        "source_scan_reviewed_code": scan_receipt["reviewed_code"],
    }


def seal(tasks, sources, task_root):
    task_root = Path(task_root)
    require(not task_root.exists(), "task root exists; never replace sealed tasks")
    task_root.mkdir(parents=True)
    rows = []
    for task in tasks:
        relative = "private/%s/slot_%02d.json" % (
            task["family_id"].replace(":", "_"), task["slot"])
        path = task_root / relative
        audit.write_new_json(path, task)
        rows.append({"family_id": task["family_id"], "slot": task["slot"],
                     "episode_id": task["episode_id"],
                     "private_task_path": relative,
                     "private_task_sha256": audit.sha256(path)})
    audit.write_new_json(task_root / "public/task-manifest.json", {
        "schema_version": "vsmt-vm04-fixed-slot-public-task-manifest-v1",
        "slot_count": 36,
        "source_scan_receipt_sha256": sources["source_scan_receipt_sha256"],
        "source_endpoint_receipt_sha256":
            sources["source_endpoint_receipt_sha256"],
        "rows": [{"family_id": row["family_id"], "slot": row["slot"],
                  "episode_id": row["episode_id"]}
                 for row in rows],
        "private_ids_exported": False,
        "semantic_positive_labels_issued": 0,
    })
    audit.write_new_json(task_root / "private/task-manifest.json", {
        "schema_version": "vsmt-vm04-fixed-slot-private-task-manifest-v1",
        "sources": sources, "rows": rows})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-stage", type=Path, required=True)
    parser.add_argument("--endpoint-stage", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--task-root", type=Path, required=True)
    args = parser.parse_args()
    tasks, sources = frozen_tasks(args.scan_stage.resolve(),
                                  args.endpoint_stage.resolve(),
                                  args.source_root.resolve())
    rows = seal(tasks, sources, args.task_root.resolve())
    print("VM04_FIXED_SLOT_TASKS_SEALED slots=%s root=%s" %
          (len(rows), args.task_root.resolve()), flush=True)


if __name__ == "__main__":
    main()
