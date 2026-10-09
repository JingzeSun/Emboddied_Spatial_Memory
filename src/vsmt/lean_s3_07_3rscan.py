"""S3-07 (ruling 111, 2026-10-07): 3RScan scans read into this project's public and private planes, as pure functions.

Ruling 111 fixes S3-07 as: convert the reference scans and rescans of 3RScan validation into this project's three-plane
episodes, then run the arms frozen by S3-04 on them. This module holds the parts of the conversion that can be tested on
their own; it reads and writes no file, renders nothing and runs no method:
  * parsing: ``_info.txt`` (intrinsics and sizes), ``frame-NNNNNN.pose.txt`` (camera to world), the alignment matrices
    and change entries of ``3RScan.json``, the instances and OBBs of ``semseg.v2.json``, the official label sheet
    (label -> NYU40 id);
  * camera: the original frame turned 90 degrees clockwise to upright, the centred square of the short side, scaled to
    224; the intrinsics follow; target pixels map back to original pixels (for the sensor-depth diagnostic);
  * axes: 3RScan world +Z up with an OpenCV camera (y down) -> this project's world +Y up with a y-up camera (the
    convention of the D-223 back-projection);
  * truth: private keys (structural parts mapped through NYU40 to the five prefixes the frozen evaluator excludes),
    object boxes, the per-class change classification (111-3) and the degenerate window;
  * public frame digest: the same formula as the S1-02 generator (S2-04 and the node audit recompute it from the bytes).
Input: the text of 3RScan files or parsed dictionaries and arrays; output: the values this project writes. Example: a
chair centred at (2.0, 1.0, 0.4) in a reference scan (+Z up) is at (2.0, 0.4, 1.0) in the project world; moved by 1.2 m
in the rescan and not under ``ambiguity``, it is recorded as ``move`` with the rescan box centre as its point.
It is not the renderer (``lean_s3_07_render`` and ``ops/vsmt/s3_07_render.py``), does not write episodes
(``ops/vsmt/s3_07_convert.py``) and changes no frozen reader. The rules marked with a star were registered in the
contract after the sample check; until then ``blocking_null_slots`` blocked the formal conversion.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from cpmt.hashing import canonical_json
from vsmt import lean_public_pose as pp
from vsmt import lean_teacher as lt

STAGE = "vsmt.lean.s3_07.3rscan.v1"
CONTRACT_SCHEMA_VERSION = "vsmt-lean-s3-07-3rscan-v1"
CONTRACT_PATH = Path(__file__).resolve().parents[2] / "configs" / "vsmt" / "lean_s3_07_3rscan_v1.json"

#: 3RScan's colour frames are 960 x 540 (width, height); the crop below is derived for this size and refuses any other
RAW_COLOR_SIZE = (960, 540)
#: raw frames are stored sideways; the official rio_renderer and 3DSSG turn them 90 degrees clockwise to stand upright
IMAGE_ROTATION = "clockwise_90"
#: the D-223 frozen front end reads 224 x 224 frames (DINO preprocessing, mask shape, free-space tiles)
TARGET_SIZE = 224
#: area averaging for the RGB downscale (540 -> 224); depth and instance images are rendered at the target camera instead
RGB_RESAMPLE = "PIL.Image.Resampling.BOX"
#: ruling 111-5 depth (a): the scan's own annotated mesh rendered at the target camera; sensor depth is a diagnostic only
DEPTH_SOURCE = "annotated_mesh_render"
#: a pixel without a mesh hit (or a sensor zero) is written as 0.0 m, invalid under the frozen [0.05, 20] m range
INVALID_DEPTH_M = 0.0
FROZEN_DEPTH_VALID_RANGE_M = (0.05, 20.0)

#: 3RScan world (+Z up, right-handed) -> project world (+Y up): swap y and z (a mirror, det -1)
WORLD_AXES = ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0))
#: OpenCV camera (x right, y down, z forward) -> project camera (x right, y up, z forward): flip y (det -1)
CAMERA_AXES = ((1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0))
#: raw OpenCV camera -> upright OpenCV camera for a clockwise 90-degree image turn: (x, y, z) -> (-y, x, z)
UPRIGHT_AXES = ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))

#: 3RScan.json: the rescan ``transform`` is 16 numbers, column-major, mapping rescan points into the reference scan
ALIGNMENT_LAYOUT = "column_major"
ALIGNMENT_DIRECTION = "rescan_to_reference"
#: ★ the FAQ says millimetres, the official readers use metres; the sample check registers one (ruling 111-5)
TRANSLATION_UNITS = {"m": 1.0, "mm": 0.001}
#: ★ ``normalizedAxes`` is nine numbers; whether they are three axis rows or three axis columns is checked on the sample
OBB_AXES_LAYOUTS = ("rows", "columns")

#: ruling 111-3 (a): NYU40 classes that are structure, mapped to the five prefixes the frozen evaluator keeps out of scope
NYU40_STRUCTURAL_PREFIX = {1: "wall", 2: "room", 8: "door", 9: "window", 22: "Ceiling_room"}
#: a handheld scan has no actions; the summary only enters the frame digest, no method reads it
ACTION_SUMMARY = {"action": "HandheldScanFrame", "success": True}
EPISODE_PREFIX = "3rscan-"
SCAN_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
#: ★ slots the sample check fills; while any is null a formal conversion is refused (ruling 111-5)
SAMPLE_CHECK_SLOTS = ("alignment_translation_unit", "obb_axes_layout", "image_rotation_confirmed", "ambiguity_structure_confirmed")
#: ruling 111-3: per-object outcomes of the change classification (only the first four become intervention rows);
#: ``remove_unlisted`` = in the reference, absent from the rescan's own annotation, missing from the official ``removed`` list
#: (111-3: an object "in the reference, not in the rescan" is a removal; change lists are not exhaustive, so it is counted on its own)
CHANGE_OUTCOMES = ("remove", "remove_unlisted", "not_rescanned", "move", "add", "small_rigid", "ambiguous_rigid", "nonrigid",
                   "unlisted_displacement", "structural_change_ignored")
#: amendment 2 of ruling 111 (2026-10-07): an object absent from the rescan annotation and not in the official removed list is a
#: removal only when the rescan covered its place -- a rescan mesh vertex within this radius (= delta_moved) of the reference box
#: centre; otherwise the rescan did not look there and the object stays present (``not_rescanned``)
COVERAGE_RADIUS_M = 0.5
#: amendment 2: an OBB value that is not finite or exceeds this magnitude (metres) is annotation garbage; the object is dropped
#: from that scan and counted (``obb_invalid``), the pair is not refused
OBB_SANITY_MAX_ABS_M = 1e4
#: input 4 x 4 matrices come from text; a rotation farther than this from orthonormal is refused, a nearer one is projected
RIGID_TOLERANCE = 1e-4


class LeanS307Error(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanS307Error(code)


def _matrix(rows: Sequence[Sequence[float]]) -> np.ndarray:
    return np.asarray(rows, dtype=np.float64)


W = _matrix(WORLD_AXES)
S = _matrix(CAMERA_AXES)
Q = _matrix(UPRIGHT_AXES)


# --------------------------------------------------------------------------
# contract
# --------------------------------------------------------------------------

def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return validate_contract(json.loads(Path(path).read_text(encoding="utf-8")))


def validate_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """The S3-07 contract must state exactly the constants this module computes with (one source of truth, checked both ways).

    The contract is the registered record for readers; the constants here are what the computation uses. They are compared
    item by item and any difference is refused, so the contract and the code cannot diverge. The four sample-check slots
    may be null (before registration), but a value that is set must be an allowed one.
    """

    _require(isinstance(contract, Mapping), "contract_not_object")
    _require(contract.get("schema_version") == CONTRACT_SCHEMA_VERSION, "contract_schema_version_invalid")
    _require(contract.get("stage_id") == STAGE, "contract_stage_invalid")
    camera = contract["camera"]
    _require(tuple(camera["raw_color_size_wh"]) == RAW_COLOR_SIZE, "contract_raw_color_size_mismatch")
    _require(camera["image_rotation"] == IMAGE_ROTATION, "contract_rotation_mismatch")
    _require(camera["target_size"] == TARGET_SIZE, "contract_target_size_mismatch")
    _require(camera["rgb_resample"] == RGB_RESAMPLE, "contract_resample_mismatch")
    axes = contract["axes"]
    _require([tuple(r) for r in axes["world"]] == list(WORLD_AXES), "contract_world_axes_mismatch")
    _require([tuple(r) for r in axes["camera"]] == list(CAMERA_AXES), "contract_camera_axes_mismatch")
    _require([tuple(r) for r in axes["upright"]] == list(UPRIGHT_AXES), "contract_upright_axes_mismatch")
    depth = contract["depth"]
    _require(depth["source"] == DEPTH_SOURCE and depth["invalid_value_m"] == INVALID_DEPTH_M, "contract_depth_mismatch")
    _require(tuple(depth["frozen_valid_range_m"]) == FROZEN_DEPTH_VALID_RANGE_M, "contract_depth_range_mismatch")
    alignment = contract["alignment"]
    _require(alignment["layout"] == ALIGNMENT_LAYOUT and alignment["direction"] == ALIGNMENT_DIRECTION, "contract_alignment_mismatch")
    truth = contract["truth"]
    _require({int(k): v for k, v in truth["nyu40_structural_prefix"].items()} == NYU40_STRUCTURAL_PREFIX,
             "contract_structural_prefix_mismatch")
    _require(truth["delta_moved_m"] == lt.DELTA_MOVED_M and truth["node_box_pad_m"] == lt.NODE_BOX_PAD_M,
             "contract_place_rule_mismatch")
    _require(truth["coverage_radius_m"] == COVERAGE_RADIUS_M and truth["obb_sanity_max_abs_m"] == OBB_SANITY_MAX_ABS_M,
             "contract_amendment_2_mismatch")
    mapping_sha = truth["label_mapping_sha256"]
    _require(isinstance(mapping_sha, str) and re.fullmatch(r"[0-9a-f]{64}", mapping_sha) is not None, "contract_label_mapping_sha256_invalid")
    _require(contract["public"]["action_summary"] == ACTION_SUMMARY, "contract_action_summary_mismatch")
    _require(contract["public"]["episode_prefix"] == EPISODE_PREFIX, "contract_episode_prefix_mismatch")
    slots = contract["sample_check"]
    _require(tuple(sorted(slots)) == tuple(sorted(SAMPLE_CHECK_SLOTS)), "contract_sample_slots_invalid")
    _require(slots["alignment_translation_unit"] in (None, *TRANSLATION_UNITS), "contract_translation_unit_invalid")
    _require(slots["obb_axes_layout"] in (None, *OBB_AXES_LAYOUTS), "contract_obb_layout_invalid")
    _require(slots["image_rotation_confirmed"] in (None, True), "contract_rotation_confirmed_invalid")
    _require(slots["ambiguity_structure_confirmed"] in (None, True), "contract_ambiguity_confirmed_invalid")
    return json.loads(json.dumps(contract))


def blocking_null_slots(contract: Mapping[str, Any]) -> list[str]:
    """The sample-check slots still null: a formal conversion refuses while this list is not empty."""

    return [name for name in SAMPLE_CHECK_SLOTS if contract["sample_check"][name] is None]


# --------------------------------------------------------------------------
# 3RScan files (text or parsed JSON in, plain values out)
# --------------------------------------------------------------------------

def _intrinsics_from_matrix(values: Sequence[float], code: str) -> dict[str, float]:
    _require(len(values) == 16 and all(math.isfinite(v) for v in values), code)
    fx, cx, fy, cy = float(values[0]), float(values[2]), float(values[5]), float(values[6])
    _require(fx > 0 and fy > 0, code)
    return {"fx": fx, "fy": fy, "cx": cx, "cy": cy}


def parse_info(text: str) -> dict[str, Any]:
    """``_info.txt`` -> sizes, depth shift, colour and depth intrinsics (row-major 4 x 4: fx=[0], cx=[2], fy=[5], cy=[6]).

    ``_info.txt`` holds one ``key = value`` per line. Both intrinsics and the sizes are read; both extrinsics must be the
    identity (colour and depth registered, one optical centre), otherwise the file is refused, because the depth is later
    used at the colour camera's target.
    """

    entries: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            entries[key.strip()] = value.strip()
    numbers = {key: [float(v) for v in value.split()] for key, value in entries.items() if key.startswith("m_calibration")}
    for key in ("m_colorWidth", "m_colorHeight", "m_depthWidth", "m_depthHeight", "m_depthShift",
                "m_calibrationColorIntrinsic", "m_calibrationDepthIntrinsic"):
        _require(key in entries, "info_field_missing:" + key)
    for key in ("m_calibrationColorExtrinsic", "m_calibrationDepthExtrinsic"):
        if key in numbers:
            _require(np.allclose(np.asarray(numbers[key]).reshape(4, 4), np.eye(4)), "info_extrinsic_not_identity:" + key)
    info = {
        "color_size_wh": (int(entries["m_colorWidth"]), int(entries["m_colorHeight"])),
        "depth_size_wh": (int(entries["m_depthWidth"]), int(entries["m_depthHeight"])),
        "depth_shift": float(entries["m_depthShift"]),
        "color_intrinsics": _intrinsics_from_matrix(numbers["m_calibrationColorIntrinsic"], "info_color_intrinsic_invalid"),
        "depth_intrinsics": _intrinsics_from_matrix(numbers["m_calibrationDepthIntrinsic"], "info_depth_intrinsic_invalid"),
        "frames": int(entries["m_frames.size"]) if "m_frames.size" in entries else None,
    }
    _require(info["depth_shift"] > 0, "info_depth_shift_invalid")
    return info


def _rigid(matrix: np.ndarray, code: str) -> np.ndarray:
    _require(matrix.shape == (4, 4) and bool(np.isfinite(matrix).all()), code)
    _require(bool(np.allclose(matrix[3], [0.0, 0.0, 0.0, 1.0], atol=1e-9)), code)
    rotation = matrix[:3, :3]
    _require(bool(np.allclose(rotation @ rotation.T, np.eye(3), atol=RIGID_TOLERANCE))
             and abs(float(np.linalg.det(rotation)) - 1.0) < RIGID_TOLERANCE, code)
    return matrix


def matmul(a: Any, b: Any) -> np.ndarray:
    """A small matrix product written out in a fixed order (no BLAS, no LAPACK): the same bits on every host."""

    x, y = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    _require(x.ndim == 2 and y.ndim == 2 and x.shape[1] == y.shape[0], "matmul_shape_invalid")
    out = np.zeros((x.shape[0], y.shape[1]), dtype=np.float64)
    for i in range(x.shape[0]):
        for j in range(y.shape[1]):
            total = 0.0
            for k in range(x.shape[1]):
                total = total + float(x[i, k]) * float(y[k, j])
            out[i, j] = total
    return out


def affine(matrix: np.ndarray, points: Any) -> np.ndarray:
    """``matrix[:3, :3] . p + matrix[:3, 3]`` for points as rows, element by element in a fixed order."""

    m = np.asarray(matrix, dtype=np.float64)
    p = np.asarray(points, dtype=np.float64)
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    return np.stack([m[i, 0] * x + m[i, 1] * y + m[i, 2] * z + m[i, 3] for i in range(3)], axis=-1)


def orthonormal_rotation(rotation: np.ndarray) -> tuple[np.ndarray, float]:
    """An exact rotation from a near-orthonormal one (Gram-Schmidt on the columns, fixed order) and the largest entry moved.

    3RScan poses are text with limited decimals, so their rotations are only nearly orthonormal, while the frozen quaternion
    encoding requires an exact rotation. Gram-Schmidt on the columns (normalise the first; remove its component from the
    second and normalise; the third is their cross product) uses element-wise arithmetic only and is bit-identical on every
    host (an SVD goes through LAPACK and can differ in the last bits). The change is returned (the conversion report keeps
    the largest); matrices farther from orthonormal than ``RIGID_TOLERANCE`` were already refused when read.
    """

    r = np.asarray(rotation, dtype=np.float64)
    c0 = r[:, 0] / math.sqrt(float(r[0, 0] * r[0, 0] + r[1, 0] * r[1, 0] + r[2, 0] * r[2, 0]))
    dot = float(c0[0] * r[0, 1] + c0[1] * r[1, 1] + c0[2] * r[2, 1])
    c1 = r[:, 1] - dot * c0
    c1 = c1 / math.sqrt(float(c1[0] * c1[0] + c1[1] * c1[1] + c1[2] * c1[2]))
    c2 = np.asarray([c0[1] * c1[2] - c0[2] * c1[1], c0[2] * c1[0] - c0[0] * c1[2], c0[0] * c1[1] - c0[1] * c1[0]])
    _require(float(c2[0] * r[0, 2] + c2[1] * r[1, 2] + c2[2] * r[2, 2]) > 0.0, "rotation_not_proper")
    out = np.column_stack((c0, c1, c2))
    return out, float(np.max(np.abs(out - r)))


def orthonormal_rigid(matrix: np.ndarray) -> tuple[np.ndarray, float]:
    """A 4 x 4 rigid transform with its rotation made exactly orthonormal (``orthonormal_rotation``); the translation is kept.

    Poses and alignments are made orthonormal once, here, at the raw level: the axes swap and the upright turn are signed
    permutations, exact in floating point, so the rendered image, the public pose and the truth boxes all use the same rotation.
    """

    m = _rigid(np.asarray(matrix, dtype=np.float64), "transform_not_rigid")
    rotation, moved = orthonormal_rotation(m[:3, :3])
    out = m.copy()
    out[:3, :3] = rotation
    return out, moved


def parse_pose(text: str) -> np.ndarray:
    """``frame-NNNNNN.pose.txt`` -> the RGB camera-to-world 4 x 4 (row-major text, metres) of that scan's own frame."""

    values = [float(v) for v in text.split()]
    _require(len(values) == 16, "pose_not_16_numbers")
    return _rigid(np.asarray(values, dtype=np.float64).reshape(4, 4), "pose_not_rigid")


