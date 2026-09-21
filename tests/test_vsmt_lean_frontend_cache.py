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

    def test_this_stage_does_not_select_a_descriptor(self) -> None:
        self.assertIn("descriptor_selection", self.contract["not_in_this_stage"])
        self.assertTrue(self.contract["descriptor_sets"]["selection_is_not_made_in_this_stage"])


if __name__ == "__main__":
    unittest.main()
