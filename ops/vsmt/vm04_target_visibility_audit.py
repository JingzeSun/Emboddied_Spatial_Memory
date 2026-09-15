#!/usr/bin/env python3
"""Read-only fixed-pose asset visibility profile, with two family workers."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import os
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import vm04_two_house_audit as audit  # noqa: E402
import vm04_two_house_worker as generator  # noqa: E402
import vm04_root_cause_audit as root_cause  # noqa: E402
from vsmt.vm04_target_eligibility import asset_target_profiles, authored_asset_ids  # noqa: E402

EXPORT = ROOT / "results/vsmt_vm04_target_visibility_audit_v1.json"
STAGE_NAME = "vsmt-vm04-two-house-target-visibility-audit-v1"
SCAN_REPORT = ROOT / "results/vsmt_vm04_viewpoint_scan_v1.json"
ROOT_REPORT = ROOT / "results/vsmt_vm04_root_cause_audit_v1.json"


def require(value, message):
    if not value:
        raise RuntimeError(message)


def resource_evidence(stage):
    cpus = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else (
        os.cpu_count() or 0)
    memory = audit._cgroup_memory_headroom_bytes()
    disk = shutil.disk_usage(stage.parent).free
    gpu_rows = subprocess.check_output([
        "nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"
    ], text=True, timeout=30).splitlines()
    gpu = max(int(row.strip()) for row in gpu_rows) * 1048576
    require(cpus >= 2 and memory is not None and memory >= 8589934592 and
            disk >= 8589934592 and gpu >= 8589934592,
            "two simulator workers lack safe CPU/RAM/disk/GPU headroom")
    return {"visible_cpu_count": cpus, "cgroup_memory_headroom_bytes": memory,
            "free_data_disk_bytes": disk, "free_gpu_bytes_on_one_device": gpu}


def family_worker(family, scan_stage, source_root, stage):
    family_id = family["family_id"]
    scan = Path(scan_stage)
    source = Path(source_root)
    inventory = audit.read_json(scan / "private/inventory.json")
    source_row = next(row for row in inventory["houses"]
                      if row["house_id"] == family["source_house_id"])
    house = generator.load_source_record(source, source_row["source_locator"])
    require(generator.canonical_sha256(house) == source_row["source_record_sha256"],
            "source house record changed during profile")
    assets = authored_asset_ids(house)
    family_scan = scan / "execution" / family_id
    viewpoints_path = family_scan / "initial_viewpoints.json"
    target_path = family_scan / "private/viewpoint-target-audit.json"
    require(audit.sha256(viewpoints_path) == family["family_viewpoints_sha256"] and
            audit.sha256(target_path) ==
            family["private_viewpoint_target_audit_sha256"],
            "frozen pose/target digest changed during profile")
    viewpoints = audit.read_json(viewpoints_path)
    targets = audit.read_json(target_path)["spaced_top_18"]
    indices = viewpoints["selected_pose_rank_indices"]
    require(len(indices) == len(targets) == 18 and
            [row["rank_index"] for row in targets] == indices,
            "frozen fixed-pose order changed")
    records = []
    controller = generator.make_controller(house)
    try:
        for slot, (rank, target_row) in enumerate(zip(indices, targets)):
            pose = viewpoints["ranked_poses"][rank]
            event = generator.teleport_to_initial_viewpoint(controller, pose)
            require(event.metadata.get("lastActionSuccess") is True,
                    "fixed-pose camera teleport failed at slot %s" % slot)
            objects = {str(row["objectId"]): dict(row)
                       for row in event.metadata.get("objects", [])}
            ranked = generator.rank_visible_instance_ids(
                event.instance_masks, objects.keys())
            profiles = asset_target_profiles(ranked, objects, assets)
            frozen_top2 = target_row["target_instance_ids"][:2]
            require(len(frozen_top2) == 2, "frozen top2 is incomplete")
            records.append({
                "slot": slot, "rank_index": rank,
                "frozen_top2_instance_ids": frozen_top2,
                "live_top2_instance_ids": ranked[:2],
                "frozen_live_top2_equal": frozen_top2 == ranked[:2],
                "frozen_top2_author_asset_count": sum(v in assets for v in frozen_top2),
                "visible_authored_asset_instance_ids": profiles["authored_asset"],
                "visible_movable_asset_instance_ids": profiles["movable_asset"],
                "metadata_authored_asset_count": sum(v in objects for v in assets),
                "metadata_total_object_count": len(objects),
            })
    finally:
        controller.stop()
    path = Path(stage) / "execution" / family_id / "private/target-visibility.json"
    audit.write_new_json(path, {
        "schema_version": "vsmt-vm04-private-target-visibility-v1",
        "family_id": family_id, "source_house_id": family["source_house_id"],
        "records": records, "actions_performed": 0, "frames_saved": 0,
    })
    asset_counts = [len(row["visible_authored_asset_instance_ids"]) for row in records]
    move_counts = [len(row["visible_movable_asset_instance_ids"]) for row in records]
    return {
        "family_id": family_id, "source_house_id": family["source_house_id"],
        "private_profile_sha256": audit.sha256(path), "fixed_slot_count": 18,
        "frozen_live_top2_mismatch_count": sum(
            not row["frozen_live_top2_equal"] for row in records),
        "asset_visible_min": min(asset_counts), "asset_visible_max": max(asset_counts),
        "asset_at_least_two_slot_count": sum(v >= 2 for v in asset_counts),
        "movable_visible_min": min(move_counts),
        "movable_visible_max": max(move_counts),
        "movable_at_least_two_slot_count": sum(v >= 2 for v in move_counts),
        "frozen_top2_author_asset_entry_count": sum(
            row["frozen_top2_author_asset_count"] for row in records),
        "metadata_author_asset_min": min(
            row["metadata_authored_asset_count"] for row in records),
        "metadata_author_asset_max": max(
            row["metadata_authored_asset_count"] for row in records),
        "private_ids_exported": False, "interventions_performed": 0,
        "episodes_generated": 0,
    }


def run(old_stage, scan_stage, source_root, output_root, reviewed_code):
    require(audit.git("rev-parse", "HEAD") == reviewed_code and
            not audit.git("status", "--porcelain"),
            "fixed-pose audit requires exact reviewed clean checkout")
    old_report = root_cause.analyze(old_stage, scan_stage, source_root)
    require(old_report["totals"]["v2_top2_not_authored_asset"] == 70 and
            audit.sha256(ROOT_REPORT) ==
            "ecf4e6735016db4dea71873193d0a7fbdb606480a18237cb7871129f562ece73",
            "root-cause provenance changed")
    scan = Path(scan_stage).resolve()
    source = Path(source_root).resolve()
    receipt = audit.read_json(scan / "scan.receipt.json")
    families = sorted(receipt["families"], key=lambda row: row["family_id"])
    require([row["family_id"] for row in families] ==
            ["audit-family:00", "audit-family:01"],
            "fixed two-family inventory changed")
    stage = Path(output_root).resolve() / STAGE_NAME
    require(not stage.exists(), "profile stage already exists: preserve prior output")
    resources = resource_evidence(stage)
    stage.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    rows = []
    exits = []
    try:
        with ProcessPoolExecutor(max_workers=2) as pool:
            futures = {pool.submit(family_worker, family, scan, source, stage):
                       family["family_id"] for family in families}
            for future in as_completed(futures):
                family_id = futures[future]
                try:
                    row = future.result()
                    rows.append(row)
                    exits.append({"family_id": family_id, "exit_status": "success"})
                except BaseException as error:
                    exits.append({"family_id": family_id, "exit_status": "failed",
                                  "error_type": type(error).__name__,
                                  "error": str(error)})
    except BaseException as error:
        exits.append({"family_id": "dispatcher", "exit_status": "failed",
                      "error_type": type(error).__name__, "error": str(error)})
    rows.sort(key=lambda row: row["family_id"])
    exits.sort(key=lambda row: row["family_id"])
    success = len(rows) == 2 and len(exits) == 2 and all(
        row["exit_status"] == "success" for row in exits)
    receipt_path = stage / "audit.receipt.json"
    audit.write_new_json(receipt_path, {
        "schema_version": "vsmt-vm04-target-visibility-audit-receipt-v1",
        "reviewed_code": reviewed_code, "requested_workers": 2,
        "actual_workers": len(exits), "resource_evidence": resources,
        "deterministic_merge_order": ["audit-family:00", "audit-family:01"],
        "worker_exits": exits, "families": rows,
        "old_root_cause_report_sha256": audit.sha256(ROOT_REPORT),
        "v2_scan_report_sha256": audit.sha256(SCAN_REPORT),
        "bound_sha256": {name: audit.sha256(ROOT / name) for name in (
            "ops/vsmt/vm04_target_visibility_audit.py",
            "ops/vsmt/vm04_two_house_worker.py",
            "src/vsmt/vm04_target_eligibility.py",
        )},
        "frozen_d_m": 1.0, "target_repeat_policy": "report_only",
        "wall_seconds": time.monotonic() - started,
        "episodes_generated": 0, "interventions_performed": 0,
        "frames_saved": 0, "success": success,
    })
    require(success, "target profile failed: preserve stage and receipt")
    report = {
        "schema_version": "vsmt-vm04-target-visibility-audit-report-v1",
        "stage_receipt_sha256": audit.sha256(receipt_path),
        "reviewed_code": reviewed_code, "requested_workers": 2,
        "actual_workers": len(exits), "families": rows,
        "total_fixed_slot_count": 36,
        "total_asset_at_least_two_slot_count": sum(
            row["asset_at_least_two_slot_count"] for row in rows),
        "total_movable_at_least_two_slot_count": sum(
            row["movable_at_least_two_slot_count"] for row in rows),
        "total_frozen_top2_author_asset_entry_count": sum(
            row["frozen_top2_author_asset_entry_count"] for row in rows),
        "total_frozen_live_top2_mismatch_count": sum(
            row["frozen_live_top2_mismatch_count"] for row in rows),
        "frozen_d_m": 1.0, "target_repeat_policy": "report_only",
        "private_ids_exported": False, "episodes_generated": 0,
        "interventions_performed": 0, "frames_saved": 0,
    }
    audit.write_new_json(EXPORT, report)
    print("VM04_TARGET_VISIBILITY_AUDIT_OK stage=%s report=%s sha256=%s" %
          (stage, EXPORT, audit.sha256(EXPORT)), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-stage", type=Path, required=True)
    parser.add_argument("--scan-stage", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--reviewed-code", required=True)
    args = parser.parse_args()
    run(args.old_stage, args.scan_stage, args.source_root, args.output_root,
        args.reviewed_code)


if __name__ == "__main__":
    main()
