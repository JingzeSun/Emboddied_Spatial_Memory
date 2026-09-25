"""D-224 / S1-03: the shared frozen frontend cache.

What is pinned here: the D-215 proposal boundary (196 px, 64 per frame, overflow and duplicates
fail the episode rather than truncate), the bounding box this stage adds on top of the frozen
D-223 record, the two descriptor sets, the frame and episode seals, and the projection into the
frame shape S0-03 validates.  No simulator and no model are started.

The bounding-box test is the load-bearing one: the frozen region record carries the point-cloud
mean and the box size, which cannot be combined into a box, so this stage recomputes the box from
the same world points.  The test pins ``aabb_max - aabb_min`` against the frozen ``extent_m`` so a
change in the upstream backprojection fails loudly instead of yielding a quietly wrong box.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
import unittest

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt import lean_assignment  # noqa: E402
from vsmt import lean_frontend_cache as fc  # noqa: E402
from vsmt.l1_entities import backproject_public_entity_geometry  # noqa: E402
from vsmt.shared_frontend_core import AnonymousMask, PublicGeometryConfig  # noqa: E402

CONTRACT_PATH = PROJECT_ROOT / "configs" / "vsmt" / "lean_s1_03_frontend_cache_v1.json"
#: The frozen D-223 fragment geometry, used as-is so the tests exercise the real thresholds.
GEOMETRY = PublicGeometryConfig(
    depth_convention="ai2thor_linear01_camera_axis_z_m",
    minimum_depth_m=0.05, maximum_depth_m=20.0,
    absolute_minimum_valid_depth_points=32, minimum_valid_depth_fraction=0.25,
)
CALIBRATION = {"fx": 112.0, "fy": 112.0, "cx": 111.5, "cy": 111.5}
POSE = {"position_m": [0.25, 1.5, -0.75], "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0]}
SIZE = 48


def mask_of(array: np.ndarray, region_id: str = "region:0000") -> AnonymousMask:
    binary = np.ascontiguousarray(array.astype(np.uint8))
    payload = [int(binary.shape[0]), int(binary.shape[1]), *binary.reshape(-1).tolist()]
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return AnonymousMask(
        region_id=region_id, mask_sha256=digest, height=int(binary.shape[0]),
        width=int(binary.shape[1]), row_major_values=tuple(int(v) for v in binary.reshape(-1)),
        visible_pixel_count=int(binary.sum()),
        touches_border=bool(binary[0].any() or binary[-1].any() or binary[:, 0].any() or binary[:, -1].any()),
    )


def block(top: int, left: int, side: int = 16, size: int = SIZE) -> AnonymousMask:
    array = np.zeros((size, size), dtype=np.uint8)
    array[top:top + side, left:left + side] = 1
    return mask_of(array, f"region:{top:02d}{left:02d}")


def depth_field(seed: int = 0, size: int = SIZE) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return (1.0 + rng.random((size, size)) * 2.0).astype(np.float32)


def unit(dimension: int, seed: int = 0) -> list[float]:
    rng = np.random.default_rng(seed)
    values = rng.normal(size=dimension)
    return [float(v) for v in values / np.linalg.norm(values)]


def descriptors(seed: int = 0) -> dict[str, list[float]]:
    return {"vits14": unit(384, seed), "vitb14": unit(768, seed + 1)}


def halfspaces() -> list[dict]:
    """Six world half-spaces, the shape the frozen materialiser writes."""
    return [{"normal": [1.0, 0.0, 0.0], "offset_m": float(index)} for index in range(6)]


def free_space_record(ordinal: int = 0, time_s: float = 0.0) -> dict:
    return {"free_space_id": f"free-space:{ordinal:04d}", "time_s": time_s,
            "halfspaces_world": halfspaces(), "reliability": 1.0, "support_sha256": "d" * 64}


def visibility_record(ordinal: int = 0, time_s: float = 0.0) -> dict:
    return {"visibility_id": f"visibility:{ordinal:04d}", "time_s": time_s,
            "halfspaces_world": halfspaces(), "reliability": 1.0, "support_sha256": "e" * 64}


def surface_record(ordinal: int = 0) -> dict:
    return {"surface_id": f"surface:{ordinal:04d}", "centroid_m": [0.0, 0.5, 1.0],
            "extent_m": [1.0, 0.0, 1.0], "plane_normal": [0.0, 1.0, 0.0],
            "plane_offset_m": 0.5, "mask_sha256": "f" * 64}


class TestProposalBoundary(unittest.TestCase):
    """D-215: 196 px minimum, 64 per frame, and overflow is a failure, never a truncation."""

    def test_small_masks_are_not_proposals_and_do_not_count_towards_the_cap(self) -> None:
        big = block(4, 4, side=16)                      # 256 px
        small = block(30, 30, side=13)                  # 169 px, below 196
        kept = fc.admit_proposals([big, small])
        self.assertEqual([m.mask_sha256 for m in kept], [big.mask_sha256])

    def test_the_cap_fails_the_episode_and_names_the_count(self) -> None:
        masks = [block(0, 0, side=16)]
        masks = [mask_of(np.pad(np.ones((16, 16), np.uint8), ((i % 32, SIZE - 16 - i % 32),
                                                              (i // 32, SIZE - 16 - i // 32))))
                 for i in range(65)]
        with self.assertRaises(fc.LeanFrontendCacheError) as ctx:
            fc.admit_proposals(masks)
        self.assertEqual(ctx.exception.reason, "proposal_overflow")
        self.assertIn("65", str(ctx.exception))

    def test_exactly_the_cap_is_admitted(self) -> None:
        masks = [mask_of(np.pad(np.ones((16, 16), np.uint8), ((i % 32, SIZE - 16 - i % 32),
                                                              (i // 32, SIZE - 16 - i // 32))))
                 for i in range(64)]
        self.assertEqual(len(fc.admit_proposals(masks)), 64)

    def test_a_duplicate_mask_fails_rather_than_being_deduplicated(self) -> None:
        one = block(4, 4)
        with self.assertRaises(fc.LeanFrontendCacheError) as ctx:
            fc.admit_proposals([one, block(4, 4)])
        self.assertEqual(ctx.exception.reason, "duplicate_proposal_mask")

    def test_admission_order_is_the_mask_digest_and_is_deterministic(self) -> None:
        masks = [block(4, 4), block(20, 4), block(4, 20)]
        first = [m.mask_sha256 for m in fc.admit_proposals(masks)]
        second = [m.mask_sha256 for m in fc.admit_proposals(list(reversed(masks)))]
        self.assertEqual(first, second)
        self.assertEqual(first, sorted(first))

    def test_every_failure_reason_is_registered(self) -> None:
        with self.assertRaises(ValueError):
            fc.LeanFrontendCacheError("some_other_reason")


class TestBoundingBox(unittest.TestCase):
    """The box this stage adds must agree with the frozen extent it cannot be derived from."""

    def test_the_box_size_equals_the_frozen_extent_on_many_shapes(self) -> None:
        depth = depth_field(3)
        for index, (top, left, side) in enumerate(
                [(2, 2, 16), (10, 20, 20), (30, 5, 14), (0, 0, 48), (18, 18, 8)]):
            with self.subTest(shape=index):
                mask = block(top, left, side=side).as_array()
                lower, upper = fc.fragment_aabb(mask, depth, CALIBRATION, POSE, GEOMETRY)
                frozen = backproject_public_entity_geometry(mask, depth, CALIBRATION, POSE, GEOMETRY)
                for axis in range(3):
                    self.assertAlmostEqual(upper[axis] - lower[axis], frozen.extent_m[axis], places=12)

    def test_the_point_cloud_mean_is_inside_the_box_but_is_not_its_centre(self) -> None:
        depth = depth_field(5)
        mask = block(6, 9, side=18).as_array()
        lower, upper = fc.fragment_aabb(mask, depth, CALIBRATION, POSE, GEOMETRY)
        frozen = backproject_public_entity_geometry(mask, depth, CALIBRATION, POSE, GEOMETRY)
        offsets = []
        for axis in range(3):
            self.assertLessEqual(lower[axis], frozen.centroid_m[axis])
            self.assertGreaterEqual(upper[axis], frozen.centroid_m[axis])
            offsets.append(abs(frozen.centroid_m[axis] - (lower[axis] + upper[axis]) / 2.0))
        # the whole reason the box is recomputed: centroid +- extent/2 would be a different box
        self.assertGreater(max(offsets), 1e-6)

    def test_a_fragment_with_no_valid_depth_fails_with_the_registered_reason(self) -> None:
        depth = np.full((SIZE, SIZE), np.nan, dtype=np.float32)
        with self.assertRaises(fc.LeanFrontendCacheError) as ctx:
            fc.fragment_aabb(block(4, 4).as_array(), depth, CALIBRATION, POSE, GEOMETRY)
        self.assertEqual(ctx.exception.reason, "fragment_depth_support_insufficient")

    def test_the_box_is_invariant_to_pixel_order(self) -> None:
        depth = depth_field(7)
        mask = block(11, 13, side=12).as_array()
        lower, upper = fc.fragment_aabb(mask, depth, CALIBRATION, POSE, GEOMETRY)
        again = fc.fragment_aabb(np.array(mask), depth.copy(), dict(CALIBRATION), dict(POSE), GEOMETRY)
        self.assertEqual((lower, upper), again)


class TestFragmentRecord(unittest.TestCase):
    def fragment(self, ordinal: int = 0, seed: int = 0) -> dict:
        return fc.build_fragment(
            ordinal=ordinal, mask=block(6, 6, side=18), depth_m=depth_field(seed),
            calibration=CALIBRATION, pose=POSE, geometry_config=GEOMETRY,
            descriptors=descriptors(seed))

    def test_the_field_order_is_the_contract_order(self) -> None:
        self.assertEqual(tuple(self.fragment()), fc.FRAGMENT_FIELDS)

    def test_both_descriptor_sets_are_stored_at_their_registered_dimensions(self) -> None:
        row = self.fragment()
        self.assertEqual(len(row["descriptor_vits14"]), 384)
        self.assertEqual(len(row["descriptor_vitb14"]), 768)

    def test_a_descriptor_that_is_not_unit_norm_is_refused(self) -> None:
        with self.assertRaises(fc.LeanFrontendCacheError) as ctx:
            fc.build_fragment(ordinal=0, mask=block(6, 6, side=18), depth_m=depth_field(),
                              calibration=CALIBRATION, pose=POSE, geometry_config=GEOMETRY,
                              descriptors={"vits14": [0.5] * 384, "vitb14": unit(768)})
        self.assertEqual(ctx.exception.reason, "descriptor_not_unit_norm")

    def test_a_missing_descriptor_set_is_refused(self) -> None:
        with self.assertRaises(fc.LeanFrontendCacheError):
            fc.build_fragment(ordinal=0, mask=block(6, 6, side=18), depth_m=depth_field(),
                              calibration=CALIBRATION, pose=POSE, geometry_config=GEOMETRY,
                              descriptors={"vits14": unit(384)})

    def test_supported_by_is_null_until_the_thresholds_are_frozen(self) -> None:
        self.assertIsNone(self.fragment()["supported_by"])
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        slots = contract["supported_by_rule"]["value_slots"]
        self.assertTrue(all(value is None for value in slots.values()))
        for name in slots:
            self.assertIn(f"supported_by_rule.value_slots.{name}",
                          contract["policy_values_without_defaults"])

    def test_the_fragment_id_is_packet_local(self) -> None:
        self.assertEqual(self.fragment(ordinal=7)["fragment_id"], "fragment:0007")


class TestFrameAndSeal(unittest.TestCase):
    def frame(self, tick: int = 1, count: int = 2, seed: int = 0) -> dict:
        fragments = [fc.build_fragment(ordinal=i, mask=block(4 + 18 * i, 6, side=16),
                                       depth_m=depth_field(seed), calibration=CALIBRATION,
                                       pose=POSE, geometry_config=GEOMETRY,
                                       descriptors=descriptors(seed + i))
                     for i in range(count)]
        return fc.build_frame(
            tick=tick, frame_digest="a" * 64, camera_position_m=[0.0, 1.5, 0.0],
            camera_forward=[0.0, 0.0, 1.0], fragments=fragments, surfaces=[],
            free_space=[free_space_record()], visibility=[visibility_record()],
            frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256,
            descriptor_asset_sha256s={"vits14": "b" * 64, "vitb14": "c" * 64})

    def test_the_frame_carries_exactly_the_contract_fields_in_order(self) -> None:
        self.assertEqual(tuple(self.frame()), fc.CACHE_FRAME_FIELDS)

    def test_entity_geometry_is_not_a_cache_field(self) -> None:
        self.assertNotIn("entity_geometry", self.frame())

    def test_the_seal_changes_with_any_public_content(self) -> None:
        base = self.frame()["frame_seal"]["payload_sha256"]
        self.assertEqual(base, self.frame()["frame_seal"]["payload_sha256"])
        self.assertNotEqual(base, self.frame(tick=2)["frame_seal"]["payload_sha256"])
        self.assertNotEqual(base, self.frame(count=1)["frame_seal"]["payload_sha256"])
        self.assertNotEqual(base, self.frame(seed=4)["frame_seal"]["payload_sha256"])

    def test_a_forbidden_key_fails_the_frame(self) -> None:
        with self.assertRaises(fc.LeanFrontendCacheError) as ctx:
            fc.build_frame(tick=1, frame_digest="a" * 64, camera_position_m=[0.0, 0.0, 0.0],
                           camera_forward=[0.0, 0.0, 1.0], fragments=[], surfaces=[],
                           free_space=[{**free_space_record(), "house_id": "x"}], visibility=[],
                           frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256,
                           descriptor_asset_sha256s={})
        self.assertEqual(ctx.exception.reason, "forbidden_key_in_cache")

    def test_a_non_unit_camera_forward_is_refused(self) -> None:
        with self.assertRaises(fc.LeanFrontendCacheError):
            fc.build_frame(tick=1, frame_digest="a" * 64, camera_position_m=[0.0, 0.0, 0.0],
                           camera_forward=[0.0, 0.0, 2.0], fragments=[], surfaces=[],
                           free_space=[], visibility=[],
                           frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256,
                           descriptor_asset_sha256s={})

    def test_the_episode_seal_covers_every_frame_and_requires_consecutive_ticks(self) -> None:
        frames = [self.frame(tick=1), self.frame(tick=2)]
        sealed = fc.seal_episode(frames, frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256)
        self.assertEqual(sealed["episode_frame_count"], 2)
        self.assertEqual(sealed, fc.seal_episode(frames, frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256))
        self.assertNotEqual(
            sealed["payload_sha256"],
            fc.seal_episode(frames[:1], frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256)["payload_sha256"])
        with self.assertRaises(fc.LeanFrontendCacheError):
            fc.seal_episode([self.frame(tick=1), self.frame(tick=3)],
                            frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256)

    def test_a_consumer_recomputes_the_frame_seal_from_the_bytes_it_loaded(self) -> None:
        assets = {"vits14": "b" * 64, "vitb14": "c" * 64}
        loaded = json.loads(json.dumps(self.frame()))  # the JSON round trip a cache file goes through
        fc.verify_frame_seal(loaded, frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256, descriptor_asset_sha256s=assets)
        # a descriptor changed while the stored seal string stays: refused
        tampered = json.loads(json.dumps(loaded))
        tampered["fragments"][0]["descriptor_vits14"] = unit(384, seed=99)
        with self.assertRaises(fc.LeanFrontendCacheError) as ctx:
            fc.verify_frame_seal(tampered, frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256, descriptor_asset_sha256s=assets)
        self.assertIn("frame_seal_mismatch", ctx.exception.detail)
        # a mask digest changed, a box changed, a volume changed: each refused
        for mutate in (lambda f: f["fragments"][1].__setitem__("mask_sha256", "9" * 64),
                       lambda f: f["fragments"][0].__setitem__("aabb_max_m", [9.0, 9.0, 9.0]),
                       lambda f: f["free_space"][0].__setitem__("reliability", 0.5)):
            copy = json.loads(json.dumps(loaded))
            mutate(copy)
            with self.assertRaises(fc.LeanFrontendCacheError):
                fc.verify_frame_seal(copy, frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256, descriptor_asset_sha256s=assets)
        # the seal binds the frontend identity too: other asset digests or another config are refused
        with self.assertRaises(fc.LeanFrontendCacheError):
            fc.verify_frame_seal(loaded, frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256,
                                 descriptor_asset_sha256s={"vits14": "b" * 64, "vitb14": "d" * 64})
        with self.assertRaises(fc.LeanFrontendCacheError):
            fc.verify_frame_seal(loaded, frontend_config_sha256="0" * 64, descriptor_asset_sha256s=assets)

    def test_the_fast_mask_digest_is_the_anonymous_mask_digest(self) -> None:
        rng = np.random.default_rng(3)
        for shape in ((1, 1), (3, 5), (17, 31), (64, 64)):
            binary = rng.random(shape) > 0.5
            payload = [int(shape[0]), int(shape[1]), *binary.astype(np.uint8).reshape(-1).tolist()]
            self.assertEqual(fc.mask_sha256_of(binary), fc.sha(payload), shape)
        all_zero = np.zeros((8, 8), dtype=bool)
        self.assertEqual(fc.mask_sha256_of(all_zero), fc.sha([8, 8, *([0] * 64)]))
        self.assertEqual(fc.mask_sha256_of(mask_of(np.ones((16, 16), dtype=np.uint8), "region:x").as_array()),
                         mask_of(np.ones((16, 16), dtype=np.uint8), "region:x").mask_sha256)
        with self.assertRaises(fc.LeanFrontendCacheError):
            fc.mask_sha256_of(np.zeros((2, 2, 2), dtype=bool))


class TestVolumesAndSurfaces(unittest.TestCase):
    """The cache keeps the frozen volumes as written, and keeps only a surface's geometry."""

    def test_a_surface_keeps_its_geometry_and_loses_its_descriptor(self) -> None:
        frozen = {"region_id": "region:0007", "structure_kind": "surface", "mask_sha256": "f" * 64,
                  "descriptor": [0.0] * 384, "centroid_m": [0.0, 0.5, 1.0], "extent_m": [1.0, 0.0, 1.0],
                  "reliability": 1.0, "proposal_source_id": "x", "plane_normal": [0.0, 1.0, 0.0],
                  "plane_offset_m": 0.5}
        projected = fc.project_surface(frozen, ordinal=7)
        self.assertEqual(tuple(projected), fc.SURFACE_FIELDS)
        self.assertNotIn("descriptor", projected)
        self.assertEqual(projected["surface_id"], "surface:0007")

    def test_a_volume_that_is_not_fully_reliable_fails_the_frame(self) -> None:
        with self.assertRaises(fc.LeanFrontendCacheError) as ctx:
            fc.check_volume_records([{**free_space_record(), "reliability": 0.8}],
                                    fields=fc.FREE_SPACE_FIELDS, label="free_space")
        self.assertIn("reliability_not_one", str(ctx.exception))

    def test_a_volume_without_six_halfspaces_fails_the_frame(self) -> None:
        broken = {**free_space_record(), "halfspaces_world": halfspaces()[:5]}
        with self.assertRaises(fc.LeanFrontendCacheError):
            fc.check_volume_records([broken], fields=fc.FREE_SPACE_FIELDS, label="free_space")

    def test_the_seal_covers_the_volumes(self) -> None:
        def frame(free):
            return fc.build_frame(
                tick=1, frame_digest="a" * 64, camera_position_m=[0.0, 0.0, 0.0],
                camera_forward=[0.0, 0.0, 1.0], fragments=[], surfaces=[], free_space=free,
                visibility=[visibility_record()],
                frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256, descriptor_asset_sha256s={})
        one = frame([free_space_record()])["frame_seal"]["payload_sha256"]
        two = frame([free_space_record(), free_space_record(1)])["frame_seal"]["payload_sha256"]
        self.assertNotEqual(one, two)


