"""D-224 / S2-01 tests for the common runner.

Pinned here: the entity-geometry ratios are a pure function of the frame's public volumes and the
previous memory (fully inside, outside, half inside, union of blocks, no blocks, deterministic, the
resolution must be given); only the two frozen descriptor choices are accepted and the projection
is digest-checked; every policy value and arm parameter must be explicit; the eight steps run
end to end for every runnable arm on hand-built frames with the expected atoms (BIRTH, BIND, NOOP
into dormancy, REACTIVATE, ELU-P and RAC RETRACT with their temporal state, AssocOnly without
existence, NoVersion deleting retracted); an illegal program rolls back and the frame commits an
empty program and is counted; two runs are byte-identical; the byte-identical cache gate accepts
equal seals and refuses a tampered one; the truth-table builder applies the S0-04 scope rule and
its output is accepted by the S0-04 evaluator; the machine contract binds the implementation.
Torch on CPU for the projection; nothing here touches a real cache or a private file.
"""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
import sys
import unittest
from pathlib import Path
from typing import Any, Mapping
from unittest import mock

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vsmt import lean_arms as arms  # noqa: E402
from vsmt import lean_assignment as la  # noqa: E402
from vsmt import lean_memory as lm  # noqa: E402
from vsmt import lean_reid_head as rh  # noqa: E402
from vsmt import lean_runner as lr  # noqa: E402
from vsmt import lean_teacher as lt  # noqa: E402

CONTRACT_PATH = PROJECT_ROOT / "configs" / "vsmt" / "lean_s2_01_runner_v1.json"
DIM = 8  # synthetic frozen descriptor width; the synthetic projector maps it to the frozen 128
POLICY = {
    "dormancy_missed_opportunity_limit": 2,
    "dedup": {"period_ticks": 1000, "descriptor_cosine_min": 0.999, "centroid_distance_max_m": 0.01, "aabb_iou_min": 0.99},
    "should_be_visible_min_ratio": 1 / 64,  # the frozen value (ruling 68); under ruling 74 a present box shows about its front layer
    "entity_geometry_samples_per_axis": 4,
}
CONFIGS: dict[str, dict[str, Any]] = {
    "TAF": {"theta_a": 0.5, "d_a": None},
    "LOW": {"d_low": None},
    "ELU-P": {"theta_a": 0.5, "d_a": None, "free_space_weight": 1.0, "retract_threshold": -1.0,
              "initial_log_odds": 0.5, "persistence_log_decay_per_tick": 0.5, "match_gain": 1.0},
    "RAC": {"theta_a": 0.5, "d_a": None, "rho_rac": 0.5, "n_rac": 2},
    "HandCost": {"theta_b": 0.5, "rho_h": 0.5},
    "VSMT-lean": {"tau_r": 0.5},
    "NoVersion": {"tau_r": 0.5},
    "HeuristicLabel": {"tau_r": 0.5},
    "AssocOnly": {},
    "VSMT-lean-ctx": {"tau_r": 0.5},
}