def alignment_matrix(values: Sequence[float], *, unit: str | None) -> np.ndarray:
    """``3RScan.json`` rescan ``transform`` (16 numbers, column-major) -> 4 x 4 rescan-to-reference, translation in metres.

    ``unit`` is the sample-registered translation unit (★ FAQ: mm; official readers: m); a null unit is refused.
    """

    _require(unit is not None, "alignment_translation_unit_not_registered")
    _require(unit in TRANSLATION_UNITS, "alignment_translation_unit_invalid")
    numbers = [float(v) for v in values]
    _require(len(numbers) == 16, "alignment_not_16_numbers")
    matrix = np.asarray(numbers, dtype=np.float64).reshape(4, 4).T  # column-major
    matrix = matrix.copy()
    matrix[:3, 3] *= TRANSLATION_UNITS[unit]
    return _rigid(matrix, "alignment_not_rigid")


def parse_label_mapping(csv_text: str) -> dict[str, int]:
    """The official 3RScan class sheet (``3RScan.v2 Semantic Classes - Mapping.csv``) -> label -> NYU40 id.

    The sheet's first row is a note and the second the header (Global ID, Label, NYU40 id and name, ...). Only
    "label -> NYU40 id" is kept; a label that appears twice is refused. The file is third-party and not in the repository;
    the conversion reads it after checking the SHA-256 registered in the contract.
    """

    rows = list(csv.reader(io.StringIO(csv_text)))
    header_index = next((i for i, row in enumerate(rows) if len(row) > 3 and row[1] == "Label" and "NYU40 Mapping" in row), None)
    _require(header_index is not None, "label_mapping_header_missing")
    header = rows[header_index]
    id_column = header.index("NYU40 Mapping") - 1
    mapping: dict[str, int] = {}
    for row in rows[header_index + 1:]:
        if len(row) <= id_column or not row[1].strip():
            continue
        label = row[1].strip()
        _require(label not in mapping, "label_mapping_duplicate:" + label)
        _require(row[id_column].strip().isdigit(), "label_mapping_nyu40_invalid:" + label)
        mapping[label] = int(row[id_column])
    _require(bool(mapping), "label_mapping_empty")
    return mapping