class TestAssignmentView(unittest.TestCase):
    """The projection must be exactly what S0-03's own validator accepts."""

    def frame(self, seed: int = 0) -> dict:
        fragments = [fc.build_fragment(ordinal=i, mask=block(4 + 18 * i, 6, side=16),
                                       depth_m=depth_field(seed), calibration=CALIBRATION,
                                       pose=POSE, geometry_config=GEOMETRY,
                                       descriptors=descriptors(seed + i))
                     for i in range(2)]
        return fc.build_frame(
            tick=1, frame_digest="a" * 64, camera_position_m=[0.0, 1.5, 0.0],
            camera_forward=[0.0, 0.0, 1.0], fragments=fragments, surfaces=[surface_record()],
            free_space=[free_space_record()], visibility=[visibility_record()],
            frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256, descriptor_asset_sha256s={})

    def test_the_view_passes_the_s0_03_validator(self) -> None:
        for name, dimension in fc.DESCRIPTOR_DIMENSIONS.items():
            with self.subTest(descriptor_set=name):
                view = fc.assignment_view(self.frame(), descriptor_set=name)
                checked = lean_assignment.validate_cache_frame(view)
                self.assertEqual(len(checked["fragments"][0]["descriptor"]), dimension)

    def test_the_view_drops_the_mask_digest_the_other_descriptor_and_the_volumes(self) -> None:
        view = fc.assignment_view(self.frame(), descriptor_set="vits14")
        self.assertEqual(tuple(view), fc.VIEW_FRAME_FIELDS)
        self.assertEqual(tuple(view["fragments"][0]), fc.VIEW_FRAGMENT_FIELDS)
        self.assertNotIn("surfaces", view)
        self.assertNotIn("free_space", view)

    def test_entity_geometry_is_injected_by_the_caller_and_defaults_to_empty(self) -> None:
        self.assertEqual(fc.assignment_view(self.frame(), descriptor_set="vits14")["entity_geometry"], {})
        injected = fc.assignment_view(
            self.frame(), descriptor_set="vits14",
            entity_geometry={"entity:0001": {"should_be_visible_ratio": 0.5,
                                             "free_space_coverage_ratio": 0.25}})
        lean_assignment.validate_cache_frame(injected)
        self.assertEqual(injected["entity_geometry"]["entity:0001"]["should_be_visible_ratio"], 0.5)

    def test_an_unregistered_descriptor_set_is_refused(self) -> None:
        with self.assertRaises(fc.LeanFrontendCacheError):
            fc.assignment_view(self.frame(), descriptor_set="vitl14")

    def test_the_two_views_differ_only_in_the_descriptor(self) -> None:
        frame = self.frame()
        small = fc.assignment_view(frame, descriptor_set="vits14")
        large = fc.assignment_view(frame, descriptor_set="vitb14")
        for row_s, row_b in zip(small["fragments"], large["fragments"], strict=True):
            self.assertNotEqual(row_s["descriptor"], row_b["descriptor"])
            for field in ("fragment_id", "centroid_m", "aabb_min_m", "aabb_max_m",
                          "pixel_count", "depth_valid_ratio", "supported_by"):
                self.assertEqual(row_s[field], row_b[field])


