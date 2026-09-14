from __future__ import annotations

import hashlib
import math
from pathlib import Path
import sys
import unittest

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from cpmt.executor import ContractError, execute_transaction  # noqa: E402
from cpmt.hashing import seal_graph  # noqa: E402
from vsmt.contracts import validate_observation_packet  # noqa: E402
from vsmt.graph_ops import STATE_KEY, fully_covered_by_free_space  # noqa: E402
from vsmt.l1_entities import DINORegionConfig  # noqa: E402
from vsmt.l1_structures import (  # noqa: E402
    FreeSpaceMaterializationConfig,
    MaterializedRegion,
    PlaceMaterializationConfig,
    SurfaceMaterializationConfig,
    assemble_free_space_history,
    assemble_region_records,
    materialize_public_free_space,
    materialize_public_places,
    materialize_public_relations,
    materialize_public_surfaces,
)


def descriptor_config() -> DINORegionConfig:
    return DINORegionConfig(
        image_height=224,
        image_width=224,
        patch_size_pixels=14,
        patch_token_dimension=4,
        minimum_total_patch_weight=1.0,
        unit_norm_validation_tolerance=0.00001,
    )


def surface_config() -> SurfaceMaterializationConfig:
    return SurfaceMaterializationConfig(
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
    )


def place_config() -> PlaceMaterializationConfig:
    return PlaceMaterializationConfig(
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
    )


def free_config() -> FreeSpaceMaterializationConfig:
    return FreeSpaceMaterializationConfig(
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
    )


def calibration() -> dict[str, float]:
    return {"fx": 112.0, "fy": 112.0, "cx": 111.5, "cy": 111.5}


def patch_tokens() -> np.ndarray:
    values = np.zeros((16, 16, 4), dtype=np.float32)
    values[..., 0] = 1.0
    return values


def mask_digest(mask: np.ndarray) -> str:
    return hashlib.sha256(mask.astype(np.uint8).tobytes()).hexdigest()


class PublicStructureMaterializerTests(unittest.TestCase):
    def test_floor_depth_yields_surface_and_observed_place_cells(self) -> None:
        depth = np.full((224, 224), 1.575, dtype=np.float32)
        half = math.sqrt(0.5)
        pose = {
            "position_m": [0.0, 1.575, 0.0],
            "quaternion_xyzw": [half, 0.0, 0.0, half],
        }
        surfaces = materialize_public_surfaces(
            depth, calibration(), pose, patch_tokens(), descriptor_config(),
            surface_config(),
        )
        self.assertEqual(len(surfaces), 1)
        self.assertEqual(surfaces[0].structure_kind, "surface")
        self.assertGreaterEqual(sum(surfaces[0].mask_values), 784)
        self.assertAlmostEqual(abs(surfaces[0].plane_normal[1]), 1.0, places=6)
        places = materialize_public_places(
            surfaces, depth, calibration(), pose, patch_tokens(),
            descriptor_config(), surface_config(), place_config(),
        )
        self.assertTrue(places)
        self.assertTrue(all(item.structure_kind == "place" for item in places))
        self.assertTrue(all(item.extent_m == (0.5, 0.0, 0.5) for item in places))
        self.assertTrue(all(item.reliability >= 16 / 25 for item in places))

    def test_curved_depth_does_not_pass_planar_surface_contract(self) -> None:
        rows, columns = np.indices((224, 224))
        depth = np.where((rows + columns) % 2 == 0, 1.0, 2.0).astype(np.float32)
        surfaces = materialize_public_surfaces(
            depth, calibration(), {
                "position_m": [0.0, 0.0, 0.0],
                "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
            }, patch_tokens(), descriptor_config(), surface_config(),
        )
        self.assertEqual(surfaces, ())

    def test_multiscale_free_space_has_341_frusta_and_rolling_history(self) -> None:
        depth = np.full((224, 224), 2.0, dtype=np.float32)
        pose = {
            "position_m": [0.0, 0.0, 0.0],
            "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
        }
        first = materialize_public_free_space(
            depth, calibration(), pose, time_s=0.0,
            depth_sha256="1" * 64,
            camera_calibration_and_pose_sha256="2" * 64,
            config=free_config(),
        )
        second = materialize_public_free_space(
            depth, calibration(), pose, time_s=0.3,
            depth_sha256="3" * 64,
            camera_calibration_and_pose_sha256="2" * 64,
            config=free_config(),
        )
        self.assertEqual(len(first), 341)
        history = assemble_free_space_history(
            [first, second], rolling_public_observation_times=4,
        )
        self.assertEqual(len(history), 682)
        self.assertEqual(history[0]["free_space_id"], "free:0000")
        self.assertEqual(history[-1]["free_space_id"], "free:0681")
        node = {
            "node_type": "entity",
            STATE_KEY: {
                "descriptor": [1.0],
                "centroid_m": [0.0, 0.0, 1.0],
                "extent_m": [0.1, 0.1, 0.1],
                "reliability": 1.0,
                "last_seen_s": 0.0,
                "observation_count": 1,
            },
        }
        self.assertTrue(fully_covered_by_free_space(
            node, history, minimum_reliability=1.0,
            target_expansion_m=0.02,
        ))

    def test_invalid_depth_pixel_rejects_every_block_containing_it(self) -> None:
        depth = np.full((224, 224), 2.0, dtype=np.float32)
        depth[3, 3] = np.nan
        result = materialize_public_free_space(
            depth, calibration(), {
                "position_m": [0.0, 0.0, 0.0],
                "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
            }, time_s=0.0, depth_sha256="1" * 64,
            camera_calibration_and_pose_sha256="2" * 64,
            config=free_config(),
        )
        self.assertEqual(len(result), 336)


