#!/usr/bin/env python3
"""Append-only materialization of one post-D-183 multiview raw episode."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cpmt.executor import validate_graph  # noqa: E402
from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.causal_prior import validate_causal_prior_receipt  # noqa: E402
from vsmt.contracts import (  # noqa: E402
    canonical_sha256,
    validate_observation_packet,
)
from vsmt.vm04_materializer_receipt import (  # noqa: E402
    make_materializer_receipt,
    validate_materializer_receipt,
)
from vsmt.vm04_materializer_config import (  # noqa: E402
    build_vm04_public_frontend_sequence,
)
from vsmt.vm04_observation_runner import (  # noqa: E402
    ObservationConstructionError,
    validate_approved_contract,
)
from vsmt.vm04_public_context import (  # noqa: E402
    validate_public_frame_context_manifest,
)


MaterializeFrame = Callable[
    [Mapping[str, Any], Mapping[str, Any], int], Mapping[str, Any]
]
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SEQUENCE_RESULT_KEYS = {
    "prior_memory", "causal_prior_receipt",
    "public_frame_context_manifest", "ordered_public_packet_sha256s",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ObservationConstructionError(message)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _mask_sha256(mask: Any) -> str:
    value = np.ascontiguousarray(mask, dtype=np.uint8)
    _require(value.ndim == 2, "private instance mask must be two-dimensional")
    height, width = value.shape
    return _sha_value([
        int(height), int(width), *value.reshape(-1).tolist(),
    ])


def _hex64(value: Any, name: str) -> str:
    _require(type(value) is str and HEX64.fullmatch(value) is not None,
             f"{name} must be a lowercase SHA-256")
    return value


def _write_new_json(path: Path, value: Any) -> None:
    payload = (json.dumps(value, sort_keys=True, indent=2,
                          ensure_ascii=False) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _validate_manifests(episode_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    public_path = episode_root / "public/raw.manifest.json"
    private_path = episode_root / "private/raw.manifest.json"
    terminal_path = episode_root / "public/raw.terminal.json"
    private_terminal_path = episode_root / "private/raw.terminal.json"
    route_path = episode_root / "private/route-plan.json"
    public_route_path = episode_root / "public/route.json"
    _require(public_path.is_file() and private_path.is_file() and
             terminal_path.is_file() and private_terminal_path.is_file() and
             route_path.is_file() and public_route_path.is_file(),
             "raw episode manifests are incomplete")
    public = _read_json(public_path)
    private = _read_json(private_path)
    terminal = _read_json(terminal_path)
    _require(set(public) == {
        "schema_version", "episode_id", "public_route_file_sha256",
        "frame_count", "frames", "public_terminal_sha256",
    } and public["schema_version"] ==
             "vsmt-vm04-raw-public-episode-manifest-v1",
             "raw public manifest schema changed")
    _require(set(private) == {
        "schema_version", "episode_id", "private_route_plan_file_sha256",
        "public_manifest_sha256", "frame_count", "frames",
        "private_terminal_sha256",
    } and private["schema_version"] ==
             "vsmt-vm04-raw-private-episode-manifest-v1",
             "raw private manifest schema changed")
    _require(terminal.get("status") == "raw_complete" and
             type(terminal.get("route_receipt")) is dict and
             type(terminal.get("construction_verdict")) is dict and
             terminal["construction_verdict"].get("constructed") is True,
             "only raw-complete episodes may be materialized")
    _require(public["episode_id"] == private["episode_id"] ==
             terminal.get("episode_id"), "raw episode IDs differ")
    _require(public["public_terminal_sha256"] == _sha_file(terminal_path),
             "raw public terminal changed")
    _require(private["public_manifest_sha256"] == _sha_file(public_path),
             "raw private manifest does not bind the public manifest")
    _require(public["public_route_file_sha256"] == _sha_file(public_route_path) and
             private["private_route_plan_file_sha256"] == _sha_file(route_path) and
             private["private_terminal_sha256"] ==
             _sha_file(private_terminal_path),
             "raw route or private terminal bytes changed")
    _require(public["frame_count"] == private["frame_count"] ==
             len(public["frames"]) == len(private["frames"]) and
             public["frame_count"] > 0,
             "raw manifest frame counts differ")
    route = _read_json(route_path)
    _require(public["frame_count"] == len(route.get("registered_actions", [])) + 1 and
             terminal["route_plan_sha256"] == route.get("route_plan_sha256") and
             terminal["route_receipt"].get("route_plan_sha256") ==
             route.get("route_plan_sha256"),
             "raw frame count or route binding changed")
    indices = list(range(public["frame_count"]))
    _require([row.get("observation_index") for row in public["frames"]] == indices and
             [row.get("observation_index") for row in private["frames"]] == indices,
             "raw manifest frames must be contiguous from zero")
    return public, private


def _load_verified_frame(
    episode_root: Path, index: int,
    public_row: Mapping[str, Any], private_row: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    name = f"frame_{index:04d}"
    public_root = episode_root / "public/raw" / name
    private_root = episode_root / "private/raw" / name
    paths = {
        "rgb": public_root / "rgb.npy",
        "depth": public_root / "depth_m.npy",
        "camera": public_root / "camera.json",
        "frame": public_root / "frame.json",
        "masks": private_root / "instance_masks.npz",
        "mapping": private_root / "mapping.json",
    }
    _require(all(path.is_file() for path in paths.values()),
             "raw frame file is missing")
    frame = _read_json(paths["frame"])
    mapping = _read_json(paths["mapping"])
    _require(set(frame) == {
        "schema_version", "observation_index", "rgb_sha256",
        "depth_m_sha256", "camera_sha256", "source_frame_sha256",
    } and frame["schema_version"] == "vsmt-vm04-raw-public-frame-v1" and
             frame["observation_index"] == index,
             "raw public frame record changed")
    source_payload = dict(frame)
    source_digest = source_payload.pop("source_frame_sha256")
    _require(source_digest == _sha_value(source_payload),
             "raw public source-frame digest mismatch")
    _require(frame["rgb_sha256"] == _sha_file(paths["rgb"]) and
             frame["depth_m_sha256"] == _sha_file(paths["depth"]) and
             frame["camera_sha256"] == _sha_file(paths["camera"]) and
             public_row.get("frame_record_sha256") == _sha_file(paths["frame"]) and
             public_row.get("source_frame_sha256") == source_digest,
             "raw public frame bytes changed")
    _require(set(mapping) == {
        "schema_version", "observation_index", "private_instance_ids",
        "instance_masks_sha256", "public_frame_record_sha256",
        "public_source_frame_sha256",
    } and mapping["schema_version"] ==
             "vsmt-vm04-raw-private-frame-map-v1" and
             mapping["observation_index"] == index,
             "raw private mapping changed")
    _require(mapping["instance_masks_sha256"] == _sha_file(paths["masks"]) ==
             private_row.get("instance_masks_sha256") and
             private_row.get("private_mapping_sha256") ==
             _sha_file(paths["mapping"]) and
             mapping["public_frame_record_sha256"] ==
             public_row["frame_record_sha256"] ==
             private_row.get("public_frame_record_sha256") and
             mapping["public_source_frame_sha256"] == source_digest,
             "raw private/public frame binding changed")
    rgb = np.load(paths["rgb"], allow_pickle=False)
    depth = np.load(paths["depth"], allow_pickle=False)
    masks = np.load(paths["masks"], allow_pickle=False)["masks"]
    _require(rgb.ndim == 3 and depth.shape == rgb.shape[:2] and
             masks.ndim == 3 and masks.shape[1:] == depth.shape and
             masks.shape[0] == len(mapping["private_instance_ids"]),
             "raw array shapes or private ID count changed")
    return ({
        "rgb": rgb, "depth_m": depth,
        "camera": _read_json(paths["camera"]),
        "rgb_sha256": frame["rgb_sha256"],
        "depth_sha256": frame["depth_m_sha256"],
        "source_frame_sha256": source_digest,
    }, {
        "instance_masks": masks,
        "private_instance_ids": list(mapping["private_instance_ids"]),
        "instance_masks_sha256": mapping["instance_masks_sha256"],
        "private_mapping_sha256": private_row["private_mapping_sha256"],
    })


def _validate_materialized_pair(
    output: Mapping[str, Any], private_raw: Mapping[str, Any], index: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _require(type(output) is dict and set(output) == {
        "public_packet", "private_crosswalk",
    }, "materializer callback returned unexpected fields")
    packet = validate_observation_packet(output["public_packet"])
    crosswalk = output["private_crosswalk"]
    _require(type(crosswalk) is dict and set(crosswalk) == {
        "schema_version", "frame_role", "bindings",
    } and crosswalk["schema_version"] ==
             "vsmt-vm04-private-region-crosswalk-v1" and
             type(crosswalk["frame_role"]) is str and
             crosswalk["frame_role"] and type(crosswalk["bindings"]) is list,
             "private crosswalk schema changed")
    private_ids = list(private_raw["private_instance_ids"])
    private_masks = np.asarray(private_raw["instance_masks"])
    _require(private_masks.ndim == 3 and
             private_masks.shape[0] == len(private_ids),
             "verified private raw mask stack changed")
    raw_mask_sha256_by_instance = {
        private_id: _mask_sha256(private_masks[private_index])
        for private_index, private_id in enumerate(private_ids)
    }
    private_set = set(private_ids)
    public_regions = {
        row["region_id"]: row for row in packet["region_observations"]
        if row["structure_kind"] == "entity"
    }
    seen_instances, seen_regions = set(), set()
    for row in crosswalk["bindings"]:
        _require(type(row) is dict and set(row) == {
            "instance_id", "region_id", "mask_sha256",
        }, "private crosswalk binding changed")
        _require(row["instance_id"] in private_set and
                 row["instance_id"] not in seen_instances and
                 row["region_id"] not in seen_regions and
                 _hex64(row["mask_sha256"], "mask_sha256") and
                 raw_mask_sha256_by_instance[row["instance_id"]] ==
                 row["mask_sha256"] and
                 row["region_id"] in public_regions and
                 public_regions[row["region_id"]]["mask_sha256"] ==
                 row["mask_sha256"],
                 "private crosswalk does not uniquely bind a public entity mask")
        seen_instances.add(row["instance_id"])
        seen_regions.add(row["region_id"])
    public_text = canonical_json(packet)
    _require(not any(private_id in public_text for private_id in private_ids),
             "private instance ID leaked into public packet")
    _hex64(packet.get("sample_id_hash"),
           f"materialized packet {index} sample_id_hash")
    return packet, crosswalk


def _validated_sequence_result(
    materialize_frame: MaterializeFrame, *, packets: list[Mapping[str, Any]],
    public_route_sha256: str,
) -> dict[str, Any]:
    """Close and cross-check the stateful public sequence after its last frame."""

    finalize = getattr(materialize_frame, "finalized_result", None)
    _require(callable(finalize),
             "materializer callback must expose finalized_result")
    result = finalize()
    _require(type(result) is dict and set(result) == SEQUENCE_RESULT_KEYS,
             "materializer sequence result has unexpected fields")
    prior = result["prior_memory"]
    validate_graph(prior, verify_hash=True)
    receipt = validate_causal_prior_receipt(
        result["causal_prior_receipt"], final_memory=prior)
    packet_digests = [canonical_sha256(packet) for packet in packets]
    _require(result["ordered_public_packet_sha256s"] == packet_digests and
             receipt["ordered_public_packet_sha256s"] == packet_digests,
             "causal prior does not bind the materialized packet sequence")
    manifest = validate_public_frame_context_manifest(
        result["public_frame_context_manifest"],
        expected_observation_count=len(packets),
        expected_public_route_sha256=public_route_sha256,
    )
    return {
        "prior_memory": prior,
        "causal_prior_receipt": receipt,
        "public_frame_context_manifest": manifest,
    }


def materialize_episode_core(
    episode_root: Path, *, materialize_frame: MaterializeFrame,
    materializer_code_sha256: str, materializer_config_sha256: str,
) -> dict[str, Any]:
    """Materialize one raw-complete episode; retain partial outputs on failure."""

    episode_root = Path(episode_root)
    _hex64(materializer_code_sha256, "materializer_code_sha256")
    _hex64(materializer_config_sha256, "materializer_config_sha256")
    public_manifest, private_manifest = _validate_manifests(episode_root)
    output_root = episode_root / "materialized"
    _require(not output_root.exists(), "materialized output already exists")
    public_output = output_root / "public"
    private_output = output_root / "private"
    public_output.mkdir(parents=True)
    private_output.mkdir()
    bindings = []
    packets = []
    try:
        for index, (public_row, private_row) in enumerate(zip(
                public_manifest["frames"], private_manifest["frames"])):
            public_raw, private_raw = _load_verified_frame(
                episode_root, index, public_row, private_row)
            packet, crosswalk = _validate_materialized_pair(
                materialize_frame(public_raw, private_raw, index),
                private_raw, index)
            packet_path = public_output / f"frame_{index:04d}.json"
            crosswalk_path = private_output / f"frame_{index:04d}.json"
            _write_new_json(packet_path, packet)
            _write_new_json(crosswalk_path, crosswalk)
            packets.append(packet)
            bindings.append({
                "observation_index": index,
                "raw_public_frame_sha256": public_raw["source_frame_sha256"],
                "raw_private_masks_sha256":
                    private_raw["instance_masks_sha256"],
                "public_packet_sha256": _sha_file(packet_path),
                "private_crosswalk_sha256": _sha_file(crosswalk_path),
            })
        # Re-open every raw binding after the callback work and before sealing.
        for index, (public_row, private_row) in enumerate(zip(
                public_manifest["frames"], private_manifest["frames"])):
            _load_verified_frame(episode_root, index, public_row, private_row)
        route = _read_json(episode_root / "private/route-plan.json")
        public_route = _read_json(episode_root / "public/route.json")
        sequence = _validated_sequence_result(
            materialize_frame,
            packets=packets,
            public_route_sha256=public_route["public_route_sha256"],
        )
        context_path = public_output / "public-frame-context.manifest.json"
        causal_path = public_output / "causal-prior.receipt.json"
        prior_path = public_output / "prior-memory.json"
        _write_new_json(context_path, sequence["public_frame_context_manifest"])
        _write_new_json(causal_path, sequence["causal_prior_receipt"])
        _write_new_json(prior_path, sequence["prior_memory"])
        receipt = make_materializer_receipt(
            bindings, episode_id=public_manifest["episode_id"],
            route_plan_sha256=route["route_plan_sha256"],
            raw_episode_manifest_sha256=_sha_file(
                episode_root / "private/raw.manifest.json"),
            materializer_code_sha256=materializer_code_sha256,
            materializer_config_sha256=materializer_config_sha256,
            public_frame_context_manifest_sha256=_sha_file(context_path),
            causal_prior_receipt_sha256=_sha_file(causal_path),
            prior_memory_sha256=_sha_file(prior_path),
        )
        receipt_path = public_output / "materializer.receipt.json"
        _write_new_json(receipt_path, receipt)
        _write_new_json(public_output / "materializer.success.json", {
            "receipt_sha256": _sha_file(receipt_path),
        })
        return {
            "status": "materialized_complete",
            "frame_count": len(bindings),
            "receipt_sha256": _sha_file(receipt_path),
        }
    except BaseException as error:
        _write_new_json(public_output / "materializer.failure.json", {
            "schema_version": "vsmt-vm04-materializer-failure-v1",
            "reason": "materializer_or_raw_verification_failed",
            "completed_frame_count": len(bindings),
            "failed_output_replacement_allowed": False,
        })
        _write_new_json(private_output / "materializer.failure.json", {
            "schema_version": "vsmt-vm04-private-materializer-failure-v1",
            "exception_type": type(error).__name__,
            "exception_message": str(error),
            "completed_frame_count": len(bindings),
        })
        return {
            "status": "materialized_failure",
            "frame_count": len(bindings),
            "failure_reason": "materializer_or_raw_verification_failed",
        }


def verify_materialized_episode(
    episode_root: Path, *, contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Re-open raw, public packets, private crosswalks and the final receipt."""

    episode_root = Path(episode_root)
    public_manifest, private_manifest = _validate_manifests(episode_root)
    output_root = episode_root / "materialized"
    receipt_path = output_root / "public/materializer.receipt.json"
    success_path = output_root / "public/materializer.success.json"
    context_path = output_root / "public/public-frame-context.manifest.json"
    causal_path = output_root / "public/causal-prior.receipt.json"
    prior_path = output_root / "public/prior-memory.json"
    _require(receipt_path.is_file() and success_path.is_file(),
             "materializer receipt and success marker are required")
    _require(context_path.is_file() and causal_path.is_file() and
             prior_path.is_file(),
             "materializer public sequence artifacts are required")
    receipt = validate_materializer_receipt(_read_json(receipt_path))
    _require(_read_json(success_path) == {
        "receipt_sha256": _sha_file(receipt_path),
    }, "materializer success marker does not bind the receipt")
    route = _read_json(episode_root / "private/route-plan.json")
    public_route = _read_json(episode_root / "public/route.json")
    _require(receipt["episode_id"] == public_manifest["episode_id"] and
             receipt["route_plan_sha256"] == route["route_plan_sha256"] and
             receipt["raw_episode_manifest_sha256"] == _sha_file(
                 episode_root / "private/raw.manifest.json") and
             receipt["frame_count"] == public_manifest["frame_count"],
             "materializer receipt does not bind the raw episode")
    prior = _read_json(prior_path)
    validate_graph(prior, verify_hash=True)
    causal = validate_causal_prior_receipt(
        _read_json(causal_path), final_memory=prior,
    )
    validate_public_frame_context_manifest(
        _read_json(context_path),
        expected_observation_count=receipt["frame_count"],
        expected_public_route_sha256=public_route["public_route_sha256"],
    )
    _require(
        receipt["public_frame_context_manifest_sha256"] ==
        _sha_file(context_path) and
        receipt["causal_prior_receipt_sha256"] == _sha_file(causal_path) and
        receipt["prior_memory_sha256"] == _sha_file(prior_path),
        "materializer public sequence artifact binding changed",
    )
    if contract is not None:
        approved = validate_approved_contract(contract)
        provenance = approved["crosswalk_provenance"]
        _require(receipt["materializer_code_sha256"] ==
                 provenance.get("expected_materializer_code_sha256") and
                 receipt["materializer_config_sha256"] ==
                 provenance.get("expected_materializer_config_sha256"),
                 "materializer receipt differs from reviewed code or config")
    for index, (binding, public_row, private_row) in enumerate(zip(
            receipt["frames"], public_manifest["frames"],
            private_manifest["frames"])):
        public_raw, private_raw = _load_verified_frame(
            episode_root, index, public_row, private_row)
        packet_path = output_root / "public" / f"frame_{index:04d}.json"
        crosswalk_path = output_root / "private" / f"frame_{index:04d}.json"
        _require(packet_path.is_file() and crosswalk_path.is_file(),
                 "materialized frame output is missing")
        _require(binding["raw_public_frame_sha256"] ==
                 public_raw["source_frame_sha256"] and
                 binding["raw_private_masks_sha256"] ==
                 private_raw["instance_masks_sha256"] and
                 binding["public_packet_sha256"] == _sha_file(packet_path) and
                 binding["private_crosswalk_sha256"] ==
                 _sha_file(crosswalk_path),
                 "materialized frame binding changed")
        _validate_materialized_pair({
            "public_packet": _read_json(packet_path),
            "private_crosswalk": _read_json(crosswalk_path),
        }, private_raw, index)
    _require(
        causal["ordered_public_packet_sha256s"] == [
            canonical_sha256(_read_json(
                output_root / "public" / f"frame_{index:04d}.json"
            ))
            for index in range(receipt["frame_count"])
        ],
        "causal prior packet sequence binding changed",
    )
    return {
        "status": "materialized_verified",
        "frame_count": receipt["frame_count"],
        "receipt_sha256": _sha_file(receipt_path),
    }


