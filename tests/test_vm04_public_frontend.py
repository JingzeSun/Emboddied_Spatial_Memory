from __future__ import annotations

from copy import deepcopy
import inspect
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

from vsmt.causal_prior import empty_public_memory  # noqa: E402
from vsmt.l1_entities import (  # noqa: E402
    AI2THOR_CAMERA_AXIS_Z,
    DINORegionConfig,
    PublicGeometryConfig,
)
from vsmt.l1_masks import (  # noqa: E402
    KEEP_SUPPORTED_BORDER_REGIONS,
    L1MaskConfig,
)
from vsmt.l1_structures import (  # noqa: E402
    FreeSpaceMaterializationConfig,
    PlaceMaterializationConfig,
    SurfaceMaterializationConfig,
)
from vsmt.vm04_public_frontend import (  # noqa: E402
    Vm04PublicFrontendConfig,
    materialize_vm04_l2_public_frontend_frame,
    materialize_vm04_public_frontend_frame,
)
from vsmt.vm04_l2_proposals import (  # noqa: E402
    MODEL_ID,
    PROMPT_POLICY,
    PROPOSAL_SOURCE_ID as L2_PROPOSAL_SOURCE_ID,
    Vm04L2ProposalConfig,
    run_vm04_l2_proposal_frontend,
)
from vsmt.vm04_public_packet_builder import make_public_packet  # noqa: E402


def config() -> Vm04PublicFrontendConfig:
    return Vm04PublicFrontendConfig(
        mask=L1MaskConfig(196, KEEP_SUPPORTED_BORDER_REGIONS),
        descriptor=DINORegionConfig(
            image_height=224,
            image_width=224,
            patch_size_pixels=14,
            patch_token_dimension=4,
            minimum_total_patch_weight=1.0,
            unit_norm_validation_tolerance=1e-5,
        ),
        entity_geometry=PublicGeometryConfig(
            depth_convention=AI2THOR_CAMERA_AXIS_Z,
            minimum_depth_m=0.05,
            maximum_depth_m=20.0,
            absolute_minimum_valid_depth_points=32,
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
            minimum_inlier_pixels=784,
            minimum_depth_m=0.05,
            maximum_depth_m=20.0,
        ),
        place=PlaceMaterializationConfig(
            maximum_floor_normal_angle_degrees=10.0,
            maximum_support_height_difference_m=0.05,
            cell_size_m=0.5,
            grid_origin_m=(0.0, 0.0, 0.0),
            coverage_subcell_size_m=0.1,
            minimum_covered_subcells=16,
            minimum_mask_pixels=196,
            camera_to_agent_center_y_m=0.675,
            agent_half_height_m=0.9,
            located_at_boundary_margin_m=0.02,
        ),
        free_space=FreeSpaceMaterializationConfig(
            tile_size_pixels=14,
            block_widths_in_tiles=(1, 2, 4, 8, 16),
            angular_boundary_erosion_pixels=1,
            minimum_depth_m=0.05,
            maximum_valid_depth_m=20.0,
            near_axis_depth_m=0.1,
            surface_clearance_m=0.1,
            maximum_axis_depth_m=5.0,
            minimum_longitudinal_thickness_m=0.1,
            rolling_public_observation_times=4,
        ),
        supported_by_maximum_normal_angle_degrees=10.0,
        supported_by_minimum_gap_m=-0.02,
        supported_by_maximum_gap_m=0.05,
        supported_by_minimum_projected_overlap=0.25,
        supported_by_maximum_mask_overlap_fraction=0.05,
    )


def inputs() -> dict:
    masks = np.zeros((2, 224, 224), dtype=np.uint8)
    masks[0, :14, :14] = 1
    masks[1, 28:42, 28:42] = 1
    tokens = np.zeros((16, 16, 4), dtype=np.float32)
    tokens[..., 0] = 1.0
    return {
        "sample_id_hash": "1" * 64,
        "decision_time_s": 0.0,
        "rgbd_refs": {
            "rgb_sha256": "2" * 64,
            "depth_sha256": "3" * 64,
        },
        "camera": {
            "pose": {
                "position_m": [0.0, 0.0, 0.0],
                "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
            },
            "calibration": {
                "fx": 112.0, "fy": 112.0, "cx": 111.5, "cy": 111.5,
            },
        },
        "robot_state": {"feature_names": [], "values": []},
        "past_actions": [],
        "depth_m": np.full((224, 224), 2.0, dtype=np.float32),
        "patch_tokens": tokens,
        "private_instance_ids": ["Chair|private-a", "Mug|private-b"],
        "private_instance_masks": masks,
        "prior_free_space": [],
        "public_constants": {
            "coordinate_frame": "map",
            "depth_unit": "metre",
            "descriptor_model_id": "dinov2.vits14",
            "proposal_model_id": "l1.oracle-mask.public-depth.v1",
        },
        "observation_index": 0,
        "config": config(),
    }


