"""L1 single-frame oracle-mask anonymization.

The isolated materializer may inspect simulator instance identifiers only long
enough to collect each instance's complete visible mask.  Public output is
ordered solely by mask content and never contains those identifiers.  This
module does not link regions across frames, extract visual descriptors, infer
geometry, or choose memory transactions.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping

import numpy as np

from cpmt.hashing import canonical_json


KEEP_SUPPORTED_BORDER_REGIONS = "keep_if_minimum_support"
REJECT_BORDER_REGIONS = "reject_if_touches_border"
BORDER_POLICIES = {KEEP_SUPPORTED_BORDER_REGIONS, REJECT_BORDER_REGIONS}


@dataclass(frozen=True)
class L1MaskConfig:
    """Explicit support rules; there are deliberately no scientific defaults."""

    minimum_visible_pixels: int
    border_truncation_policy: str

    def __post_init__(self) -> None:
        if type(self.minimum_visible_pixels) is not int or self.minimum_visible_pixels < 1:
            raise ValueError("minimum_visible_pixels must be a positive integer")
        if self.border_truncation_policy not in BORDER_POLICIES:
            raise ValueError(
                "border_truncation_policy must be one of "
                f"{sorted(BORDER_POLICIES)}"
            )


@dataclass(frozen=True)
class AnonymousMask:
    region_id: str
    mask_sha256: str
    height: int
    width: int
    row_major_values: tuple[int, ...]
    visible_pixel_count: int
    touches_border: bool

    def as_array(self) -> np.ndarray:
        """Return a fresh boolean array so callers cannot mutate sealed bytes."""

        return np.asarray(self.row_major_values, dtype=np.bool_).reshape(
            self.height, self.width,
        )

    def public_record(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "structure_kind": "entity",
            "mask_sha256": self.mask_sha256,
            "height": self.height,
            "width": self.width,
            "row_major_values": list(self.row_major_values),
            "visible_pixel_count": self.visible_pixel_count,
            "touches_border": self.touches_border,
        }


@dataclass(frozen=True)
class RejectedAnonymousMask:
    mask_sha256: str
    visible_pixel_count: int
    touches_border: bool
    reason: str

    def public_record(self) -> dict[str, Any]:
        return {
            "mask_sha256": self.mask_sha256,
            "visible_pixel_count": self.visible_pixel_count,
            "touches_border": self.touches_border,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class L1MaskMaterialization:
    height: int
    width: int
    regions: tuple[AnonymousMask, ...]
    rejected: tuple[RejectedAnonymousMask, ...]
    private_instance_mapping_sha256: str

    def public_cache(self) -> dict[str, Any]:
        return {
            "schema_version": "vsmt-l1-anonymous-mask-cache-v1",
            "height": self.height,
            "width": self.width,
            "regions": [region.public_record() for region in self.regions],
            "rejected": [item.public_record() for item in self.rejected],
        }

    def public_cache_sha256(self) -> str:
        return _sha256_json(self.public_cache())


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _binary_mask(value: Any, *, name: str) -> np.ndarray:
    array = np.asarray(value)
    if array.ndim != 2 or array.shape[0] < 1 or array.shape[1] < 1:
        raise ValueError(f"{name} must be a nonempty two-dimensional mask")
    if not (
        np.issubdtype(array.dtype, np.bool_)
        or (
            np.issubdtype(array.dtype, np.number)
            and np.isfinite(array).all()
            and np.logical_or(array == 0, array == 1).all()
        )
    ):
        raise ValueError(f"{name} must contain only finite binary values")
    return np.ascontiguousarray(array, dtype=np.uint8)


def _mask_payload(mask: np.ndarray) -> list[int]:
    height, width = mask.shape
    return [int(height), int(width), *mask.reshape(-1).tolist()]


def _touches_border(mask: np.ndarray) -> bool:
    return bool(
        mask[0, :].any()
        or mask[-1, :].any()
        or mask[:, 0].any()
        or mask[:, -1].any()
    )


def anonymize_instance_masks(
    instance_masks: Mapping[str, Any], config: L1MaskConfig,
) -> L1MaskMaterialization:
    """Create packet-local masks without exposing or sorting by instance IDs.

    Every nonempty input entry is one simulator instance in the current frame.
    Disconnected components remain in that one mask.  Empty entries disappear,
    while support and border rejections remain visible as anonymous failures.
    """

    if not isinstance(instance_masks, Mapping):
        raise ValueError("instance_masks must be a mapping")

    source: list[tuple[str, np.ndarray, str, int, bool, int]] = []
    expected_shape: tuple[int, int] | None = None
    occupied: np.ndarray | None = None
    private_bindings: list[list[Any]] = []
    for source_key, value in instance_masks.items():
        if type(source_key) is not str or not source_key:
            raise ValueError("instance mask keys must be nonempty strings")
        mask = _binary_mask(value, name="instance mask")
        if expected_shape is None:
            expected_shape = (int(mask.shape[0]), int(mask.shape[1]))
            occupied = np.zeros(expected_shape, dtype=np.bool_)
        if tuple(mask.shape) != expected_shape:
            raise ValueError("all instance masks must have the same shape")
        payload = _mask_payload(mask)
        digest = _sha256_json(payload)
        count = int(mask.sum())
        private_bindings.append([source_key, digest])
        if count == 0:
            continue
        assert occupied is not None
        binary = mask.astype(np.bool_, copy=False)
        if np.logical_and(occupied, binary).any():
            raise ValueError("nonempty instance masks must not overlap")
        occupied |= binary
        first_true = int(np.flatnonzero(mask)[0])
        source.append((digest, mask, source_key, count, _touches_border(mask), first_true))

    if expected_shape is None:
        raise ValueError("instance_masks must contain at least one shaped mask")

    source.sort(key=lambda item: (item[5], item[3], item[0]))
    regions: list[AnonymousMask] = []
    rejected: list[RejectedAnonymousMask] = []
    for digest, mask, _source_key, count, touches_border, _first_true in source:
        reason: str | None = None
        if count < config.minimum_visible_pixels:
            reason = "below_minimum_visible_pixels"
        elif (
            touches_border
            and config.border_truncation_policy == REJECT_BORDER_REGIONS
        ):
            reason = "touches_image_border"
        if reason is not None:
            rejected.append(RejectedAnonymousMask(
                mask_sha256=digest,
                visible_pixel_count=count,
                touches_border=touches_border,
                reason=reason,
            ))
            continue
        if len(regions) >= 10_000:
            raise ValueError("at most 10000 public regions are supported per packet")
        height, width = mask.shape
        regions.append(AnonymousMask(
            region_id=f"region:{len(regions):04d}",
            mask_sha256=digest,
            height=int(height),
            width=int(width),
            row_major_values=tuple(int(item) for item in mask.reshape(-1)),
            visible_pixel_count=count,
            touches_border=touches_border,
        ))

    rejected.sort(key=lambda item: (
        item.visible_pixel_count, item.mask_sha256, item.reason,
    ))
    private_bindings.sort(key=lambda item: item[0])
    return L1MaskMaterialization(
        height=expected_shape[0],
        width=expected_shape[1],
        regions=tuple(regions),
        rejected=tuple(rejected),
        private_instance_mapping_sha256=_sha256_json(private_bindings),
    )
