#!/usr/bin/env python3
"""D-222 one-shot structural audit stage.

Opens the sealed audit split exactly once: extends the audit seal to the D-221
count with the same verified-prefix rule, generates those houses' RGB-D,
materializes their features, joins the private structural labels, and evaluates
the frozen E-06 weights against the metrics D-222 froze beforehand.

The audit rows are kept in their own plan file and never enter the training
plan.  A terminal audit report blocks a second evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for path in (str(ROOT / "src"), str(ROOT / "ops" / "vsmt")):
    if path not in sys.path:
        sys.path.insert(0, path)

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.d215_frontend_freeze import STRUCTURAL_LABELS  # noqa: E402
from vsmt.d217_estimator_development import (  # noqa: E402
    ordered_sample_candidates,
    public_house_ref,
)
from vsmt.d221_scale_extension import selected_house_counts  # noqa: E402
from vsmt.d218_estimator_frontend import (  # noqa: E402
    make_feature_shard_receipt,
)
from vsmt.d222_audit_evaluation import (  # noqa: E402
    ACTIVE_STATUS,
    evaluate_frozen_estimator,
    validate_d222_contract,
)

import vm04_d217_estimator_rgbd_stage as d217_stage  # noqa: E402
import vm04_d218_estimator_feature_stage as d218_stage  # noqa: E402

D217_PATH = ROOT / "configs/vsmt/vm04_d217_estimator_development_rgbd_v1.json"
D221_PATH = ROOT / "configs/vsmt/vm04_d221_estimator_scale_rule_v1.json"
D222_PATH = ROOT / "configs/vsmt/vm04_d222_structural_audit_v1.json"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_new(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(value))
        handle.write("\n")


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _contract() -> dict[str, Any]:
    return validate_d222_contract(_read_json(D222_PATH))


def _gate(contract: dict[str, Any], action: str) -> str:
    _require(contract["status"] == ACTIVE_STATUS,
             "D-222 audit is closed pending user review")
    _require(contract["authorization"][action] is True,
             f"D-222 {action} is not authorized")
    for name in contract["run_authorization_policy"]["must_remain_false"]:
        _require(contract["authorization"][name] is False,
                 f"D-222 requires {name} to stay false")
    _require(not _git("status", "--porcelain"),
             "a D-222 real run requires a clean checkout")
    return _git("rev-parse", "HEAD")


def _paths(output_root: Path) -> dict[str, Path]:
    private = output_root / "private"
    return {
        "partition": private / "plan" / "private_partition.json",
        "seal": private / "plan" / "private_audit_seal.json",
        "audit_plan": private / "plan" / "private_audit_plan.json",
        "archive": private / "plan" / "archive_audit_64",
        "report": output_root / "audit" / "audit.report.json",
    }


def check(output_root: Path | None = None) -> dict[str, Any]:
    contract = _contract()
    result = {
        "schema_version": "vsmt-vm04-d222-check-v1",
        "status": contract["status"],
        "authorization": contract["authorization"],
        "audit_house_count": contract["audit_sample"]["house_count"],
        "bootstrap_unit": contract["frozen_metric_definitions"][
            "bootstrap"]["unit"],
        "clean_checkout": not _git("status", "--porcelain"),
    }
    if output_root is not None:
        paths = _paths(output_root)
        seal = _read_json(paths["seal"]) if paths["seal"].is_file() else None
        result["sealed_audit_houses_on_disk"] = (
            len(seal["house_ids"]) if seal else None)
        result["audit_plan_present"] = paths["audit_plan"].is_file()
        result["terminal_report_present"] = paths["report"].is_file()
    return result


def extend_audit_seal(*, output_root: Path,
                      source_inventory_path: Path) -> dict[str, Any]:
    """Grow the sealed audit list to the D-221 count, prefix verified.

    D-221 extended the train and calibration prefixes but left the audit seal at
    its original 64 houses, so the contracts and the disk disagreed.  The audit
    selection is the same fixed hash prefix, so the original 64 must remain the
    leading entries; this refuses to proceed otherwise.
    """

    contract = _contract()
    commit = _gate(contract, "audit_rgbd_generation")
    paths = _paths(output_root)
    if paths["audit_plan"].is_file():
        return _read_json(paths["audit_plan"])
    _require(not paths["report"].is_file(),
             "D-222 audit already has a terminal report")

    partition = _read_json(paths["partition"])
    seal = _read_json(paths["seal"])
    _require(seal["opened_for_generation_or_debugging"] is False,
             "the audit seal is already marked opened")
    counts = selected_house_counts(_read_json(D221_PATH))
    target = counts["audit"]
    _require(contract["audit_sample"]["house_count"] == target,
             "D-222 and D-221 disagree on the audit house count")

    salt = _read_json(D217_PATH)["development_sample"]["sampling_salt"]
    ordered = ordered_sample_candidates(
        partition["rows"], split="audit", sampling_salt=salt)
    _require(len(ordered) >= target, "insufficient audit houses for the prefix")
    selected = ordered[:target]
    previous = list(seal["house_ids"])
    _require(selected[:len(previous)] == previous,
             "the extended audit prefix does not begin with the sealed houses")

    receipt = partition["partition_manifest_receipt_sha256"]
    _require(seal["partition_manifest_receipt_sha256"] == receipt,
             "the audit seal is bound to another partition manifest")
    sources = {row["house_id"]: row
               for row in _read_json(source_inventory_path)["houses"]}
    rows = []
    for rank, house_id in enumerate(selected):
        source = sources.get(house_id)
        _require(source is not None, f"source inventory lacks {house_id}")
        rows.append({
            "split": "audit", "sample_rank": rank, "house_id": house_id,
            "source_file_sha256": source["source_file_sha256"],
            "source_record_sha256": source["source_record_sha256"],
            "source_locator": source["source_locator"],
            "public_house_ref": public_house_ref(
                split="audit", sample_rank=rank,
                partition_manifest_receipt_sha256=receipt),
        })

    paths["archive"].mkdir(parents=True, exist_ok=True)
    archive_target = paths["archive"] / paths["seal"].name
    _require(not archive_target.exists(), "D-222 archive already holds the seal")
    archived = _sha_file(paths["seal"])
    shutil.copy2(paths["seal"], archive_target)

    plan = {
        "schema_version": "vsmt-vm04-d222-private-audit-plan-v1",
        "run_commit": commit,
        "partition_manifest_receipt_sha256": receipt,
        "previous_sealed_house_count": len(previous),
        "extended_house_count": target,
        "prefix_invariance_verified": True,
        "archived_seal_sha256": archived,
        "rows": rows,
    }
    plan["audit_plan_sha256"] = _sha(plan)
    _write_new(paths["audit_plan"], plan)
    return plan


def generate(*, output_root: Path, source_root: Path) -> dict[str, Any]:
    """Generate the audit houses' RGB-D, reusing the D-217 worker."""

    contract = _contract()
    commit = _gate(contract, "audit_rgbd_generation")
    paths = _paths(output_root)
    _require(paths["audit_plan"].is_file(),
             "run extend-audit-seal before generating")
    _require(not paths["report"].is_file(),
             "D-222 audit already has a terminal report")
    plan = _read_json(paths["audit_plan"])
    rows = sorted(plan["rows"], key=lambda row: row["sample_rank"])

    d217_contract = _read_json(D217_PATH)
    existing = {row["sample_rank"]: d217_stage._existing_result(
        output_root, row) for row in rows}
    pending = [row for row in rows if existing[row["sample_rank"]] is None]
    results = d217_stage._run_group(
        d217_stage._tasks(output_root, source_root, d217_contract, pending),
        _read_json(output_root / "private/capacity.receipt.json"
                   )["actual_batch_workers"]) if pending else []
    by_rank = {row["sample_rank"]: row for row in results}
    merged = [by_rank.get(row["sample_rank"], existing[row["sample_rank"]])
              for row in rows]
    failures = [row for row in merged if not row["success"]]
    receipt = {
        "schema_version": "vsmt-vm04-d222-audit-generation-receipt-v1",
        "run_commit": commit,
        "audit_plan_sha256": plan["audit_plan_sha256"],
        "planned_houses": len(rows),
        "success_count": len(merged) - len(failures),
        "failure_count": len(failures),
        "all_planned_houses_finished": all(row is not None for row in merged),
        "reused_houses": sum(1 for row in merged if row.get("reused")),
        "house_results": merged,
        "replacement_performed": False,
        "estimator_retrained": False,
    }
    receipt["generation_receipt_sha256"] = _sha(receipt)
    target = output_root / "private" / "audit_generation.receipt.json"
    if not target.exists():
        _write_new(target, receipt)
    return receipt