class PublicRelationTests(unittest.TestCase):
    def _region(
        self, kind: str, centroid: tuple[float, float, float],
        extent: tuple[float, float, float], mask: np.ndarray, *,
        place_cell: tuple[int, int] | None = None,
        plane: bool = False,
    ) -> MaterializedRegion:
        return MaterializedRegion(
            structure_kind=kind,
            mask_sha256=mask_digest(mask),
            mask_values=tuple(int(value) for value in mask.reshape(-1)),
            height=mask.shape[0],
            width=mask.shape[1],
            descriptor=(1.0, 0.0),
            centroid_m=centroid,
            extent_m=extent,
            reliability=0.8,
            proposal_source_id=f"fixture.{kind}.v1",
            plane_normal=(0.0, 1.0, 0.0) if plane else None,
            plane_offset_m=0.0 if plane else None,
            place_cell_xz=place_cell,
        )

    def test_relations_are_public_typed_and_contains_is_same_evidence(self) -> None:
        entity_mask = np.zeros((4, 4), dtype=np.bool_)
        entity_mask[0, 0] = True
        place_mask = np.zeros((4, 4), dtype=np.bool_)
        place_mask[1, 1] = True
        surface_mask = np.zeros((4, 4), dtype=np.bool_)
        surface_mask[3, 3] = True
        entity = self._region(
            "entity", (0.25, 0.1, 0.25), (0.1, 0.2, 0.1), entity_mask,
        )
        place = self._region(
            "place", (0.25, 0.0, 0.25), (0.5, 0.0, 0.5), place_mask,
            place_cell=(0, 0), plane=True,
        )
        surface = self._region(
            "surface", (0.25, 0.0, 0.25), (1.0, 0.0, 1.0),
            surface_mask, plane=True,
        )
        records, indexed = assemble_region_records([entity], [place], [surface])
        relations = materialize_public_relations(
            indexed, place_config=place_config(),
            supported_by_maximum_normal_angle_degrees=10.0,
            supported_by_minimum_gap_m=-0.02,
            supported_by_maximum_gap_m=0.05,
            supported_by_minimum_projected_overlap=0.25,
            supported_by_maximum_mask_overlap_fraction=0.05,
        )
        self.assertEqual(
            {item["relation"] for item in relations},
            {"located_at", "contains", "supported_by"},
        )
        located = next(item for item in relations if item["relation"] == "located_at")
        contains = next(item for item in relations if item["relation"] == "contains")
        self.assertEqual(located["support_sha256"], contains["support_sha256"])
        packet = {
            "schema_version": "vsmt-observation-packet-v2",
            "sample_id_hash": "1" * 64,
            "decision_time_s": 1.0,
            "rgbd_refs": {"rgb_sha256": "2" * 64, "depth_sha256": "3" * 64},
            "camera_pose": {
                "position_m": [0.0, 0.0, 0.0],
                "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
            },
            "robot_state": {"feature_names": [], "values": []},
            "past_actions": [],
            "region_observations": records,
            "relation_observations": relations,
            "free_space_observations": [],
            "prior_memory_ref": {"graph_version": "v0", "graph_sha256": "4" * 64},
            "public_constants": {
                "coordinate_frame": "map",
                "depth_unit": "metre",
                "descriptor_model_id": "dinov2.vits14",
                "proposal_model_id": "fixed.region.v2",
            },
        }
        validate_observation_packet(packet)


class TypedRelationExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = seal_graph({
            "schema_version": "cpmt-0.2",
            "graph_id": "graph:typed-relation",
            "graph_version": "v0",
            "parent_version": None,
            "nodes": [
                {
                    "node_id": node_id,
                    "node_version_id": f"{node_id}@v0",
                    "node_type": node_type,
                    "lifecycle": "confirmed",
                    "valid_from": 0,
                    "valid_to": None,
                    "evidence_refs": [f"observation:{node_id}"],
                    "latent_refs": [],
                    "canonical_id": None,
                    "predecessor_ids": [],
                    "provenance": ["fixture:public"],
                }
                for node_id, node_type in (("entity-a", "entity"), ("place-a", "place"))
            ],
            "edges": [],
            "transaction_log": [],
        })

    def test_relation_birth_then_relation_bind(self) -> None:
        edge = {
            "edge_id": "edge:located",
            "edge_version_id": "edge:located@v0",
            "source": "entity-a",
            "target": "place-a",
            "relation": "located_at",
            "frame": "map",
            "valid_from": 1,
            "valid_to": None,
            "evidence_refs": ["observation:first"],
            "provenance": ["transaction:birth-relation"],
        }
        born = execute_transaction(self.graph, {
            "schema_version": "cpmt-0.2",
            "transaction_id": "transaction:birth-relation",
            "intent": "EXPAND",
            "template": "BIRTH",
            "base_graph_version": "v0",
            "operations": [{
                "op_id": "birth:edge",
                "op_type": "ADD_EDGE",
                "arguments": {"edge": edge},
            }],
            "evidence_refs": ["observation:first"],
            "protected_ids": [],
        })
        self.assertEqual(len(born["edges"]), 1)
        bound = execute_transaction(born, {
            "schema_version": "cpmt-0.2",
            "transaction_id": "transaction:bind-relation",
            "intent": "ASSOCIATE",
            "template": "BIND",
            "base_graph_version": born["graph_version"],
            "operations": [
                {
                    "op_id": "bind:edge",
                    "op_type": "ATTACH_EVIDENCE",
                    "arguments": {
                        "target_kind": "edge",
                        "target_id": "edge:located",
                        "evidence_ref": "observation:second",
                    },
                },
                {
                    "op_id": "bind:edge-provenance",
                    "op_type": "RECORD_PROVENANCE",
                    "arguments": {
                        "target_kind": "edge",
                        "target_id": "edge:located",
                        "provenance_ref": "transaction:bind-relation",
                    },
                },
            ],
            "evidence_refs": ["observation:second"],
            "protected_ids": [],
        })
        self.assertIn("observation:second", bound["edges"][0]["evidence_refs"])
        second_edge = dict(edge)
        second_edge.update({
            "edge_id": "edge:located-second",
            "edge_version_id": "edge:located-second@v0",
            "evidence_refs": ["observation:third"],
            "provenance": ["transaction:birth-second-relation"],
        })
        two_edges = execute_transaction(bound, {
            "schema_version": "cpmt-0.2",
            "transaction_id": "transaction:birth-second-relation",
            "intent": "EXPAND",
            "template": "BIRTH",
            "base_graph_version": bound["graph_version"],
            "operations": [{
                "op_id": "birth:second-edge",
                "op_type": "ADD_EDGE",
                "arguments": {"edge": second_edge},
            }],
            "evidence_refs": ["observation:third"],
            "protected_ids": [],
        })
        with self.assertRaisesRegex(
            ContractError, "relation BIND must target exactly one edge identity",
        ):
            execute_transaction(two_edges, {
                "schema_version": "cpmt-0.2",
                "transaction_id": "transaction:bad-multi-edge-bind",
                "intent": "ASSOCIATE",
                "template": "BIND",
                "base_graph_version": two_edges["graph_version"],
                "operations": [
                    {
                        "op_id": f"bind:edge:{index}",
                        "op_type": "ATTACH_EVIDENCE",
                        "arguments": {
                            "target_kind": "edge",
                            "target_id": edge_id,
                            "evidence_ref": "observation:fourth",
                        },
                    }
                    for index, edge_id in enumerate(
                        ("edge:located", "edge:located-second")
                    )
                ] + [{
                    "op_id": "bind:multi-edge-provenance",
                    "op_type": "RECORD_PROVENANCE",
                    "arguments": {
                        "target_kind": "edge",
                        "target_id": "edge:located",
                        "provenance_ref": "transaction:bad-multi-edge-bind",
                    },
                }],
                "evidence_refs": ["observation:fourth"],
                "protected_ids": [],
            })

    def test_relation_birth_rejects_a_node_and_edge_in_same_atom(self) -> None:
        with self.assertRaisesRegex(ContractError, "exactly one node or edge"):
            execute_transaction(self.graph, {
                "schema_version": "cpmt-0.2",
                "transaction_id": "transaction:bad-birth",
                "intent": "EXPAND",
                "template": "BIRTH",
                "base_graph_version": "v0",
                "operations": [
                    {
                        "op_id": "birth:node",
                        "op_type": "CREATE_NODE",
                        "arguments": {"node": self.graph["nodes"][0]},
                    },
                    {
                        "op_id": "birth:edge",
                        "op_type": "ADD_EDGE",
                        "arguments": {"edge": {
                            "edge_id": "edge:bad",
                            "edge_version_id": "edge:bad@v0",
                            "source": "entity-a",
                            "target": "place-a",
                            "relation": "located_at",
                            "frame": "map",
                            "valid_from": 1,
                            "valid_to": None,
                            "evidence_refs": ["observation:bad"],
                            "provenance": ["transaction:bad-birth"],
                        }},
                    },
                ],
                "evidence_refs": ["observation:bad"],
                "protected_ids": [],
            })