def semseg_objects(semseg: Mapping[str, Any], *, invalid: list[int] | None = None) -> dict[int, dict[str, Any]]:
    """``semseg.v2.json`` -> objectId -> {label, obb}; ids must be unique positive integers.

    Amendment 2 of ruling 111: an OBB with a non-finite value, a value beyond ``OBB_SANITY_MAX_ABS_M`` or a negative length is
    annotation garbage (one validation rescan carries a door centred at 1e290 m); the object is left out and its id appended to
    ``invalid`` (counted by the converter) instead of refusing the pair.
    """

    out: dict[int, dict[str, Any]] = {}
    for group in semseg.get("segGroups", []):
        object_id = int(group["objectId"])
        _require(object_id > 0 and object_id not in out, f"semseg_object_id_invalid:{object_id}")
        obb = group["obb"]
        centroid = [float(v) for v in obb["centroid"]]
        lengths = [float(v) for v in obb["axesLengths"]]
        axes = [float(v) for v in obb["normalizedAxes"]]
        _require(len(centroid) == 3 and len(lengths) == 3 and len(axes) == 9, f"semseg_obb_invalid:{object_id}")
        sane = (all(math.isfinite(v) for v in centroid + lengths + axes) and min(lengths) >= 0.0
                and max(abs(v) for v in centroid + lengths) <= OBB_SANITY_MAX_ABS_M)
        if not sane:
            _require(invalid is not None, f"semseg_obb_invalid:{object_id}")
            invalid.append(object_id)
            continue
        out[object_id] = {"label": str(group["label"]), "obb": {"centroid": centroid, "axesLengths": lengths, "normalizedAxes": axes}}
    return out