def features(*, output_root: Path, dino_repository: Path,
             dino_checkpoint: Path, workers: int) -> dict[str, Any]:
    """Materialize audit features with the same frozen D-218 extractor.

    D-218's own job enumerator deliberately refuses to see an audit directory,
    which is the guard that kept audit out of E-05.  That guard is left intact:
    this function enumerates the audit split itself and reuses only D-218's
    frozen per-frame work (model load, patch tokens, the 396-dimensional row and
    the shard receipt), so the audit features are byte-comparable with E-05.
    """

    contract = _contract()
    commit = _gate(contract, "audit_feature_materialization")
    d218_contract = d218_stage._load_contracts()[2]
    public_root = output_root / "public" / "audit"
    feature_root = output_root / "features_audit"
    _require(public_root.is_dir(), "D-222 audit public RGB-D is missing")

    jobs = []
    for sample in sorted(public_root.glob("sample_*")):
        npz_path = sample / "rgbd.npz"
        receipt_path = sample / "receipt.json"
        _require(npz_path.is_file() and receipt_path.is_file(),
                 f"audit public sample is incomplete: {sample.name}")
        receipt = _read_json(receipt_path)
        payload = dict(receipt)
        digest = payload.pop("public_receipt_sha256", None)
        _require(receipt.get("split") == "audit" and
                 receipt.get("observation_count") == 32 and
                 receipt.get("rgbd_npz_sha256") == _sha_file(npz_path) and
                 digest == _sha(payload),
                 f"audit public receipt changed: {sample.name}")
        target = feature_root / "audit" / sample.name
        if (target / "features.npz").is_file():
            continue
        jobs.append({"split": "audit", "sample_name": sample.name,
                     "npz_path": npz_path, "public_receipt_sha256": digest})

    written = 0
    if jobs:
        model = d218_stage._load_model(
            dino_repository, dino_checkpoint, d218_contract, "cuda")
        with ThreadPoolExecutor(max_workers=max(2, workers)) as pool:
            for start in range(0, len(jobs), max(2, workers)):
                batch = jobs[start:start + max(2, workers)]
                for loaded in pool.map(d218_stage._load_public_job, batch):
                    tokens = d218_stage._patch_tokens(
                        model, loaded["rgb"], "cuda")
                    ids = [str(item)
                           for item in loaded["observation_ids"].tolist()]
                    rows = list(pool.map(d218_stage._materialize_row, [(
                        observation_id, loaded["rgb"][index],
                        loaded["depth"][index], loaded["intrinsics"][index],
                        tokens[index], d218_contract)
                        for index, observation_id in enumerate(ids)]))
                    arrays = {
                        "features_float32":
                            np.stack([row[1] for row in rows]).astype(
                                np.float32),
                        "observation_ids": np.asarray(ids),
                        "public_observation_sha256":
                            np.asarray([row[0] for row in rows]),
                    }
                    target = feature_root / "audit" / loaded["sample_name"]
                    d218_stage._save_npz_new(target / "features.npz", **arrays)
                    _write_new(target / "receipt.json",
                               make_feature_shard_receipt(
                                   features_float32=arrays["features_float32"],
                                   observation_ids=arrays["observation_ids"],
                                   public_observation_digests=arrays[
                                       "public_observation_sha256"],
                                   source_public_receipt_sha256=loaded[
                                       "public_receipt_sha256"],
                                   d218_contract=d218_contract))
                    written += 1

    shards = sorted((feature_root / "audit").glob("sample_*/features.npz"))
    receipt = {
        "schema_version": "vsmt-vm04-d222-audit-feature-receipt-v1",
        "run_commit": commit,
        "shard_count": len(shards),
        "newly_written": written,
        "reused": len(shards) - written,
        "frozen_extractor": "D-218 unchanged",
        "estimator_retrained": False,
    }
    receipt["feature_receipt_sha256"] = _sha(receipt)
    path = feature_root / "audit.stage.receipt.json"
    if not path.exists():
        _write_new(path, receipt)
    return receipt


