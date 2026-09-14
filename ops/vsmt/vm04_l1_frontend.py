"""Fixed VM-04 L1 environment and entity-materializer entry.

Run in order: ``contracts``, ``environment``, ``materializer``, then ``export``.
The environment step may extract the already downloaded reviewed AI2-THOR build
and launches one FloorPlan1 smoke frame.  The materializer step runs the real
reviewed DINOv2 weights on a synthetic frame and checks public visible geometry.
Neither step generates VM-04 houses, builds training data, opens confirmation
data, or trains a model.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "configs" / "vsmt" / "vm04_l1_environment_v1.json"
STAGE_ID = "vsmt-vm04-l1-entity-materializer-v1"
EXPECTED_TESTS = 22
BOUND_PATHS = (
    "configs/vsmt/vm04_l1_contract_proposal_v1.json",
    "configs/vsmt/vm04_l1_environment_v1.json",
    "src/vsmt/__init__.py",
    "src/vsmt/l1_entities.py",
    "src/vsmt/l1_masks.py",
    "tests/test_l1_entities.py",
    "tests/test_l1_masks.py",
    "ops/vsmt/vm04_l1_frontend.py",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_new_json(path: Path, value: Any, *, maximum_bytes: int = 67_108_864) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode(
        "utf-8",
    ) + b"\n"
    if len(encoded) > maximum_bytes:
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
    if config.get("status") != "authorized_install_and_smoke_only":
        raise RuntimeError("L1 environment config is not authorized for smoke")
    authorization = config.get("authorization", {})
    for key in ("dependency_install", "reviewed_asset_download", "simulator_smoke"):
        if authorization.get(key) is not True:
            raise RuntimeError(f"required authorization {key!r} is absent")
    for key in ("dataset_generation", "training", "confirmation"):
        if authorization.get(key) is not False:
            raise RuntimeError(f"smoke config requires {key}=false")
    materialization = config.get("entity_materialization", {})
    if materialization.get("anonymous_mask") != {
        "minimum_visible_pixels": 196,
        "border_truncation_policy": "keep_if_minimum_support",
    }:
        raise RuntimeError("approved anonymous-mask values are not bound")
    if materialization.get("dinov2") != {
        "image_shape": [224, 224, 3],
        "patch_grid": [16, 16],
        "patch_size_pixels": 14,
        "patch_token_dimension": 384,
        "minimum_total_patch_weight": 1.0,
        "unit_norm_validation_tolerance": 0.00001,
    }:
        raise RuntimeError("approved DINOv2 materialization values are not bound")
    if materialization.get("public_geometry") != {
        "depth_convention": "ai2thor_linear01_camera_axis_z_m",
        "depth_valid_range_m": [0.05, 20.0],
        "absolute_minimum_valid_depth_points": 32,
        "minimum_valid_depth_fraction": 0.25,
        "minimum_valid_depth_rounding": "ceil",
        "reliability": "valid_depth_point_count_divided_by_visible_pixel_count",
        "pixel_coordinates": "u_column_v_row_no_half_pixel_offset",
        "camera_axes": "x_right_y_up_z_forward",
        "source_commit": "f0825767cd50d69f666c7f282e54abfe58f1e917",
        "source_shader": "unity/Assets/Scripts/ImageSynthesis/Shaders/Depth.shader",
    }:
        raise RuntimeError("approved public-geometry values are not bound")
    return config


def git(*arguments: str, cwd: Path = PROJECT_ROOT) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=cwd, text=True, timeout=120,
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


def run_command(
    command: list[str], *, timeout: int, cwd: Path = PROJECT_ROOT,
    environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=cwd,
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
        "schema_version": "vsmt-vm04-l1-entity-materializer-started-v1",
        "stage_id": STAGE_ID,
        "started_at": utc_now(),
        "reviewed_code": commit,
        "bound_sha256": bindings,
        "expected_tests": EXPECTED_TESTS,
        "dataset_generation_authorized": False,
        "training_authorized": False,
        "confirmation_authorized": False,
    })
    command = [
        sys.executable, "-B", "-m", "unittest", "discover",
        "-s", str(PROJECT_ROOT / "tests"), "-p", "test_l1_*.py", "-v",
    ]
    test_environment = dict(os.environ)
    existing_pythonpath = test_environment.get("PYTHONPATH")
    test_environment["PYTHONPATH"] = str(PROJECT_ROOT / "src") + (
        os.pathsep + existing_pythonpath if existing_pythonpath else ""
    )
    result = run_command(
        command, timeout=1800, environment=test_environment,
    )
    log_path = stage / "contracts.unittest.log"
    log_path.write_text(result["output"], encoding="utf-8")
    print(result["output"], end="")
    matches = re.findall(r"Ran (\d+) tests?", result["output"])
    observed = int(matches[-1]) if matches else None
    success = (
        result["exit_code"] == 0
        and observed == EXPECTED_TESTS
        and "OK" in result["output"]
    )
    receipt = {
        "schema_version": "vsmt-vm04-l1-contract-receipt-v1",
        "stage_id": STAGE_ID,
        "reviewed_code": commit,
        "bound_sha256": bindings,
        "expected_tests": EXPECTED_TESTS,
        "observed_tests": observed,
        "exit_code": result["exit_code"],
        "success": success,
        "wall_seconds": result["wall_seconds"],
        "completed_at": utc_now(),
        "generation_performed": False,
        "training_steps": 0,
        "confirmation_data_opened": False,
        "log_sha256": sha256(log_path),
    }
    receipt_path = stage / "contracts.receipt.json"
    write_new_json(receipt_path, receipt)
    if not success:
        print(f"VM04_L1_CONTRACTS_FAILED stage={stage}")
        raise SystemExit(1)
    write_new_json(stage / "contracts.success.json", {
        "schema_version": "vsmt-vm04-l1-contract-success-v1",
        "reviewed_code": commit,
        "receipt_sha256": sha256(receipt_path),
        "observed_tests": observed,
        "success": True,
    })
    print(f"VM04_L1_CONTRACTS_OK stage={stage} tests={observed}")


def _ensure_reviewed_build(config: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    asset = config["reviewed_assets"]
    asset_root = Path(asset["asset_root"]).resolve()
    default_base = Path("/root/.ai2thor")
    if not default_base.is_symlink() or default_base.resolve() != asset_root:
        raise RuntimeError(
            f"AI2-THOR default base must resolve to reviewed asset root {asset_root}"
        )
    name = f"thor-CloudRendering-{asset['AI2_THOR_CloudRendering_commit']}"
    archive = asset_root / "download" / f"{name}.zip"
    if not archive.is_file():
        raise RuntimeError(f"reviewed AI2-THOR archive is missing: {archive}")
    archive_bytes = archive.stat().st_size
    archive_sha256 = sha256(archive)
    if archive_bytes != int(asset["AI2_THOR_CloudRendering_zip_bytes"]):
        raise RuntimeError("AI2-THOR archive size mismatch")
    if archive_sha256 != asset["AI2_THOR_CloudRendering_zip_sha256"]:
        raise RuntimeError("AI2-THOR archive SHA-256 mismatch")

    releases = asset_root / "releases"
    release = releases / name
    executable = release / name
    extracted_now = False
    if not release.exists():
        temporary = asset_root / "tmp" / f"{name}.extracting"
        if temporary.exists():
            raise RuntimeError(f"preserved incomplete extraction requires review: {temporary}")
        temporary.mkdir(parents=True)
        try:
            with zipfile.ZipFile(archive) as bundle:
                temporary_root = temporary.resolve()
                for member in bundle.infolist():
                    target = (temporary / member.filename).resolve()
                    if temporary_root not in target.parents and target != temporary_root:
                        raise RuntimeError(
                            f"AI2-THOR archive member escapes extraction root: {member.filename}"
                        )
                bundle.extractall(temporary)
            releases.mkdir(parents=True, exist_ok=True)
            os.rename(temporary, release)
            extracted_now = True
        except BaseException:
            raise RuntimeError(f"AI2-THOR extraction failed; preserved {temporary}")
    if not executable.is_file():
        raise RuntimeError(f"AI2-THOR executable is missing: {executable}")
    executable.chmod(0o755)
    return executable, {
        "archive_path": str(archive),
        "archive_bytes": archive_bytes,
        "archive_sha256": archive_sha256,
        "release_path": str(release),
        "executable_path": str(executable),
        "extracted_now": extracted_now,
    }


def run_environment(reviewed_code: str, output_root: Path) -> None:
    config = load_config()
    commit, bindings = verify_checkout(reviewed_code)
    stage = stage_directory(output_root, commit)
    require_success(stage, "contracts", commit)
    if (stage / "environment.receipt.json").exists():
        raise RuntimeError("environment receipt already exists")

    simulator = config["environment_separation"]["simulator_process"]
    simulator_python = Path(simulator["environment_path"]) / "bin" / "python"
    if not simulator_python.is_file():
        raise RuntimeError(f"simulator Python is missing: {simulator_python}")
    probe_code = (
        "import importlib.metadata as m,json,sys;"
        "print(json.dumps({'python':'.'.join(map(str,sys.version_info[:3])),"
        "'ai2thor':m.version('ai2thor'),'procthor':m.version('procthor')}))"
    )
    package_probe = run_command(
        [str(simulator_python), "-c", probe_code], timeout=120,
    )
    if package_probe["exit_code"] != 0:
        raise RuntimeError(f"simulator package probe failed: {package_probe['output']}")
    observed_packages = json.loads(package_probe["output"].strip())
    expected_packages = simulator["packages"]
    if not (
        observed_packages["python"] == simulator["python"]
        and observed_packages["ai2thor"] == expected_packages["ai2thor"]
        and observed_packages["procthor"] == expected_packages["procthor"]
    ):
        raise RuntimeError("simulator environment version mismatch")

    vulkan = run_command(["vulkaninfo", "--summary"], timeout=120)
    if vulkan["exit_code"] != 0 or config["system_runtime"]["required_GPU"].replace(
        "_", " ",
    ) not in vulkan["output"]:
        raise RuntimeError("Vulkan does not expose the required NVIDIA GPU")

    executable, build = _ensure_reviewed_build(config)
    smoke_code = """
