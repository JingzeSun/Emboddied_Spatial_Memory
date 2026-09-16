"""Public-only per-frame L2 entity proposal boundary for VM-04.

The proposal generator receives the current public RGB array and no prompt,
private identity, depth, history, program label, teacher value, or future
frame.  This module canonicalizes the returned masks and binds them to the
reviewed model/config/assets receipts.  Loading the real SAM 2.1 asset is a
separate, still-blocked production responsibility.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import re
from typing import Any, Mapping, Sequence

import numpy as np

from cpmt.hashing import canonical_json, clone_json

from .contracts import canonical_sha256
from .l1_masks import (
    AnonymousMask,
    KEEP_SUPPORTED_BORDER_REGIONS,
    REJECT_BORDER_REGIONS,
)


HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
MODEL_ID = "sam2.1.hiera_small.per_frame_automatic_mask_generator"
PROMPT_POLICY = "fixed_grid_only_no_text_no_private_points_or_boxes"
PROPOSAL_SOURCE_ID = "l2.sam2.1_hiera_small.per_frame.public_rgb.v1"
RECEIPT_SCHEMA = "vsmt-vm04-l2-proposal-receipt-v1"


@dataclass(frozen=True)
class Vm04L2ProposalConfig:
    """All proposal boundary values are explicit; there are no defaults."""

    image_height: int
    image_width: int
    minimum_visible_pixels: int
    border_truncation_policy: str
    maximum_proposals_per_frame: int
    model_id: str
    repository_commit: str
    checkpoint_sha256: str
    automatic_mask_generator_config_sha256: str
    assets_receipt_sha256: str
    generator_code_sha256: str
    prompt_policy: str
    cross_frame_memory_enabled: bool
    overlap_policy: str

    def __post_init__(self) -> None:
        for name in (
            "image_height", "image_width", "minimum_visible_pixels",
            "maximum_proposals_per_frame",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.border_truncation_policy not in {
            KEEP_SUPPORTED_BORDER_REGIONS, REJECT_BORDER_REGIONS,
        }:
            raise ValueError("unsupported L2 border truncation policy")
        if self.model_id != MODEL_ID:
            raise ValueError("unexpected L2 proposal model")
        if HEX40.fullmatch(self.repository_commit) is None:
            raise ValueError("repository_commit must be a lowercase 40-hex commit")
        for name in (
            "checkpoint_sha256", "automatic_mask_generator_config_sha256",
            "assets_receipt_sha256", "generator_code_sha256",
        ):
            if HEX64.fullmatch(getattr(self, name)) is None:
                raise ValueError(f"{name} must be a lowercase SHA-256")
        if self.prompt_policy != PROMPT_POLICY:
            raise ValueError("L2 proposal prompt policy changed")
        if self.cross_frame_memory_enabled is not False:
            raise ValueError("cross-frame proposal memory must remain disabled")
        if self.overlap_policy != "preserve_independent_overlapping_proposals":
            raise ValueError("L2 overlap policy changed")


@dataclass(frozen=True)
class RejectedL2Proposal:
    mask_sha256: str
    visible_pixel_count: int
    touches_border: bool
    reason: str

    def public_record(self) -> dict[str, Any]:
        return asdict(self)


def _mask_digest(mask: np.ndarray) -> str:
    height, width = mask.shape
    payload = [int(height), int(width), *mask.astype(np.uint8).reshape(-1).tolist()]
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _pixel_digest(rgb: np.ndarray) -> str:
    payload = [*rgb.shape, *rgb.reshape(-1).tolist()]
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _touches_border(mask: np.ndarray) -> bool:
    return bool(
        mask[0, :].any() or mask[-1, :].any()
        or mask[:, 0].any() or mask[:, -1].any()
    )


def _canonicalize_masks(
    rows: Sequence[Mapping[str, Any]], config: Vm04L2ProposalConfig,
) -> tuple[tuple[AnonymousMask, ...], tuple[RejectedL2Proposal, ...]]:
    if len(rows) > config.maximum_proposals_per_frame:
        raise ValueError("L2 generator exceeded maximum_proposals_per_frame")
    accepted: list[tuple[int, int, str, np.ndarray, bool]] = []
    rejected: list[RejectedL2Proposal] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping) or "segmentation" not in row:
            raise ValueError("each L2 proposal must contain segmentation")
        mask = np.asarray(row["segmentation"])
        expected = (config.image_height, config.image_width)
        if mask.shape != expected or mask.dtype != np.bool_:
            raise ValueError(f"L2 segmentation must be bool with shape {expected}")
        mask = np.ascontiguousarray(mask)
        digest = _mask_digest(mask)
        if digest in seen:
            raise ValueError("L2 generator returned a duplicate mask")
        seen.add(digest)
        count = int(mask.sum())
        border = _touches_border(mask) if count else False
        reason = None
        if count == 0:
            reason = "empty_proposal"
        elif count < config.minimum_visible_pixels:
            reason = "below_minimum_visible_pixels"
        elif (border and config.border_truncation_policy ==
              REJECT_BORDER_REGIONS):
            reason = "touches_image_border"
        if reason is not None:
            rejected.append(RejectedL2Proposal(digest, count, border, reason))
            continue
        accepted.append((int(np.flatnonzero(mask)[0]), count, digest, mask, border))
    accepted.sort(key=lambda item: (item[0], item[1], item[2]))
    masks = tuple(
        AnonymousMask(
            region_id=f"region:{index:04d}", mask_sha256=digest,
            height=config.image_height, width=config.image_width,
            row_major_values=tuple(int(value) for value in mask.reshape(-1)),
            visible_pixel_count=count, touches_border=border,
        )
        for index, (_first, count, digest, mask, border) in enumerate(accepted)
    )
    rejected.sort(key=lambda item: (
        item.visible_pixel_count, item.mask_sha256, item.reason,
    ))
    return masks, tuple(rejected)


def run_vm04_l2_proposal_frontend(
    *, rgb: Any, public_rgb_file_sha256: str, generator: Any,
    config: Vm04L2ProposalConfig,
) -> dict[str, Any]:
    """Run one public RGB frame through the prompt-free proposal boundary."""

    if type(config) is not Vm04L2ProposalConfig:
        raise ValueError("config must be Vm04L2ProposalConfig")
    if HEX64.fullmatch(public_rgb_file_sha256) is None:
        raise ValueError("public_rgb_file_sha256 must be a lowercase SHA-256")
    image = np.asarray(rgb)
    expected = (config.image_height, config.image_width, 3)
    if image.dtype != np.uint8 or image.shape != expected:
        raise ValueError(f"public RGB must be uint8 with shape {expected}")
    if not hasattr(generator, "generate") or not callable(generator.generate):
        raise ValueError("L2 generator must expose generate(rgb)")
    raw = generator.generate(np.ascontiguousarray(image).copy())
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise ValueError("L2 generator output must be a proposal sequence")
    masks, rejected = _canonicalize_masks(list(raw), config)
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "evidence_level": "L2_public_per_frame_RGB_proposals",
        "proposal_source_id": PROPOSAL_SOURCE_ID,
        "public_rgb_file_sha256": public_rgb_file_sha256,
        "public_rgb_pixel_sha256": _pixel_digest(image),
        "model_id": config.model_id,
        "repository_commit": config.repository_commit,
        "checkpoint_sha256": config.checkpoint_sha256,
        "automatic_mask_generator_config_sha256": (
            config.automatic_mask_generator_config_sha256
        ),
        "assets_receipt_sha256": config.assets_receipt_sha256,
        "generator_code_sha256": config.generator_code_sha256,
        "prompt_policy": config.prompt_policy,
        "cross_frame_memory_enabled": False,
        "overlap_policy": config.overlap_policy,
        "generator_input_fields": ["current_public_rgb"],
        "ordered_mask_sha256s": [mask.mask_sha256 for mask in masks],
        "accepted_proposal_count": len(masks),
        "rejected_proposals": [item.public_record() for item in rejected],
        "config_sha256": canonical_sha256(asdict(config)),
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return {
        "masks": masks,
        "receipt": clone_json(receipt),
    }


def validate_vm04_l2_proposal_receipt(
    receipt: Mapping[str, Any], *, expected_public_rgb_file_sha256: str,
    expected_config: Vm04L2ProposalConfig,
) -> dict[str, Any]:
    """Recompute the immutable provenance fields of an L2 proposal receipt."""

    value = clone_json(dict(receipt))
    seal = value.pop("receipt_sha256", None)
    if HEX64.fullmatch(str(seal)) is None or seal != canonical_sha256(value):
        raise ValueError("L2 proposal receipt digest mismatch")
    if value.get("schema_version") != RECEIPT_SCHEMA:
        raise ValueError("wrong L2 proposal receipt schema")
    if value.get("public_rgb_file_sha256") != expected_public_rgb_file_sha256:
        raise ValueError("L2 proposal receipt is bound to another RGB file")
    if value.get("config_sha256") != canonical_sha256(asdict(expected_config)):
        raise ValueError("L2 proposal receipt config mismatch")
    if value.get("generator_input_fields") != ["current_public_rgb"]:
        raise ValueError("L2 proposal receipt violates the public-only boundary")
    value["receipt_sha256"] = seal
    return value