def build_bundle(*, output_root: Path, bundle_root: Path) -> dict[str, Any]:
    """Join audit features with their private structural labels."""

    contract = _contract()
    commit = _gate(contract, "audit_feature_materialization")
    rows: list[dict[str, Any]] = []
    feature_root = output_root / "features_audit" / "audit"
    for sample in sorted(feature_root.glob("sample_*")):
        private = _read_json(
            output_root / "private" / "audit" / sample.name / "receipt.json")
        label_by_id = {row["observation_id"]: row["structural_label"]
                       for row in private["observations"]}
        with np.load(sample / "features.npz", allow_pickle=False) as arrays:
            matrix = arrays["features_float32"]
            ids = [str(item) for item in arrays["observation_ids"]]
        for index, observation_id in enumerate(ids):
            label = label_by_id.get(observation_id)
            _require(label in STRUCTURAL_LABELS,
                     f"no structural label for {observation_id}")
            rows.append({"features": matrix[index],
                         "label": STRUCTURAL_LABELS.index(label),
                         "house_id": private["house_id"]})
    _require(rows, "D-222 audit bundle found no rows")
    payload = {
        "features": np.stack([row["features"] for row in rows]
                             ).astype(np.float32),
        "structural_labels": np.asarray([row["label"] for row in rows],
                                        dtype=np.uint8),
        "house_ids": np.asarray([row["house_id"] for row in rows]),
    }
    bundle_root.mkdir(parents=True, exist_ok=True)
    target = bundle_root / "audit.npz"
    _require(not target.exists(), "D-222 audit.npz already exists")
    np.savez(target, **payload)
    receipt = {
        "schema_version": "vsmt-vm04-d222-audit-bundle-receipt-v1",
        "run_commit": commit, "rows": len(rows),
        "houses": len(set(payload["house_ids"].tolist())),
        "class_counts": {
            name: int((payload["structural_labels"] == index).sum())
            for index, name in enumerate(STRUCTURAL_LABELS)},
        "npz_sha256": _sha_file(target),
    }
    receipt["bundle_receipt_sha256"] = _sha(receipt)
    _write_new(bundle_root / "audit.bundle.receipt.json", receipt)
    return receipt