import json
from ai2thor.controller import Controller
from ai2thor.platform import CloudRendering
controller = Controller(
    platform=CloudRendering,
    scene='FloorPlan1', width=224, height=224,
    renderDepthImage=True, renderInstanceSegmentation=True,
)
try:
    event = controller.step(action='Pass')
    print(json.dumps({
        'last_action_success': event.metadata['lastActionSuccess'],
        'frame_shape': list(event.frame.shape),
        'depth_shape': list(event.depth_frame.shape),
        'instance_shape': list(event.instance_segmentation_frame.shape),
        'instance_mask_count': len(event.instance_masks),
    }, sort_keys=True))
finally:
    controller.stop()
"""
    runtime_dir = output_root.resolve() / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    runtime_dir.chmod(0o700)
    environment = dict(os.environ)
    environment["XDG_RUNTIME_DIR"] = str(runtime_dir)
    smoke = run_command(
        [str(simulator_python), "-c", smoke_code],
        timeout=600,
        environment=environment,
    )
    log_path = stage / "environment.smoke.log"
    log_path.write_text(smoke["output"], encoding="utf-8")
    print(smoke["output"], end="")
    success = smoke["exit_code"] == 0
    smoke_result: dict[str, Any] | None = None
    if success:
        lines = [line for line in smoke["output"].splitlines() if line.startswith("{")]
        smoke_result = json.loads(lines[-1]) if lines else None
        success = bool(
            smoke_result
            and smoke_result.get("last_action_success") is True
            and smoke_result.get("frame_shape") == [224, 224, 3]
            and smoke_result.get("depth_shape") == [224, 224]
            and smoke_result.get("instance_shape") == [224, 224, 3]
            and int(smoke_result.get("instance_mask_count", 0)) > 0
        )

    frontend = config["environment_separation"]["public_materializer_process"]
    dino_repository = Path(frontend["DINOv2_repository"])
    dino_checkpoint = Path(frontend["DINOv2_checkpoint"])
    dino_commit = git("rev-parse", "HEAD", cwd=dino_repository)
    dino_sha256 = sha256(dino_checkpoint)
    if not (
        dino_commit == frontend["DINOv2_repository_commit"]
        and dino_sha256 == frontend["DINOv2_checkpoint_sha256"]
    ):
        raise RuntimeError("reviewed DINOv2 assets do not match")

    receipt = {
        "schema_version": "vsmt-vm04-l1-environment-receipt-v1",
        "stage_id": STAGE_ID,
        "reviewed_code": commit,
        "bound_sha256": bindings,
        "success": success,
        "completed_at": utc_now(),
        "package_probe": observed_packages,
        "vulkan_summary_sha256": hashlib.sha256(
            vulkan["output"].encode("utf-8"),
        ).hexdigest(),
        "build": build,
        "smoke": smoke_result,
        "smoke_exit_code": smoke["exit_code"],
        "smoke_wall_seconds": smoke["wall_seconds"],
        "smoke_log_sha256": sha256(log_path),
        "DINOv2_repository_commit": dino_commit,
        "DINOv2_checkpoint_sha256": dino_sha256,
        "generation_performed": False,
        "training_steps": 0,
        "private_data_persisted": False,
        "confirmation_data_opened": False,
    }
    receipt_path = stage / "environment.receipt.json"
    write_new_json(receipt_path, receipt)
    if not success:
        print(f"VM04_L1_ENVIRONMENT_FAILED stage={stage}")
        raise SystemExit(1)
    write_new_json(stage / "environment.success.json", {
        "schema_version": "vsmt-vm04-l1-environment-success-v1",
        "reviewed_code": commit,
        "receipt_sha256": sha256(receipt_path),
        "success": True,
    })
    print(f"VM04_L1_ENVIRONMENT_OK stage={stage}")


def run_materializer(reviewed_code: str, output_root: Path) -> None:
    config = load_config()
    commit, bindings = verify_checkout(reviewed_code)
    stage = stage_directory(output_root, commit)
    require_success(stage, "contracts", commit)
    require_success(stage, "environment", commit)
    if (stage / "materializer.receipt.json").exists():
        raise RuntimeError("materializer receipt already exists")

    started = time.monotonic()
    success = False
    error: dict[str, str] | None = None
    summary: dict[str, Any] | None = None
    runtime: dict[str, Any] = {}
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
        import numpy as np
        import torch

        from vsmt.l1_entities import (
            AI2THOR_CAMERA_AXIS_Z,
            DINORegionConfig,
            PublicGeometryConfig,
            extract_dinov2_patch_tokens,
            materialize_l1_entity_observation,
        )
        from vsmt.l1_masks import (
            KEEP_SUPPORTED_BORDER_REGIONS,
            L1MaskConfig,
            anonymize_instance_masks,
        )

        frontend = config["environment_separation"]["public_materializer_process"]
        expected_python = frontend["python"]
        observed_python = ".".join(map(str, sys.version_info[:3]))
        if observed_python != expected_python:
            raise RuntimeError(
                f"public materializer Python {observed_python} != {expected_python}"
            )
        dino_repository = Path(frontend["DINOv2_repository"])
        dino_checkpoint = Path(frontend["DINOv2_checkpoint"])
        if git("rev-parse", "HEAD", cwd=dino_repository) != frontend["DINOv2_repository_commit"]:
            raise RuntimeError("reviewed DINOv2 repository commit mismatch")
        if sha256(dino_checkpoint) != frontend["DINOv2_checkpoint_sha256"]:
            raise RuntimeError("reviewed DINOv2 checkpoint digest mismatch")
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is required for the real DINOv2 smoke")
        sys.path.insert(0, str(dino_repository))
        from dinov2.hub.backbones import dinov2_vits14

        dino_values = config["entity_materialization"]["dinov2"]
        geometry_values = config["entity_materialization"]["public_geometry"]
        descriptor_config = DINORegionConfig(
            image_height=dino_values["image_shape"][0],
            image_width=dino_values["image_shape"][1],
            patch_size_pixels=dino_values["patch_size_pixels"],
            patch_token_dimension=dino_values["patch_token_dimension"],
            minimum_total_patch_weight=dino_values["minimum_total_patch_weight"],
            unit_norm_validation_tolerance=dino_values["unit_norm_validation_tolerance"],
        )
        geometry_config = PublicGeometryConfig(
            depth_convention=AI2THOR_CAMERA_AXIS_Z,
            minimum_depth_m=geometry_values["depth_valid_range_m"][0],
            maximum_depth_m=geometry_values["depth_valid_range_m"][1],
            absolute_minimum_valid_depth_points=geometry_values[
                "absolute_minimum_valid_depth_points"
            ],
            minimum_valid_depth_fraction=geometry_values[
                "minimum_valid_depth_fraction"
            ],
        )

        device = "cuda"
        model = dinov2_vits14(pretrained=False)
        state = torch.load(dino_checkpoint, map_location="cpu", weights_only=True)
        model.load_state_dict(state, strict=True)
        model.requires_grad_(False).eval().to(device)
        rows, columns = np.indices((224, 224), dtype=np.uint16)
        rgb = np.stack((
            rows % 256,
            columns % 256,
            (rows + columns) % 256,
        ), axis=-1).astype(np.uint8)
        private_mask = np.zeros((224, 224), dtype=np.bool_)
        private_mask[98:112, 98:112] = True
        mask_values = config["entity_materialization"]["anonymous_mask"]
        region = anonymize_instance_masks(
            {"synthetic-private-key": private_mask},
            L1MaskConfig(
                minimum_visible_pixels=mask_values["minimum_visible_pixels"],
                border_truncation_policy=KEEP_SUPPORTED_BORDER_REGIONS,
            ),
        ).regions[0]
        patch_tokens = extract_dinov2_patch_tokens(
            model, rgb, descriptor_config, device=device,
        )
        depth = np.full((224, 224), 1.5, dtype=np.float32)
        observation = materialize_l1_entity_observation(
            region,
            patch_tokens,
            depth,
            {"fx": 112.0, "fy": 112.0, "cx": 111.5, "cy": 111.5},
            {
                "position_m": [0.0, 0.0, 0.0],
                "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
            },
            descriptor_config,
            geometry_config,
        )
        record = observation.public_record()
        descriptor_array = np.asarray(record["descriptor"], dtype="<f4")
        descriptor_norm = float(np.linalg.norm(descriptor_array.astype(np.float64)))
        success = bool(
            patch_tokens.shape == (16, 16, 384)
            and len(record["descriptor"]) == 384
            and abs(descriptor_norm - 1.0)
            <= dino_values["unit_norm_validation_tolerance"]
            and observation.descriptor.total_patch_weight == 1.0
            and observation.geometry.valid_depth_point_count == 196
            and observation.geometry.required_valid_depth_point_count == 49
            and observation.geometry.reliability == 1.0
        )
        summary = {
            "input_kind": "deterministic_synthetic_non_dataset_frame",
            "rgb_shape": list(rgb.shape),
            "patch_token_shape": list(patch_tokens.shape),
            "region_visible_pixels": region.visible_pixel_count,
            "total_patch_weight": observation.descriptor.total_patch_weight,
            "descriptor_dimension": len(record["descriptor"]),
            "descriptor_norm": descriptor_norm,
            "descriptor_float32_sha256": hashlib.sha256(
                descriptor_array.tobytes(),
            ).hexdigest(),
            "centroid_m": record["centroid_m"],
            "extent_m": record["extent_m"],
            "valid_depth_point_count": observation.geometry.valid_depth_point_count,
            "required_valid_depth_point_count": (
                observation.geometry.required_valid_depth_point_count
            ),
            "reliability": record["reliability"],
            "private_instance_value_in_public_record": (
                "synthetic-private-key" in json.dumps(record, sort_keys=True)
            ),
        }
        runtime = {
            "python": observed_python,
            "torch": torch.__version__,
            "cuda_device": torch.cuda.get_device_name(0),
            "DINOv2_repository_commit": frontend["DINOv2_repository_commit"],
            "DINOv2_checkpoint_sha256": frontend["DINOv2_checkpoint_sha256"],
        }
        del model, state
        torch.cuda.empty_cache()
    except BaseException as exception:
        error = {
            "type": type(exception).__name__,
            "message": str(exception),
        }

    receipt = {
        "schema_version": "vsmt-vm04-l1-entity-materializer-receipt-v1",
        "stage_id": STAGE_ID,
        "reviewed_code": commit,
        "bound_sha256": bindings,
        "success": success,
        "completed_at": utc_now(),
        "wall_seconds": time.monotonic() - started,
        "runtime": runtime,
        "materializer_smoke": summary,
        "error": error,
        "generation_performed": False,
        "training_steps": 0,
        "private_data_persisted": False,
        "confirmation_data_opened": False,
    }
    receipt_path = stage / "materializer.receipt.json"
    write_new_json(receipt_path, receipt)
    if not success:
        print(f"VM04_L1_MATERIALIZER_FAILED stage={stage} error={error}")
        raise SystemExit(1)
    write_new_json(stage / "materializer.success.json", {
        "schema_version": "vsmt-vm04-l1-entity-materializer-success-v1",
        "reviewed_code": commit,
        "receipt_sha256": sha256(receipt_path),
        "success": True,
    })
    print(f"VM04_L1_MATERIALIZER_OK stage={stage}")


def run_export(reviewed_code: str, output_root: Path) -> None:
    load_config()
    commit, bindings = verify_checkout(reviewed_code)
    stage = stage_directory(output_root, commit)
    contracts = require_success(stage, "contracts", commit)
    environment = require_success(stage, "environment", commit)
    materializer = require_success(stage, "materializer", commit)
    destination = PROJECT_ROOT / "results" / "vsmt_vm04_l1_entity_materializer.json"
    report = {
        "schema_version": "vsmt-vm04-l1-entity-materializer-report-v1",
        "stage_id": STAGE_ID,
        "reviewed_code": commit,
        "bound_sha256": bindings,
        "contract_tests": contracts["observed_tests"],
        "contract_success": contracts["success"],
        "environment_success": environment["success"],
        "package_probe": environment["package_probe"],
        "build": environment["build"],
        "smoke": environment["smoke"],
        "DINOv2_repository_commit": environment["DINOv2_repository_commit"],
        "DINOv2_checkpoint_sha256": environment["DINOv2_checkpoint_sha256"],
        "materializer_success": materializer["success"],
        "materializer_runtime": materializer["runtime"],
        "materializer_smoke": materializer["materializer_smoke"],
        "generation_performed": False,
        "training_steps": 0,
        "confirmation_data_opened": False,
        "exported_at": utc_now(),
    }
    write_new_json(destination, report)
    print(f"VM04_L1_EXPORT_OK report={destination} sha256={sha256(destination)}")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument(
        "mode", choices=("contracts", "environment", "materializer", "export"),
    )
    value.add_argument("--reviewed-code", required=True)
    value.add_argument(
        "--output-root", type=Path,
        default=Path("/root/autodl-tmp/vsmt_outputs"),
    )
    return value


def main() -> None:
    arguments = parser().parse_args()
    if arguments.mode == "contracts":
        run_contracts(arguments.reviewed_code, arguments.output_root)
    elif arguments.mode == "environment":
        run_environment(arguments.reviewed_code, arguments.output_root)
    elif arguments.mode == "materializer":
        run_materializer(arguments.reviewed_code, arguments.output_root)
    else:
        run_export(arguments.reviewed_code, arguments.output_root)


if __name__ == "__main__":
    main()
