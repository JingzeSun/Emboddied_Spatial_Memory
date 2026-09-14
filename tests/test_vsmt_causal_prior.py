from __future__ import annotations

from copy import deepcopy
import inspect
from pathlib import Path
import sys
import unittest
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vsmt.causal_prior import (  # noqa: E402
    PublicBootstrapConfig,
    advance_public_bootstrap,
    build_causal_prior,
    empty_public_memory,
    validate_causal_prior_receipt,
)
from vsmt.graph_ops import STATE_KEY  # noqa: E402


def bootstrap_config(**updates: Any) -> PublicBootstrapConfig:
    values = {
        "visual_weight": 0.5,
        "geometry_weight": 0.5,
        "geometry_scale_m": 1.0,
        "association_threshold": 0.7,
        "maximum_regions_per_packet": 8,
        "builder_revision": "fixture.v1",
    }
    values.update(updates)
    return PublicBootstrapConfig(**values)


def region(index: int, centroid_x: float, kind: str = "entity") -> dict[str, Any]:
    return {
        "region_id": f"region:{index:04d}",
        "structure_kind": kind,
        "mask_sha256": f"{index + 4:x}" * 64,
        "descriptor": [1.0, 0.0],
        "centroid_m": [centroid_x, 0.0, 0.0],
        "extent_m": [0.2, 0.2, 0.2],
        "reliability": 1.0,
        "proposal_source_id": "fixed.region.v1",
    }


def packet(
    graph: Mapping[str, Any], *, time_s: float, regions: list[Mapping[str, Any]],
    relations: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "vsmt-observation-packet-v2",
        "sample_id_hash": "1" * 64,
        "decision_time_s": time_s,
        "rgbd_refs": {"rgb_sha256": "2" * 64, "depth_sha256": "3" * 64},
        "camera_pose": {
            "position_m": [0.0, 0.0, 1.0],
            "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
        },
        "robot_state": {"feature_names": [], "values": []},
        "past_actions": [],
        "region_observations": [deepcopy(dict(item)) for item in regions],
        "relation_observations": [
            deepcopy(dict(item)) for item in (relations or [])
        ],
        "free_space_observations": [],
        "prior_memory_ref": {
            "graph_version": graph["graph_version"],
            "graph_sha256": graph["graph_hash"],
        },
        "public_constants": {
            "coordinate_frame": "map",
            "depth_unit": "metre",
            "descriptor_model_id": "dinov2.vits14",
            "proposal_model_id": "fixed.region.v1",
        },
    }


class CausalPriorTests(unittest.TestCase):
    def test_builder_signature_has_no_private_teacher_or_path_argument(self) -> None:
        parameters = inspect.signature(build_causal_prior).parameters
        self.assertEqual(
            set(parameters), {"packets", "config", "builder_code_sha256"},
        )
        self.assertFalse(any(
            token in name for name in parameters
            for token in ("private", "teacher", "future", "path")
        ))

    def test_sequence_births_then_binds_and_seals_every_step(self) -> None:
        initial = empty_public_memory()
        first = packet(initial, time_s=0.0, regions=[region(0, 0.0)])
        first_result = advance_public_bootstrap(
            first, initial, config=bootstrap_config(),
        )
        second = packet(
            first_result["post_memory"], time_s=1.0,
            regions=[region(0, 0.05)],
        )
        built = build_causal_prior(
            [first, second],
            config=bootstrap_config(),
            builder_code_sha256="a" * 64,
        )

        receipt = built["receipt"]
        self.assertEqual(receipt["packet_count"], 2)
        self.assertEqual(len(receipt["version_chain_sha256s"]), 3)
        self.assertEqual(len(receipt["committed_update_sha256s"]), 2)
        self.assertEqual(receipt["final_prior_memory_sha256"],
                         built["prior_memory"]["graph_hash"])
        versions = built["prior_memory"]["nodes"]
        self.assertEqual(len(versions), 2)
        self.assertEqual(len({item["node_id"] for item in versions}), 1)
        self.assertEqual(
            [row["observed_templates"] for row in built["prior_memory"]["transaction_log"]],
            [["BIRTH"], ["BIND"]],
        )
        self.assertEqual(
            next(item for item in versions if item["valid_to"] is None)[STATE_KEY][
                "observation_count"
            ],
            2,
        )

    def test_bootstrap_births_first_public_relation_after_endpoint_nodes(self) -> None:
        initial = empty_public_memory()
        current = packet(
            initial, time_s=0.0,
            regions=[region(0, 0.0), region(1, 0.0, kind="place")],
            relations=[{
                "relation_id": "relation:0000",
                "source_region_id": "region:0000",
                "target_region_id": "region:0001",
                "relation": "located_at",
                "reliability": 1.0,
                "support_sha256": "8" * 64,
            }],
        )
        result = advance_public_bootstrap(
            current, initial, config=bootstrap_config(),
        )
        self.assertEqual(len(result["post_memory"]["nodes"]), 2)
        self.assertEqual(len(result["post_memory"]["edges"]), 1)
        self.assertEqual(result["post_memory"]["edges"][0]["relation"], "located_at")
        self.assertEqual(
            result["diagnostics"]["relation_updates"],
            {"born": 1, "bound": 0, "relinked": 0, "inverse_deduplicated": 0},
        )

    def test_audit_identity_changes_receipt_binding_not_prior_or_adapter_bytes(self) -> None:
        initial = empty_public_memory()
        original = packet(initial, time_s=0.0, regions=[region(0, 0.0)])
        changed = deepcopy(original)
        changed["sample_id_hash"] = "b" * 64
        changed["rgbd_refs"] = {
            "rgb_sha256": "c" * 64,
            "depth_sha256": "d" * 64,
        }
        left = build_causal_prior(
            [original], config=bootstrap_config(), builder_code_sha256="a" * 64,
        )
        right = build_causal_prior(
            [changed], config=bootstrap_config(), builder_code_sha256="a" * 64,
        )
        self.assertEqual(left["prior_memory"], right["prior_memory"])
        self.assertEqual(
            left["receipt"]["ordered_adapter_input_sha256s"],
            right["receipt"]["ordered_adapter_input_sha256s"],
        )
        self.assertNotEqual(
            left["receipt"]["ordered_public_packet_sha256s"],
            right["receipt"]["ordered_public_packet_sha256s"],
        )

    def test_prior_reference_mismatch_fails_closed(self) -> None:
        initial = empty_public_memory()
        bad = packet(initial, time_s=0.0, regions=[])
        bad["prior_memory_ref"]["graph_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "digest does not match"):
            build_causal_prior(
                [bad], config=bootstrap_config(), builder_code_sha256="a" * 64,
            )

    def test_receipt_tampering_is_rejected(self) -> None:
        initial = empty_public_memory()
        built = build_causal_prior(
            [packet(initial, time_s=0.0, regions=[])],
            config=bootstrap_config(), builder_code_sha256="a" * 64,
        )
        tampered = deepcopy(built["receipt"])
        tampered["final_prior_memory_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "digest mismatch|does not end"):
            validate_causal_prior_receipt(tampered)


if __name__ == "__main__":
    unittest.main()
