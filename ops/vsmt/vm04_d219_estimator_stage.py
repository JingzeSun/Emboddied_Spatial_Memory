#!/usr/bin/env python3
"""Closed-by-default D-219 structural-only estimator stage.

D-220 replaced the two-commit activation gate with a simpler rule: the run
authorization lives in the step contract, the user reviews it before the run,
and every real run records its commit, contract digests, input digests, output
digests and failures.  A real run still requires a clean checkout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.d215_frontend_freeze import (  # noqa: E402
    STRUCTURAL_LABELS,
    validate_d215_contract,
)
from vsmt.d219_estimator_training import (  # noqa: E402
    ACTIVE_STATUS,
    FROZEN_PREDECESSORS,
    NPZ_ARRAY_NAMES,
    fit_and_seal_structural_estimator,
    make_structural_bundle_manifest,
    validate_d219_contract,
    verify_frozen_predecessors,
)


D215_PATH = ROOT / "configs/vsmt/vm04_d215_frontend_freeze_v1.json"
D219_PATH = ROOT / "configs/vsmt/vm04_d219_structural_only_estimator_v1.json"
SPLITS = ("train", "calibration", "audit")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
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


def _load_contract() -> dict[str, Any]:
    contract = validate_d219_contract(_read_json(D219_PATH))
    bindings = contract["frozen_predecessor_bindings"]
    blobs = {
        bindings[f"{key}_relative_path"]:
            (ROOT / bindings[f"{key}_relative_path"]).read_bytes()
        for key in FROZEN_PREDECESSORS
    }
    verify_frozen_predecessors(contract, file_bytes=blobs)
    return contract


def _run_provenance(contract: dict[str, Any]) -> dict[str, Any]:
    """Record what D-220 requires of every real run, then gate on it."""

    _require(contract["status"] == ACTIVE_STATUS,
             "D-219 structural training is closed pending user review")
    _require(contract["authorization"]["structural_training"] is True,
             "D-219 structural_training is not authorized")
    for name in contract["run_authorization_policy"]["must_remain_false"]:
        _require(contract["authorization"][name] is False,
                 f"D-219 requires {name} to stay false")
    _require(not _git("status", "--porcelain"),
             "a D-219 real run requires a clean checkout")
    bindings = contract["frozen_predecessor_bindings"]
    return {
        "git_commit": _git("rev-parse", "HEAD"),
        "d219_contract_sha256": _sha256_file(D219_PATH),
        "d215_contract_sha256": _sha256_file(D215_PATH),
        "frozen_predecessor_sha256": {
            key: bindings[f"{key}_file_sha256"] for key in FROZEN_PREDECESSORS
        },
    }


def check() -> dict[str, Any]:
    contract = _load_contract()
    return {
        "schema_version": "vsmt-vm04-d219-check-v1",
        "status": contract["status"],
        "structural_training":
            contract["authorization"]["structural_training"],
        "semantic_head_removed":
            contract["removed_semantic_head"]["removed_entirely"],
        "human_annotation_required":
            contract["label_boundary"]["human_semantic_annotation_required"],
        "frozen_predecessor_chain_intact": True,
        "downstream_closed": {
            name: contract["authorization"][name]
            for name in contract["run_authorization_policy"]["must_remain_false"]
        },
        "clean_checkout": not _git("status", "--porcelain"),
    }


def build_bundle(*, public_root: Path, feature_root: Path,
                 private_root: Path, bundle_root: Path) -> dict[str, Any]:
    """Join public features with the private structural labels.

    The features carry no label, and the labels live only in the private house
    receipts, so this trusted step performs the join and writes one NPZ per
    split.  It is the only place the private reachable-graph labels enter
    training, exactly as the D-219 label boundary registers.  The audit split is
    never read: it stays sealed until E-08.
    """

    contract = _load_contract()
    provenance = _run_provenance(contract)
    bundle_root.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {}
    for split in ("train", "calibration"):
        rows: list[dict[str, Any]] = []
        for sample in sorted((feature_root / split).glob("sample_*")):
            name = sample.name
            feature_path = sample / "features.npz"
            private_path = private_root / split / name / "receipt.json"
            public_path = public_root / split / name / "receipt.json"
            _require(feature_path.is_file() and private_path.is_file() and
                     public_path.is_file(),
                     f"D-219 bundle input is incomplete for {split}/{name}")
            private = _read_json(private_path)
            public = _read_json(public_path)
            _require(private["public_receipt_sha256"] ==
                     public["public_receipt_sha256"],
                     f"private and public receipts disagree for {split}/{name}")
            label_by_id = {row["observation_id"]: row["structural_label"]
                           for row in private["observations"]}
            receipt_digest = private["private_receipt_sha256"]
            with np.load(feature_path, allow_pickle=False) as arrays:
                features = arrays["features_float32"]
                ids = [str(item) for item in arrays["observation_ids"]]
                publics = [str(item)
                           for item in arrays["public_observation_sha256"]]
            _require(len(ids) == features.shape[0] == len(publics),
                     f"feature shard arrays disagree for {split}/{name}")
            for index, observation_id in enumerate(ids):
                label = label_by_id.get(observation_id)
                _require(label in STRUCTURAL_LABELS,
                         f"no structural label for observation {observation_id}")
                rows.append({
                    "features": features[index],
                    "structural_label": STRUCTURAL_LABELS.index(label),
                    "house_id": private["house_id"],
                    "observation_id": observation_id,
                    "public_observation_sha256": publics[index],
                    "structural_label_receipt_sha256": receipt_digest,
                })
        _require(rows, f"D-219 bundle found no rows for {split}")
        payload = {
            "features": np.stack([row["features"] for row in rows]
                                 ).astype(np.float32),
            "structural_labels": np.asarray(
                [row["structural_label"] for row in rows], dtype=np.uint8),
            "house_ids": np.asarray([row["house_id"] for row in rows]),
            "observation_ids": np.asarray(
                [row["observation_id"] for row in rows]),
            "public_observation_sha256": np.asarray(
                [row["public_observation_sha256"] for row in rows]),
            "structural_label_receipt_sha256": np.asarray(
                [row["structural_label_receipt_sha256"] for row in rows]),
        }
        target = bundle_root / f"{split}.npz"
        _require(not target.exists(), f"D-219 bundle {split}.npz already exists")
        np.savez(target, **payload)
        counts = [int((payload["structural_labels"] == index).sum())
                  for index in range(3)]
        summary[split] = {
            "rows": len(rows), "houses": len(set(payload["house_ids"].tolist())),
            "class_counts": dict(zip(STRUCTURAL_LABELS, counts)),
            "npz_sha256": _sha256_file(target),
        }
    receipt = {
        "schema_version": "vsmt-vm04-d219-bundle-build-receipt-v1",
        "run_provenance": provenance,
        "splits": summary,
        "audit_split_read": False,
        "semantic_labels_present": False,
        "private_labels_used_for": "train_and_calibration_label_assembly_only",
    }
    receipt["bundle_build_receipt_sha256"] = hashlib.sha256(
        canonical_json(receipt).encode("utf-8")).hexdigest()
    _write_new(bundle_root / "bundle.build.receipt.json", receipt)
    return receipt


def _load_split_arrays(bundle_root: Path) -> dict[str, dict[str, Any]]:
    arrays: dict[str, dict[str, Any]] = {}
    for split in SPLITS:
        path = bundle_root / f"{split}.npz"
        _require(path.is_file(), f"D-219 bundle is missing {split}.npz")
        with np.load(path, allow_pickle=False) as loaded:
            _require(set(loaded.files) == set(NPZ_ARRAY_NAMES),
                     f"D-219 {split}.npz arrays differ from the exact schema")
            arrays[split] = {name: loaded[name] for name in NPZ_ARRAY_NAMES}
    return arrays


def train(*, bundle_root: Path, partition_manifest_path: Path,
          output_root: Path, device: str) -> dict[str, Any]:
    contract = _load_contract()
    provenance = _run_provenance(contract)
    final_path = output_root / "training.receipt.json"
    _require(not final_path.exists(),
             "D-219 training receipt already exists and is immutable")
    partition = _read_json(partition_manifest_path)
    split_arrays = _load_split_arrays(bundle_root)
    bundle = make_structural_bundle_manifest(
        split_arrays=split_arrays, partition_manifest=partition,
        d219_contract=contract)
    sealed = fit_and_seal_structural_estimator(
        split_arrays=split_arrays, partition_manifest=partition,
        structural_bundle_manifest=bundle,
        d215_contract=_read_json(D215_PATH), d219_contract=contract,
        implementation_commit=provenance["git_commit"], device=device)
    for name in ("normalization", "weights", "training_receipt", "success"):
        _write_new(output_root / f"{name}.json", sealed[name])
    _write_new(output_root / "structural_bundle.json", bundle)
    receipt = {
        "schema_version": "vsmt-vm04-d219-training-stage-receipt-v1",
        "run_provenance": provenance,
        "input_npz_sha256": {
            split: _sha256_file(bundle_root / f"{split}.npz")
            for split in SPLITS
        },
        "partition_manifest_sha256": _sha256_file(partition_manifest_path),
        "structural_bundle_sha256": bundle["structural_bundle_sha256"],
        "weights_sha256": sealed["weights"]["weights_sha256"],
        "training_receipt_sha256":
            sealed["training_receipt"]["training_receipt_sha256"],
        "device": device,
        "semantic_head_trained": False,
        "human_annotation_consumed": False,
        "audit_opened": False,
        "production_reader_executed": False,
    }
    receipt["stage_receipt_sha256"] = hashlib.sha256(
        canonical_json(receipt).encode("utf-8")).hexdigest()
    _write_new(final_path, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    builder = commands.add_parser("build-bundle")
    builder.add_argument("--public-root", type=Path, required=True)
    builder.add_argument("--feature-root", type=Path, required=True)
    builder.add_argument("--private-root", type=Path, required=True)
    builder.add_argument("--bundle-root", type=Path, required=True)
    trainer = commands.add_parser("train")
    trainer.add_argument("--bundle-root", type=Path, required=True)
    trainer.add_argument("--partition-manifest", type=Path, required=True)
    trainer.add_argument("--output-root", type=Path, required=True)
    trainer.add_argument("--device", default="cpu")
    args = parser.parse_args()
    if args.command == "check":
        result = check()
    elif args.command == "build-bundle":
        result = build_bundle(
            public_root=args.public_root, feature_root=args.feature_root,
            private_root=args.private_root, bundle_root=args.bundle_root)
    else:
        result = train(
            bundle_root=args.bundle_root,
            partition_manifest_path=args.partition_manifest,
            output_root=args.output_root, device=args.device)
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