def scene_entry(scenes: Sequence[Mapping[str, Any]], reference_scan: str) -> Mapping[str, Any]:
    """The ``3RScan.json`` scene whose ``reference`` is this scan."""

    found = [scene for scene in scenes if scene.get("reference") == reference_scan]
    _require(len(found) == 1, "scene_not_found_once:" + reference_scan)
    return found[0]


def ambiguity_ids(value: Any) -> set[int]:
    """Every instance id named under ``instance_source`` / ``instance_target`` anywhere in an ``ambiguity`` value.

    ★ The README shows a list of lists of {instance_source, instance_target, transform}; one community reader parses a flat
    list.  Walking the value covers both; anything non-empty that names no instance is refused rather than read as "none".
    """

    found: set[int] = set()

    def walk(item: Any) -> None:
        if isinstance(item, Mapping):
            for key in ("instance_source", "instance_target"):
                if key in item:
                    found.add(int(item[key]))
            for child in item.values():
                if isinstance(child, (list, Mapping)):
                    walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(value)
    _require(bool(found) or not value, "ambiguity_structure_unrecognized")
    return found


def rescan_changes(scene: Mapping[str, Any], rescan: str) -> dict[str, Any]:
    """One rescan's change entry: alignment numbers, removed, nonrigid, rigid pairs, and the ambiguity ids (scene and rescan)."""

    entries = [item for item in scene.get("scans", []) if item.get("reference") == rescan]
    _require(len(entries) == 1, "rescan_not_found_once:" + rescan)
    entry = entries[0]
    _require("transform" in entry, "rescan_alignment_missing:" + rescan)
    rigid = []
    for item in entry.get("rigid", []):
        rigid.append((int(item["instance_reference"]), int(item["instance_rescan"])))
    return {
        "transform": [float(v) for v in entry["transform"]],
        "removed": sorted({int(v) for v in entry.get("removed", [])}),
        "nonrigid": sorted({int(v) for v in entry.get("nonrigid", [])}),
        "rigid": sorted(set(rigid)),
        "ambiguity": sorted(ambiguity_ids(scene.get("ambiguity", [])) | ambiguity_ids(entry.get("ambiguity", []))),
    }


# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------

def to_project_world(points: Any) -> np.ndarray:
    """3RScan world (+Z up) -> project world (+Y up), points as rows."""

    array = np.asarray(points, dtype=np.float64)
    return array[..., [0, 2, 1]].copy()  # W swaps y and z: exact


def transform_points(matrix: np.ndarray, points: Any) -> np.ndarray:
    return affine(matrix, points)


def obb_corners(obb: Mapping[str, Any], *, layout: str | None) -> np.ndarray:
    """The eight corners of a semseg OBB in its scan's frame; ``layout`` says whether ``normalizedAxes`` holds rows or columns (★)."""

    _require(layout is not None, "obb_axes_layout_not_registered")
    _require(layout in OBB_AXES_LAYOUTS, "obb_axes_layout_invalid")
    axes = np.asarray(obb["normalizedAxes"], dtype=np.float64).reshape(3, 3)
    if layout == "columns":
        axes = axes.T
    half = 0.5 * np.asarray(obb["axesLengths"], dtype=np.float64)
    centre = np.asarray(obb["centroid"], dtype=np.float64)
    signs = np.asarray([[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)], dtype=np.float64)
    offsets = signs * half
    return centre + (offsets[:, 0:1] * axes[0] + offsets[:, 1:2] * axes[1] + offsets[:, 2:3] * axes[2])


def object_box(obb: Mapping[str, Any], *, layout: str | None, alignment: np.ndarray | None = None) -> dict[str, list[float]]:
    """An annotated object's axis-aligned box in the project world: OBB corners, aligned to the reference scan if a rescan, then
    the axes swap.  The box is the corners' min/max, its centre the box centre (the frozen truth box is translation-only)."""

    corners = obb_corners(obb, layout=layout)
    if alignment is not None:
        corners = transform_points(orthonormal_rigid(alignment)[0], corners)
    corners = to_project_world(corners)
    lower, upper = corners.min(axis=0), corners.max(axis=0)
    return {"aabb_min_m": [float(v) for v in lower], "aabb_max_m": [float(v) for v in upper],
            "centroid_m": [float(v) for v in (lower + upper) / 2.0], "size_m": [float(v) for v in upper - lower]}


# --------------------------------------------------------------------------
# camera
# --------------------------------------------------------------------------

def _square_crop(color_size_wh: Sequence[int]) -> tuple[int, int, int, int, int]:
    """(upright width, upright height, side, x offset, y offset) of the centred square after the clockwise turn."""

    width, height = (int(v) for v in color_size_wh)
    _require((width, height) == RAW_COLOR_SIZE, "color_size_unexpected")
    upright_w, upright_h = height, width
    side = min(upright_w, upright_h)
    return upright_w, upright_h, side, (upright_w - side) // 2, (upright_h - side) // 2


def target_intrinsics(color: Mapping[str, float], color_size_wh: Sequence[int]) -> dict[str, float]:
    """The 224 x 224 target camera's intrinsics from a scan's raw colour intrinsics.

    Turn clockwise: fx' = fy, fy' = fx, cx' = (H - 1) - cy, cy' = cx.  Crop: subtract the offsets.  Scale by k = 224 / side with
    pixel centres on integers (the frozen convention, ProcTHOR's cx = 111.5): c'' = (c' + 0.5) k - 0.5, f'' = k f'.
    """

    _upright_w, _upright_h, side, x_offset, y_offset = _square_crop(color_size_wh)
    raw_h = int(color_size_wh[1])
    fx_u, fy_u = float(color["fy"]), float(color["fx"])
    cx_u, cy_u = (raw_h - 1) - float(color["cy"]), float(color["cx"])
    k = TARGET_SIZE / side
    return {"fx": fx_u * k, "fy": fy_u * k,
            "cx": (cx_u - x_offset + 0.5) * k - 0.5, "cy": (cy_u - y_offset + 0.5) * k - 0.5}