class TestMaskSource(unittest.TestCase):
    """Ruling 72: the instance-segmentation source, its anonymous masks and the source in the episode seal."""

    @staticmethod
    def seal_inputs(count: int = 2) -> list[dict]:
        return [{"tick": t, "frame_seal": {"payload_sha256": f"{t:064x}"}} for t in range(1, count + 1)]

    def test_a_sam2_seal_keeps_the_pre_ruling_72_bytes(self) -> None:
        frames = self.seal_inputs()
        old_payload = {"episode_frame_count": 2, "frame_seals": [f["frame_seal"]["payload_sha256"] for f in frames],
                       "frontend_config_sha256": fc.D223_FRONTEND_CONFIG_SHA256}
        sealed = fc.seal_episode(frames, frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256)
        self.assertEqual(sealed["payload_sha256"], fc.sha(old_payload))
        self.assertNotIn("mask_source", sealed)
        self.assertEqual(sealed, fc.seal_episode(frames, frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256,
                                                 mask_source=fc.MASK_SOURCE_SAM2))
        self.assertEqual(fc.sealed_mask_source(sealed), fc.MASK_SOURCE_SAM2)

    def test_an_instance_seal_carries_its_source_and_cannot_be_relabelled(self) -> None:
        frames = self.seal_inputs()
        sam2 = fc.seal_episode(frames, frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256)
        instance = fc.seal_episode(frames, frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256,
                                   mask_source=fc.MASK_SOURCE_INSTANCE)
        self.assertEqual(instance["mask_source"], fc.MASK_SOURCE_INSTANCE)
        self.assertEqual(fc.sealed_mask_source(instance), fc.MASK_SOURCE_INSTANCE)
        self.assertNotEqual(instance["payload_sha256"], sam2["payload_sha256"])
        # dropping the source from an instance seal makes it read as sam2, whose recomputed payload differs
        relabelled = {k: v for k, v in instance.items() if k != "mask_source"}
        recomputed = fc.seal_episode(frames, frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256,
                                     mask_source=fc.sealed_mask_source(relabelled))
        self.assertNotEqual(recomputed["payload_sha256"], relabelled["payload_sha256"])
        with self.assertRaises(fc.LeanFrontendCacheError):
            fc.seal_episode(frames, frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256, mask_source="sam")
        with self.assertRaises(fc.LeanFrontendCacheError):
            fc.sealed_mask_source({"mask_source": "oracle"})

    def test_instance_masks_are_anonymous_one_per_listed_label_and_digest_ordered(self) -> None:
        image = np.zeros((40, 40), dtype=np.uint16)
        image[0:20, 0:20] = 1       # 400 px
        image[20:40, 20:40] = 2     # 400 px
        image[0:5, 30:40] = 3       # 50 px: a mask here, dropped later by admission
        image[30:40, 0:10] = 7      # a label the frame's mapping does not list: not a mask
        masks = fc.instance_label_masks(image, [1, 2, 3, 5])   # 5 is listed but absent from the image
        self.assertEqual(len(masks), 3)
        self.assertEqual([m.dtype for m in masks], [np.dtype(bool)] * 3)
        self.assertEqual(sorted(int(m.sum()) for m in masks), [50, 400, 400])
        self.assertEqual([fc.mask_sha256_of(m) for m in masks], sorted(fc.mask_sha256_of(m) for m in masks))
        self.assertFalse((masks[0] & masks[1]).any() or (masks[0] & masks[2]).any() or (masks[1] & masks[2]).any())
        with self.assertRaises(fc.LeanFrontendCacheError):
            fc.instance_label_masks(image, [0, 1])            # 0 is background, never an instance
        admitted = fc.admit_proposals([mask_of(m, f"region:{n:04d}") for n, m in enumerate(masks)])
        self.assertEqual(len(admitted), 2)                    # the 50 px instance is below 196 px

    def test_relabelling_the_instance_image_leaves_the_masks_byte_identical(self) -> None:
        # DATA section eight, check 3 under ruling 72: only the pixel geometry is a frontend input
        image = np.zeros((30, 30), dtype=np.uint16)
        image[0:15, 0:15], image[15:30, 15:30], image[0:15, 20:30] = 1, 2, 3
        permuted = np.zeros_like(image)
        permuted[image == 1], permuted[image == 2], permuted[image == 3] = 7, 1, 40
        original = fc.instance_label_masks(image, [1, 2, 3])
        relabelled = fc.instance_label_masks(permuted, [40, 7, 1])
        self.assertEqual([m.tobytes() for m in original], [m.tobytes() for m in relabelled])

    def test_more_than_64_instances_is_a_construction_failure_not_a_truncation(self) -> None:
        image = np.zeros((150, 150), dtype=np.uint16)
        for n in range(65):
            row, col = divmod(n, 10)
            image[row * 15:row * 15 + 14, col * 15:col * 15 + 14] = n + 1     # 196 px each
        masks = fc.instance_label_masks(image, list(range(1, 66)))
        self.assertEqual(len(masks), 65)
        with self.assertRaises(fc.LeanFrontendCacheError) as caught:
            fc.admit_proposals([mask_of(m, f"region:{n:04d}") for n, m in enumerate(masks)])
        self.assertEqual(caught.exception.reason, "proposal_overflow")


