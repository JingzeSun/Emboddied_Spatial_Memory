"""Digest bindings for the post-D-183 trusted VM-04 materializer.

This module does not materialize a frame.  It seals the already-written raw
public/private inputs and their public-packet/private-crosswalk outputs so a
later RELINK proof can bind one reviewed materialization event.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Sequence

from cpmt.hashing import canonical_json, clone_json


SCHEMA = "vsmt-vm04-trusted-materializer-receipt-v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
FRAME_KEYS = {
    "observation_index", "raw_public_frame_sha256",
    "raw_private_masks_sha256", "public_packet_sha256",
    "private_crosswalk_sha256",
}


class MaterializerReceiptError(ValueError):
    """A materializer receipt is incomplete or has a broken binding."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MaterializerReceiptError(message)


def _hex64(value: Any, name: str) -> str:
    _require(type(value) is str and HEX64.fullmatch(value) is not None,
             f"{name} must be a lowercase SHA-256")
    return value


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def make_materializer_receipt(
    frame_bindings: Sequence[Mapping[str, Any]], *,
    episode_id: str, route_plan_sha256: str,
    raw_episode_manifest_sha256: str,
    materializer_code_sha256: str, materializer_config_sha256: str,
) -> dict[str, Any]:
    """Seal contiguous raw-to-materialized frame bindings."""

    _require(type(episode_id) is str and episode_id,
             "episode_id must be nonempty")
    digests = {
        "route_plan_sha256": route_plan_sha256,
        "raw_episode_manifest_sha256": raw_episode_manifest_sha256,
        "materializer_code_sha256": materializer_code_sha256,
        "materializer_config_sha256": materializer_config_sha256,
    }
    for name, value in digests.items():
        _hex64(value, name)
    frames = []
    for expected, raw in enumerate(frame_bindings):
        _require(type(raw) is dict and set(raw) == FRAME_KEYS,
                 "materializer frame binding has unexpected fields")
        row = clone_json(raw)
        _require(row["observation_index"] == expected,
                 "materializer frame bindings must be contiguous from zero")
        for name in FRAME_KEYS - {"observation_index"}:
            _hex64(row[name], name)
        frames.append(row)
    _require(frames, "materializer receipt requires at least one frame")
    receipt = {
        "schema_version": SCHEMA,
        "episode_id": episode_id,
        **digests,
        "frame_count": len(frames),
        "frames": frames,
        "sealed_after_all_public_packets_and_private_crosswalks": True,
        "deployment_reader_may_open_private_crosswalks": False,
    }
    receipt["receipt_sha256"] = _sha(receipt)
    return receipt


def validate_materializer_receipt(
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Recompute a receipt and reject altered or self-reported bindings."""

    expected = {
        "schema_version", "episode_id", "route_plan_sha256",
        "raw_episode_manifest_sha256", "materializer_code_sha256",
        "materializer_config_sha256", "frame_count", "frames",
        "sealed_after_all_public_packets_and_private_crosswalks",
        "deployment_reader_may_open_private_crosswalks", "receipt_sha256",
    }
    _require(type(receipt) is dict and set(receipt) == expected,
             "materializer receipt has unexpected fields")
    record = clone_json(receipt)
    _require(record["schema_version"] == SCHEMA,
             "wrong materializer receipt schema")
    _require(record["sealed_after_all_public_packets_and_private_crosswalks"]
             is True, "materializer outputs were not sealed before the receipt")
    _require(record["deployment_reader_may_open_private_crosswalks"] is False,
             "deployment reader may not open private crosswalks")
    rebuilt = make_materializer_receipt(
        record["frames"], episode_id=record["episode_id"],
        route_plan_sha256=record["route_plan_sha256"],
        raw_episode_manifest_sha256=record["raw_episode_manifest_sha256"],
        materializer_code_sha256=record["materializer_code_sha256"],
        materializer_config_sha256=record["materializer_config_sha256"],
    )
    _require(record["frame_count"] == len(record["frames"]),
             "materializer frame count mismatch")
    _require(record == rebuilt, "materializer receipt digest mismatch")
    return record