def target_to_raw_pixel(u: Any, v: Any, color_size_wh: Sequence[int]) -> tuple[np.ndarray, np.ndarray]:
    """Continuous raw colour pixel coordinates of target pixels (u right, v down), inverse of turn, crop and scale."""

    _upright_w, _upright_h, side, x_offset, y_offset = _square_crop(color_size_wh)
    raw_h = int(color_size_wh[1])
    k = TARGET_SIZE / side
    u_upright = (np.asarray(u, dtype=np.float64) + 0.5) / k - 0.5 + x_offset
    v_upright = (np.asarray(v, dtype=np.float64) + 0.5) / k - 0.5 + y_offset
    # clockwise turn: (u', v') = (H - 1 - v, u)  <=>  u = v', v = H - 1 - u'
    return v_upright, (raw_h - 1) - u_upright


def upright_rgb(raw_rgb: Any) -> np.ndarray:
    """Raw 540 x 960 x 3 colour frame -> 224 x 224 x 3 uint8: turn clockwise, centred square, area-average downscale."""

    from PIL import Image

    raw = np.asarray(raw_rgb)
    _require(raw.dtype == np.uint8 and raw.ndim == 3 and raw.shape[2] == 3, "raw_rgb_invalid")
    _require((raw.shape[1], raw.shape[0]) == RAW_COLOR_SIZE, "color_size_unexpected")
    upright = np.ascontiguousarray(np.rot90(raw, k=-1))
    _upright_w, _upright_h, side, x_offset, y_offset = _square_crop(RAW_COLOR_SIZE)
    square = np.ascontiguousarray(upright[y_offset:y_offset + side, x_offset:x_offset + side])
    image = Image.fromarray(square).resize((TARGET_SIZE, TARGET_SIZE), resample=Image.Resampling.BOX)
    out = np.asarray(image, dtype=np.uint8)
    _require(out.shape == (TARGET_SIZE, TARGET_SIZE, 3), "target_rgb_shape_invalid")
    return out


def sensor_depth_on_target(depth_raw: Any, *, depth_shift: float, depth_intrinsics: Mapping[str, float],
                           color_intrinsics: Mapping[str, float], color_size_wh: Sequence[int]) -> np.ndarray:
    """Diagnostic only (ruling 111-5): the scan's sensor depth (16-bit, 0 = invalid) nearest-sampled onto the target grid, metres.

    Each target pixel's ray is followed back to the raw colour camera and into the registered depth camera (same centre, own
    intrinsics); the nearest depth pixel inside the image gives the axial depth (turning and cropping keep the optical axis), else 0.
    """

    depth = np.asarray(depth_raw)
    _require(depth.ndim == 2, "sensor_depth_shape_invalid")
    vv, uu = np.mgrid[0:TARGET_SIZE, 0:TARGET_SIZE].astype(np.float64)
    u_raw, v_raw = target_to_raw_pixel(uu, vv, color_size_wh)
    dx = (u_raw - float(color_intrinsics["cx"])) / float(color_intrinsics["fx"])
    dy = (v_raw - float(color_intrinsics["cy"])) / float(color_intrinsics["fy"])
    u_d = np.rint(dx * float(depth_intrinsics["fx"]) + float(depth_intrinsics["cx"])).astype(np.int64)
    v_d = np.rint(dy * float(depth_intrinsics["fy"]) + float(depth_intrinsics["cy"])).astype(np.int64)
    inside = (u_d >= 0) & (u_d < depth.shape[1]) & (v_d >= 0) & (v_d < depth.shape[0])
    out = np.full((TARGET_SIZE, TARGET_SIZE), INVALID_DEPTH_M, dtype=np.float32)
    out[inside] = (depth[v_d[inside], u_d[inside]].astype(np.float64) / float(depth_shift)).astype(np.float32)
    return out


def camera_pose(pose_raw: np.ndarray, *, alignment: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray, float]:
    """A raw frame pose -> (rotation, position, orthonormality residual) of the upright target camera in the project world.

    R' = W . R . Q^T . S and t' = W . t, after left-multiplying a rescan's pose by its rescan-to-reference alignment.  W and S
    are each a mirror, Q a proper turn, so det R' = +1: a proper camera-to-world rotation the frozen reader accepts.  R' is then
    made exactly orthonormal (``orthonormal_rigid``, once, on the raw pose and alignment) because the quaternion encoder
    requires it.  Every product is written
    out in a fixed order (``matmul``), so the public pose has the same bits on every host.
    """

    matrix, residual = orthonormal_rigid(_rigid(np.asarray(pose_raw, dtype=np.float64), "pose_not_rigid"))
    if alignment is not None:
        aligned, moved = orthonormal_rigid(alignment)
        matrix, residual = matmul(aligned, matrix), max(residual, moved)
    rotation = matmul(matmul(matmul(W, matrix[:3, :3]), Q.T), S)
    position = to_project_world(matrix[:3, 3])
    _require(abs(float(np.linalg.det(rotation)) - 1.0) < 1e-9, "converted_rotation_not_proper")
    return rotation, position, residual


#: frames whose forward axis is within this sine of straight up or down have no defined roll and are not judged
ROLL_UNDEFINED_BELOW = 0.2
#: the camera turns the sample check compares (ruling 111-5 amendment, pending): image up is camera +y after each turn
ROLL_CANDIDATE_TURNS = ("clockwise_90", "none", "counterclockwise_90", "half_turn")