def digest(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def unit(seed: int, dim: int = DIM) -> list[float]:
    rng = np.random.default_rng(seed)
    values = rng.normal(size=dim)
    return [float(v) for v in values / np.linalg.norm(values)]


def box_block(lower: list[float], upper: list[float], *, ordinal: int, kind: str) -> dict[str, Any]:
    """An axis-aligned box as the six world halfspaces the frozen materialiser writes."""

    planes = []
    for axis in range(3):
        plus = [0.0, 0.0, 0.0]
        plus[axis] = 1.0
        minus = [0.0, 0.0, 0.0]
        minus[axis] = -1.0
        planes.append({"normal": plus, "offset_m": float(upper[axis])})
        planes.append({"normal": minus, "offset_m": float(-lower[axis])})
    return {f"{kind}_id": f"{kind}:{ordinal:04d}", "time_s": 0.0, "halfspaces_world": planes,
            "reliability": 1.0, "support_sha256": "d" * 64}


def fragment_row(fragment_id: str, *, descriptor: list[float], centroid: list[float], half: float = 0.1, pixels: int = 400) -> dict[str, Any]:
    return {
        "fragment_id": fragment_id,
        "descriptor_vits14": list(descriptor), "descriptor_vitb14": list(descriptor),
        "centroid_m": list(centroid),
        "aabb_min_m": [v - half for v in centroid], "aabb_max_m": [v + half for v in centroid],
        "pixel_count": pixels, "depth_valid_ratio": 1.0, "supported_by": None, "mask_sha256": "a" * 64,
    }


#: Ruling 74 test fixture: a 224 x 224 public depth view rendered by ray casting the boxes that are physically
#: present this frame (by default the frame's own fragment boxes) from a camera at the origin looking along +z
#: (or away, when the frame sees nothing), background at FAR_M.  The camera sits at CAMERA_AT so the whole synthetic
#: scene (x in [-2, 3] m near z = 2 m) is inside the 90-degree view.  A present box then reads as surface / occluded
#: from outside, and the place of an object that is gone reads as seen through.
DEPTH_SIZE = 224
DEPTH_CALIBRATION = {"fx": 112.0, "fy": 112.0, "cx": 112.0, "cy": 112.0}
CAMERA_AT = [0.5, 0.0, -1.0]
FACING_SCENE = {"position_m": list(CAMERA_AT), "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0]}
FACING_AWAY = {"position_m": list(CAMERA_AT), "quaternion_xyzw": [0.0, 1.0, 0.0, 0.0]}
FAR_M = 15.0


def rendered_depth(boxes: list[tuple[list[float], list[float]]]) -> np.ndarray:
    """Axial depth of the first box each pixel ray meets (slab test), FAR_M where it meets none."""

    grid = np.arange(DEPTH_SIZE, dtype=np.float64)
    columns, rows = np.meshgrid(grid, grid)
    direction = np.stack([(columns - DEPTH_CALIBRATION["cx"]) / DEPTH_CALIBRATION["fx"],
                          (DEPTH_CALIBRATION["cy"] - rows) / DEPTH_CALIBRATION["fy"], np.ones_like(columns)], axis=-1)
    depth = np.full((DEPTH_SIZE, DEPTH_SIZE), FAR_M)
    with np.errstate(divide="ignore", invalid="ignore"):
        for lower, upper in boxes:  # the camera looks along +z without rotation, so a box moves by -CAMERA_AT
            t1 = (np.asarray(lower, dtype=np.float64) - CAMERA_AT) / direction
            t2 = (np.asarray(upper, dtype=np.float64) - CAMERA_AT) / direction
            near = np.nanmax(np.minimum(t1, t2), axis=-1)
            far = np.nanmin(np.maximum(t1, t2), axis=-1)
            hit = (near <= far) & (far > 0)
            depth = np.where(hit, np.minimum(depth, np.maximum(near, 0.0)), depth)
    return depth.astype(np.float32)


def depth_view(frame_digest: str, boxes: list[tuple[list[float], list[float]]], *, sees: bool = True) -> dict[str, Any]:
    return {"frame_digest": frame_digest, "depth_m": rendered_depth(boxes if sees else []),
            "calibration": dict(DEPTH_CALIBRATION), "pose": dict(FACING_SCENE if sees else FACING_AWAY)}


def cache_frame(tick: int, fragments: list[dict[str, Any]], *, visibility: list[dict[str, Any]], free_space: list[dict[str, Any]],
                present: list[tuple[list[float], list[float]]] | None = None) -> dict[str, Any]:
    frame = {
        "frame_digest": digest(f"frame-{tick}"), "tick": tick,
        "camera_position_m": [0.0, 0.0, 0.0], "camera_forward": [0.0, 0.0, 1.0],
        "fragments": fragments, "surfaces": [], "free_space": free_space, "visibility": visibility,
    }
    frame["frame_seal"] = {"payload_sha256": digest(json.dumps(frame, sort_keys=True)), "frontend_config_sha256": "0" * 64}
    boxes = present if present is not None else [(f["aabb_min_m"], f["aabb_max_m"]) for f in fragments]
    frame[lr.PUBLIC_DEPTH_VIEW_KEY] = depth_view(frame["frame_digest"], boxes, sees=bool(visibility))
    return frame


A_DESC, B_DESC = unit(1), unit(2)
A_AT, B_AT = [0.0, 0.0, 2.0], [1.0, 0.0, 2.0]
SEES_ALL = [box_block([-2.0, -1.0, 0.5], [2.0, 1.0, 3.0], ordinal=0, kind="visibility")]
FREE_AT_A = [box_block([-0.5, -0.5, 1.5], [0.5, 0.5, 2.5], ordinal=0, kind="free-space")]


def scenario() -> list[dict[str, Any]]:
    """A and B seen twice; A vanishes for two frames while its place is visible and free; A returns."""

    a = fragment_row("region:a", descriptor=A_DESC, centroid=A_AT)
    b = fragment_row("region:b", descriptor=B_DESC, centroid=B_AT)
    return [
        cache_frame(1, [a, b], visibility=SEES_ALL, free_space=[]),
        cache_frame(2, [a, b], visibility=SEES_ALL, free_space=[]),
        cache_frame(3, [b], visibility=SEES_ALL, free_space=FREE_AT_A),
        cache_frame(4, [b], visibility=SEES_ALL, free_space=FREE_AT_A),
        cache_frame(5, [a, b], visibility=SEES_ALL, free_space=[]),
    ]


def synthetic_projector():
    import torch
    torch.manual_seed(0)
    head = rh.make_head(DIM, output_dimension=la.REID_OUTPUT_DIMENSION)
    payload = rh.weights_payload(head, input_dimension=DIM, output_dimension=la.REID_OUTPUT_DIMENSION, training={"synthetic": True})
    return payload, lr.descriptor_projector(payload, expected_sha256=payload["sha256"])


class CosineScorer:
    """A stand-in for the S2-03 heads: cosine as the association logit, a constant birth logit, a fixed existence logit."""

    def __init__(self, *, birth: float = 0.5, existence: float = 10.0) -> None:
        self.birth, self.existence = birth, existence

    def association_and_birth_logits(self, stage_a: Mapping[str, Any]) -> dict[str, Any]:
        at = arms.feature_index(stage_a["association_feature_order"], "cosine_to_descriptor_mean")
        return {"association_logits": {f"{r['fragment_id']}|{r['entity_id']}": float(r["features"][at]) for r in stage_a["association_rows"]},
                "birth_logits": {str(f): self.birth for f in stage_a["rows"]}}

    def existence_logits(self, rows, order) -> dict[str, float]:
        return {str(r["entity_id"]): self.existence for r in rows}


def run_all(arm: str, *, descriptor: str = la.FROZEN_DESCRIPTOR_BASELINE, projector=None, scorer=None, frames=None, config=None):
    steps = list(lr.run_episode(frames or scenario(), episode_id="ep-0001", arm=arm, config=config or CONFIGS[arm], policy=POLICY,
                                descriptor=descriptor, projector=projector, scorer=scorer))
    return steps, lr.episode_summary(steps[-1]["state"], [s["receipt"] for s in steps])


def atoms_of(step: Mapping[str, Any]) -> dict[str, int]:
    return {k: v for k, v in step["receipt"]["program"]["atom_counts"].items() if v}


class EntityGeometryTests(unittest.TestCase):
    def entity(self, lower, upper, entity_id="entity:x"):
        return {"entity_id": entity_id, "aabb_min_m": lower, "aabb_max_m": upper}

    def geometry(self, memory_entities, *, visibility=(), free_space=(), s=4):
        # the superseded block-frustum rule, kept for diagnostics (ruling 74)
        frame = cache_frame(1, [], visibility=list(visibility), free_space=list(free_space))
        return lr.entity_geometry_blocks({"entities": memory_entities}, frame, samples_per_axis=s)

    def test_inside_outside_half_and_union(self) -> None:
        block = box_block([0.0, 0.0, 0.0], [1.0, 1.0, 1.0], ordinal=0, kind="visibility")
        inside = self.geometry([self.entity([0.2, 0.2, 0.2], [0.8, 0.8, 0.8])], visibility=[block])["entity:x"]
        self.assertEqual(inside, {"should_be_visible_ratio": 1.0, "free_space_coverage_ratio": 0.0})
        outside = self.geometry([self.entity([2.0, 2.0, 2.0], [3.0, 3.0, 3.0])], visibility=[block])["entity:x"]
        self.assertEqual(outside["should_be_visible_ratio"], 0.0)
        # a box straddling the block's x = 1 face: exactly half of the 4x4x4 cell centres are inside
        half = self.geometry([self.entity([0.5, 0.2, 0.2], [1.5, 0.8, 0.8])], visibility=[block])["entity:x"]
        self.assertEqual(half["should_be_visible_ratio"], 0.5)
        other = box_block([1.0, 0.0, 0.0], [2.0, 1.0, 1.0], ordinal=1, kind="visibility")
        union = self.geometry([self.entity([0.5, 0.2, 0.2], [1.5, 0.8, 0.8])], visibility=[block, other])["entity:x"]
        self.assertEqual(union["should_be_visible_ratio"], 1.0)
        free = self.geometry([self.entity([0.2, 0.2, 0.2], [0.8, 0.8, 0.8])],
                             free_space=[box_block([0.0, 0.0, 0.0], [1.0, 1.0, 1.0], ordinal=0, kind="free-space")])["entity:x"]
        self.assertEqual(free, {"should_be_visible_ratio": 0.0, "free_space_coverage_ratio": 1.0})

    def test_no_blocks_gives_zero_and_a_flat_box_is_sampled_once_per_flat_axis(self) -> None:
        self.assertEqual(self.geometry([self.entity([0.0, 0.0, 0.0], [1.0, 1.0, 1.0])])["entity:x"],
                         {"should_be_visible_ratio": 0.0, "free_space_coverage_ratio": 0.0})
        points = lr.sample_points([0.0, 0.5, 0.0], [1.0, 0.5, 1.0], samples_per_axis=3)
        self.assertEqual(points.shape, (27, 3))
        self.assertTrue(np.all(points[:, 1] == 0.5))
        self.assertTrue(np.all((points[:, 0] > 0.0) & (points[:, 0] < 1.0)))

    def test_resolution_must_be_given_and_the_result_is_deterministic(self) -> None:
        with self.assertRaises(lr.LeanRunnerError) as caught:
            self.geometry([self.entity([0.0, 0.0, 0.0], [1.0, 1.0, 1.0])], s=None)
        self.assertEqual(str(caught.exception), "policy_value_missing:entity_geometry_samples_per_axis")
        rng = np.random.default_rng(3)
        blocks = [box_block(list(lo), list(lo + rng.random(3) + 0.1), ordinal=i, kind="visibility")
                  for i, lo in enumerate(rng.random((20, 3)) * 2.0)]
        entities = [self.entity(list(lo), list(lo + 0.4), entity_id=f"entity:{i}") for i, lo in enumerate(rng.random((10, 3)) * 2.0)]
        first = self.geometry(entities, visibility=blocks)
        second = self.geometry(entities, visibility=blocks)
        self.assertEqual(first, second)
        for value in first.values():
            self.assertTrue(0.0 <= value["should_be_visible_ratio"] <= 1.0)
            self.assertAlmostEqual(value["should_be_visible_ratio"] * 64, round(value["should_be_visible_ratio"] * 64))

    def test_the_block_prefilter_changes_no_ratio(self) -> None:
        # Engineering (LOG-254): block_aabbs lets entity_geometry skip blocks that cannot meet the entity
        # box; the ratios must equal the brute force over every block to the last bit, on rotated blocks too
        rng = np.random.default_rng(11)

        def rotated(block, angle, axis, shift):
            axis = axis / np.linalg.norm(axis)
            k = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
            rotation = np.eye(3) + np.sin(angle) * k + (1 - np.cos(angle)) * (k @ k)
            planes = []
            for plane in block["halfspaces_world"]:
                normal = rotation @ np.asarray(plane["normal"])
                planes.append({"normal": [float(v) for v in normal], "offset_m": float(plane["offset_m"] + normal @ shift)})
            return {**block, "halfspaces_world": planes}

        blocks = []
        for i in range(30):
            lo = rng.random(3) * 3.0
            box = box_block(list(lo), list(lo + rng.random(3) * 0.8 + 0.05), ordinal=i, kind="visibility")
            blocks.append(rotated(box, float(rng.random() * 3.0), rng.normal(size=3), rng.normal(size=3) * 0.5))
        lower, upper = lr.block_aabbs(*lr._blocks(blocks))
        self.assertEqual(lower.shape, (30, 3))
        self.assertTrue(np.all(np.isfinite(lower)) and np.all(lower < upper))
        unit = box_block([0.0, 0.0, 0.0], [1.0, 1.0, 1.0], ordinal=0, kind="visibility")
        lo1, hi1 = lr.block_aabbs(*lr._blocks([unit]))
        self.assertTrue(np.allclose(lo1, -lr.BLOCK_AABB_MARGIN_M) and np.allclose(hi1, 1.0 + lr.BLOCK_AABB_MARGIN_M))
        entities = [self.entity(list(lo), list(lo + rng.random(3) * 0.6 + 0.02), entity_id=f"entity:{i}") for i, lo in enumerate(rng.random((40, 3)) * 3.5)]
        frame = cache_frame(1, [], visibility=blocks, free_space=blocks[:7])
        filtered = lr.entity_geometry_blocks({"entities": entities}, frame, samples_per_axis=4)
        normals, offsets = lr._blocks(blocks)
        free_normals, free_offsets = lr._blocks(blocks[:7])
        hits = 0
        for entity in entities:
            points = lr.sample_points(entity["aabb_min_m"], entity["aabb_max_m"], samples_per_axis=4)
            brute = {"should_be_visible_ratio": lr.inside_union_fraction(points, normals, offsets),
                     "free_space_coverage_ratio": lr.inside_union_fraction(points, free_normals, free_offsets)}
            self.assertEqual(filtered[entity["entity_id"]], brute, entity["entity_id"])
            hits += brute["should_be_visible_ratio"] > 0.0
        self.assertGreaterEqual(hits, 3)  # the scene is dense enough that the comparison is not vacuous

    def test_the_public_phase_takes_no_private_input(self) -> None:
        for function in (lr.entity_geometry, lr.entity_geometry_blocks, lr.point_depth_counts, lr.assignment_frame,
                         lr.run_frame, lr.run_episode):
            names = " ".join(inspect.signature(function).parameters)
            for token in ("private", "truth", "teacher", "instance", "object_id"):
                self.assertNotIn(token, names, function.__name__)


class PerPointDepthGeometryTests(unittest.TestCase):
    """Ruling 74: the two ratios by the per-point depth test on the frame's public depth view."""

    BOX = ([-0.1, -0.1, 1.9], [0.1, 0.1, 2.1])

    def ratios(self, boxes, *, sees=True, entity_box=None, margin=lr.DEPTH_MARGIN_M):
        view = depth_view("f" * 64, boxes, sees=sees)
        lower, upper = entity_box or self.BOX
        memory = {"entities": [{"entity_id": "entity:x", "aabb_min_m": list(lower), "aabb_max_m": list(upper)}]}
        return lr.entity_geometry(memory, view, samples_per_axis=4, margin_m=margin)["entity:x"]

    def test_a_present_object_is_seen_on_its_surface_and_never_through(self) -> None:
        present = self.ratios([self.BOX])
        self.assertEqual(present["should_be_visible_ratio"], 16 / 64)   # the front layer of the 4 x 4 x 4 grid
        self.assertEqual(present["free_space_coverage_ratio"], 0.0)

    def test_the_place_of_a_removed_object_is_seen_through(self) -> None:
        gone = self.ratios([])
        self.assertEqual(gone["should_be_visible_ratio"], 1.0)
        self.assertEqual(gone["free_space_coverage_ratio"], 1.0)

    def test_an_occluded_place_is_not_evidence(self) -> None:
        wall = ([-1.0, -1.0, 1.0], [1.0, 1.0, 1.05])
        occluded = self.ratios([wall])
        self.assertEqual(occluded, {"should_be_visible_ratio": 0.0, "free_space_coverage_ratio": 0.0})

    def test_a_place_the_camera_does_not_look_at_is_not_evidence(self) -> None:
        self.assertEqual(self.ratios([], sees=False), {"should_be_visible_ratio": 0.0, "free_space_coverage_ratio": 0.0})

    def test_a_box_half_behind_its_own_surface_splits_by_the_margin(self) -> None:
        # a thin surface at z = 2.0 inside a deeper entity box: the layer in front is seen through, the layer on it
        # is surface, the layers behind are occluded
        slab = ([-0.1, -0.1, 2.0], [0.1, 0.1, 2.3])
        out = self.ratios([slab], entity_box=([-0.1, -0.1, 1.9], [0.1, 0.1, 2.1]))
        # layers at z 1.925 (d 2.0 > z + 0.05: through), 1.975 and 2.025 (within 0.05: surface), 2.075 (occluded)
        self.assertEqual(out["should_be_visible_ratio"], 48 / 64)
        counts = lr.point_depth_counts(lr.sample_points([-0.1, -0.1, 1.9], [0.1, 0.1, 2.1], samples_per_axis=4)[None],
                                       depth_view("f" * 64, [slab]))
        self.assertEqual((int(counts["through"][0]), int(counts["surface"][0]), int(counts["occluded"][0])), (16, 32, 16))
        self.assertEqual(out["free_space_coverage_ratio"], 16 / 48)

    def test_the_projection_inverts_the_frozen_back_projection(self) -> None:
        from vsmt.l1_entities import _camera_values

        pose = {"position_m": [1.0, 1.5, -2.0], "quaternion_xyzw": [0.0, float(np.sin(np.pi / 8)), 0.0, float(np.cos(np.pi / 8))]}
        fx, fy, cx, cy, position, rotation = _camera_values(DEPTH_CALIBRATION, pose)
        depth = np.full((DEPTH_SIZE, DEPTH_SIZE), 3.0, dtype=np.float32)
        view = {"frame_digest": "f" * 64, "depth_m": depth, "calibration": dict(DEPTH_CALIBRATION), "pose": pose}
        for row, column in ((10, 20), (112, 112), (200, 5)):
            point = rotation @ np.array([(column - cx) * 3.0 / fx, (cy - row) * 3.0 / fy, 3.0]) + position
            counts = lr.point_depth_counts(point[None, None, :], view)
            self.assertEqual(int(counts["surface"][0]), 1, (row, column))

    def test_the_view_must_be_of_the_same_frame_and_well_formed(self) -> None:
        frame = cache_frame(1, [], visibility=SEES_ALL, free_space=[])
        lr.public_depth_view_of(frame)
        other = dict(frame, public_depth_view=dict(frame[lr.PUBLIC_DEPTH_VIEW_KEY], frame_digest="0" * 64))
        for broken, code in ((other, "public_depth_view_of_another_frame"),
                             ({k: v for k, v in frame.items() if k != lr.PUBLIC_DEPTH_VIEW_KEY}, "public_depth_view_missing")):
            with self.assertRaises(lr.LeanRunnerError) as caught:
                lr.public_depth_view_of(broken)
            self.assertEqual(str(caught.exception), code)

    def test_the_margin_is_the_frozen_value(self) -> None:
        self.assertEqual(lr.DEPTH_MARGIN_M, 0.05)
        self.assertEqual(lr.DEPTH_VALID_RANGE_M, (0.05, 20.0))


class DescriptorChoiceTests(unittest.TestCase):
    def test_only_the_two_frozen_choices_are_accepted(self) -> None:
        self.assertEqual(lr.DESCRIPTOR_CHOICES, ("reid_projection:vitb14", "vitb14"))
        self.assertEqual(lr.source_set_of("reid_projection:vitb14"), "vitb14")
        self.assertEqual(lr.source_set_of("vitb14"), "vitb14")
        for bad in ("vits14", "reid_projection:vits14", "dinov3"):
            with self.subTest(bad=bad), self.assertRaises(lr.LeanRunnerError) as caught:
                lr.source_set_of(bad)
            self.assertEqual(str(caught.exception), "descriptor_choice_not_frozen")

    def test_the_projection_is_digest_checked_and_required_exactly_when_selected(self) -> None:
        payload, projector = synthetic_projector()
        with self.assertRaises(lr.LeanRunnerError) as caught:
            lr.descriptor_projector(payload, expected_sha256="0" * 64)
        self.assertEqual(str(caught.exception), "reid_weights_digest_not_the_frozen_one")
        frame = scenario()[0]
        with self.assertRaises(lr.LeanRunnerError):
            lr.assignment_frame(frame, descriptor=la.SELECTED_DESCRIPTOR, projector=None, entity_geometry_by_id={})
        with self.assertRaises(lr.LeanRunnerError):
            lr.assignment_frame(frame, descriptor=la.FROZEN_DESCRIPTOR_BASELINE, projector=projector, entity_geometry_by_id={})
        selected = lr.assignment_frame(frame, descriptor=la.SELECTED_DESCRIPTOR, projector=projector, entity_geometry_by_id={})
        baseline = lr.assignment_frame(frame, descriptor=la.FROZEN_DESCRIPTOR_BASELINE, projector=None, entity_geometry_by_id={})
        self.assertEqual(len(selected["fragments"][0]["descriptor"]), la.REID_OUTPUT_DIMENSION)
        self.assertAlmostEqual(sum(v * v for v in selected["fragments"][0]["descriptor"]), 1.0, places=5)
        self.assertEqual(baseline["fragments"][0]["descriptor"], frame["fragments"][0]["descriptor_vitb14"])
        self.assertEqual(tuple(selected), la.CACHE_FRAME_FIELDS)


class PolicyAndConfigTests(unittest.TestCase):
    def test_every_policy_value_must_be_given(self) -> None:
        self.assertEqual(lr.validate_policy(POLICY)["entity_geometry_samples_per_axis"], 4)
        for name in lr.POLICY_FIELDS:
            broken = copy.deepcopy(POLICY)
            broken[name] = None
            with self.subTest(name=name), self.assertRaises((lr.LeanRunnerError, lm.LeanMemoryError)) as caught:
                lr.validate_policy(broken)
            self.assertIn("missing" if name != "dedup" else "dedup", str(caught.exception))
        broken = copy.deepcopy(POLICY)
        broken["should_be_visible_min_ratio"] = 0.0
        with self.assertRaises(lr.LeanRunnerError):
            lr.validate_policy(broken)

    def test_arm_configuration_is_explicit_and_only_the_gate_may_be_none(self) -> None:
        for arm, config in CONFIGS.items():
            self.assertEqual(lr.validate_arm_config(arm, config), config, arm)
        with self.assertRaises(lr.LeanRunnerError) as caught:
            lr.validate_arm_config("TAF", {"theta_a": 0.5})
        self.assertEqual(str(caught.exception), "arm_config_missing:TAF")
        with self.assertRaises(lr.LeanRunnerError) as caught:
            lr.validate_arm_config("TAF", {"theta_a": None, "d_a": None})
        self.assertEqual(str(caught.exception), "arm_config_missing:TAF:theta_a")
        with self.assertRaises(lr.LeanRunnerError) as caught:
            lr.validate_arm_config("ELU-P", {k: v for k, v in CONFIGS["ELU-P"].items() if k != "match_gain"})
        self.assertEqual(str(caught.exception), "arm_config_missing:ELU-P")
        with self.assertRaises(lr.LeanRunnerError) as caught:
            lr.validate_arm_config("LLM-op", {})
        self.assertEqual(str(caught.exception), "arm_not_runnable_here:LLM-op")
        self.assertNotIn("LLM-op", lr.RUNNABLE_ARMS)


class FrameStepTests(unittest.TestCase):
    def test_taf_births_binds_goes_dormant_and_reactivates(self) -> None:
        steps, summary = run_all("TAF")
        self.assertEqual([atoms_of(s) for s in steps], [
            {"BIRTH": 2}, {"BIND": 2}, {"BIND": 1, "NOOP": 1}, {"BIND": 1, "NOOP": 1}, {"BIND": 1, "REACTIVATE": 1},
        ])
        # the shared dormancy rule fired on the fourth frame (two consecutive misses)
        self.assertIn("DORMANT", sum(steps[3]["receipt"]["frame_delta"]["changed_entities"].values(), []))
        self.assertEqual(steps[3]["receipt"]["entities_by_state"], {"active": 1, "dormant": 1, "retracted": 0})
        self.assertEqual(steps[4]["receipt"]["entities_by_state"], {"active": 2, "dormant": 0, "retracted": 0})
        self.assertEqual(summary["atoms"], {"NOOP": 2, "BIND": 5, "BIRTH": 2, "RETRACT": 0, "REACTIVATE": 1})
        self.assertEqual(summary["illegal_programs"], 0)
        self.assertEqual(summary["existence_candidates"], 2)
        for step in steps:
            receipt = step["receipt"]
            self.assertEqual(receipt["private_gate"]["stage_a_seal_sha256"], receipt["stage_a_seal_sha256"])
            self.assertEqual(receipt["private_gate"]["stage_b_seal_sha256"], receipt["stage_b_seal_sha256"])
            self.assertTrue(receipt["private_gate"]["private_may_open"])
            self.assertEqual(receipt["memory_digest_after"], step["state"]["memory"]["memory_digest"])
        for earlier, later in zip(steps, steps[1:]):
            self.assertEqual(later["receipt"]["memory_digest_before"], earlier["receipt"]["memory_digest_after"])
        self.assertEqual(summary["cache_frame_seals"], [f["frame_seal"]["payload_sha256"] for f in scenario()])

    def test_elu_p_retracts_after_the_log_odds_fall_and_reactivates_on_return(self) -> None:
        steps, summary = run_all("ELU-P")
        self.assertEqual([atoms_of(s) for s in steps][2:], [{"BIND": 1, "NOOP": 1}, {"BIND": 1, "RETRACT": 1}, {"BIND": 1, "REACTIVATE": 1}])
        entity_a = next(iter(steps[2]["receipt"]["existence"]["decisions"]))
        # bound in frame 2: initial 0.5 + match_gain 1.0 = 1.5; frame 3 unmatched under full free-space
        # coverage: 1.5 - 0.5 - 1.0 = 0.0 (NOOP); frame 4: 0.0 - 1.5 = -1.5 < -1.0 (RETRACT);
        # frame 5 reactivated: -1.5 + 1.0
        self.assertAlmostEqual(steps[1]["state"]["arm_state"]["log_odds"][entity_a], 1.5)
        self.assertAlmostEqual(steps[2]["state"]["arm_state"]["log_odds"][entity_a], 0.0)
        self.assertAlmostEqual(steps[3]["state"]["arm_state"]["log_odds"][entity_a], -1.5)
        self.assertAlmostEqual(steps[4]["state"]["arm_state"]["log_odds"][entity_a], -0.5)
        self.assertEqual(summary["final_entities_by_state"], {"active": 2, "dormant": 0, "retracted": 0})

    def test_rac_retracts_after_two_negative_renders_and_recreates_instead_of_reviving(self) -> None:
        steps, summary = run_all("RAC")
        self.assertEqual([atoms_of(s) for s in steps][2:], [{"BIND": 1, "NOOP": 1}, {"BIND": 1, "RETRACT": 1}, {"BIND": 1, "BIRTH": 1}])
        self.assertEqual(steps[4]["receipt"]["existence"]["excluded_retracted"], [next(iter(steps[2]["receipt"]["existence"]["decisions"]))])
        self.assertEqual(summary["final_entities_by_state"], {"active": 2, "dormant": 0, "retracted": 1})

    def test_low_and_hand_cost_run_and_assoc_only_never_judges_existence(self) -> None:
        low_steps, low_summary = run_all("LOW")
        self.assertEqual(low_summary["atoms"]["BIRTH"], 2)
        self.assertEqual(low_summary["atoms"]["RETRACT"], 0)
        hand_steps, hand_summary = run_all("HandCost")
        self.assertEqual([atoms_of(s) for s in hand_steps][2:4], [{"BIND": 1, "RETRACT": 1}, {"BIND": 1}])
        assoc_steps, assoc_summary = run_all("AssocOnly", scorer=CosineScorer())
        self.assertEqual([atoms_of(s) for s in assoc_steps], [{"BIRTH": 2}, {"BIND": 2}, {"BIND": 1}, {"BIND": 1}, {"BIND": 2}])
        self.assertEqual(assoc_summary["existence_candidates"], 0)
        self.assertEqual(assoc_summary["final_entities_by_state"], {"active": 2, "dormant": 0, "retracted": 0})
        for step in assoc_steps:
            self.assertEqual(step["receipt"]["existence"]["decisions"], {})

    def test_learned_arms_take_a_scorer_and_no_version_deletes_retracted(self) -> None:
        payload, projector = synthetic_projector()
        with self.assertRaises(lr.LeanRunnerError) as caught:
            run_all("VSMT-lean", descriptor=la.SELECTED_DESCRIPTOR, projector=projector)
        self.assertEqual(str(caught.exception), "scorer_missing_for_learned_arm:VSMT-lean")
        steps, summary = run_all("VSMT-lean", descriptor=la.SELECTED_DESCRIPTOR, projector=projector, scorer=CosineScorer())
        self.assertEqual([atoms_of(s) for s in steps][2:], [{"BIND": 1, "RETRACT": 1}, {"BIND": 1}, {"BIND": 1, "REACTIVATE": 1}])
        self.assertEqual(len(steps[0]["state"]["memory"]["entities"][0]["descriptor_mean"]), la.REID_OUTPUT_DIMENSION)
        self.assertEqual(steps[0]["receipt"]["descriptor"], la.SELECTED_DESCRIPTOR)
        nv_steps, nv_summary = run_all("NoVersion", descriptor=la.SELECTED_DESCRIPTOR, projector=projector, scorer=CosineScorer())
        self.assertEqual([atoms_of(s) for s in nv_steps][2:], [{"BIND": 1, "RETRACT": 1}, {"BIND": 1}, {"BIND": 1, "BIRTH": 1}])
        self.assertEqual(len(nv_steps[2]["receipt"]["no_version_deleted"]), 1)
        self.assertEqual(nv_steps[2]["receipt"]["entities_by_state"], {"active": 1, "dormant": 0, "retracted": 0})
        self.assertEqual(nv_summary["no_version_deleted"], 1)
        # a scorer whose keys do not match the sealed rows is refused
        class Sloppy(CosineScorer):
            def association_and_birth_logits(self, stage_a):
                out = super().association_and_birth_logits(stage_a)
                out["birth_logits"]["region:zzz"] = 0.0
                return out
        with self.assertRaises(lr.LeanRunnerError) as caught:
            run_all("VSMT-lean", descriptor=la.SELECTED_DESCRIPTOR, projector=projector, scorer=Sloppy())
        self.assertEqual(str(caught.exception), "scorer_birth_logits_do_not_match_the_sealed_rows")

    def test_an_illegal_program_rolls_back_commits_an_empty_program_and_is_counted(self) -> None:
        real = lm.apply_program
        calls = {"n": 0}

        def flaky(memory, program, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2 and program["operations"]:  # the second frame's real program
                raise lm.LeanMemoryError("forced_illegal_program")
            return real(memory, program, **kwargs)

        with mock.patch.object(lr.lm, "apply_program", side_effect=flaky):
            steps, summary = run_all("TAF")
        second = steps[1]["receipt"]
        self.assertEqual(second["illegal_program"]["code"], "forced_illegal_program")
        self.assertEqual(second["illegal_program"]["atoms_attempted"]["BIND"], 2)
        self.assertEqual(second["program"]["operations"], [])
        self.assertEqual(steps[1]["state"]["memory"]["tick"], 2)  # the tick still advanced
        self.assertEqual(summary["illegal_programs"], 1)
        self.assertEqual(summary["frames"], 5)
        # the episode went on: the third frame's program was applied against the advanced memory
        self.assertEqual(steps[2]["state"]["memory"]["tick"], 3)
        self.assertEqual(len(steps[2]["state"]["memory"]["transaction_log"][1]["operations"]), 0)

    def test_an_illegal_program_also_rolls_back_the_arm_state(self) -> None:
        # S2 review (2026-09-24): the whole frame rolls back, the arm's temporal state included
        real = lm.apply_program
        calls = {"n": 0}

        def flaky(memory, program, **kwargs):
            calls["n"] += 1
            if calls["n"] == 3 and program["operations"]:  # the third frame's real program: RAC's first negative render
                raise lm.LeanMemoryError("forced_illegal_program")
            return real(memory, program, **kwargs)

        with mock.patch.object(lr.lm, "apply_program", side_effect=flaky):
            steps, summary = run_all("RAC")
        third = steps[2]["receipt"]
        self.assertEqual(third["illegal_program"]["code"], "forced_illegal_program")
        self.assertTrue(third["illegal_program"]["arm_state_rolled_back"])
        # the counter RAC advanced for the rolled-back frame is back at the frame-2 state
        self.assertEqual(steps[2]["state"]["arm_state"], steps[1]["state"]["arm_state"])
        self.assertEqual(third["arm_state_sha256"], steps[1]["receipt"]["arm_state_sha256"])
        # so the fourth frame is the FIRST negative render (NOOP), not the second (RETRACT)
        self.assertEqual([atoms_of(s) for s in steps][2:], [{}, {"BIND": 1, "NOOP": 1}, {"BIND": 2}])
        self.assertEqual(summary["atoms"]["RETRACT"], 0)
        self.assertEqual(summary["illegal_programs"], 1)

    def test_two_runs_are_byte_identical_and_the_cache_gate_holds_across_arms(self) -> None:
        first, first_summary = run_all("TAF")
        second, second_summary = run_all("TAF")
        self.assertEqual([s["receipt"] for s in first], [s["receipt"] for s in second])
        self.assertEqual(first_summary, second_summary)
        _, low = run_all("LOW")
        _, elu = run_all("ELU-P")
        gate = lr.assert_identical_cache_across_arms([first_summary, low, elu])
        self.assertEqual(gate["arms"], ["TAF", "LOW", "ELU-P"])
        self.assertEqual(gate["frames"], 5)
        tampered = copy.deepcopy(low)
        tampered["cache_frame_seals"][2] = "0" * 64
        with self.assertRaises(lr.LeanRunnerError) as caught:
            lr.assert_identical_cache_across_arms([first_summary, tampered])
        self.assertEqual(str(caught.exception), "cache_gate_arm_read_different_cache:LOW")

    def test_a_frame_out_of_order_or_from_another_arm_is_refused(self) -> None:
        frames = scenario()
        state = lr.initial_state(episode_id="ep-0001", arm="TAF")
        with self.assertRaises(lr.LeanRunnerError) as caught:
            lr.run_frame(state, frames[1], arm="TAF", config=CONFIGS["TAF"], policy=POLICY, descriptor="vitb14")
        self.assertEqual(str(caught.exception), "frame_tick_not_next")
        with self.assertRaises(lr.LeanRunnerError) as caught:
            lr.run_frame(state, frames[0], arm="LOW", config=CONFIGS["LOW"], policy=POLICY, descriptor="vitb14")
        self.assertEqual(str(caught.exception), "state_belongs_to_another_arm")


class TruthTableBuilderTests(unittest.TestCase):
    def record(self, index: int, visibility: dict[str, int]) -> dict[str, Any]:
        return {"observation_index": index, "object_visibility": dict(visibility),
                "object_id_to_entity_id": {k: n for n, k in enumerate(sorted(visibility), start=1)}}

    def test_scope_follows_observability_and_type_and_structure_carries_no_box(self) -> None:
        builder = lr.TruthTableBuilder()
        tracker = {"Mug|1": {"present": True, "aabb_min_m": [0.0, 0.0, 1.9], "aabb_max_m": [0.2, 0.2, 2.1], "centroid_m": [0.1, 0.1, 2.0]}}
        first = builder.update(self.record(0, {"Mug|1": 50, "wall|3": 5000}), tracker)
        self.assertEqual(first["Mug|1"]["in_scope"], False)  # below 196 pixels so far
        self.assertEqual(first["wall|3"], {"present": True, "in_scope": False})
        second = builder.update(self.record(1, {"Mug|1": 300, "wall|3": 5000}), tracker)
        self.assertEqual(second["Mug|1"]["in_scope"], True)
        third = builder.update(self.record(2, {"wall|3": 5000}), tracker)
        self.assertEqual(third["Mug|1"]["in_scope"], True)  # once observable, stays observable
        self.assertEqual(third["Mug|1"]["aabb_min_m"], [0.0, 0.0, 1.9])
        gone = builder.update(self.record(3, {"wall|3": 5000}), {"Mug|1": {"present": False}})
        self.assertEqual(gone["Mug|1"], {"present": False, "in_scope": True})

    def test_unknown_non_structural_keys_and_boxless_in_scope_objects_are_refused(self) -> None:
        builder = lr.TruthTableBuilder()
        with self.assertRaises(lr.LeanRunnerError) as caught:
            builder.update(self.record(0, {"Ceiling|1": 500}), {})
        self.assertEqual(str(caught.exception), "truth_key_outside_geometry_table:Ceiling|1")
        # ruling 69: a ceiling is structure, a physics-spawned key is present, out of scope and counted
        builder = lr.TruthTableBuilder()
        table = builder.update(self.record(0, {"Ceiling_room|2|0": 900, "Egg|surface|2|3|EggCracked_0": 300}), {})
        self.assertEqual(table["Ceiling_room|2|0"], {"present": True, "in_scope": False})
        self.assertEqual(table["Egg|surface|2|3|EggCracked_0"], {"present": True, "in_scope": False})
        self.assertEqual(builder.spawned_keys, {"Egg|surface|2|3|EggCracked_0"})
        builder = lr.TruthTableBuilder()
        with self.assertRaises(lr.LeanRunnerError) as caught:
            builder.update(self.record(0, {"Mug|1": 500}), {"Mug|1": {"present": True, "aabb_min_m": None, "aabb_max_m": None, "centroid_m": [0.0, 0.0, 0.0]}})
        self.assertEqual(str(caught.exception), "truth_object_without_box:Mug|1")

    def test_the_table_is_accepted_by_the_s0_04_evaluator(self) -> None:
        steps, _ = run_all("TAF")
        memory = steps[1]["state"]["memory"]
        mug = next(e for e in memory["entities"] if e["evidence"][0]["fragment_id"] == "region:a")
        evidence = {f"{item['frame_digest']}|{item['fragment_id']}": ("Mug|1" if item["fragment_id"] == "region:a" else "wall|3")
                    for entity in memory["entities"] for item in entity["evidence"]}
        tracker = {"Mug|1": {"present": True, "aabb_min_m": mug["aabb_min_m"], "aabb_max_m": mug["aabb_max_m"], "centroid_m": mug["centroid_m"]}}
        builder = lr.TruthTableBuilder()
        builder.update(self.record(0, {"Mug|1": 400, "wall|3": 5000}), tracker)
        table = builder.update(self.record(1, {"Mug|1": 400, "wall|3": 5000}), tracker)
        result = lt.evaluate_frame(memory, truth_objects=table, evidence_instance=evidence, iou_min=0.3, delta_moved_m=0.5)
        self.assertEqual(result["node_f1"], 1.0)
        self.assertEqual(len(result["out_of_scope_entities"]), 1)  # the entity that resolves to the wall
        self.assertEqual(result["truth"], 1)


class MachineContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_the_contract_binds_the_implementation(self) -> None:
        checked = lr.validate_runner_contract(self.contract)
        self.assertEqual(checked["stage_id"], "S2-01")
        self.assertEqual(checked["descriptor"]["selected"], la.SELECTED_DESCRIPTOR)
        self.assertEqual(checked["entity_geometry"]["samples_per_axis"], 4)  # D-224-S1 ruling 60 (2026-09-24)
        self.assertEqual(checked["entity_geometry"]["samples_per_axis"], lr.ENTITY_GEOMETRY_SAMPLES_PER_AXIS)
        self.assertNotIn("entity_geometry.samples_per_axis", checked["policy_values_without_defaults"])
        self.assertEqual(checked["registered_value_slots"], ["entity_geometry.samples_per_axis"])
        # both bits opened on 2026-09-24 (rulings 64/67, the S2-05 review) and named by the activation policy
        self.assertTrue(all(checked["authorization"].values()))
        self.assertEqual(sorted(checked["activation_policy"]["active_true_authorizations"]), sorted(checked["authorization"]))
        self.assertEqual(tuple(checked["frame_step"]["order"]), lr.FRAME_STEP_ORDER)
        for key, path in checked["depends_on"].items():
            if key.endswith("_contract"):
                self.assertTrue((PROJECT_ROOT / path).is_file(), path)

    def test_weakened_claims_and_unfrozen_values_are_refused(self) -> None:
        for edit, code in (
            (lambda c: c["entity_geometry"].__setitem__("rule", "another"), "contract_entity_geometry_rule_mismatch"),
            (lambda c: c["entity_geometry"].__setitem__("identical_bytes_for_all_arms", False), "contract_entity_geometry_claim_weakened:identical_bytes_for_all_arms"),
            (lambda c: c["frame_step"].__setitem__("no_private_file_is_read_in_the_public_phase", False), "contract_frame_step_claim_weakened:no_private_file_is_read_in_the_public_phase"),
            (lambda c: c["frame_step"]["order"].reverse(), "contract_frame_step_order_mismatch"),
            (lambda c: c["truth_table"].__setitem__("observable_min_pixels", 100), "contract_truth_pixels_mismatch"),
            (lambda c: c["descriptor"].__setitem__("selected", "vits14"), "contract_descriptor_selected_mismatch"),
            (lambda c: c.pop("activation_policy"), "contract_bit_opened_without_a_ruling:episode_run"),
            (lambda c: c["entity_geometry"].__setitem__("samples_per_axis", None), "contract_samples_per_axis_null_but_not_registered_as_open"),
            (lambda c: c["frame_step"]["arm_state"].__setitem__("arm_state_rolled_back_with_the_frame_on_an_illegal_program", False),
             "contract_frame_step_claim_weakened:arm_state_rolled_back_with_the_frame_on_an_illegal_program"),
        ):
            broken = copy.deepcopy(self.contract)
            edit(broken)
            with self.subTest(code=code), self.assertRaises(lr.LeanRunnerError) as caught:
                lr.validate_runner_contract(broken)
            self.assertEqual(str(caught.exception), code)
        # a value differing from the bound constant is refused as well
        broken = copy.deepcopy(self.contract)
        broken["entity_geometry"]["samples_per_axis"] = 8
        with self.assertRaises(lr.LeanRunnerError) as caught:
            lr.validate_runner_contract(broken)
        self.assertEqual(str(caught.exception), "contract_samples_per_axis_differs_from_the_frozen_constant")

    def test_a_bit_opens_only_through_an_activation_policy_that_names_a_ruling(self) -> None:
        # D-224-S1 ruling 61: the S1-03 / S1-04 mechanism, exercised from a closed copy
        closed = copy.deepcopy(self.contract)
        closed["authorization"] = {name: False for name in closed["authorization"]}
        closed.pop("activation_policy", None)
        lr.validate_runner_contract(closed)
        opened = copy.deepcopy(closed)
        opened["authorization"]["episode_run"] = True
        opened["activation_policy"] = {"opened_by": "D-224-S1 ruling <n>", "opened_on": "2026-09-30",
                                       "active_true_authorizations": ["episode_run"]}
        self.assertTrue(lr.validate_runner_contract(opened)["authorization"]["episode_run"])
        opened["authorization"]["server_run"] = True  # opened but not named by the policy
        with self.assertRaises(lr.LeanRunnerError) as caught:
            lr.validate_runner_contract(opened)
        self.assertEqual(str(caught.exception), "contract_bit_opened_without_a_ruling:server_run")
        nameless = copy.deepcopy(closed)
        nameless["activation_policy"] = {"opened_by": "", "active_true_authorizations": []}
        with self.assertRaises(lr.LeanRunnerError) as caught:
            lr.validate_runner_contract(nameless)
        self.assertEqual(str(caught.exception), "contract_activation_policy_names_no_ruling")
        broken = copy.deepcopy(self.contract)
        broken["authorization"]["episode_run"] = "yes"
        with self.assertRaises(lr.LeanRunnerError) as caught:
            lr.validate_runner_contract(broken)
        self.assertEqual(str(caught.exception), "contract_authorization_not_boolean:episode_run")


if __name__ == "__main__":
    unittest.main()
