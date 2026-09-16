"""Exact executable configuration boundary for the VM-04 materializer.

This module only validates and constructs already-reviewed scientific values.
It deliberately supplies no threshold, model, timing, or action defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
import hashlib
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping, TypeVar

from cpmt.hashing import canonical_json, clone_json

from .causal_prior import PublicBootstrapConfig
from .l1_entities import DINORegionConfig, PublicGeometryConfig
from .l1_masks import L1MaskConfig
from .l1_structures import (
    FreeSpaceMaterializationConfig,
    PlaceMaterializationConfig,
    SurfaceMaterializationConfig,
)
from .vm04_public_frontend import Vm04PublicFrontendConfig
from .vm04_public_frontend_sequence import Vm04PublicFrontendSequence


SCHEMA = "vsmt-vm04-materializer-config-v1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
TOP_KEYS = {
    "schema_version", "status", "frontend", "bootstrap", "model",
    "public_constants", "builder_code_sha256", "config_sha256",
}
FRONTEND_KEYS = {
    "mask", "descriptor", "entity_geometry", "surface", "place",
    "free_space", "supported_by_maximum_normal_angle_degrees",
    "supported_by_minimum_gap_m", "supported_by_maximum_gap_m",
    "supported_by_minimum_projected_overlap",
    "supported_by_maximum_mask_overlap_fraction",
}
MODEL_KEYS = {
    "model_id", "architecture", "repository_commit", "checkpoint_sha256",
    "patch_token_output_key", "input_image_height", "input_image_width",
    "patch_size_pixels", "patch_token_dimension", "evaluation_mode",
    "parameters_frozen",
}
PUBLIC_CONSTANT_KEYS = {
    "coordinate_frame", "depth_unit", "descriptor_model_id",
    "proposal_model_id",
}
T = TypeVar("T")


@dataclass(frozen=True)
class ValidatedVm04MaterializerConfig:
    frontend: Vm04PublicFrontendConfig
    bootstrap: PublicBootstrapConfig
    model: dict[str, Any]
    public_constants: dict[str, Any]
    builder_code_sha256: str
    config_sha256: str


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _construct_exact(
    cls: type[T], raw: Any, name: str, *, tuple_fields: set[str] | None = None,
) -> T:
    expected = {field.name for field in fields(cls)}
    _require(type(raw) is dict and set(raw) == expected,
             f"{name} must contain exactly {sorted(expected)}")
    values = clone_json(raw)
    for field_name in tuple_fields or set():
        _require(type(values[field_name]) is list,
                 f"{name}.{field_name} must be an array")
        values[field_name] = tuple(values[field_name])
    return cls(**values)


def validate_vm04_materializer_config(
    raw: Mapping[str, Any],
) -> ValidatedVm04MaterializerConfig:
    """Validate one complete config and construct typed front-end objects."""

    _require(type(raw) is dict and set(raw) == TOP_KEYS,
             "materializer config has unexpected fields")
    record = clone_json(raw)
    _require(record["schema_version"] == SCHEMA,
             "wrong materializer config schema")
    _require(record["status"] == "frozen_executable",
             "materializer config is not frozen executable")
    claimed = record.pop("config_sha256")
    _require(type(claimed) is str and HEX64.fullmatch(claimed) is not None,
             "config_sha256 must be a lowercase SHA-256")
    _require(claimed == _sha(record), "materializer config digest mismatch")

    frontend_raw = record["frontend"]
    _require(type(frontend_raw) is dict and set(frontend_raw) == FRONTEND_KEYS,
             "frontend config has unexpected fields")
    frontend = Vm04PublicFrontendConfig(
        mask=_construct_exact(L1MaskConfig, frontend_raw["mask"], "mask"),
        descriptor=_construct_exact(
            DINORegionConfig, frontend_raw["descriptor"], "descriptor",
        ),
        entity_geometry=_construct_exact(
            PublicGeometryConfig, frontend_raw["entity_geometry"],
            "entity_geometry",
        ),
        surface=_construct_exact(
            SurfaceMaterializationConfig, frontend_raw["surface"], "surface",
        ),
        place=_construct_exact(
            PlaceMaterializationConfig, frontend_raw["place"], "place",
            tuple_fields={"grid_origin_m"},
        ),
        free_space=_construct_exact(
            FreeSpaceMaterializationConfig, frontend_raw["free_space"],
            "free_space", tuple_fields={"block_widths_in_tiles"},
        ),
        **{
            key: frontend_raw[key]
            for key in FRONTEND_KEYS
            if key not in {
                "mask", "descriptor", "entity_geometry", "surface", "place",
                "free_space",
            }
        },
    )
    bootstrap = _construct_exact(
        PublicBootstrapConfig, record["bootstrap"], "bootstrap",
    )

    model = record["model"]
    _require(type(model) is dict and set(model) == MODEL_KEYS,
             "materializer model provenance has unexpected fields")
    for key in ("model_id", "architecture", "patch_token_output_key"):
        _require(type(model[key]) is str and model[key],
                 f"materializer model {key} must be nonempty")
    _require(type(model["repository_commit"]) is str and
             HEX40.fullmatch(model["repository_commit"]) is not None,
             "model repository_commit must be a lowercase Git commit")
    _require(type(model["checkpoint_sha256"]) is str and
             HEX64.fullmatch(model["checkpoint_sha256"]) is not None,
             "model checkpoint_sha256 must be a lowercase SHA-256")
    _require(model["evaluation_mode"] is True and
             model["parameters_frozen"] is True,
             "materializer model must be frozen in evaluation mode")
    descriptor_shape = {
        "input_image_height": frontend.descriptor.image_height,
        "input_image_width": frontend.descriptor.image_width,
        "patch_size_pixels": frontend.descriptor.patch_size_pixels,
        "patch_token_dimension": frontend.descriptor.patch_token_dimension,
    }
    _require(all(
        type(model[name]) is int and model[name] == expected
        for name, expected in descriptor_shape.items()
    ), "materializer model shape does not match descriptor config")

    constants = record["public_constants"]
    _require(type(constants) is dict and set(constants) == PUBLIC_CONSTANT_KEYS,
             "materializer public constants have unexpected fields")
    _require(all(type(value) is str and value for value in constants.values()),
             "materializer public constants must be nonempty strings")
    _require(constants["descriptor_model_id"] == model["model_id"],
             "descriptor_model_id does not bind the frozen model")
    builder_code = record["builder_code_sha256"]
    _require(type(builder_code) is str and HEX64.fullmatch(builder_code) is not None,
             "builder_code_sha256 must be a lowercase SHA-256")
    return ValidatedVm04MaterializerConfig(
        frontend=frontend,
        bootstrap=bootstrap,
        model=clone_json(model),
        public_constants=clone_json(constants),
        builder_code_sha256=builder_code,
        config_sha256=claimed,
    )


def build_vm04_public_frontend_sequence(
    raw_config: Mapping[str, Any], *,
    public_frame_context_bundle: Mapping[str, Any],
    private_frame_roles: list[str],
    patch_token_extractor: Any,
) -> tuple[Vm04PublicFrontendSequence, str]:
    """Build the production callback only from one sealed executable config."""

    parsed = validate_vm04_materializer_config(raw_config)
    _require(callable(patch_token_extractor),
             "patch_token_extractor must be callable")

    callback = Vm04PublicFrontendSequence(
        public_frame_context_bundle=public_frame_context_bundle,
        private_frame_roles=private_frame_roles,
        patch_token_extractor=patch_token_extractor,
        frontend_config=parsed.frontend,
        bootstrap_config=parsed.bootstrap,
        builder_code_sha256=parsed.builder_code_sha256,
    )
    return callback, parsed.config_sha256


def verify_vm04_materializer_assets(
    parsed: ValidatedVm04MaterializerConfig, *,
    repository_root: Path, checkpoint_path: Path,
) -> dict[str, Any]:
    """Read-only verification of the frozen repository and checkpoint bytes."""

    _require(type(parsed) is ValidatedVm04MaterializerConfig,
             "parsed materializer config has the wrong type")
    repository_root = Path(repository_root)
    checkpoint_path = Path(checkpoint_path)
    _require(repository_root.is_dir(), "model repository is missing")
    _require(checkpoint_path.is_file(), "model checkpoint is missing")

    def git(*arguments: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(repository_root), *arguments],
            check=False, capture_output=True, text=True,
        )
        _require(result.returncode == 0,
                 "model repository Git verification failed")
        return result.stdout.strip()

    commit = git("rev-parse", "HEAD")
    _require(commit == parsed.model["repository_commit"],
             "model repository commit differs from sealed config")
    _require(git("status", "--porcelain", "--untracked-files=all") == "",
             "model repository worktree is not clean")
    digest = hashlib.sha256()
    with checkpoint_path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    checkpoint_sha256 = digest.hexdigest()
    _require(checkpoint_sha256 == parsed.model["checkpoint_sha256"],
             "model checkpoint digest differs from sealed config")
    receipt = {
        "schema_version": "vsmt-vm04-materializer-assets-receipt-v1",
        "materializer_config_sha256": parsed.config_sha256,
        "model_id": parsed.model["model_id"],
        "repository_commit": commit,
        "repository_worktree_clean": True,
        "checkpoint_sha256": checkpoint_sha256,
        "network_access_required": False,
    }
    receipt["receipt_sha256"] = _sha(receipt)
    return receipt