class Vm04PublicFrontendTests(unittest.TestCase):
    def test_materializes_valid_public_packet_row_and_private_crosswalk(self):
        output = materialize_vm04_public_frontend_frame(**inputs())
        packet = make_public_packet(output["frontend_row"], empty_public_memory())

        entities = [
            row for row in packet["region_observations"]
            if row["structure_kind"] == "entity"
        ]
        self.assertEqual(len(entities), 2)
        self.assertEqual(len(output["private_crosswalk"]["bindings"]), 2)
        self.assertEqual(len(packet["free_space_observations"]), 341)
        self.assertEqual(len(packet["visibility_observations"]), 341)
        encoded = json.dumps(packet, sort_keys=True)
        self.assertNotIn("Chair", encoded)
        self.assertNotIn("Mug", encoded)
        self.assertNotIn("private", encoded)

    def test_private_id_and_input_order_changes_do_not_change_public_row(self):
        first_inputs = inputs()
        first = materialize_vm04_public_frontend_frame(**first_inputs)
        second_inputs = inputs()
        second_inputs["private_instance_ids"] = ["opaque-y", "opaque-x"]
        second_inputs["private_instance_masks"] = np.asarray(
            second_inputs["private_instance_masks"][[1, 0]],
        )
        second = materialize_vm04_public_frontend_frame(**second_inputs)

        self.assertEqual(first["frontend_row"], second["frontend_row"])
        self.assertNotEqual(
            first["private_crosswalk"], second["private_crosswalk"],
        )

    def test_no_program_specific_mask_or_descriptor_mutation_is_possible(self):
        parameters = inspect.signature(
            materialize_vm04_public_frontend_frame,
        ).parameters
        self.assertFalse(any(
            token in name
            for name in parameters
            for token in ("program", "target", "teacher", "future")
        ))
        self.assertEqual(
            {field.name for field in __import__("dataclasses").fields(
                Vm04PublicFrontendConfig
            )},
            {
                "mask", "descriptor", "entity_geometry", "surface", "place",
                "free_space", "supported_by_maximum_normal_angle_degrees",
                "supported_by_minimum_gap_m", "supported_by_maximum_gap_m",
                "supported_by_minimum_projected_overlap",
                "supported_by_maximum_mask_overlap_fraction",
            },
        )

    def test_rejected_small_mask_is_anonymous_and_not_crosswalk_bound(self):
        values = inputs()
        values["private_instance_masks"][1] = 0
        values["private_instance_masks"][1, 30, 30] = 1
        output = materialize_vm04_public_frontend_frame(**values)
        self.assertEqual(len(output["private_crosswalk"]["bindings"]), 1)
        rejected = output["public_frontend_diagnostics"][
            "anonymous_mask_rejections"
        ]
        self.assertEqual(rejected[0]["reason"], "below_minimum_visible_pixels")
        self.assertNotIn("Mug", json.dumps(rejected))

    def test_l2_public_masks_materialize_without_private_crosswalk(self):
        mask = np.zeros((224, 224), dtype=np.bool_)
        mask[28:42, 28:42] = True

        class Generator:
            def generate(self, rgb):
                return [{"segmentation": mask}]

        proposal_config = Vm04L2ProposalConfig(
            image_height=224, image_width=224, minimum_visible_pixels=196,
            border_truncation_policy=KEEP_SUPPORTED_BORDER_REGIONS,
            maximum_proposals_per_frame=64, model_id=MODEL_ID,
            repository_commit="1" * 40, checkpoint_sha256="2" * 64,
            automatic_mask_generator_config_sha256="3" * 64,
            assets_receipt_sha256="4" * 64,
            generator_code_sha256="5" * 64, prompt_policy=PROMPT_POLICY,
            cross_frame_memory_enabled=False,
            overlap_policy="preserve_independent_overlapping_proposals",
        )
        proposal = run_vm04_l2_proposal_frontend(
            rgb=np.zeros((224, 224, 3), dtype=np.uint8),
            public_rgb_file_sha256="2" * 64,
            generator=Generator(), config=proposal_config,
        )
        values = inputs()
        for key in ("private_instance_ids", "private_instance_masks"):
            values.pop(key)
        values.update({
            "public_entity_masks": proposal["masks"],
            "l2_proposal_receipt": proposal["receipt"],
            "l2_proposal_config": proposal_config,
        })
        output = materialize_vm04_l2_public_frontend_frame(**values)
        entities = [
            row for row in output["frontend_row"]["region_observations"]
            if row["structure_kind"] == "entity"
        ]
        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0]["proposal_source_id"],
                         L2_PROPOSAL_SOURCE_ID)
        self.assertNotIn("private_crosswalk", output)


if __name__ == "__main__":
    unittest.main()
