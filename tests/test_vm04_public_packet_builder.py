from __future__ import annotations

from copy import deepcopy
import inspect
from pathlib import Path
import sys
import unittest
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vsmt.causal_prior import PublicBootstrapConfig  # noqa: E402
from vsmt.vm04_public_packet_builder import (  # noqa: E402
    build_public_packet_sequence,
    make_public_packet,
)


def bootstrap_config() -> PublicBootstrapConfig:
    return PublicBootstrapConfig(
        association_rules={
            kind: {
                "visual_weight": 0.5,
                "geometry_weight": 0.5,
                "geometry_scale_m": 1.0,
                "association_threshold": 0.7,
            }
            for kind in ("entity", "surface", "fragment")
        },
        support_envelope_reliability_threshold=0.9,
        maximum_regions_per_packet=8,
        builder_revision="fixture.v1",
    )


def region(index: int, *, mask: str, centroid_x: float) -> dict[str, Any]:
    return {
        "region_id": f"region:{index:04d}",
        "structure_kind": "entity",
        "mask_sha256": mask * 64,
        "descriptor": [1.0, 0.0],
        "centroid_m": [centroid_x, 0.0, 0.0],
        "extent_m": [0.2, 0.2, 0.2],
        "reliability": 1.0,
        "proposal_source_id": "fixed.region.v1",
    }


def frontend_row(
    *, time_s: float, mask: str, centroid_x: float,
) -> dict[str, Any]:
    return {
        "sample_id_hash": "1" * 64,
        "decision_time_s": time_s,
        "rgbd_refs": {
            "rgb_sha256": "2" * 64,
            "depth_sha256": "3" * 64,
        },
        "camera_pose": {
            "position_m": [0.0, 0.0, 1.0],
            "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
        },
        "robot_state": {"feature_names": [], "values": []},
        "past_actions": [],
        "region_observations": [
            region(0, mask=mask, centroid_x=centroid_x),
        ],
        "relation_observations": [],
        "free_space_observations": [],
        "visibility_observations": [],
        "public_constants": {
            "coordinate_frame": "map",
            "depth_unit": "metre",
            "descriptor_model_id": "dinov2.vits14",
            "proposal_model_id": "fixed.region.v1",
        },
    }


class Vm04PublicPacketBuilderTests(unittest.TestCase):
    def test_sequence_binds_each_packet_to_online_memory_then_replays(self) -> None:
        built = build_public_packet_sequence(
            [
                frontend_row(time_s=0.0, mask="4", centroid_x=0.0),
                frontend_row(time_s=1.0, mask="5", centroid_x=0.05),
            ],
            bootstrap_config=bootstrap_config(),
            builder_code_sha256="a" * 64,
        )

        packets = built["public_packets"]
        receipt = built["causal_prior_receipt"]
        self.assertEqual(len(packets), 2)
        self.assertEqual(
            packets[0]["prior_memory_ref"]["graph_sha256"],
            receipt["initial_memory_sha256"],
        )
        self.assertEqual(
            packets[1]["prior_memory_ref"]["graph_sha256"],
            receipt["version_chain_sha256s"][1],
        )
        self.assertEqual(
            built["prior_memory"]["graph_hash"],
            receipt["final_prior_memory_sha256"],
        )
        current = [
            node for node in built["prior_memory"]["nodes"]
            if node["valid_to"] is None
        ]
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]["lifecycle"], "confirmed")

    def test_time_regression_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "ordered by decision_time_s"):
            build_public_packet_sequence(
                [
                    frontend_row(time_s=1.0, mask="4", centroid_x=0.0),
                    frontend_row(time_s=0.0, mask="5", centroid_x=0.05),
                ],
                bootstrap_config=bootstrap_config(),
                builder_code_sha256="a" * 64,
            )

    def test_private_or_unregistered_frontend_field_is_rejected(self) -> None:
        row = frontend_row(time_s=0.0, mask="4", centroid_x=0.0)
        row["private_program"] = "SPLIT"
        with self.assertRaisesRegex(ValueError, "contain exactly"):
            make_public_packet(row, _empty_memory())

        target = frontend_row(time_s=0.0, mask="4", centroid_x=0.0)
        target["region_observations"][0]["instance_id"] = "private-id"
        with self.assertRaisesRegex(ValueError, "exactly"):
            make_public_packet(target, _empty_memory())

    def test_public_builder_signatures_expose_no_private_teacher_or_future(self) -> None:
        for function in (make_public_packet, build_public_packet_sequence):
            names = inspect.signature(function).parameters
            self.assertFalse(any(
                token in name
                for name in names
                for token in ("private", "teacher", "future", "program", "target")
            ))


def _empty_memory() -> dict[str, Any]:
    from vsmt.causal_prior import empty_public_memory

    return deepcopy(empty_public_memory())


if __name__ == "__main__":
    unittest.main()
