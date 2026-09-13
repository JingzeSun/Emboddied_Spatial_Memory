"""Verified R4 branch reader with model inputs separated from training targets."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from pathlib import Path

from .pair_contract import require
from .r4_generation_v2 import ACTIONS
from .r4_public_v2 import model_input as select_public_model_input
from .r4_query_v2 import from_public_query
from .r4_scoring_v2 import validate_labels
from .r4_storage import file_record

VERSION = "spatial-history-r4-learning-branch-v1"
WORLDS = ("LL", "LR", "RL", "RR")


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _gzip_json(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def _manifest_record(root, manifest, relative):
    path = Path(root) / relative
    require(relative in manifest, "file absent from sealed family manifest: " + relative)
    require(file_record(path) == manifest[relative], "sealed family file changed: " + relative)
    return path


def _array(path, expected, compressed_expected):
    import numpy as np
    require(file_record(path) == compressed_expected, "compressed array changed")
    with gzip.open(path, "rb") as handle:
        header = json.loads(handle.readline(4096))
        raw = handle.read()
    require(header["version"] == "r4-array-v1" and header["shape"] == expected["shape"]
            and header["dtype"] == expected["dtype"], "array header changed")
    require(len(raw) == expected["raw_bytes"] and hashlib.sha256(raw).hexdigest() == expected["raw_sha256"],
            "array raw payload changed")
    return np.frombuffer(raw, dtype=np.dtype(header["dtype"])).reshape(header["shape"]).copy()


def verify_family_seal(data_root, expected):
    data_root = Path(data_root).resolve(strict=True)
    require(set(expected) == {"public_manifest", "labels_manifest", "audit_manifest", "family_result"},
            "expected family seal fields")
    result = {}
    for channel in ("public", "labels", "audit"):
        manifest_path = data_root / f"{channel}_manifest.json"
        require(file_record(manifest_path) == expected[f"{channel}_manifest"],
                channel + " manifest seal changed")
        manifest = _json(manifest_path)
        actual_names = {path.relative_to(data_root / channel).as_posix()
                        for path in (data_root / channel).rglob("*") if path.is_file()}
        require(set(manifest) == actual_names, channel + " file census changed")
        result[channel] = {"manifest": manifest, "manifest_file": file_record(manifest_path)}
    family_path = data_root / "audit/family_result.json"
    require(file_record(family_path) == expected["family_result"], "family result seal changed")
    family = _json(family_path)
    require(family["schema_version"] == "sh04-r4-family-result-v2" and family["accepted"],
            "family is not an accepted v2 source")
    require(family["unique_branches"] == family["independent_replays"] == 36 and family["histories"] == 4,
            "family branch census changed")
    result["family_result"] = {
        "file": expected["family_result"], "accepted": True,
        "histories": family["histories"], "unique_branches": family["unique_branches"],
        "independent_replays": family["independent_replays"],
    }
    result["data_root"] = str(data_root)
    return result


def branch_index(family_roots, expected_seals):
    require(isinstance(family_roots, dict) and family_roots, "family roots required")
    require(set(family_roots) == set(expected_seals), "family roots and external seals differ")
    require(isinstance(expected_seals, dict) and set(expected_seals) == set(family_roots),
            "one expected seal per family required")
    rows = []
    seals = {}
    for family_id, root in family_roots.items():
        require(type(family_id) is str and family_id.startswith("r4-"), "invalid family id")
        root = Path(root).resolve(strict=True)
        require(root.name == "data" and root.parent.name == family_id,
                "family id/root mismatch")
        seal = verify_family_seal(root, expected_seals[family_id])
        seals[family_id] = seal
        rows.extend({"family_id": family_id, "world": world, "action": action, "action_slot": slot}
                    for world in WORLDS for slot, action in enumerate(ACTIONS))
    return {"schema_version": VERSION, "rows": rows, "seals": seals}


def load_branch(index, family_id, world, action_slot, *, include_auxiliary_rgbd):
    require(index["schema_version"] == VERSION, "learning index version")
    require(family_id in index["seals"] and world in WORLDS
            and type(action_slot) is int and 0 <= action_slot < len(ACTIONS),
            "branch identity outside index")
    seal = index["seals"][family_id]
    root = Path(seal["data_root"])
    action = ACTIONS[action_slot]
    public_rel = f"{world}.json.gz"
    label_rel = f"{world}-{action}.json.gz"
    public = _gzip_json(_manifest_record(root / "public", seal["public"]["manifest"], public_rel))
    query = from_public_query(select_public_model_input(public, action_slot))
    label_record = _gzip_json(_manifest_record(root / "labels", seal["labels"]["manifest"], label_rel))
    validate_labels(label_record["labels"])
    trajectory_rel = f"{world}/primary-{action}/trajectory.jsonl.gz"
    require(label_record["trajectory"] == seal["audit"]["manifest"][trajectory_rel],
            "label/trajectory seal changed")
    labels = label_record["labels"]
    require(labels["physics_valid"] and labels["visibility_valid"],
            "invalid branch retained but cannot train")
    targets = {
        "prediction_times_s": list(labels["prediction_times_s"]),
        "object_position_m": [list(value) for value in labels["object_position_m"]],
        "interval_contact": [bool(value) for value in labels["interval_contact"]],
        "task_success": bool(labels["task_success"]),
    }
    auxiliary = None
    if include_auxiliary_rgbd:
        directory = root / "audit" / world / f"primary-{action}"
        complete_rel = f"{world}/primary-{action}/complete.json"
        complete = _json(_manifest_record(root / "audit", seal["audit"]["manifest"], complete_rel))
        require(complete["exit_code"] == 0 and set(complete["arrays"]) == {
            "rgb.npy.gz", "depth.npy.gz", "integration.npy.gz",
            "sensor_times.npy.gz", "sensor_step_indices.npy.gz"
        }, "primary array completion changed")
        def array(name):
            relative = f"{world}/primary-{action}/{name}"
            require(relative in seal["audit"]["manifest"], "array absent from audit manifest")
            return _array(directory / name, complete["arrays"][name], seal["audit"]["manifest"][relative])
        rgb = array("rgb.npy.gz")
        depth = array("depth.npy.gz")
        times = array("sensor_times.npy.gz")
        steps = array("sensor_step_indices.npy.gz")
        require(rgb.shape == (201, 80, 80, 3) and depth.shape == (201, 80, 80),
                "future RGBD shape")
        require(all(math.isclose(float(value), i / 10, abs_tol=1e-12, rel_tol=0)
                    for i, value in enumerate(times)), "future sensor times changed")
        require(steps.tolist() == [50 * i for i in range(201)],
                "future sensor step indices changed")
        auxiliary = {
            "future_rgb": rgb[1:].copy(), "future_depth_m": depth[1:].copy(),
            "future_depth_valid": (depth[1:] > 0).copy(),
        }
    audit = {
        "family_id": family_id, "world": world, "action": action, "action_slot": action_slot,
        "public_file": seal["public"]["manifest"][public_rel],
        "label_file": seal["labels"]["manifest"][label_rel],
        "actual_future_robot_motion_returned": False,
        "integration_state_returned": False,
    }
    return {"schema_version": VERSION, "model_input": query, "targets": targets,
            "auxiliary_targets": auxiliary, "audit": audit}
