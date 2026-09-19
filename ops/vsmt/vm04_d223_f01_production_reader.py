#!/usr/bin/env python3
"""F-01 closed-by-default public RGB-D production reader."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cpmt.hashing import canonical_json  # noqa: E402
import vsmt.vm04_l2_proposals as proposal_module  # noqa: E402
from vsmt.d223_f01_compat_input import (  # noqa: E402
    build_observation_zero_compat_bundle,
    select_first_d217_public_train_sample,
)
from vsmt.d223_f01_production_reader import (  # noqa: E402
    F01ProductionReader,
    MAIN_METHODS,
    assert_real_f01_authorized,
    identical_method_cache_views,
    load_frozen_processors,
    public_array_sha256,
    validate_episode_cache,
    validate_f01_contract,
    validate_public_input_manifest,
)


F01_PATH = ROOT / "configs/vsmt/vm04_d223_f01_production_reader_v1.json"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"),
                      object_pairs_hook=_reject_duplicates)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _seal(value: dict[str, Any], field: str) -> dict[str, Any]:
    result = json.loads(canonical_json(value))
    result[field] = hashlib.sha256(
        canonical_json(result).encode("utf-8")).hexdigest()
    return result


def write_new_json(path: Path, value: Any) -> None:
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(value))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def write_new_bytes(path: Path, value: bytes) -> None:
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())


def git(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=ROOT, text=True).strip()


def load_contract() -> dict[str, Any]:
    contract = validate_f01_contract(read_json(F01_PATH))
    bindings = contract["bindings"]
    for path_field, digest_field in (
        ("d223_relative_path", "d223_file_sha256"),
        ("f00_contract_relative_path", "f00_contract_file_sha256"),
        ("f00_public_summary_relative_path", "f00_public_summary_file_sha256"),
        ("d215_relative_path", "d215_file_sha256"),
        ("public_entity_geometry_relative_path",
         "public_entity_geometry_file_sha256"),
        ("public_non_entity_geometry_relative_path",
         "public_non_entity_geometry_file_sha256"),
        ("d217_relative_path", "d217_file_sha256"),
    ):
        path = ROOT / bindings[path_field]
        _require(path.is_file() and sha256(path) == bindings[digest_field],
                 f"bound evidence bytes changed: {path.name}")
    f00 = read_json(ROOT / bindings["f00_public_summary_relative_path"])
    _require(f00.get("continue_to_f01") is True and
             f00.get("production_reader_started") is False and
             f00.get("raw_generated") is False and
             all(row.get("status") == "success" and
                 row.get("qualifying_path_exists") is True
                 for row in f00.get("houses", [])) and
             len(f00.get("houses", [])) == 2,
             "F-00 public completion no longer permits F-01 review")
    return contract


def check() -> dict[str, Any]:
    contract = load_contract()
    return {
        "stage_id": "F-01",
        "status": contract["status"],
        "authorization": contract["authorization"],
        "bound_f00_two_house_qualification": True,
        "real_assets_opened": False,
        "real_public_inputs_opened": False,
        "compatibility_bundle_generated": False,
        "outputs_written": False,
    }


def _execution_checkout(contract: dict[str, Any]) -> str:
    assert_real_f01_authorized(contract)
    expected = contract["expected_reviewed_implementation_commit"]
    head, parent = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^")
    _require(parent == expected and head != expected,
             "F-01 requires one activation child of reviewed implementation")
    changed = git("diff", "--name-only", expected, head).splitlines()
    _require(changed == contract["activation_policy"]
             ["activation_commit_may_change_only"],
             "F-01 activation changed files outside its allowlist")
    _require(not git("status", "--porcelain"),
             "F-01 execution requires a clean checkout")
    return head


def _nearest_existing_parent(path: Path) -> Path:
    candidate = path.resolve()
    while not candidate.exists():
        _require(candidate.parent != candidate,
                 "F-01 output path has no existing parent")
        candidate = candidate.parent
    return candidate


def _read_public_bundle(
    input_root: Path, contract: dict[str, Any],
) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    _require(input_root.is_dir(), "F-01 public input root is missing")
    _require(sorted(item.name for item in input_root.iterdir()) ==
             ["arrays.npz", "manifest.json"],
             "F-01 public input root must contain only arrays.npz and manifest.json")
    manifest_path, arrays_path = (
        input_root / "manifest.json", input_root / "arrays.npz")
    manifest = validate_public_input_manifest(read_json(manifest_path))
    _require(sha256(arrays_path) == manifest["arrays_npz_sha256"],
             "F-01 public array bundle digest changed")
    with np.load(arrays_path, allow_pickle=False) as arrays:
        _require(set(arrays.files) == {"rgb_uint8", "depth_m_float32"},
                 "F-01 NPZ fields changed")
        rgb = np.ascontiguousarray(arrays["rgb_uint8"])
        depth = np.ascontiguousarray(arrays["depth_m_float32"])
    frame_count = manifest["frame_count"]
    expected_image = tuple(contract["assets"]["dinov2"]["input_shape"])
    _require(rgb.dtype == np.uint8 and
             rgb.shape == (frame_count, *expected_image),
             "F-01 bundled RGB dtype or shape changed")
    _require(depth.dtype == np.float32 and
             depth.shape == (frame_count, *expected_image[:2]),
             "F-01 bundled depth dtype or shape changed")
    return manifest, rgb, depth


def prepare_d217_compat(
    *, d217_public_root: Path, output_root: Path, receipt_path: Path,
) -> dict[str, Any]:
    contract = load_contract()
    execution_commit = _execution_checkout(contract)

    # External source and output paths remain unopened until all execution and
    # checkout gates have succeeded.
    _require(not output_root.exists(),
             "F-01 compatibility output root already exists")
    _require(not receipt_path.exists(),
             "F-01 compatibility receipt already exists")
    output_resolved, receipt_resolved = output_root.resolve(), receipt_path.resolve()
    _require(receipt_resolved != output_resolved and
             output_resolved not in receipt_resolved.parents,
             "F-01 compatibility receipt must be outside the input bundle")
    _require(receipt_path.parent.is_dir(),
             "F-01 compatibility receipt parent is missing")
    disk = shutil.disk_usage(_nearest_existing_parent(output_root)).free
    _require(disk >= contract["resource_policy"]["minimum_free_disk_bytes"],
             "F-01 compatibility free disk guard failed")
    _selected, source_receipt, source_arrays = (
        select_first_d217_public_train_sample(d217_public_root))
    npz_bytes, manifest, receipt = build_observation_zero_compat_bundle(
        source_receipt=source_receipt, source_arrays=source_arrays,
        frontend_config_sha256=contract["frontend"]["frontend_config_sha256"],
        execution_commit=execution_commit)
    output_root.mkdir(parents=True, exist_ok=False)
    write_new_bytes(output_root / "arrays.npz", npz_bytes)
    write_new_json(output_root / "manifest.json", manifest)
    write_new_json(receipt_path, receipt)
    return receipt


def run(
    *, input_root: Path, output_root: Path,
    dino_repository: Path, dino_checkpoint: Path,
    sam_repository: Path, sam_checkpoint: Path,
) -> dict[str, Any]:
    contract = load_contract()
    execution_commit = _execution_checkout(contract)

    # All user-supplied paths remain unopened until the closed execution gate,
    # activation-child check, and clean-checkout check have succeeded.
    _require(not output_root.exists(), "F-01 output root already exists")
    disk = shutil.disk_usage(_nearest_existing_parent(output_root)).free
    _require(disk >= contract["resource_policy"]["minimum_free_disk_bytes"],
             "F-01 free disk guard failed")
    manifest, rgb, depth = _read_public_bundle(input_root, contract)
    sam_generator, token_extractor, assets_receipt = load_frozen_processors(
        contract, dino_repository=dino_repository,
        dino_checkpoint=dino_checkpoint, sam_repository=sam_repository,
        sam_checkpoint=sam_checkpoint)
    reader = F01ProductionReader(
        contract=contract, sam_generator=sam_generator,
        patch_token_extractor=token_extractor,
        frozen_assets_receipt_sha256=
            assets_receipt["frozen_assets_receipt_sha256"],
        proposal_generator_code_sha256=sha256(
            Path(proposal_module.__file__).resolve()),
    )
    for index, row in enumerate(manifest["rows"]):
        _require(math.isfinite(float(row["decision_time_s"])),
                 "F-01 decision time is not finite")
        reader.read_frame(
            observation_index=index,
            decision_time_s=float(row["decision_time_s"]),
            rgb_uint8=rgb[index], depth_m_float32=depth[index],
            rgb_source_sha256=row["rgb_source_sha256"],
            depth_source_sha256=row["depth_source_sha256"],
            camera_intrinsics=row["camera_intrinsics"],
            causal_episode_relative_camera_pose=
                row["causal_episode_relative_camera_pose"],
            continuous_pose_belief=row["continuous_pose_belief"],
            incoming_transition_action_summary=
                row["incoming_transition_action_summary"])
    episode = validate_episode_cache(reader.seal_episode(
        episode_public_id=manifest["episode_public_id"]))
    views = identical_method_cache_views(episode)
    view_digests = {
        method: hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
        for method, value in views.items()
    }
    _require(list(view_digests) == list(MAIN_METHODS) and
             len(set(view_digests.values())) == 1,
             "F-01 main methods did not receive identical cache bytes")
    receipt = _seal({
        "schema_version": "vsmt-vm04-d223-f01-production-run-receipt-v1",
        "stage_id": "F-01",
        "execution_commit": execution_commit,
        "input_manifest_sha256": manifest["manifest_sha256"],
        "input_arrays_npz_sha256": manifest["arrays_npz_sha256"],
        "episode_cache_sha256": episode["episode_cache_sha256"],
        "frame_count": episode["frame_count"],
        "method_cache_view_sha256s": view_digests,
        "requested_worker_count": 1,
        "actual_worker_count": 1,
        "single_worker_reason":
            "one frozen GPU model pair and causal sequential free-space history",
        "deterministic_frame_order": list(range(episode["frame_count"])),
        "disk_free_bytes_before_run": disk,
        "semantic_or_structural_output_present": False,
        "route_or_raw_generated": False,
        "private_evaluation_run": False,
        "training_run": False,
        "audit_rerun": False,
    }, "run_receipt_sha256")
    output_root.mkdir(parents=True, exist_ok=False)
    write_new_json(output_root / "episode_cache.json", episode)
    write_new_json(output_root / "run_receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check")
    compat_parser = subparsers.add_parser("prepare-d217-compat")
    compat_parser.add_argument("--d217-public-root", type=Path, required=True)
    compat_parser.add_argument("--output-root", type=Path, required=True)
    compat_parser.add_argument("--receipt-path", type=Path, required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--input-root", type=Path, required=True)
    run_parser.add_argument("--output-root", type=Path, required=True)
    run_parser.add_argument("--dino-repository", type=Path, required=True)
    run_parser.add_argument("--dino-checkpoint", type=Path, required=True)
    run_parser.add_argument("--sam-repository", type=Path, required=True)
    run_parser.add_argument("--sam-checkpoint", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "check":
        result = check()
    elif arguments.command == "prepare-d217-compat":
        result = prepare_d217_compat(
            d217_public_root=arguments.d217_public_root,
            output_root=arguments.output_root,
            receipt_path=arguments.receipt_path)
    else:
        result = run(
            input_root=arguments.input_root,
            output_root=arguments.output_root,
            dino_repository=arguments.dino_repository,
            dino_checkpoint=arguments.dino_checkpoint,
            sam_repository=arguments.sam_repository,
            sam_checkpoint=arguments.sam_checkpoint)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
