from __future__ import annotations

from copy import deepcopy
import hashlib
import inspect
import json
from pathlib import Path
import sys
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.d210_place_memory import build_continuous_pose_belief  # noqa: E402
from vsmt.d214_shared_frontend import (  # noqa: E402
    D214Error,
    D214FrontendConfig,
    MAIN_METHODS,
    P08EligibilityConfig,
    identical_method_cache_views,
    legacy_grid_retirement_readiness,
    materialize_shared_rgbd_frame,
    materializer_parameter_names,
    qualify_p04,
    qualify_p08,
    seal_episode_cache,
    validate_contract,
    validate_episode_cache,
    validate_frame_cache,
)
from vsmt.l1_entities import (  # noqa: E402
    AI2THOR_CAMERA_AXIS_Z,
    DINORegionConfig,
    PublicGeometryConfig,
)
from vsmt.l1_masks import AnonymousMask  # noqa: E402
from vsmt.l1_structures import (  # noqa: E402
    FreeSpaceMaterializationConfig,
    SurfaceMaterializationConfig,
)


CONTRACT_PATH = ROOT / "configs/vsmt/vm04_d214_shared_rgbd_frontend_v1.json"


def _sha(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def config() -> D214FrontendConfig:
    return D214FrontendConfig(
        descriptor=DINORegionConfig(
            image_height=56, image_width=56, patch_size_pixels=14,
            patch_token_dimension=4, minimum_total_patch_weight=0.5,
            unit_norm_validation_tolerance=1e-5,
        ),
        fragment_geometry=PublicGeometryConfig(
            depth_convention=AI2THOR_CAMERA_AXIS_Z,
            minimum_depth_m=0.05, maximum_depth_m=20.0,
            absolute_minimum_valid_depth_points=16,
            minimum_valid_depth_fraction=0.25,
        ),
        surface=SurfaceMaterializationConfig(
            tile_size_pixels=14,
            minimum_valid_depth_fraction_per_tile=0.9,
            initial_maximum_rms_point_to_plane_m=0.015,
            initial_maximum_p95_point_to_plane_m=0.03,
            merge_maximum_normal_angle_degrees=10.0,
            merge_maximum_mutual_centroid_to_plane_m=0.03,
            final_inlier_point_to_plane_m=0.02,
            final_minimum_inlier_fraction=0.9,
            final_maximum_rms_point_to_plane_m=0.01,
            minimum_inlier_pixels=196,
            minimum_depth_m=0.05, maximum_depth_m=20.0,
        ),
        free_space=FreeSpaceMaterializationConfig(
            tile_size_pixels=14, block_widths_in_tiles=(1, 2, 4),
            angular_boundary_erosion_pixels=1,
            minimum_depth_m=0.05, maximum_valid_depth_m=20.0,
            near_axis_depth_m=0.1, surface_clearance_m=0.1,
            maximum_axis_depth_m=5.0,
            minimum_longitudinal_thickness_m=0.1,
            rolling_public_observation_times=4,
        ),
        frontend_config_sha256="a" * 64,
    )


def mask(shift: int = 0) -> AnonymousMask:
    array = np.zeros((56, 56), dtype=np.uint8)
    array[7 + shift:21 + shift, 14:28] = 1
    payload = [56, 56, *array.reshape(-1).tolist()]
    return AnonymousMask(
        region_id="region:0000", mask_sha256=_sha(payload),
        height=56, width=56,
        row_major_values=tuple(int(item) for item in array.reshape(-1)),
        visible_pixel_count=int(array.sum()), touches_border=False,
    )


def pose_belief(index: int, x: float = 0.0) -> dict:
    return build_continuous_pose_belief(
        observation_index=index, mean_x_y_z_yaw=[x, 0.0, 0.0, 0.0],
        covariance_diagonal=[0.01, 0.01, 0.01, 1.0],
        source_id="fixture.causal.odometry.v1",
    )


def frame(index: int, *, role: str = "basin", descriptor_axis: int = 0,
          x: float = 0.0, semantics=None) -> dict:
    tokens = np.zeros((4, 4, 4), dtype=np.float32)
    tokens[..., descriptor_axis] = 1.0
    structural = {"basin": 0.05, "bottleneck": 0.05, "unknown": 0.90}
    structural[role] = 0.90
    structural["unknown"] = 0.05
    semantic = semantics or {"room": 0.6, "corridor": 0.2, "unknown": 0.2}
    return materialize_shared_rgbd_frame(
        observation_index=index, decision_time_s=float(index),
        rgb_sha256=f"{index + 1:x}" * 64,
        depth_sha256=f"{index + 9:x}"[-1] * 64,
        camera_calibration={"fx": 28.0, "fy": 28.0,
                            "cx": 27.5, "cy": 27.5},
        causal_camera_pose={
            "position_m": [x, 0.0, 0.0],
            "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
            "is_world_pose": False,
            "source_id": "fixture.causal.odometry.v1",
        },
        pose_belief=pose_belief(index, x),
        incoming_transition_action_summary=None if index == 0 else {
            "schema_version": "fixture-transition-summary-v1",
            "start_observation_index": index - 1,
            "end_observation_index": index,
            "summary_sha256": "b" * 64,
        },
        depth_m=np.full((56, 56), 2.0, dtype=np.float32),
        patch_tokens=tokens, public_fragment_masks=[mask()],
        l2_proposal_receipt_sha256="c" * 64,
        semantic_probabilities=semantic,
        structural_role_probabilities=structural,
        semantic_model_receipt_sha256="d" * 64,
        prior_free_space=[], config=config(),
    )


def episode(frames) -> dict:
    return seal_episode_cache(
        frames, episode_public_id="episode:fixture",
        dinov2_assets_receipt_sha256="e" * 64,
        sam2_assets_receipt_sha256="f" * 64,
        semantic_assets_receipt_sha256="1" * 64,
    )


class D214SharedRgbdFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = validate_contract(json.loads(
            CONTRACT_PATH.read_text(encoding="utf-8")
        ))

    def test_contract_is_global_scenario_blind_and_all_gates_stay_closed(self):
        self.assertEqual(
            [f"P{index:02d}" for index in range(1, 9)],
            self.contract["global_scope"]["covered_scenarios"],
        )
        self.assertFalse(self.contract["global_scope"]["frontend_receives_scenario_id"])
        self.assertEqual(list(MAIN_METHODS), self.contract["global_scope"]
                         ["identical_cached_bytes_for_main_methods"])
        self.assertIn("P01_P02_P03_P05_P06_P07",
                      self.contract["scenario_qualification"])
        self.assertFalse(any(self.contract["authorization"].values()))
        self.assertFalse(self.contract["implementation_boundary"]
                         ["production_raw_reader_implemented"])
        tampered = deepcopy(self.contract)
        tampered["public_inputs"].append("scenario_id")
        with self.assertRaisesRegex(D214Error, "input boundary"):
            validate_contract(tampered)
        self.assertEqual("6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38",
                         self.contract["asset_state"]["sam2"]["checkpoint_sha256"])
        self.assertIsNone(self.contract["asset_state"]["semantic_structural_estimator"]
                          ["weights_sha256"])

    def test_materializer_signature_has_no_scenario_private_teacher_or_future(self):
        names = materializer_parameter_names()
        self.assertEqual(tuple(inspect.signature(
            materialize_shared_rgbd_frame).parameters), names)
        forbidden = ("scenario", "private", "teacher", "future")
        self.assertFalse(any(token in name.lower()
                             for name in names for token in forbidden))

    def test_frame_has_fragments_non_grid_place_surfaces_and_public_volumes(self):
        value = frame(0)
        self.assertEqual("fragment", value["fragment_observations"][0]
                         ["structure_kind"])
        self.assertFalse(any(
            row["structure_kind"] == "entity"
            for row in [*value["fragment_observations"],
                        *value["surface_observations"]]
        ))
        place = value["place_observation"]
        self.assertIsNone(place["persistent_place_id"])
        self.assertFalse(place["metric_grid_identity_used"])
        self.assertFalse(place["semantic_class_defines_identity"])
        self.assertAlmostEqual(1.0, sum(place["semantic_probabilities"].values()))
        self.assertTrue(value["surface_observations"])
        self.assertTrue(value["free_space_observations"])
        self.assertTrue(value["visibility_observations"])
        self.assertEqual(value, validate_frame_cache(value))

    def test_forbidden_field_is_rejected_even_when_nested(self):
        value = frame(0)
        value["place_observation"]["scenario_id"] = "P08"
        value["frame_cache_sha256"] = _sha({
            key: item for key, item in value.items()
            if key != "frame_cache_sha256"
        })
        with self.assertRaisesRegex(D214Error, "unexpected fields|forbidden field"):
            validate_frame_cache(value)

    def test_all_main_methods_receive_identical_cache_bytes(self):
        sealed = episode([frame(0), frame(1, x=0.25)])
        views = identical_method_cache_views(sealed)
        self.assertEqual(set(MAIN_METHODS), set(views))
        self.assertEqual(1, len({_sha(value) for value in views.values()}))
        views["VSMT"]["frames"][0]["decision_time_s"] = 99.0
        self.assertNotEqual(views["VSMT"], views["TAF"])

    def test_episode_revalidation_rejects_time_drift(self):
        sealed = episode([frame(0), frame(1, x=0.25)])
        sealed["frames"][1]["decision_time_s"] = 0.0
        sealed["frames"][1]["frame_cache_sha256"] = _sha({
            key: value for key, value in sealed["frames"][1].items()
            if key != "frame_cache_sha256"
        })
        sealed["ordered_frame_cache_sha256s"][1] = (
            sealed["frames"][1]["frame_cache_sha256"])
        sealed["episode_cache_sha256"] = _sha({
            key: value for key, value in sealed.items()
            if key != "episode_cache_sha256"
        })
        with self.assertRaisesRegex(D214Error, "strictly increasing"):
            validate_episode_cache(sealed)

    def test_p04_uses_dino_top_pair_at_frozen_separation(self):
        sealed = episode([
            frame(0, descriptor_axis=0, x=0.0),
            frame(1, descriptor_axis=1, x=0.5),
            frame(2, descriptor_axis=0, x=2.0),
        ])
        receipt = qualify_p04(
            sealed, public_nominal_positions_xz_m=[
                [0.0, 0.0], [0.5, 0.0], [2.0, 0.0],
            ],
        )
        self.assertEqual([0, 2], receipt["selected_observation_indices"])
        self.assertAlmostEqual(1.0, receipt["dinov2_cosine_similarity"])
        self.assertFalse(receipt["old_quadrant_rgbd_descriptor_used"])

    def test_p08_requires_ordered_structure_and_stable_multiview_fragments(self):
        frames = [
            frame(0, role="basin", x=0.00),
            frame(1, role="basin", x=0.02),
            frame(2, role="bottleneck", x=1.00,
                  semantics={"room": 0.1, "corridor": 0.8, "unknown": 0.1}),
            frame(3, role="bottleneck", x=1.10,
                  semantics={"room": 0.1, "corridor": 0.8, "unknown": 0.1}),
            frame(4, role="basin", x=2.00),
            frame(5, role="basin", x=2.02),
        ]
        sealed = episode(frames)
        eligibility = P08EligibilityConfig(
            basin_probability_minimum=0.7,
            bottleneck_probability_minimum=0.7,
            fragment_descriptor_cosine_minimum=0.85,
            fragment_centroid_distance_maximum_m=0.35,
        )
        receipt = qualify_p08(sealed, config=eligibility)
        self.assertEqual([2, 3], receipt["bottleneck_observation_indices"])
        self.assertFalse(receipt["room_corridor_semantics_used_for_place_identity"])
        broken = episode([
            frame(0, role="basin", descriptor_axis=0, x=0.00),
            frame(1, role="basin", descriptor_axis=1, x=0.02),
            frame(2, role="bottleneck", x=1.00),
            frame(3, role="bottleneck", x=1.10),
            frame(4, role="basin", x=2.00),
            frame(5, role="basin", x=2.02),
        ])
        with self.assertRaisesRegex(D214Error, "stable fragments"):
            qualify_p08(broken, config=eligibility)

    def test_semantics_are_recorded_but_do_not_gate_p08_identity(self):
        frames = [
            frame(0, role="basin", x=0.00), frame(1, role="basin", x=0.02),
            frame(2, role="bottleneck", x=1.00),
            frame(3, role="basin", x=2.00), frame(4, role="basin", x=2.02),
        ]
        config_value = P08EligibilityConfig(0.7, 0.7, 0.85, 0.35)
        first = qualify_p08(episode(frames), config=config_value)
        changed = []
        for item in frames:
            copy = deepcopy(item)
            copy["place_observation"]["semantic_probabilities"] = {
                "room": 0.0, "corridor": 0.0, "unknown": 1.0,
            }
            copy["place_observation"]["place_observation_sha256"] = _sha({
                key: value for key, value in copy["place_observation"].items()
                if key != "place_observation_sha256"
            })
            copy["frame_cache_sha256"] = _sha({
                key: value for key, value in copy.items()
                if key != "frame_cache_sha256"
            })
            changed.append(copy)
        second = qualify_p08(episode(changed), config=config_value)
        self.assertEqual(first["first_basin_observation_indices"],
                         second["first_basin_observation_indices"])
        self.assertEqual(first["second_basin_observation_indices"],
                         second["second_basin_observation_indices"])

    def test_grid_retirement_is_read_only_and_requires_every_precondition(self):
        blocked = legacy_grid_retirement_readiness(
            all_new_caches_generated=False, all_digests_verified=True,
            p04_and_p08_requalified=True, all_routes_rebound=True,
            reviewed_exact_targets=["outputs/legacy-grid-v1"],
            reproduction_dependencies_remaining=[],
        )
        self.assertFalse(blocked["ready_for_user_requested_deletion"])
        ready = legacy_grid_retirement_readiness(
            all_new_caches_generated=True, all_digests_verified=True,
            p04_and_p08_requalified=True, all_routes_rebound=True,
            reviewed_exact_targets=["outputs/legacy-grid-v1"],
            reproduction_dependencies_remaining=[],
        )
        self.assertTrue(ready["ready_for_user_requested_deletion"])
        self.assertFalse(ready["deletion_performed"])
        with self.assertRaisesRegex(D214Error, "without wildcards"):
            legacy_grid_retirement_readiness(
                all_new_caches_generated=True, all_digests_verified=True,
                p04_and_p08_requalified=True, all_routes_rebound=True,
                reviewed_exact_targets=["outputs/legacy-*"],
                reproduction_dependencies_remaining=[],
            )


if __name__ == "__main__":
    unittest.main()