def evaluate(*, output_root: Path, bundle_root: Path,
             estimator_root: Path) -> dict[str, Any]:
    """Run the audit once and seal its terminal report."""

    contract = _contract()
    commit = _gate(contract, "audit_evaluation")
    paths = _paths(output_root)
    _require(not paths["report"].is_file(),
             "D-222 audit has already been run; it runs exactly once")
    with np.load(bundle_root / "audit.npz", allow_pickle=False) as loaded:
        arrays = {name: loaded[name] for name in
                  ("features", "structural_labels", "house_ids")}
    report = evaluate_frozen_estimator(
        audit_arrays=arrays,
        weights=_read_json(estimator_root / "weights.json"),
        normalization=_read_json(estimator_root / "normalization.json"),
        training_receipt=_read_json(estimator_root / "training_receipt.json"),
        d222_contract=contract, run_commit=commit)
    _write_new(paths["report"], report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    checker = commands.add_parser("check")
    checker.add_argument("--output-root", type=Path)
    sealer = commands.add_parser("extend-audit-seal")
    sealer.add_argument("--output-root", type=Path, required=True)
    sealer.add_argument("--source-inventory", type=Path, required=True)
    generator = commands.add_parser("generate")
    generator.add_argument("--output-root", type=Path, required=True)
    generator.add_argument("--source-root", type=Path, required=True)
    feature = commands.add_parser("features")
    feature.add_argument("--output-root", type=Path, required=True)
    feature.add_argument("--dino-repository", type=Path, required=True)
    feature.add_argument("--dino-checkpoint", type=Path, required=True)
    feature.add_argument("--workers", type=int, default=8)
    bundler = commands.add_parser("build-bundle")
    bundler.add_argument("--output-root", type=Path, required=True)
    bundler.add_argument("--bundle-root", type=Path, required=True)
    evaluator = commands.add_parser("evaluate")
    evaluator.add_argument("--output-root", type=Path, required=True)
    evaluator.add_argument("--bundle-root", type=Path, required=True)
    evaluator.add_argument("--estimator-root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "check":
        result = check(args.output_root)
    elif args.command == "extend-audit-seal":
        result = extend_audit_seal(output_root=args.output_root,
                                   source_inventory_path=args.source_inventory)
    elif args.command == "generate":
        result = generate(output_root=args.output_root,
                          source_root=args.source_root)
    elif args.command == "features":
        result = features(output_root=args.output_root,
                          dino_repository=args.dino_repository,
                          dino_checkpoint=args.dino_checkpoint,
                          workers=args.workers)
    elif args.command == "build-bundle":
        result = build_bundle(output_root=args.output_root,
                              bundle_root=args.bundle_root)
    else:
        result = evaluate(output_root=args.output_root,
                          bundle_root=args.bundle_root,
                          estimator_root=args.estimator_root)
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