def assert_materialization_authorized(
    contract: Mapping[str, Any], *, code_sha256: str, config_sha256: str,
) -> None:
    """Fail before output when the reviewed executor/config are not frozen."""

    approved = validate_approved_contract(contract)
    provenance = approved["crosswalk_provenance"]
    _require(provenance.get("expected_materializer_code_sha256") == code_sha256,
             "materializer code digest is not frozen")
    _require(provenance.get("expected_materializer_config_sha256") == config_sha256,
             "materializer config digest is not frozen")
    _require(approved["authorization"].get("materialization_authorized") is True,
             "materialization is not authorized")


def run_authorized_materializer(
    episode_root: Path, *, contract: Mapping[str, Any],
    materialize_frame: MaterializeFrame, materializer_code_sha256: str,
    materializer_config_sha256: str,
) -> dict[str, Any]:
    """Production entry: authorization precedes every output read or write."""

    assert_materialization_authorized(
        contract, code_sha256=materializer_code_sha256,
        config_sha256=materializer_config_sha256)
    return materialize_episode_core(
        episode_root, materialize_frame=materialize_frame,
        materializer_code_sha256=materializer_code_sha256,
        materializer_config_sha256=materializer_config_sha256,
    )


def run_authorized_materializer_from_config(
    episode_root: Path, *, contract: Mapping[str, Any],
    raw_materializer_config: Mapping[str, Any],
    public_frame_context_bundle: Mapping[str, Any],
    private_frame_roles: list[str], patch_token_extractor: Any,
    materializer_code_sha256: str,
) -> dict[str, Any]:
    """Build the stateful callback from one sealed config, then run it."""

    callback, config_sha256 = build_vm04_public_frontend_sequence(
        raw_materializer_config,
        public_frame_context_bundle=public_frame_context_bundle,
        private_frame_roles=private_frame_roles,
        patch_token_extractor=patch_token_extractor,
    )
    return run_authorized_materializer(
        episode_root,
        contract=contract,
        materialize_frame=callback,
        materializer_code_sha256=materializer_code_sha256,
        materializer_config_sha256=config_sha256,
    )
