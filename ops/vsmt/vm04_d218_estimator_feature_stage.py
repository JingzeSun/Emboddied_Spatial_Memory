#!/usr/bin/env python3
"""Closed-by-default D-218 frozen DINOv2 plus public geometry feature stage."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
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
from vsmt.d215_frontend_freeze import validate_d215_contract  # noqa: E402
from vsmt.d217_estimator_development import validate_d217_contract  # noqa: E402
from vsmt.d218_estimator_frontend import (  # noqa: E402
    make_feature_shard_receipt,
    materialize_estimator_feature,
    public_observation_sha256,
    validate_d218_contract,
    validate_upstream_contracts,
)
from vsmt.l1_entities import DINORegionConfig, preprocess_dinov2_rgb  # noqa: E402


D215_PATH = ROOT / "configs/vsmt/vm04_d215_frontend_freeze_v1.json"
D217_PATH = ROOT / "configs/vsmt/vm04_d217_estimator_development_rgbd_v1.json"
D218_PATH = ROOT / "configs/vsmt/vm04_d218_estimator_annotation_features_v1.json"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
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


def _git(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def _load_contracts() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    d215 = validate_d215_contract(_read_json(D215_PATH))
    d217 = validate_d217_contract(_read_json(D217_PATH))
    d218 = validate_d218_contract(_read_json(D218_PATH))
    validate_upstream_contracts(
        d215_contract=d215, d217_contract=d217, d218_contract=d218)
    _require(_sha256(D215_PATH) == d218["bindings"]["d215_file_sha256"] and
             _sha256(D217_PATH) == d218["bindings"]["d217_file_sha256"],
             "D-218 bound upstream file bytes changed")
    return d215, d217, d218


def _execution_checkout(contract: dict[str, Any]) -> str:
    _require(contract["status"] ==
             contract["activation_policy"]["active_status"],
             "D-218 execution is closed pending implementation review")
    _require(contract["authorization"]["feature_materialization"] is True,
             "D-218 feature materialization is not authorized")
    head = _git(ROOT, "rev-parse", "HEAD")
    parent = _git(ROOT, "rev-parse", "HEAD^")
    _require(parent == contract["expected_reviewed_implementation_commit"],
             "D-218 activation parent is not the reviewed implementation")
    changed = _git(ROOT, "diff-tree", "--no-commit-id", "--name-only", "-r", head)
    _require(changed.splitlines() ==
             contract["activation_policy"]["activation_commit_may_change_only"],
             "D-218 activation changed files outside its allowlist")
    _require(not _git(ROOT, "status", "--porcelain"),
             "D-218 execution requires a clean checkout")
    return head


def check() -> dict[str, Any]:
    _, _, contract = _load_contracts()
    return {
        "schema_version": "vsmt-vm04-d218-feature-check-v1",
        "status": contract["status"],
        "feature_materialization":
            contract["authorization"]["feature_materialization"],
        "audit_open": contract["authorization"]["audit_open_or_generation"],
        "estimator_training": contract["authorization"]["estimator_training"],
        "production_reader": contract["authorization"]["production_reader"],
        "p04_p08_qualification":
            contract["authorization"]["p04_p08_qualification"],
        "route_or_raw_generation":
            contract["authorization"]["route_or_raw_generation"],
    }


def _public_jobs(public_root: Path) -> list[dict[str, Any]]:
    _require(public_root.is_dir(), "D-218 public RGB-D root is missing")
    _require(not (public_root / "audit").exists(),
             "D-218 must not open or materialize audit observations")
    jobs = []
    for split in ("train", "calibration"):
        for sample in sorted((public_root / split).glob("sample_*")):
            npz_path = sample / "rgbd.npz"
            receipt_path = sample / "receipt.json"
            _require(npz_path.is_file() and receipt_path.is_file(),
                     "public RGB-D sample is incomplete")
            receipt = _read_json(receipt_path)
            digest = receipt.get("public_receipt_sha256")
            payload = dict(receipt)
            payload.pop("public_receipt_sha256", None)
            _require(receipt.get("schema_version") ==
                     "vsmt-vm04-d217-public-rgbd-house-v1" and
                     receipt.get("split") == split and
                     receipt.get("observation_count") == 32 and
                     receipt.get("rgbd_npz_sha256") == _sha256(npz_path) and
                     receipt.get(
                         "contains_house_world_pose_grid_instance_scenario_teacher_or_future")
                     is False and digest == hashlib.sha256(
                         canonical_json(payload).encode("utf-8")).hexdigest(),
                     "D-217 public RGB-D receipt changed")
            jobs.append({
                "split": split, "sample_name": sample.name,
                "npz_path": npz_path,
                "public_receipt_sha256": digest,
            })
    _require(jobs, "D-218 found no train/calibration public RGB-D")
    return jobs


def _load_public_job(job: dict[str, Any]) -> dict[str, Any]:
    with np.load(job["npz_path"], allow_pickle=False) as arrays:
        _require(set(arrays.files) == {
            "rgb_uint8", "depth_m_float32", "camera_intrinsics_float64",
            "observation_ids"}, "D-217 public NPZ arrays changed")
        rgb = arrays["rgb_uint8"].copy()
        depth = arrays["depth_m_float32"].copy()
        intrinsics = arrays["camera_intrinsics_float64"].copy()
        observation_ids = arrays["observation_ids"].copy()
    _require(rgb.shape == (32, 224, 224, 3) and rgb.dtype == np.uint8 and
             depth.shape == (32, 224, 224) and depth.dtype == np.float32 and
             intrinsics.shape == (32, 4) and intrinsics.dtype == np.float64 and
             observation_ids.shape == (32,),
             "D-217 public RGB-D house array schema changed")
    return {**job, "rgb": rgb, "depth": depth, "intrinsics": intrinsics,
            "observation_ids": observation_ids}


def _load_model(repository: Path, checkpoint: Path,
                contract: dict[str, Any], device: str):
    dino = contract["features"]["dinov2"]
    _require(repository.is_dir() and checkpoint.is_file(),
             "reviewed DINOv2 assets are missing")
    _require(_git(repository, "rev-parse", "HEAD") ==
             dino["repository_commit"] and
             not _git(repository, "status", "--porcelain") and
             _sha256(checkpoint) == dino["checkpoint_sha256"],
             "reviewed DINOv2 assets do not match the freeze")
    import torch
    _require(device == "cuda" and torch.cuda.is_available(),
             "D-218 real DINOv2 extraction requires CUDA")
    sys.path.insert(0, str(repository))
    from dinov2.hub.backbones import dinov2_vits14
    model = dinov2_vits14(pretrained=False)
    state = torch.load(checkpoint, map_location="cpu", weights_only=True)
    model.load_state_dict(state, strict=True)
    return model.requires_grad_(False).eval().to(device)


def _patch_tokens(model: Any, rgb: np.ndarray, device: str) -> np.ndarray:
    import torch
    config = DINORegionConfig(
        image_height=224, image_width=224, patch_size_pixels=14,
        patch_token_dimension=384, minimum_total_patch_weight=1.0,
        unit_norm_validation_tolerance=1e-5)
    preprocessed = np.stack([
        preprocess_dinov2_rgb(frame, config) for frame in rgb])
    tensor = torch.from_numpy(preprocessed).to(device)
    with torch.inference_mode():
        output = model.forward_features(tensor)
    _require(type(output) is dict and "x_norm_patchtokens" in output,
             "DINOv2 forward_features did not return patch tokens")
    tokens = output["x_norm_patchtokens"].detach().to(
        "cpu", torch.float32).numpy()
    _require(tokens.shape == (len(rgb), 256, 384) and
             np.isfinite(tokens).all(),
             "DINOv2 batch patch-token schema changed")
    return np.ascontiguousarray(tokens.reshape(len(rgb), 16, 16, 384))


def _save_npz_new(path: Path, **arrays: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _require(not path.exists(), "D-218 feature shard already exists")
    with path.open("xb") as handle:
        np.savez_compressed(handle, **arrays)


def _materialize_row(task: tuple[
        str, np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, Any],
]) -> tuple[str, np.ndarray]:
    """Compute one public digest and feature row in the bounded CPU pool."""

    observation_id, rgb, depth, intrinsics, tokens, contract = task
    public_digest = public_observation_sha256(
        observation_id=observation_id, rgb_uint8=rgb,
        depth_m_float32=depth, camera_intrinsics_float64=intrinsics)
    feature = materialize_estimator_feature(
        depth_m_float32=depth, camera_intrinsics_float64=intrinsics,
        patch_tokens=tokens, d218_contract=contract)
    return public_digest, feature


def _existing_result(
    output_root: Path, job: dict[str, Any], contract: dict[str, Any],
) -> dict[str, Any] | None:
    target = output_root / job["split"] / job["sample_name"]
    shard_path = target / "features.npz"
    receipt_path = target / "receipt.json"
    if shard_path.is_file() or receipt_path.is_file():
        _require(shard_path.is_file() and receipt_path.is_file(),
                 "existing feature shard is incomplete")
        receipt = _read_json(receipt_path)
        _require(receipt.get("feature_npz_sha256") == _sha256(shard_path),
                 "existing feature NPZ bytes changed")
        with np.load(shard_path, allow_pickle=False) as arrays:
            _require(set(arrays.files) == {
                "features_float32", "observation_ids",
                "public_observation_sha256"},
                "existing feature NPZ arrays changed")
            rebuilt = make_feature_shard_receipt(
                features_float32=arrays["features_float32"],
                observation_ids=arrays["observation_ids"],
                public_observation_digests=arrays["public_observation_sha256"],
                source_public_receipt_sha256=
                    job["public_receipt_sha256"],
                d218_contract=contract)
        _require(all(receipt.get(key) == value for key, value in rebuilt.items()),
                 "existing feature shard core receipt changed")
        stage_sha = receipt.get("stage_receipt_sha256")
        payload = dict(receipt)
        payload.pop("stage_receipt_sha256", None)
        _require(stage_sha == hashlib.sha256(
            canonical_json(payload).encode("utf-8")).hexdigest(),
            "existing feature stage receipt changed")
        return {"split": job["split"], "sample_name": job["sample_name"],
                "success": True, "reused": True,
                "stage_receipt_sha256": stage_sha}
    failure_path = (output_root / "failures" / job["split"] /
                    f"{job['sample_name']}.json")
    if failure_path.is_file():
        failure = _read_json(failure_path)
        _require(failure.get("split") == job["split"] and
                 failure.get("sample_name") == job["sample_name"] and
                 failure.get("source_public_receipt_sha256") ==
                 job["public_receipt_sha256"] and
                 failure.get("replacement_allowed") is False,
                 "existing feature failure changed")
        return {"split": job["split"], "sample_name": job["sample_name"],
                "success": False, "reused": True,
                "failure_sha256": _sha256(failure_path)}
    return None


def materialize(
    *, public_root: Path, output_root: Path, dino_repository: Path,
    dino_checkpoint: Path, requested_io_workers: int,
    authorization_check=None,
) -> dict[str, Any]:
    """Materialize the frozen 396-dimensional features.

    ``authorization_check`` lets D-221 substitute the simpler D-220 run gate for
    the retired two-commit activation gate without forking this loop.  When it
    is None the original D-218 gate applies unchanged.
    """

    _, _, contract = _load_contracts()
    activation = (_execution_checkout(contract) if authorization_check is None
                  else authorization_check(contract))
    final_path = output_root / "stage.receipt.json"
    if final_path.is_file():
        existing_stage = _read_json(final_path)
        digest = existing_stage.pop("feature_stage_receipt_sha256", None)
        _require(digest == hashlib.sha256(
            canonical_json(existing_stage).encode("utf-8")).hexdigest(),
            "existing feature stage receipt changed")
        existing_stage["feature_stage_receipt_sha256"] = digest
        return existing_stage
    _require(type(requested_io_workers) is int and requested_io_workers >= 2,
             "D-218 feature extraction requires at least two I/O workers")
    jobs = _public_jobs(public_root)
    available_cpus = os.cpu_count() or 1
    actual_workers = min(requested_io_workers, max(2, available_cpus), len(jobs))
    existing = [_existing_result(output_root, job, contract) for job in jobs]
    pending = [job for job, result in zip(jobs, existing) if result is None]
    model = (_load_model(dino_repository, dino_checkpoint, contract, "cuda")
             if pending else None)
    generated: dict[tuple[str, str], dict[str, Any]] = {}
    new_failures = 0
    with ThreadPoolExecutor(max_workers=actual_workers) as pool:
        for start in range(0, len(pending), actual_workers):
            loaded_jobs = pool.map(
                _load_public_job, pending[start:start + actual_workers])
            for loaded in loaded_jobs:
                split = loaded["split"]
                sample_name = loaded["sample_name"]
                try:
                    tokens = _patch_tokens(model, loaded["rgb"], "cuda")
                    observation_ids = [str(item) for item in
                                       loaded["observation_ids"].tolist()]
                    row_tasks = [(
                        observation_id, loaded["rgb"][index],
                        loaded["depth"][index], loaded["intrinsics"][index],
                        tokens[index], contract)
                        for index, observation_id in enumerate(observation_ids)]
                    materialized = list(pool.map(_materialize_row, row_tasks))
                    public_digests = [row[0] for row in materialized]
                    features = [row[1] for row in materialized]
                    arrays = {
                        "features_float32":
                            np.stack(features).astype(np.float32),
                        "observation_ids": np.asarray(observation_ids),
                        "public_observation_sha256": np.asarray(public_digests),
                    }
                    target = output_root / split / sample_name
                    shard_path = target / "features.npz"
                    _save_npz_new(shard_path, **arrays)
                    receipt = make_feature_shard_receipt(
                        features_float32=arrays["features_float32"],
                        observation_ids=arrays["observation_ids"],
                        public_observation_digests=
                            arrays["public_observation_sha256"],
                        source_public_receipt_sha256=
                            loaded["public_receipt_sha256"],
                        d218_contract=contract)
                    receipt["feature_npz_sha256"] = _sha256(shard_path)
                    receipt["stage_receipt_sha256"] = hashlib.sha256(
                        canonical_json(receipt).encode("utf-8")).hexdigest()
                    _write_new(target / "receipt.json", receipt)
                    generated[(split, sample_name)] = {
                        "split": split, "sample_name": sample_name,
                        "success": True, "reused": False,
                        "stage_receipt_sha256": receipt["stage_receipt_sha256"]}
                except Exception as error:
                    failure = {
                        "schema_version": "vsmt-vm04-d218-feature-failure-v1",
                        "split": split, "sample_name": sample_name,
                        "source_public_receipt_sha256":
                            loaded["public_receipt_sha256"],
                        "error_type": type(error).__name__, "message": str(error),
                        "replacement_allowed": False,
                    }
                    failure_path = (output_root / "failures" / split /
                                    f"{sample_name}.json")
                    _write_new(failure_path, failure)
                    new_failures += 1
                    generated[(split, sample_name)] = {
                        "split": split, "sample_name": sample_name,
                        "success": False, "reused": False,
                        "failure_sha256": _sha256(failure_path)}
    results = []
    for job, prior in zip(jobs, existing):
        results.append(prior if prior is not None else generated[
            (job["split"], job["sample_name"])])
    failure_count = sum(not row["success"] for row in results)
    receipt = {
        "schema_version": "vsmt-vm04-d218-feature-stage-receipt-v1",
        "activation_commit": activation,
        "requested_io_workers": requested_io_workers,
        "actual_io_workers": actual_workers,
        "worker_basis": {"available_cpu_count": available_cpus,
                         "gpu_process_count": 1,
                         "reason": "one_frozen_model_on_one_gpu_with_bounded_parallel_public_npz_io_and_geometry"},
        "deterministic_merge_order": "train_then_calibration_then_sample_name",
        "result_count": len(results),
        "success_count": len(results) - failure_count,
        "failure_count": failure_count,
        "reused_terminal_count": sum(bool(row.get("reused")) for row in results),
        "new_failure_count": new_failures,
        "results": results,
        "audit_opened": False,
        "private_label_or_metadata_read": False,
        "estimator_training_reader_p04_p08_route_or_raw_run": False,
        "wall_clock_timeout_used": False,
    }
    receipt["feature_stage_receipt_sha256"] = hashlib.sha256(
        canonical_json(receipt).encode("utf-8")).hexdigest()
    _write_new(final_path, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    run = commands.add_parser("materialize")
    run.add_argument("--public-root", type=Path, required=True)
    run.add_argument("--output-root", type=Path, required=True)
    run.add_argument("--dino-repository", type=Path, required=True)
    run.add_argument("--dino-checkpoint", type=Path, required=True)
    run.add_argument("--io-workers", type=int, required=True)
    args = parser.parse_args()
    if args.command == "check":
        result = check()
    else:
        result = materialize(
            public_root=args.public_root, output_root=args.output_root,
            dino_repository=args.dino_repository,
            dino_checkpoint=args.dino_checkpoint,
            requested_io_workers=args.io_workers)
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
