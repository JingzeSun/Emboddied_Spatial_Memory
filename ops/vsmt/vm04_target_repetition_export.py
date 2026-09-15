#!/usr/bin/env python3
"""Export anonymous repeat counts from frozen private target profiles."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vm04_two_house_audit as audit  # noqa: E402

SOURCE_REPORT = ROOT / "results/vsmt_vm04_target_visibility_audit_v1.json"
EXPORT = ROOT / "results/vsmt_vm04_target_repetition_audit_v1.json"


def require(value, message):
    if not value:
        raise RuntimeError(message)


def anonymous_repeats(records, field):
    """Private IDs stay in this function; only cardinalities leave it."""
    top1 = []
    sets = []
    for row in records:
        ids = row[field]
        require(type(ids) is list and len(ids) >= 2 and
                all(type(value) is str for value in ids[:2]),
                "private profile has fewer than two qualified targets")
        top1.append(ids[0])
        sets.append(tuple(sorted(ids[:2])))
    return {"recorded_slot_count": len(records),
            "distinct_top1_count": len(set(top1)),
            "repeated_top1_count": len(top1) - len(set(top1)),
            "distinct_top2_set_count": len(set(sets)),
            "repeated_top2_set_count": len(sets) - len(set(sets))}


def run(stage, reviewed_code):
    require(audit.git("rev-parse", "HEAD") == reviewed_code and
            not audit.git("status", "--porcelain"),
            "repetition export requires clean reviewed checkout")
    stage = stage.resolve()
    receipt_path = stage / "audit.receipt.json"
    receipt = audit.read_json(receipt_path)
    source = audit.read_json(SOURCE_REPORT)
    require(receipt["schema_version"] ==
            "vsmt-vm04-target-visibility-audit-receipt-v1" and
            receipt["success"] is True and
            source["stage_receipt_sha256"] == audit.sha256(receipt_path) and
            source["reviewed_code"] == receipt["reviewed_code"] and
            source["total_fixed_slot_count"] == 36 and
            source["total_asset_at_least_two_slot_count"] == 36 and
            source["total_movable_at_least_two_slot_count"] == 36,
            "source target-visibility stage or report binding changed")
    require([row["family_id"] for row in receipt["families"]] ==
            ["audit-family:00", "audit-family:01"],
            "fixed family merge order changed")
    families = []
    for row in receipt["families"]:
        family_id = row["family_id"]
        # Keep object IDs out of the public report.
        private_path = (stage / "execution" / family_id /
                        "private/target-visibility.json")
        require(audit.sha256(private_path) == row["private_profile_sha256"],
                "private profile digest changed")
        private = audit.read_json(private_path)
        records = private["records"]
        require(len(records) == 18 and
                [record["slot"] for record in records] == list(range(18)),
                "fixed slot order changed")
        families.append({
            "family_id": family_id,
            "private_profile_sha256": row["private_profile_sha256"],
            "authored_asset": anonymous_repeats(
                records, "visible_authored_asset_instance_ids"),
            "movable_asset": anonymous_repeats(
                records, "visible_movable_asset_instance_ids"),
        })
    report = {
        "schema_version": "vsmt-vm04-target-repetition-audit-report-v1",
        "status": "read_only_export_from_existing_private_profiles",
        "source_visibility_report_sha256": audit.sha256(SOURCE_REPORT),
        "source_stage_receipt_sha256": audit.sha256(receipt_path),
        "reviewed_code": reviewed_code,
        "bound_sha256": {"ops/vsmt/vm04_target_repetition_export.py":
                         audit.sha256(Path(__file__).resolve())},
        "families": families,
        "frozen_d_m": 1.0, "target_repeat_policy": "report_only",
        "private_ids_exported": False, "simulator_started": False,
        "episodes_generated": 0, "interventions_performed": 0,
    }
    audit.write_new_json(EXPORT, report)
    print("VM04_TARGET_REPETITION_EXPORT_OK report=%s sha256=%s" %
          (EXPORT, audit.sha256(EXPORT)), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--reviewed-code", required=True)
    args = parser.parse_args()
    run(args.stage, args.reviewed_code)


if __name__ == "__main__":
    main()
