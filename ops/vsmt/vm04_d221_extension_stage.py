#!/usr/bin/env python3
"""D-221 development-scale prefix extension stage.

Extends the sampled prefix from 512/64 to 2048/128 train/calibration houses,
generates only the newly added houses, and materializes their features.  The
already generated 559 successes and 17 failures are reused untouched: the
selection is a fixed hash prefix, so existing ranks cannot move, and this stage
refuses to run unless it can prove that house by house.

Run authorization follows D-220: the contract booleans plus a clean checkout,
recorded with the commit and every input and output digest.  The retired
two-commit activation gate is not used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
for path in (str(SRC), str(ROOT / "ops" / "vsmt")):
    if path not in sys.path:
        sys.path.insert(0, path)

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.d221_scale_extension import (  # noqa: E402
    ACTIVE_STATUS,
    plan_prefix_extension,
    selected_house_counts,
    validate_d221_contract,
    validate_extension_plan,
)

import vm04_d217_estimator_rgbd_stage as d217_stage  # noqa: E402
import vm04_d218_estimator_feature_stage as d218_stage  # noqa: E402


D217_PATH = ROOT / "configs/vsmt/vm04_d217_estimator_development_rgbd_v1.json"
D221_PATH = ROOT / "configs/vsmt/vm04_d221_estimator_scale_rule_v1.json"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _write_new(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(value))
        handle.write("\n")


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _contract() -> dict[str, Any]:
    return validate_d221_contract(_read_json(D221_PATH))


def _run_gate(contract: dict[str, Any]) -> str:
    """The D-220 run gate: contract booleans, clean checkout, recorded commit."""

    _require(contract["status"] == ACTIVE_STATUS,
             "D-221 expansion is closed pending user review")
    _require(contract["authorization"]["structural_rgbd_expansion"] is True,
             "D-221 structural_rgbd_expansion is not authorized")
    for name in ("structural_training", "audit_open_or_generation",
                 "production_reader", "route_or_raw_generation"):
        _require(contract["authorization"][name] is False,
                 f"D-221 requires {name} to stay false")
    _require(not _git("status", "--porcelain"),
             "a D-221 real run requires a clean checkout")
    return _git("rev-parse", "HEAD")


def _d217_gate(_d217_contract: dict[str, Any]) -> str:
    """Gate injected into the reused D-217/D-218 orchestration loops."""

    return _run_gate(_contract())


def _plan_paths(output_root: Path) -> dict[str, Path]:
    private = output_root / "private"
    return {
        "partition": private / "plan" / "private_partition.json",
        "plan": private / "plan" / "private_plan.json",
        "generation_receipt": private / "generation.receipt.json",
        "extension": private / "plan" / "d221_extension_plan.json",
        "archive": private / "plan" / "archive_512_64",
    }


def check(output_root: Path | None = None) -> dict[str, Any]:
    contract = _contract()
    result = {
        "schema_version": "vsmt-vm04-d221-check-v1",
        "status": contract["status"],
        "structural_rgbd_expansion":
            contract["authorization"]["structural_rgbd_expansion"],
        "selected_house_counts": selected_house_counts(contract),
        "previous_house_counts":
            _read_json(D217_PATH)["development_sample"]["house_counts"],
        "full_house_expansion": False,
        "clean_checkout": not _git("status", "--porcelain"),
    }
    if output_root is not None:
        paths = _plan_paths(output_root)
        result["existing_plan_present"] = paths["plan"].is_file()
        result["extension_plan_present"] = paths["extension"].is_file()
    return result


def extend_plan(*, output_root: Path,
                source_inventory_path: Path) -> dict[str, Any]:
    """Verify prefix invariance, archive the old seals, write the new plan.

    The generator reads ``private_plan.json``, so this command writes the full
    2176-row plan there and keeps a byte-identical copy of the 512/64 plan and
    its terminal generation receipt in an archive directory: those are the
    evidence behind LOG-202 and are never deleted.
    """

    contract = _contract()
    commit = _run_gate(contract)
    paths = _plan_paths(output_root)
    if paths["extension"].is_file():
        return _read_json(paths["extension"])
    _require(paths["plan"].is_file(), "D-221 needs the existing D-217 plan")
    _require(paths["partition"].is_file(), "D-221 needs the partition manifest")
    existing_plan = _read_json(paths["plan"])
    partition = _read_json(paths["partition"])
    inventory = _read_json(source_inventory_path)
    source_rows = {row["house_id"]: row for row in inventory["houses"]}

    plan = plan_prefix_extension(
        partition_manifest=partition, existing_private_plan=existing_plan,
        source_rows_by_house=source_rows,
        d217_contract=_read_json(D217_PATH), d221_contract=contract)
    validate_extension_plan(plan)

    archived = {}
    paths["archive"].mkdir(parents=True, exist_ok=True)
    for name in ("plan", "generation_receipt"):
        source = paths[name]
        if source.is_file():
            target = paths["archive"] / source.name
            _require(not target.exists(),
                     f"D-221 archive already holds {source.name}")
            archived[source.name] = _sha_file(source)
            shutil.copy2(source, target)
    _require("private_plan.json" in archived,
             "D-221 must archive the 512/64 plan before replacing it")

    merged_rows = list(existing_plan["rows"])
    known = {(row["split"], row["sample_rank"]) for row in merged_rows}
    for row in plan["rows_to_generate"]:
        key = (row["split"], row["sample_rank"])
        _require(key not in known, f"D-221 would duplicate {key}")
        known.add(key)
        merged_rows.append(row)
    merged_rows.sort(key=lambda row: (
        ("train", "calibration").index(row["split"]), row["sample_rank"]))
    _require(len(merged_rows) ==
             plan["unchanged_row_count"] + plan["generate_row_count"],
             "D-221 merged plan row count is inconsistent")

    merged = dict(existing_plan)
    merged["rows"] = merged_rows
    merged["d221_extended_house_counts"] = plan["extended_house_counts"]
    merged["d221_extension_plan_sha256"] = plan["extension_plan_sha256"]
    merged.pop("private_plan_sha256", None)
    merged["private_plan_sha256"] = _sha(merged)

    # Replace the live plan only after the archive copy exists.
    paths["plan"].unlink()
    _write_new(paths["plan"], merged)
    # The terminal receipt would short-circuit the generator; it is archived,
    # so removing the live copy loses nothing.
    if paths["generation_receipt"].is_file():
        paths["generation_receipt"].unlink()

    receipt = {
        "schema_version": "vsmt-vm04-d221-extension-plan-receipt-v1",
        "run_commit": commit,
        "d221_contract_sha256": _sha_file(D221_PATH),
        "d217_contract_sha256": _sha_file(D217_PATH),
        "partition_sha256": _sha_file(paths["partition"]),
        "source_inventory_sha256": _sha_file(source_inventory_path),
        "archived_file_sha256": archived,
        "new_private_plan_sha256": _sha_file(paths["plan"]),
        "new_private_plan_row_count": len(merged_rows),
        "extension_plan": plan,
        "prefix_invariance_verified": True,
        "audit_opened": False,
        "full_house_expansion": False,
        "estimator_training_run": False,
    }
    receipt["extension_receipt_sha256"] = _sha(receipt)
    _write_new(paths["extension"], receipt)
    return receipt


def generate(*, output_root: Path, source_root: Path) -> dict[str, Any]:
    """Generate only the newly added houses, reusing every existing result.

    The reused D-217 loop reopens each finished house, revalidates its public
    and private receipts and its RGB-D digest, and keeps previously failed
    houses as failures rather than retrying them.
    """

    contract = _contract()
    commit = _run_gate(contract)
    paths = _plan_paths(output_root)
    _require(paths["extension"].is_file(),
             "D-221 extension plan is missing; run extend-plan first")
    plan = validate_extension_plan(
        _read_json(paths["extension"])["extension_plan"])
    live = _read_json(paths["plan"])
    _require(len(live["rows"]) ==
             plan["unchanged_row_count"] + plan["generate_row_count"],
             "the live plan does not carry the extended row set")

    started_path = output_root / "private/d221_generation.started.json"
    if not started_path.exists():
        _write_new(started_path, {
            "schema_version": "vsmt-vm04-d221-generation-started-v1",
            "run_commit": commit,
            "unchanged_rows": plan["unchanged_row_count"],
            "rows_to_generate": plan["generate_row_count"],
            "audit_opened": False,
        })

    result = d217_stage.generate_train_calibration(
        output_root=output_root, source_root=source_root,
        authorization_check=_d217_gate)
    return {
        "schema_version": "vsmt-vm04-d221-generation-stage-receipt-v1",
        "run_commit": commit,
        "extension_plan_sha256": plan["extension_plan_sha256"],
        "generation_receipt": result,
        "audit_opened": False,
        "full_house_expansion": False,
        "estimator_training_run": False,
    }


def features(*, public_root: Path, output_root: Path, dino_repository: Path,
             dino_checkpoint: Path, workers: int) -> dict[str, Any]:
    """Materialize features for the newly added houses; reuse existing shards."""

    contract = _contract()
    commit = _run_gate(contract)

    # E-05 left a terminal stage receipt covering only the 559 original houses.
    # D-218 returns it unchanged when it is present, so the extension would
    # silently skip the new houses.  Archive it first; the 512/64 feature
    # evidence behind LOG-204 is kept, never deleted.
    archived = {}
    final_path = output_root / "stage.receipt.json"
    if final_path.is_file():
        archive = output_root / "archive_512_64"
        archive.mkdir(parents=True, exist_ok=True)
        target = archive / final_path.name
        _require(not target.exists(),
                 "D-221 feature archive already holds stage.receipt.json")
        archived[final_path.name] = _sha_file(final_path)
        shutil.copy2(final_path, target)
        final_path.unlink()

    result = d218_stage.materialize(
        public_root=public_root, output_root=output_root,
        dino_repository=dino_repository, dino_checkpoint=dino_checkpoint,
        requested_io_workers=workers, authorization_check=_d221_feature_gate)
    return {
        "schema_version": "vsmt-vm04-d221-feature-stage-receipt-v1",
        "run_commit": commit,
        "archived_file_sha256": archived,
        "feature_receipt": result,
        "audit_opened": False,
        "estimator_training_run": False,
    }


def _d221_feature_gate(_d218_contract: dict[str, Any]) -> str:
    return _run_gate(_contract())


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    checker = commands.add_parser("check")
    checker.add_argument("--output-root", type=Path)
    planner = commands.add_parser("extend-plan")
    planner.add_argument("--output-root", type=Path, required=True)
    planner.add_argument("--source-inventory", type=Path, required=True)
    generator = commands.add_parser("generate")
    generator.add_argument("--output-root", type=Path, required=True)
    generator.add_argument("--source-root", type=Path, required=True)
    feature = commands.add_parser("features")
    feature.add_argument("--public-root", type=Path, required=True)
    feature.add_argument("--output-root", type=Path, required=True)
    feature.add_argument("--dino-repository", type=Path, required=True)
    feature.add_argument("--dino-checkpoint", type=Path, required=True)
    feature.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if args.command == "check":
        result = check(args.output_root)
    elif args.command == "extend-plan":
        result = extend_plan(output_root=args.output_root,
                             source_inventory_path=args.source_inventory)
    elif args.command == "generate":
        result = generate(output_root=args.output_root,
                          source_root=args.source_root)
    else:
        result = features(
            public_root=args.public_root, output_root=args.output_root,
            dino_repository=args.dino_repository,
            dino_checkpoint=args.dino_checkpoint, workers=args.workers)
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