class TestContract(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_the_contract_matches_the_implementation(self) -> None:
        fc.validate_contract(self.contract)

    def test_every_open_authorization_bit_names_the_ruling_that_opened_it(self) -> None:
        policy = self.contract["activation_policy"]
        self.assertTrue(policy["opened_by"])
        for name, value in self.contract["authorization"].items():
            if value:
                self.assertIn(name, policy["active_true_authorizations"], name)

    def test_it_binds_the_frozen_frontend_rather_than_redefining_it(self) -> None:
        bound = self.contract["bound_frozen_frontend"]
        d223 = json.loads((PROJECT_ROOT / "configs" / "vsmt" /
                           "vm04_d223_f01_production_reader_v1.json").read_text(encoding="utf-8"))
        d215 = json.loads((PROJECT_ROOT / "configs" / "vsmt" /
                           "vm04_d215_frontend_freeze_v1.json").read_text(encoding="utf-8"))
        self.assertEqual(bound["d223_frontend_config_sha256"],
                         d223["frontend"]["frontend_config_sha256"])
        self.assertEqual(bound["sam2_repository_commit"], d215["sam2"]["repository_commit"])
        self.assertEqual(bound["sam2_checkpoint_sha256"], d215["sam2"]["checkpoint_sha256"])
        self.assertEqual(bound["sam2_automatic_mask_and_boundary_config_sha256"],
                         d215["sam2"]["automatic_mask_and_boundary_config_sha256"])

    def test_the_pose_correction_block_is_bound_to_the_core_and_lists_only_registered_commits(self) -> None:
        from vsmt import lean_public_pose as pp
        block = self.contract["public_pose_correction"]
        self.assertEqual(block["rule"], pp.CORRECTION_RULE)
        self.assertEqual(block["defect"], pp.DEFECT_ID)
        self.assertEqual(len(block["applies_to_s1_02_code_commits"]), 2)
        self.assertTrue(all(len(c) == 40 for c in block["applies_to_s1_02_code_commits"]))
        weakened = json.loads(json.dumps(self.contract))
        weakened["public_pose_correction"]["an_episode_from_an_unlisted_commit_is_refused"] = False
        with self.assertRaises(fc.LeanFrontendCacheError):
            fc.validate_contract(weakened)
        renamed = json.loads(json.dumps(self.contract))
        renamed["public_pose_correction"]["rule"] = "something_else"
        with self.assertRaises(fc.LeanFrontendCacheError):
            fc.validate_contract(renamed)

    def test_the_mask_rule_is_bound_and_cannot_be_weakened(self) -> None:
        block = self.contract["fragment_masks"]
        self.assertEqual(block["file"], fc.MASK_FILE_NAME_TEMPLATE)
        self.assertEqual(block["order"], "cache_fragment_order_the_sealed_frame_lists")
        self.assertTrue(block["written_during_generation"])
        self.assertTrue(block["separate_recovery_pass_no_longer_required"])
        self.assertTrue(block["recovery_pass_kept_for_caches_generated_before_this_ruling"])
        for key in ("written_during_generation", "digest_must_reproduce_from_pixels",
                    "consumer_must_re_digest_before_use", "separate_recovery_pass_no_longer_required"):
            weakened = json.loads(json.dumps(self.contract))
            weakened["fragment_masks"][key] = False
            with self.assertRaises(fc.LeanFrontendCacheError, msg=key):
                fc.validate_contract(weakened)
        renamed = json.loads(json.dumps(self.contract))
        renamed["fragment_masks"]["order"] = "whatever_order"
        with self.assertRaises(fc.LeanFrontendCacheError):
            fc.validate_contract(renamed)

    def test_the_mask_source_block_is_bound_and_cannot_be_weakened(self) -> None:
        block = self.contract["mask_source"]
        self.assertEqual(tuple(block["registered_values"]), fc.MASK_SOURCES)
        self.assertEqual(block["main_table"], fc.MASK_SOURCE_INSTANCE)
        self.assertEqual(tuple(block[fc.MASK_SOURCE_INSTANCE]["private_reads"]), fc.INSTANCE_MODE_PRIVATE_READS)
        self.assertEqual(block[fc.MASK_SOURCE_SAM2]["private_reads"], [])
        for key in ("one_cache_root_holds_one_mask_source", "admission_rule_is_proposal_rule_unchanged",
                    "overflow_is_a_construction_failure_never_truncation", "descriptors_geometry_volumes_and_pose_unchanged",
                    "episode_seal_carries_the_source_unless_sam2",
                    "an_entry_that_names_a_source_refuses_a_cache_sealed_with_another"):
            weakened = json.loads(json.dumps(self.contract))
            weakened["mask_source"][key] = False
            with self.assertRaises(fc.LeanFrontendCacheError, msg=key):
                fc.validate_contract(weakened)
        widened = json.loads(json.dumps(self.contract))
        widened["mask_source"][fc.MASK_SOURCE_INSTANCE]["private_reads"].append("private/NNNN.frame.json:object_poses")
        with self.assertRaises(fc.LeanFrontendCacheError):
            fc.validate_contract(widened)
        swapped = json.loads(json.dumps(self.contract))
        swapped["mask_source"]["main_table"] = fc.MASK_SOURCE_SAM2
        with self.assertRaises(fc.LeanFrontendCacheError):
            fc.validate_contract(swapped)
        for key, value in (("mask_source_in_the_payload_only_when_not_sam2", False),
                           ("private_read_before_the_seal_only_under", fc.MASK_SOURCE_SAM2),
                           ("private_derived_value_admitted_only_as", "anything_private")):
            changed = json.loads(json.dumps(self.contract))
            changed["seal"][key] = value
            with self.assertRaises(fc.LeanFrontendCacheError, msg=key):
                fc.validate_contract(changed)

    def test_the_proposal_boundary_is_the_d215_one(self) -> None:
        d215 = json.loads((PROJECT_ROOT / "configs" / "vsmt" /
                           "vm04_d215_frontend_freeze_v1.json").read_text(encoding="utf-8"))
        boundary = d215["sam2"]["proposal_boundary"]
        rule = self.contract["proposal_rule"]
        self.assertEqual(rule["minimum_visible_pixels"], boundary["minimum_visible_pixels"])
        self.assertEqual(rule["maximum_proposals_per_frame"], boundary["maximum_proposals_per_frame"])
        self.assertEqual(rule["prompt_policy"], boundary["prompt_policy"])
        self.assertFalse(rule["cross_frame_memory_enabled"])

    def test_the_view_fields_are_exactly_what_s0_03_validates(self) -> None:
        self.assertEqual(tuple(self.contract["assignment_view"]["produces"]),
                         lean_assignment.CACHE_FRAME_FIELDS)

    def test_a_weakened_rule_is_refused(self) -> None:
        for path, value in (
            (("proposal_rule", "maximum_proposals_per_frame"), 128),
            (("proposal_rule", "overflow_action"), "truncate"),
            (("proposal_rule", "duplicate_mask_action"), "deduplicate"),
            (("proposal_rule", "cross_frame_memory_enabled"), True),
            (("assignment_view", "entity_geometry_is_injected_by_the_s2_runner_not_stored"), False),
            (("aabb_rule", "not_derived_from_centroid_and_extent"), False),
            (("seal", "sealed_before_any_private_file_is_opened"), False),
            (("failure_rules", "any_frame_failure_fails_the_episode"), False),
        ):
            with self.subTest(path=path):
                broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
                node = broken
                for key in path[:-1]:
                    node = node[key]
                node[path[-1]] = value
                with self.assertRaises(fc.LeanFrontendCacheError):
                    fc.validate_contract(broken)

    def test_a_bit_opened_without_a_ruling_is_refused(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["authorization"]["invented_bit"] = True
        with self.assertRaises(fc.LeanFrontendCacheError) as ctx:
            fc.validate_contract(broken)
        self.assertIn("invented_bit", str(ctx.exception))

    def test_an_activation_policy_without_a_ruling_is_refused(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["activation_policy"]["opened_by"] = ""
        with self.assertRaises(fc.LeanFrontendCacheError):
            fc.validate_contract(broken)

    def test_rho_free_is_resolved_as_subsumed_with_its_evidence(self) -> None:
        volumes = self.contract["volumes"]
        self.assertEqual(volumes["free_space_reliability_gate_rho_free"],
                         "subsumed_by_the_bound_d223_free_space_configuration")
        self.assertNotIn("volumes.free_space_reliability_gate_rho_free",
                         self.contract["policy_values_without_defaults"])
        resolution = volumes["rho_free_resolution"]
        self.assertEqual(resolution["implied_gate_value"], 1.0)
        self.assertEqual(len(resolution["evidence"]), 3)
        self.assertTrue(resolution["ruling"].startswith("D-224"))

    def test_the_implied_gate_is_what_the_frozen_materialiser_actually_does(self) -> None:
        """The claim is checkable: a block with one invalid pixel yields no free-space frustum."""
        from vsmt.l1_structures import materialize_public_free_space
        from vsmt.shared_frontend_core import FreeSpaceMaterializationConfig
        d223 = json.loads((PROJECT_ROOT / "configs" / "vsmt" /
                           "vm04_d223_f01_production_reader_v1.json").read_text(encoding="utf-8"))
        raw = dict(d223["frontend"]["free_space"])
        raw["block_widths_in_tiles"] = tuple(raw["block_widths_in_tiles"])
        config = FreeSpaceMaterializationConfig(**raw)
        side = raw["tile_size_pixels"] * raw["block_widths_in_tiles"][-1]
        calibration = {"fx": 112.0, "fy": 112.0, "cx": (side - 1) / 2, "cy": (side - 1) / 2}
        pose = {"position_m": [0.0, 0.0, 0.0], "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0]}
        clean = np.full((side, side), 4.0, dtype=np.float32)
        digest = "a" * 64
        full = materialize_public_free_space(clean, calibration, pose, time_s=0.0, depth_sha256=digest,
                                             camera_calibration_and_pose_sha256=digest, config=config)
        self.assertGreater(len(full), 0)
        holed = clean.copy()
        holed[0, 0] = np.nan                      # one unreliable ray in the largest block
        fewer = materialize_public_free_space(holed, calibration, pose, time_s=0.0, depth_sha256=digest,
                                              camera_calibration_and_pose_sha256=digest, config=config)
        self.assertLess(len(fewer), len(full))
        self.assertTrue(all(record.public_record("free-space:0000")["reliability"] == 1.0
                            for record in full))

    def test_ruling_43_supersedes_exactly_the_two_nms_thresholds_by_reference(self) -> None:
        nms = self.contract["sam2_nms_supersession"]
        d215 = json.loads((PROJECT_ROOT / "configs" / "vsmt" /
                           "vm04_d215_frontend_freeze_v1.json").read_text(encoding="utf-8"))
        frozen = d215["sam2"]["automatic_mask_generator"]
        self.assertEqual(frozen["box_nms_thresh"], 1.0)            # D-215 itself is untouched
        self.assertEqual(frozen["crop_nms_thresh"], 1.0)
        effective = nms["effective_automatic_mask_generator"]
        self.assertEqual(effective, {**frozen, "box_nms_thresh": 0.7, "crop_nms_thresh": 0.7})
        self.assertEqual({k for k in frozen if frozen[k] != effective[k]}, {"box_nms_thresh", "crop_nms_thresh"})
        self.assertTrue(nms["predecessor_bytes_must_not_change"])

    def test_the_effective_digest_uses_d215s_own_formula(self) -> None:
        from vsmt.d215_frontend_freeze import _derived_digests
        d215 = json.loads((PROJECT_ROOT / "configs" / "vsmt" /
                           "vm04_d215_frontend_freeze_v1.json").read_text(encoding="utf-8"))
        shadow = json.loads(json.dumps(d215))
        shadow["sam2"]["automatic_mask_generator"] = self.contract["sam2_nms_supersession"]["effective_automatic_mask_generator"]
        self.assertEqual(_derived_digests(shadow)["automatic"], fc.EFFECTIVE_AUTOMATIC_CONFIG_SHA256)
        self.assertEqual(_derived_digests(d215)["automatic"], fc.D215_AUTOMATIC_CONFIG_SHA256)
        self.assertNotEqual(fc.EFFECTIVE_AUTOMATIC_CONFIG_SHA256, fc.D215_AUTOMATIC_CONFIG_SHA256)

    def test_a_third_superseded_argument_is_refused(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["sam2_nms_supersession"]["effective_automatic_mask_generator"]["points_per_side"] = 16
        with self.assertRaises(fc.LeanFrontendCacheError):
            fc.validate_contract(broken)

    def test_this_stage_does_not_select_a_descriptor(self) -> None:
        self.assertIn("descriptor_selection", self.contract["not_in_this_stage"])
        self.assertTrue(self.contract["descriptor_sets"]["selection_is_not_made_in_this_stage"])


if __name__ == "__main__":
    unittest.main()