def image_roll_cosine(rotation: np.ndarray) -> float:
    """Cosine of the image's roll: the target image's up axis against world up projected onto the image plane (★ sample check).

    Whether the turned image is upright is a question of roll, not pitch. World up is projected onto the image plane and
    compared with the image's up axis: about 1 when the turn is right, about 0 at 90 degrees off, about -1 when reversed,
    whatever the camera's pitch. When the camera faces the ceiling or the floor almost squarely, roll is undefined and NaN
    is returned (left out of the decision). It is not the angle between the image's up axis and world up, which mixes in
    pitch: for a hand-held scan looking down 55 degrees that is only about 0.5 even when the turn is right (2026-10-07
    sample rehearsal).
    """

    r = np.asarray(rotation, dtype=np.float64)
    forward, up = r[:, 2], np.asarray([0.0, 1.0, 0.0])
    projected = up - float(forward[1]) * forward
    norm = math.sqrt(float(projected[0] * projected[0] + projected[1] * projected[1] + projected[2] * projected[2]))
    if norm < ROLL_UNDEFINED_BELOW:
        return float("nan")
    unit = projected / norm
    return float(r[0, 1] * unit[0] + r[1, 1] * unit[1] + r[2, 1] * unit[2])


def turned_rotation(pose_raw: np.ndarray, turn: str) -> np.ndarray:
    """The converted camera rotation under one candidate turn (sample check only; conversion always uses the registered turn)."""

    _require(turn in ROLL_CANDIDATE_TURNS, "turn_unknown")
    matrix, _residual = orthonormal_rigid(np.asarray(pose_raw, dtype=np.float64))
    turns = {"clockwise_90": Q, "none": np.eye(3), "counterclockwise_90": Q.T, "half_turn": matmul(Q, Q)}
    return matmul(matmul(matmul(W, matrix[:3, :3]), turns[turn].T), S)


def relative_pose(rotation: np.ndarray, position: np.ndarray, origin_position: Sequence[float]) -> dict[str, Any]:
    """The public ``relative_pose``: position minus observation 0's camera position, absolute rotation, as S1-02 writes it."""

    offset = np.asarray(position, dtype=np.float64) - np.asarray(origin_position, dtype=np.float64)
    return {"position_m": [float(v) for v in offset], "quaternion_xyzw": pp.quaternion_xyzw_from_rotation(rotation),
            "origin": "observation_0_camera"}


def frame_digest(rgb: Any, depth: Any, *, observation_index: int, relative_pose_record: Mapping[str, Any],
                 action_summary: Mapping[str, Any]) -> str:
    """The S1-02 public frame digest: sha256 of canonical JSON over the RGB and depth byte digests and three public fields."""

    rgb_array = np.asarray(rgb)
    depth_array = np.asarray(depth)
    _require(rgb_array.dtype == np.uint8 and rgb_array.shape == (TARGET_SIZE, TARGET_SIZE, 3), "digest_rgb_invalid")
    _require(depth_array.dtype == np.float32 and depth_array.shape == (TARGET_SIZE, TARGET_SIZE), "digest_depth_invalid")
    payload = {"rgb": hashlib.sha256(rgb_array.tobytes()).hexdigest(), "depth": hashlib.sha256(depth_array.tobytes()).hexdigest(),
               "observation_index": int(observation_index), "relative_pose": dict(relative_pose_record),
               "action_summary": dict(action_summary)}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# truth
# --------------------------------------------------------------------------

def episode_id(reference_scan: str, rescan: str) -> str:
    _require(SCAN_ID.fullmatch(reference_scan) is not None and SCAN_ID.fullmatch(rescan) is not None, "scan_id_invalid")
    _require(reference_scan != rescan, "rescan_is_reference")
    return f"{EPISODE_PREFIX}{reference_scan}-{rescan}"


def degenerate_window(reference_frames: int) -> list[int]:
    """Ruling 111-2: zero frames between the scans, written as [n_ref - 1, n_ref - 1] (the evaluator reads only the end)."""

    _require(int(reference_frames) >= 1, "reference_without_frames")
    last = int(reference_frames) - 1
    return [last, last]


def object_key(object_id: int, label: str, nyu40_id: int) -> str:
    """The private key of an annotated object: ``<prefix>|<objectId>``.

    Structure (NYU40 wall, floor, door, window, ceiling) takes the frozen evaluator's prefix so it is out of the node scope;
    everything else takes its label as one token (``obj_`` in front if the token would read as a structural prefix).  The last
    field is digits, never a spawn tag.
    """

    _require(int(object_id) > 0, "object_id_invalid")
    prefix = NYU40_STRUCTURAL_PREFIX.get(int(nyu40_id))
    if prefix is None:
        token = re.sub(r"[^A-Za-z0-9]+", "_", str(label)).strip("_") or "object"
        prefix = "obj_" + token if token in lt.STRUCTURAL_TYPES_EXCLUDED else token
    key = f"{prefix}|{int(object_id)}"
    _require(not lt.is_spawned_after_reload(key), "object_key_reads_as_spawn_tag")
    return key


def is_structural(nyu40_id: int) -> bool:
    return int(nyu40_id) in NYU40_STRUCTURAL_PREFIX


def _place_state(box: Mapping[str, Any]) -> dict[str, list[float]]:
    """A box as the frozen place rule reads it: plain Python floats (``lean_teacher`` refuses numpy scalars)."""

    return {key: [float(v) for v in box[key]] for key in ("centroid_m", "aabb_min_m", "aabb_max_m")}


def _holds(old: Mapping[str, Any], new: Mapping[str, Any]) -> bool:
    holds, _distance, _test = lt.place_holds(_place_state(old)["centroid_m"], _place_state(new), delta_moved_m=lt.DELTA_MOVED_M)
    return holds


