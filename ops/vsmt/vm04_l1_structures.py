"""Fixed VM-04 L1 structural-materialization verification entry.

Run in order: ``contracts``, ``smoke``, then ``export``.  This stage uses
contract tests and a deterministic synthetic public-depth packet only.  It
does not launch the simulator, generate house data, train, or open private or
confirmation data.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = (
    PROJECT_ROOT / "configs" / "vsmt"
    / "vm04_l1_non_entity_geometry_review_v1.json"
)
STAGE_ID = "vsmt-vm04-l1-candidate-revision-v1"
TEST_GROUPS = (
    ("executor", "test_executor.py", 42),
    ("l1", "test_l1_*.py", 31),
    ("vsmt", "test_vsmt_*.py", 66),
)
EXPECTED_TESTS = sum(group[2] for group in TEST_GROUPS)
BOUND_PATHS = (
    "configs/vsmt/vm04_l1_contract_proposal_v1.json",
    "configs/vsmt/vm04_l1_non_entity_geometry_review_v1.json",
    "configs/vsmt/vm04_l1_threshold_review_v1.json",
    "schemas/vsmt_vm01_contracts.schema.json",
    "src/cpmt/executor.py",
    "src/vsmt/__init__.py",
    "src/vsmt/baselines.py",
    "src/vsmt/causal_prior.py",
    "src/vsmt/contracts.py",
    "src/vsmt/graph_ops.py",
    "src/vsmt/l1_entities.py",
    "src/vsmt/l1_masks.py",
    "src/vsmt/l1_structures.py",
    "src/vsmt/place_scaffold.py",
    "src/vsmt/public_candidates.py",
    "tests/test_executor.py",
    "tests/test_l1_entities.py",
    "tests/test_l1_masks.py",
    "tests/test_l1_structures.py",
    "tests/test_vsmt_baselines.py",
    "tests/test_vsmt_causal_prior.py",
    "tests/test_vsmt_contracts.py",
    "tests/test_vsmt_place_scaffold.py",
    "tests/test_vsmt_public_candidates.py",
    "tests/test_vsmt_vm04_protocol.py",
    "ops/vsmt/vm04_l1_structures.py",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_new_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        value, ensure_ascii=False, indent=2, sort_keys=True,
    ).encode("utf-8") + b"\n"
    if len(encoded) > 67_108_864:
        raise RuntimeError(f"refusing oversized JSON output: {len(encoded)} bytes")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def load_config() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config.get("status") != "approved_implementation_authorized_not_generation":
        raise RuntimeError("L1 structure config is not implementation-authorized")
    approval = config.get("approval", {})
    for key in (
        "numeric_rules_approved",
        "packet_schema_v2_approved",
        "typed_relation_birth_and_bind_approved",
        "implementation_authorized",
    ):
        if approval.get(key) is not True:
            raise RuntimeError(f"required approval {key!r} is absent")
    for key in (
        "data_generation_authorized",
        "training_authorized",
        "confirmation_authorized",
    ):
        if approval.get(key) is not False:
            raise RuntimeError(f"verification stage requires {key}=false")
    free_space = config.get("free_space_proposal", {})
    if free_space.get("rolling_public_observation_times") != 4:
        raise RuntimeError("approved rolling public history is not bound")
    if free_space.get("minimum_two_evidence_time_separation_s") != 0.25:
        raise RuntimeError("approved negative-evidence separation is not bound")
    if free_space.get("target_aabb_expansion_m_per_side") != 0.02:
        raise RuntimeError("approved negative-evidence expansion is not bound")
    return config


def git(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=PROJECT_ROOT, text=True, timeout=120,
    ).strip()


def verify_checkout(reviewed_code: str) -> tuple[str, dict[str, str]]:
    root = Path(git("rev-parse", "--show-toplevel")).resolve()
    if root != PROJECT_ROOT.resolve():
        raise RuntimeError(f"repository root mismatch: {root}")
    head = git("rev-parse", "HEAD")
    if head != reviewed_code:
        raise RuntimeError(f"HEAD {head} is not reviewed code {reviewed_code}")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("tracked checkout is dirty")
    bindings: dict[str, str] = {}
    for relative in BOUND_PATHS:
        path = PROJECT_ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"missing bound file: {relative}")
        bindings[relative] = sha256(path)
    return head, bindings


def stage_directory(output_root: Path, commit: str) -> Path:
    return output_root.resolve() / f"{STAGE_ID}-{commit[:12]}"


def run_command(command: list[str], *, timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    environment = dict(os.environ)
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src") + (
        os.pathsep + existing if existing else ""
    )
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    return {
        "command": command,
        "exit_code": completed.returncode,
        "wall_seconds": time.monotonic() - started,
        "output": completed.stdout,
    }


def require_success(stage: Path, name: str, commit: str) -> dict[str, Any]:
    receipt_path = stage / f"{name}.receipt.json"
    marker_path = stage / f"{name}.success.json"
    if not receipt_path.is_file() or not marker_path.is_file():
        raise RuntimeError(f"{name} receipt and success marker are required")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if not (
        receipt.get("reviewed_code") == commit
        and receipt.get("success") is True
        and marker.get("receipt_sha256") == sha256(receipt_path)
    ):
        raise RuntimeError(f"{name} success binding is invalid")
    return receipt


def run_contracts(reviewed_code: str, output_root: Path) -> None:
    load_config()
    commit, bindings = verify_checkout(reviewed_code)
    stage = stage_directory(output_root, commit)
    if stage.exists():
        raise RuntimeError(f"stage directory already exists: {stage}")
    stage.mkdir(parents=True)
    write_new_json(stage / "started.json", {
        "schema_version": "vsmt-vm04-l1-candidate-revision-started-v1",
        "stage_id": STAGE_ID,
        "started_at": utc_now(),
        "reviewed_code": commit,
        "bound_sha256": bindings,
        "expected_tests": EXPECTED_TESTS,
        "test_groups": [
            {"name": name, "pattern": pattern, "expected": expected}
            for name, pattern, expected in TEST_GROUPS
        ],
        "dataset_generation_authorized": False,
        "training_authorized": False,
        "confirmation_authorized": False,
    })
    group_receipts: list[dict[str, Any]] = []
    for name, pattern, expected in TEST_GROUPS:
        command = [
            sys.executable, "-B", "-m", "unittest", "discover",
            "-s", str(PROJECT_ROOT / "tests"), "-p", pattern, "-v",
        ]
        result = run_command(command, timeout=1800)
        log_path = stage / f"contracts.{name}.unittest.log"
        log_path.write_text(result["output"], encoding="utf-8")
        print(result["output"], end="")
        matches = re.findall(r"Ran (\d+) tests?", result["output"])
        observed = int(matches[-1]) if matches else None
        success = (
            result["exit_code"] == 0
            and observed == expected
            and "OK" in result["output"]
        )
        group_receipts.append({
            "name": name,
            "pattern": pattern,
            "expected_tests": expected,
            "observed_tests": observed,
            "exit_code": result["exit_code"],
            "wall_seconds": result["wall_seconds"],
            "success": success,
            "log_sha256": sha256(log_path),
        })
        if not success:
            break
    observed_total = sum(
        int(group["observed_tests"] or 0) for group in group_receipts
    )
    success = (
        len(group_receipts) == len(TEST_GROUPS)
        and all(group["success"] for group in group_receipts)
        and observed_total == EXPECTED_TESTS
    )
    receipt = {
        "schema_version": "vsmt-vm04-l1-candidate-revision-contract-receipt-v1",
        "stage_id": STAGE_ID,
        "reviewed_code": commit,
        "bound_sha256": bindings,
        "expected_tests": EXPECTED_TESTS,
        "observed_tests": observed_total,
        "groups": group_receipts,
        "success": success,
        "completed_at": utc_now(),
        "generation_performed": False,
        "training_steps": 0,
        "private_data_opened": False,
        "confirmation_data_opened": False,
    }
    receipt_path = stage / "contracts.receipt.json"
    write_new_json(receipt_path, receipt)
    if not success:
        print(f"VM04_L1_CANDIDATE_REVISION_CONTRACTS_FAILED stage={stage}")
        raise SystemExit(1)
    write_new_json(stage / "contracts.success.json", {
        "schema_version": "vsmt-vm04-l1-candidate-revision-contract-success-v1",
        "reviewed_code": commit,
        "receipt_sha256": sha256(receipt_path),
        "observed_tests": observed_total,
        "success": True,
    })
    print(f"VM04_L1_CANDIDATE_REVISION_CONTRACTS_OK stage={stage} tests={observed_total}")


def run_smoke(reviewed_code: str, output_root: Path) -> None:
    config = load_config()
    commit, bindings = verify_checkout(reviewed_code)
    stage = stage_directory(output_root, commit)
    require_success(stage, "contracts", commit)
    if (stage / "smoke.receipt.json").exists():
        raise RuntimeError("smoke receipt already exists")
    started = time.monotonic()
    success = False
    summary: dict[str, Any] | None = None
    error: dict[str, str] | None = None
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
        import numpy as np

        from vsmt.causal_prior import (
            PublicBootstrapConfig,
            advance_public_bootstrap,
            empty_public_memory,
        )
        from vsmt.contracts import validate_observation_packet
        from vsmt.l1_entities import (
            AI2THOR_CAMERA_AXIS_Z,
            DINORegionConfig,
            PublicGeometryConfig,
            materialize_l1_entity_observation,
        )
        from vsmt.l1_masks import (
            KEEP_SUPPORTED_BORDER_REGIONS,
            L1MaskConfig,
            anonymize_instance_masks,
        )
        from vsmt.l1_structures import (
            FreeSpaceMaterializationConfig,
            PlaceMaterializationConfig,
            SurfaceMaterializationConfig,
            assemble_free_space_history,
            assemble_region_records,
            entity_regions_with_masks,
            materialize_public_free_space,
            materialize_public_places,
            materialize_public_relations,
            materialize_public_surfaces,
        )
        from vsmt.public_candidates import (
            PublicCandidateConfig,
            generate_public_candidate_catalog,
        )

        surface_values = config["surface_proposal"]
        place_values = config["place_proposal"]
        free_values = config["free_space_proposal"]
        descriptor_config = DINORegionConfig(
            image_height=224,
            image_width=224,
            patch_size_pixels=14,
            patch_token_dimension=4,
            minimum_total_patch_weight=1.0,
            unit_norm_validation_tolerance=0.00001,
        )
        surface_config = SurfaceMaterializationConfig(
            tile_size_pixels=surface_values["base_tile_pixels"][0],
            minimum_valid_depth_fraction_per_tile=surface_values[
                "minimum_valid_depth_fraction_per_tile"
            ],
            initial_maximum_rms_point_to_plane_m=surface_values[
                "initial_maximum_rms_point_to_plane_m"
            ],
            initial_maximum_p95_point_to_plane_m=surface_values[
                "initial_maximum_p95_point_to_plane_m"
            ],
            merge_maximum_normal_angle_degrees=surface_values[
                "merge_maximum_normal_angle_degrees"
            ],
            merge_maximum_mutual_centroid_to_plane_m=surface_values[
                "merge_maximum_mutual_centroid_to_plane_m"
            ],
            final_inlier_point_to_plane_m=surface_values[
                "final_inlier_point_to_plane_m"
            ],
            final_minimum_inlier_fraction=surface_values[
                "final_minimum_inlier_fraction"
            ],
            final_maximum_rms_point_to_plane_m=surface_values[
                "final_maximum_rms_point_to_plane_m"
            ],
            minimum_inlier_pixels=surface_values["minimum_inlier_pixels"],
            minimum_depth_m=0.05,
            maximum_depth_m=20.0,
        )
        place_config = PlaceMaterializationConfig(
            maximum_floor_normal_angle_degrees=place_values[
                "maximum_floor_normal_angle_degrees"
            ],
            maximum_support_height_difference_m=place_values[
                "maximum_surface_height_difference_from_agent_support_m"
            ],
            cell_size_m=place_values["world_aligned_cell_size_m"],
            grid_origin_m=tuple(place_values["grid_origin_m"]),
            coverage_subcell_size_m=place_values["coverage_subcell_size_m"],
            minimum_covered_subcells=place_values["minimum_covered_subcells"],
            minimum_mask_pixels=place_values["minimum_mask_pixels"],
            camera_to_agent_center_y_m=config["source_audit"][
                "standard_agent_camera_local_y_m"
            ],
            agent_half_height_m=(
                config["source_audit"]["standard_agent_character_controller_height_m"]
                / 2.0
            ),
            located_at_boundary_margin_m=0.02,
        )
        free_config = FreeSpaceMaterializationConfig(
            tile_size_pixels=free_values["base_tile_pixels"][0],
            block_widths_in_tiles=tuple(
                free_values["aligned_multiscale_block_widths_in_base_tiles"]
            ),
            angular_boundary_erosion_pixels=free_values[
                "angular_boundary_erosion_pixels"
            ],
            minimum_depth_m=0.05,
            maximum_valid_depth_m=20.0,
            near_axis_depth_m=free_values["near_axis_depth_m"],
            surface_clearance_m=free_values["surface_clearance_m"],
            maximum_axis_depth_m=free_values["maximum_axis_depth_m"],
            minimum_longitudinal_thickness_m=free_values[
                "minimum_longitudinal_thickness_m"
            ],
            rolling_public_observation_times=free_values[
                "rolling_public_observation_times"
            ],
        )
        calibration = {"fx": 112.0, "fy": 112.0, "cx": 111.5, "cy": 111.5}
        half = math.sqrt(0.5)
        pose = {
            "position_m": [0.0, 1.575, 0.0],
            "quaternion_xyzw": [half, 0.0, 0.0, half],
        }
        depth = np.full((224, 224), 1.575, dtype=np.float32)
        tokens = np.zeros((16, 16, 4), dtype=np.float32)
        tokens[..., 0] = 1.0
        surfaces = materialize_public_surfaces(
            depth, calibration, pose, tokens, descriptor_config, surface_config,
        )
        place_result = materialize_public_places(
            surfaces, depth, calibration, pose, tokens, descriptor_config,
            surface_config, place_config,
        )
        places = place_result.regions
        if not surfaces or not places:
            raise RuntimeError("synthetic public floor did not materialize")
        entity_mask = np.zeros((224, 224), dtype=np.bool_)
        entity_mask[:14, :14] = True
        anonymous = anonymize_instance_masks(
            {"smoke-private-entity": entity_mask},
            L1MaskConfig(196, KEEP_SUPPORTED_BORDER_REGIONS),
        )
        entity_observation = materialize_l1_entity_observation(
            anonymous.regions[0], tokens, depth, calibration, pose,
            descriptor_config,
            PublicGeometryConfig(
                depth_convention=AI2THOR_CAMERA_AXIS_Z,
                minimum_depth_m=0.05,
                maximum_depth_m=20.0,
                absolute_minimum_valid_depth_points=32,
                minimum_valid_depth_fraction=0.25,
            ),
        )
        entities = entity_regions_with_masks(
            [entity_observation], anonymous.regions,
        )
        regions, indexed = assemble_region_records(entities, places, surfaces)
        relations = materialize_public_relations(
            indexed,
            place_config=place_config,
            supported_by_maximum_normal_angle_degrees=10.0,
            supported_by_minimum_gap_m=-0.02,
            supported_by_maximum_gap_m=0.05,
            supported_by_minimum_projected_overlap=0.25,
            supported_by_maximum_mask_overlap_fraction=0.05,
        )
        free_first = materialize_public_free_space(
            depth, calibration, pose, time_s=0.0,
            depth_sha256="1" * 64,
            camera_calibration_and_pose_sha256="2" * 64,
            config=free_config,
        )
        free_second = materialize_public_free_space(
            depth, calibration, pose, time_s=0.3,
            depth_sha256="3" * 64,
            camera_calibration_and_pose_sha256="2" * 64,
            config=free_config,
        )
        free_spaces = assemble_free_space_history(
            [free_first, free_second],
            rolling_public_observation_times=free_config.rolling_public_observation_times,
        )
        memory = empty_public_memory()
        packet = {
            "schema_version": "vsmt-observation-packet-v2",
            "sample_id_hash": "4" * 64,
            "decision_time_s": 0.3,
            "rgbd_refs": {"rgb_sha256": "5" * 64, "depth_sha256": "3" * 64},
            "camera_pose": pose,
            "robot_state": {"feature_names": [], "values": []},
            "past_actions": [],
            "region_observations": regions,
            "relation_observations": relations,
            "free_space_observations": free_spaces,
            "prior_memory_ref": {
                "graph_version": memory["graph_version"],
                "graph_sha256": memory["graph_hash"],
            },
            "public_constants": {
                "coordinate_frame": "map",
                "depth_unit": "metre",
                "descriptor_model_id": "dinov2.vits14",
                "proposal_model_id": "fixed.region.v2",
            },
        }
        validate_observation_packet(packet)
        result = advance_public_bootstrap(
            packet,
            memory,
            config=PublicBootstrapConfig(
                association_rules={
                    kind: {
                        "visual_weight": 0.5,
                        "geometry_weight": 0.5,
                        "geometry_scale_m": 1.0,
                        "association_threshold": 0.8,
                    }
                    for kind in ("entity", "surface", "fragment")
                },
                maximum_regions_per_packet=512,
                builder_revision="smoke-v1",
            ),
        )
        candidate_packet = dict(packet)
        candidate_packet["prior_memory_ref"] = {
            "graph_version": result["post_memory"]["graph_version"],
            "graph_sha256": result["post_memory"]["graph_hash"],
        }
        candidate_catalog = generate_public_candidate_catalog(
            candidate_packet,
            result["post_memory"],
            config=PublicCandidateConfig(
                association_rules={
                    kind: {
                        "visual_weight": 0.5,
                        "geometry_weight": 0.5,
                        "geometry_scale_m": 1.0,
                        "bind_threshold": 0.8,
                        "merge_threshold": 0.9,
                        "split_region_threshold": 0.8,
                    }
                    for kind in ("entity", "surface", "fragment")
                },
                split_minimum_separation_m=0.3,
                free_space_reliability_threshold=0.9,
                free_space_target_expansion_m=0.02,
                minimum_free_space_time_separation_s=0.25,
                maximum_candidates_per_bucket=20,
                maximum_split_incident_edges=8,
            ),
        )
        relation_counts = result["diagnostics"]["relation_updates"]
        success = bool(
            len(surfaces) >= 1
            and len(places) >= 1
            and len(free_spaces) == 682
            and len(relations) >= 2
            and relation_counts.get("born", 0) >= 1
            and len(candidate_catalog["candidates"]) >= 1
            and all(
                row["scope"] != "place"
                for row in candidate_catalog["capacity_audit"]
            )
        )
        summary = {
            "surface_regions": len(surfaces),
            "place_regions": len(places),
            "packet_regions": len(regions),
            "free_space_frusta": len(free_spaces),
            "relation_observations": len(relations),
            "canonical_relation_edges": len(result["post_memory"]["edges"]),
            "relation_updates": relation_counts,
            "post_memory_sha256": result["post_memory_sha256"],
            "candidate_catalog_schema": candidate_catalog["schema_version"],
            "candidate_count": len(candidate_catalog["candidates"]),
            "candidate_capacity_buckets": len(
                candidate_catalog["capacity_audit"]
            ),
        }
    except Exception as caught:
        error = {"type": type(caught).__name__, "message": str(caught)}
    receipt = {
        "schema_version": "vsmt-vm04-l1-candidate-revision-smoke-receipt-v1",
        "stage_id": STAGE_ID,
        "reviewed_code": commit,
        "bound_sha256": bindings,
        "success": success,
        "summary": summary,
        "error": error,
        "wall_seconds": time.monotonic() - started,
        "completed_at": utc_now(),
        "synthetic_public_depth_only": True,
        "simulator_launched": False,
        "generation_performed": False,
        "training_steps": 0,
        "private_data_opened": False,
        "confirmation_data_opened": False,
    }
    receipt_path = stage / "smoke.receipt.json"
    write_new_json(receipt_path, receipt)
    if not success:
        print(f"VM04_L1_CANDIDATE_REVISION_SMOKE_FAILED stage={stage} error={error}")
        raise SystemExit(1)
    write_new_json(stage / "smoke.success.json", {
        "schema_version": "vsmt-vm04-l1-candidate-revision-smoke-success-v1",
        "reviewed_code": commit,
        "receipt_sha256": sha256(receipt_path),
        "success": True,
    })
    print(f"VM04_L1_CANDIDATE_REVISION_SMOKE_OK stage={stage} summary={summary}")


def export_stage(reviewed_code: str, output_root: Path) -> None:
    load_config()
    commit, bindings = verify_checkout(reviewed_code)
    stage = stage_directory(output_root, commit)
    contracts = require_success(stage, "contracts", commit)
    smoke = require_success(stage, "smoke", commit)
    report = {
        "schema_version": "vsmt-vm04-l1-candidate-revision-report-v1",
        "stage_id": STAGE_ID,
        "reviewed_code": commit,
        "bound_sha256": bindings,
        "contract_tests": contracts["observed_tests"],
        "contract_success": True,
        "smoke_success": True,
        "smoke_summary": smoke["summary"],
        "generation_performed": False,
        "training_steps": 0,
        "private_data_opened": False,
        "confirmation_data_opened": False,
        "contract_receipt_sha256": sha256(stage / "contracts.receipt.json"),
        "smoke_receipt_sha256": sha256(stage / "smoke.receipt.json"),
    }
    destination = (
        PROJECT_ROOT / "results" / "vsmt_vm04_l1_candidate_revision.json"
    )
    if destination.exists():
        existing = json.loads(destination.read_text(encoding="utf-8"))
        if existing != report:
            raise RuntimeError(f"refusing to overwrite different report: {destination}")
        print(f"VM04_L1_CANDIDATE_REVISION_EXPORT_REUSED path={destination}")
        return
    write_new_json(destination, report)
    print(f"VM04_L1_CANDIDATE_REVISION_EXPORT_OK path={destination} sha256={sha256(destination)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("contracts", "smoke", "export"))
    parser.add_argument("--reviewed-code", required=True)
    parser.add_argument(
        "--output-root", type=Path,
        default=Path("/root/autodl-tmp/vsmt_outputs"),
    )
    arguments = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", arguments.reviewed_code):
        raise SystemExit("--reviewed-code must be a full lowercase commit hash")
    if arguments.mode == "contracts":
        run_contracts(arguments.reviewed_code, arguments.output_root)
    elif arguments.mode == "smoke":
        run_smoke(arguments.reviewed_code, arguments.output_root)
    else:
        export_stage(arguments.reviewed_code, arguments.output_root)


if __name__ == "__main__":
    main()
