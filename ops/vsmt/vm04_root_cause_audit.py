#!/usr/bin/env python3
"""Read-only, digest-bound VM-04 target-boundary diagnosis; exports no IDs."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import vm04_two_house_audit as audit  # noqa: E402
import vm04_two_house_worker as generator  # noqa: E402
from vsmt.vm04_target_eligibility import authored_asset_ids  # noqa: E402

CONFIG = ROOT / "configs/vsmt/vm04_root_cause_audit_v1.json"
SCAN_REPORT = ROOT / "results/vsmt_vm04_viewpoint_scan_v1.json"
EXPORT = ROOT / "results/vsmt_vm04_root_cause_audit_v1.json"


def require(value, message):
    if not value:
        raise RuntimeError(message)


def summarize_targets(rows, asset_ids):
    """Private IDs are used only for membership; output is counts by source boundary."""
    counts = Counter()
    for row in rows:
        targets = row["target_instance_ids"][:2]
        require(len(targets) == 2 and all(type(v) is str for v in targets),
                "frozen selected top2 is incomplete")
        for target in targets:
            counts["authored_asset" if target in asset_ids else "not_authored_asset"] += 1
    counts["selected_pose_count"] = len(rows)
    return dict(sorted(counts.items()))


def analyze(old_stage, scan_stage, source_root):
    cfg = audit.read_json(CONFIG)
    require(cfg["version"] == "vsmt-vm04-root-cause-audit-v1" and
            cfg["status"] == "read_only_diagnostic" and
            cfg["generation_authorized"] is False and
            cfg["intervention_authorized"] is False, "audit authorization changed")
    old = old_stage.resolve()
    scan = scan_stage.resolve()
    source = source_root.resolve()
    require(audit.sha256(old / "generate.receipt.json") ==
            cfg["old_generate_receipt_sha256"] and
            audit.sha256(old / "verify.receipt.json") ==
            cfg["old_verify_receipt_sha256"] and
            audit.sha256(scan / "scan.receipt.json") ==
            cfg["v2_scan_receipt_sha256"] and
            audit.sha256(SCAN_REPORT) == cfg["v2_scan_report_sha256"],
            "frozen old or scan receipt digest changed")
    old_receipt = audit.read_json(old / "generate.receipt.json")
    scan_receipt = audit.read_json(scan / "scan.receipt.json")
    require(old_receipt["attempted_episode_count"] == 36 and
            old_receipt["raw_complete_episode_count"] == 16 and
            old_receipt["raw_failed_episode_count"] == 20 and
            scan_receipt["episode_generation_performed"] is False and
            scan_receipt["minimum_position_spacing_m"] == 1.0,
            "old counts or frozen scan scope changed")
    inventory = audit.validate_source_inventory(
        audit.read_json(scan / "private/inventory.json"))
    require(audit.git("rev-parse", "HEAD", cwd=source) ==
            inventory["source_release_commit"], "source checkout commit changed")
    families = sorted(scan_receipt["families"], key=lambda row: row["family_id"])
    require([row["family_id"] for row in families] == cfg["fixed_family_ids"] and
            [row["source_house_id"] for row in families] ==
            cfg["fixed_source_house_ids"], "frozen family/source mismatch")
    old_families = {row["family_id"]: row for row in old_receipt["family_receipts"]}
    out_families = []
    for family in families:
        family_id = family["family_id"]
        source_row = next(row for row in inventory["houses"]
                          if row["house_id"] == family["source_house_id"])
        locator = source_row["source_locator"]
        source_file = (source / locator["relative_path"]).resolve()
        require(source in source_file.parents and
                audit.sha256(source_file) == source_row["source_file_sha256"],
                "source asset file digest changed")
        house = generator.load_source_record(source, locator)
        require(generator.canonical_sha256(house) ==
                source_row["source_record_sha256"],
                "source house record digest changed")
        assets = authored_asset_ids(house)
        scan_family = scan / "execution" / family_id
        private_path = scan_family / "private/viewpoint-target-audit.json"
        require(audit.sha256(private_path) ==
                family["private_viewpoint_target_audit_sha256"],
                "private scan target audit digest changed")
        private = audit.read_json(private_path)
        require([row["selection_index"] for row in private["spaced_top_18"]] ==
                list(range(18)), "frozen selected pose order changed")
        new_targets = summarize_targets(private["spaced_top_18"], assets)
        old_row = old_families[family_id]
        old_root = old / "execution" / family_id / "episodes"
        old_counts = Counter()
        old_failures = Counter()
        for row in old_row["summary"]["episodes"]:
            episode = old_root / row["episode_id"]
            if row["status"] == "failed":
                path = episode / "raw.failure.json"
                require(audit.sha256(path) == row["failure_sha256"],
                        "old raw failure digest changed")
                failure = audit.read_json(path)
                old_failures[failure["error"]] += 1
                old_counts["failed_without_private_intervention_attempts"] += int(
                    not (episode / "private/intervention-attempts.json").exists())
                old_counts["failed_without_action_diagnostic"] += int(
                    set(failure) == {"attempted", "episode_id", "error", "error_type",
                                     "family_id", "raw_complete", "schema_version", "slot"})
            else:
                require(row["status"] == "complete" and
                        audit.sha256(episode / "raw.receipt.json") ==
                        row["receipt_sha256"], "old raw receipt changed")
                intervention = audit.read_json(episode / "private/intervention.json")
                old_counts["complete_episode_count"] += 1
                old_counts["complete_top1_not_authored_asset"] += int(
                    intervention["target_instance_ids"][0] not in assets)
                old_counts["complete_any_target_not_authored_asset"] += int(
                    any(target not in assets for target in
                        intervention["target_instance_ids"]))
        require(old_counts["complete_episode_count"] == 8 and
                sum(old_failures.values()) == 10 and
                new_targets["selected_pose_count"] == 18,
                "frozen family expected counts changed")
        out_families.append({
            "family_id": family_id, "source_house_id": family["source_house_id"],
            "source_record_sha256": source_row["source_record_sha256"],
            "author_asset_count_recursive": len(assets),
            "old": dict(sorted(old_counts.items())),
            "old_failure_reasons": dict(sorted(old_failures.items())),
            "v2_scan_selected_top2": new_targets,
            "private_v2_target_audit_sha256": audit.sha256(private_path),
        })
    total = Counter()
    for row in out_families:
        total.update(row["old"])
        total.update({"v2_top2_" + name: count for name, count in
                      row["v2_scan_selected_top2"].items()})
    return {
        "schema_version": "vsmt-vm04-root-cause-audit-report-v1",
        "status": "read_only_diagnostic_no_episode_or_action",
        "frozen_d_m": 1.0, "target_repeat_policy": "report_only",
        "old_generate_receipt_sha256": cfg["old_generate_receipt_sha256"],
        "old_verify_receipt_sha256": cfg["old_verify_receipt_sha256"],
        "v2_scan_receipt_sha256": cfg["v2_scan_receipt_sha256"],
        "v2_scan_report_sha256": cfg["v2_scan_report_sha256"],
        "bound_sha256": {name: audit.sha256(ROOT / name) for name in (
            "configs/vsmt/vm04_root_cause_audit_v1.json",
            "ops/vsmt/vm04_root_cause_audit.py",
            "src/vsmt/vm04_target_eligibility.py",
        )},
        "families": out_families, "totals": dict(sorted(total.items())),
        "private_ids_exported": False,
        "simulator_started": False, "episodes_generated": 0,
        "interventions_performed": 0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-stage", type=Path, required=True)
    parser.add_argument("--scan-stage", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.old_stage, args.scan_stage, args.source_root)
    audit.write_new_json(EXPORT, report)
    print("VM04_ROOT_CAUSE_AUDIT_OK report=%s sha256=%s" %
          (EXPORT, audit.sha256(EXPORT)), flush=True)


if __name__ == "__main__":
    main()