def classify_changes(reference: Mapping[int, Mapping[str, Any]], rescan: Mapping[int, Mapping[str, Any]],
                     changes: Mapping[str, Any], *, structural: Iterable[int], covered: Mapping[int, bool] | None = None,
                     residual_ratio: Mapping[int, float] | None = None) -> dict[str, Any]:
    """Ruling 111-3 with amendment 2: each object's outcome and the intervention rows the frozen evaluator reads.

    ``reference`` / ``rescan`` map objectId -> box (``object_box`` output, both in the reference-aligned project world);
    ``changes`` is ``rescan_changes`` output; ``structural`` the objectIds mapped to a structural prefix; ``covered`` says per
    reference object whether the rescan mesh reached its place (``COVERAGE_RADIUS_M``; None = every place covered, the pre-amendment
    reading); ``residual_ratio`` gives, for an official removal still annotated in the rescan, its rescan-to-reference vertex ratio.

    Rules: an official ``removed`` entry is ``remove`` (a residual annotation in the rescan does not override the official
    list; its ratio is kept in ``residual_annotations``); an object in neither the official list nor the rescan annotation
    is ``remove_unlisted`` only if the rescan reached its place (a rescan vertex within 0.5 m of the reference box centre),
    otherwise ``not_rescanned`` and the object stays present at its reference place (amendment 2); an object only in the
    rescan is ``add`` (point = rescan box centre); ``rigid`` uses the rule of the node primary column
    (``lean_teacher.place_holds``: old centroid within delta_moved of the new one, or inside the new box enlarged by
    0.25 m) -- ``move`` when it fails, otherwise only counted as ``small_rigid``; a rigid instance under ``ambiguity`` is
    not a ``move`` (the correspondence is not unique), while removals are still recorded; ``nonrigid`` is only counted; an
    object outside every list that fails the place rule is only counted as ``unlisted_displacement``; changes of
    structural parts never enter the intervention log and are counted as ``structural_change_ignored``. Inconsistent
    change entries (an instance listed twice, a rigid instance missing from a scan) refuse the whole pair rather than
    guess. Example: a chair moved 1.2 m is ``move``, moved 0.1 m ``small_rigid``. It judges no method and reads no method
    output.
    """

    structural_ids = {int(v) for v in structural}
    removed = set(changes["removed"])
    nonrigid = set(changes["nonrigid"])
    ambiguous = set(changes["ambiguity"])
    rescan_of: dict[int, int] = {}
    for ref_id, rescan_id in changes["rigid"]:
        _require(ref_id in reference, f"rigid_reference_instance_missing:{ref_id}")
        _require(rescan_id in rescan, f"rigid_rescan_instance_missing:{rescan_id}")
        _require(ref_id not in rescan_of, f"rigid_instance_listed_twice:{ref_id}")
        rescan_of[ref_id] = rescan_id
    _require(len(set(rescan_of.values())) == len(rescan_of), "rigid_rescan_instance_listed_twice")
    taken_by_other = {rescan_id for ref_id, rescan_id in rescan_of.items() if rescan_id != ref_id}

    def rescan_box(ref_id: int) -> Mapping[str, Any] | None:
        if ref_id in rescan_of:
            return rescan[rescan_of[ref_id]]
        if ref_id in rescan and ref_id not in taken_by_other:
            return rescan[ref_id]
        return None

    outcomes: dict[int, str] = {}
    rows: list[dict[str, Any]] = []
    used_rescan_ids: set[int] = set()
    residuals: dict[int, float] = {}
    for object_id in sorted(reference):
        new = rescan_box(object_id)
        if object_id in removed:
            outcome = "remove"  # the official list wins over a residual annotation (amendment 2), the residual is recorded
            if new is not None:
                residuals[object_id] = float((residual_ratio or {}).get(object_id, float("nan")))
                used_rescan_ids.add(rescan_of.get(object_id, object_id))
        elif new is None:
            outcome = "remove_unlisted" if (covered is None or covered.get(object_id, True)) else "not_rescanned"
        else:
            used_rescan_ids.add(rescan_of.get(object_id, object_id))
            holds = _holds(reference[object_id], new)
            if object_id in rescan_of:
                outcome = "ambiguous_rigid" if object_id in ambiguous else ("small_rigid" if holds else "move")
            elif object_id in nonrigid:
                outcome = "nonrigid"
            else:
                outcome = None if holds else "unlisted_displacement"
        if outcome is not None and object_id in structural_ids:
            outcome = "structural_change_ignored"
        if outcome is not None:
            outcomes[object_id] = outcome
        if outcome in ("remove", "remove_unlisted"):
            rows.append({"object_id": object_id, "kind": "remove", "point": None, "executed": True})
        elif outcome == "move":
            rows.append({"object_id": object_id, "kind": "move", "point": _place_state(new)["centroid_m"], "executed": True})
    for rescan_id in sorted(set(rescan) - used_rescan_ids):
        _require(rescan_id not in reference or rescan_id in taken_by_other, f"rescan_instance_unresolved:{rescan_id}")
        if rescan_id in structural_ids:
            outcomes[rescan_id] = "structural_change_ignored"
            continue
        outcomes[rescan_id] = "add"
        rows.append({"object_id": rescan_id, "kind": "add", "point": _place_state(rescan[rescan_id])["centroid_m"], "executed": True})
    counts = {name: sum(1 for value in outcomes.values() if value == name) for name in CHANGE_OUTCOMES}
    return {"interventions": rows, "outcomes": {str(k): v for k, v in sorted(outcomes.items())}, "counts": counts,
            "rescan_id_of": {str(k): v for k, v in sorted(rescan_of.items()) if k != v},
            "residual_annotations": {str(k): v for k, v in sorted(residuals.items())}}

