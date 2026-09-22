"""D-224-S1 ruling 45 / S1-04: the per-episode object geometry table and the truth boxes it yields.

What is pinned here: the table's fields are the S0-02 v3 contract's fields; a truth box is the
reload's initial box translated by the recorded private position and expressed in the episode
frame; presence flips only for removed objects and only after the unobservable window; a moved
object's position comes from the placement point until it is seen again; the IoU arithmetic is
the S0-04 evaluator's; the private-mask backprojection lands in the same frame as the S1-03
fragment box; and the drift check reports rather than hides a non-intervened object that moved.
No simulator is started.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vsmt import lean_frontend_cache as fc  # noqa: E402
from vsmt import lean_object_geometry as og  # noqa: E402
from vsmt.lean_intervention import PRIVATE_HOUSE_GEOMETRY_FIELDS, PRIVATE_HOUSE_GEOMETRY_FILE  # noqa: E402
from vsmt.lean_teacher import _aabb_iou as teacher_iou  # noqa: E402
from vsmt.shared_frontend_core import PublicGeometryConfig  # noqa: E402

CONTRACT_PATH = PROJECT_ROOT / "configs" / "vsmt" / "lean_s0_intervention_data_v3.json"


def xyz(x: float, y: float, z: float) -> dict[str, float]:
    return {"x": x, "y": y, "z": z}


def metadata_objects() -> list[dict]:
    return [
        {"objectId": "Chair|1", "assetId": "Chair_1", "objectType": "Chair", "pickupable": False, "receptacle": True,
         "position": xyz(3.0, 0.0, 2.0), "rotation": xyz(0.0, 90.0, 0.0),
         "axisAlignedBoundingBox": {"center": xyz(3.1, 0.45, 2.0), "size": xyz(0.5, 0.9, 0.5)}},
        {"objectId": "Mug|2", "assetId": "Mug_2", "objectType": "Mug", "pickupable": True, "receptacle": False,
         "position": xyz(1.0, 0.9, 1.0), "rotation": xyz(0.0, 0.0, 0.0),
         "axisAlignedBoundingBox": {"center": xyz(1.0, 0.95, 1.0), "size": xyz(0.1, 0.1, 0.1)}},
        {"objectId": "Wall|9", "assetId": None, "objectType": "Wall", "pickupable": False, "receptacle": False,
         "position": xyz(0.0, 1.0, 0.0), "rotation": xyz(0.0, 0.0, 0.0)},
    ]


def table() -> dict:
    return og.build_geometry_table(
        episode_id="procthor10k-0.1.2-train-00001", house_id="procthor10k-0.1.2-train-00001", source_index=1,
        code_commit="abc123", metadata_objects=metadata_objects(), camera_position_world=xyz(0.5, 1.5, -0.5),
        agent_pose={"position": xyz(0.5, 0.9, -0.5), "rotation": xyz(0.0, 0.0, 0.0), "cameraHorizon": 30.0})


def private_record(index: int, poses: dict[str, dict[str, float]]) -> dict:
    ids = sorted(poses)
    return {"observation_index": index, "instance_mask_path": f"{index:04d}.instance.png",
            "object_id_to_entity_id": {oid: n for n, oid in enumerate(ids, start=1)},
            "object_poses": dict(poses), "object_visibility": {oid: 300 for oid in ids}, "frame_digest": "a" * 64}


class TableTests(unittest.TestCase):
    def test_the_table_binds_the_contract_fields_and_file_name(self) -> None:
        self.assertEqual(og.OBJECT_FIELDS, PRIVATE_HOUSE_GEOMETRY_FIELDS)
        self.assertEqual(og.TABLE_FILE_NAME, PRIVATE_HOUSE_GEOMETRY_FILE)
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))["private_house_geometry"]
        self.assertEqual(tuple(contract["fields"]), og.OBJECT_FIELDS)
        self.assertEqual(contract["file"], og.TABLE_FILE_NAME)

    def test_rows_are_sorted_converted_and_a_missing_box_is_counted_not_dropped(self) -> None:
        built = table()
        self.assertEqual(tuple(built.keys()), og.TABLE_FIELDS)
        self.assertEqual([row["object_id"] for row in built["objects"]], ["Chair|1", "Mug|2", "Wall|9"])
        self.assertEqual(built["objects"][0]["initial_aabb_size_m"], [0.5, 0.9, 0.5])
        self.assertEqual(built["objects"][0]["initial_rotation_degrees"], [0.0, 90.0, 0.0])
        self.assertEqual(built["objects_without_box"], ["Wall|9"])
        self.assertIsNone(built["objects"][2]["initial_aabb_center_world_m"])
        self.assertEqual(built["episode_origin_world_m"], [0.5, 1.5, -0.5])
        self.assertEqual(og.validate_geometry_table(json.loads(json.dumps(built))), built)

    def test_a_tampered_row_or_digest_is_refused(self) -> None:
        built = table()
        broken = json.loads(json.dumps(built))
        broken["objects"][0]["initial_aabb_size_m"] = [0.6, 0.9, 0.5]
        with self.assertRaises(og.LeanObjectGeometryError) as caught:
            og.validate_geometry_table(broken)
        self.assertEqual(str(caught.exception), "table_digest_mismatch")
        broken = json.loads(json.dumps(built))
        broken["objects"][0]["initial_aabb_size_m"] = None
        with self.assertRaises(og.LeanObjectGeometryError) as caught:
            og.validate_geometry_table(broken)
        self.assertEqual(str(caught.exception), "object_box_half_missing:Chair|1")
        with self.assertRaises(og.LeanObjectGeometryError):
            og.build_geometry_table(episode_id="e", house_id="h", source_index=0, code_commit="c",
                                    metadata_objects=metadata_objects() + [metadata_objects()[0]],
                                    camera_position_world=xyz(0, 0, 0),
                                    agent_pose={"position": xyz(0, 0, 0), "rotation": xyz(0, 0, 0)})


class TruthBoxTests(unittest.TestCase):
    def test_the_box_translates_with_the_recorded_position_and_lands_in_the_episode_frame(self) -> None:
        built = table()
        chair = built["objects"][0]
        lower, upper = og.truth_box(chair, [5.5, 0.0, 2.0], built["episode_origin_world_m"])
        # centre 3.1 + (5.5 - 3.0) = 5.6 in world, minus origin 0.5 -> 5.1; half sizes 0.25 / 0.45 / 0.25
        self.assertEqual([round(v, 9) for v in lower], [4.85, -1.5, 2.25])
        self.assertEqual([round(v, 9) for v in upper], [5.35, -0.6, 2.75])
        self.assertEqual([round(b - a, 9) for a, b in zip(lower, upper)], [0.5, 0.9, 0.5])
        with self.assertRaises(og.LeanObjectGeometryError):
            og.truth_box(built["objects"][2], [0.0, 0.0, 0.0], built["episode_origin_world_m"])

    def test_iou_matches_the_evaluator_and_union_grows_a_box(self) -> None:
        rng = np.random.default_rng(45)
        for _ in range(50):
            a = rng.uniform(-2, 2, size=(2, 3)); b = rng.uniform(-2, 2, size=(2, 3))
            la, ua = np.minimum(a[0], a[1]), np.maximum(a[0], a[1])
            lb, ub = np.minimum(b[0], b[1]), np.maximum(b[0], b[1])
            self.assertEqual(og.aabb_iou(la, ua, lb, ub), teacher_iou(la, ua, lb, ub))
        self.assertEqual(og.aabb_iou([0, 0, 0], [1, 1, 1], [0, 0, 0], [1, 1, 1]), 1.0)
        lower, upper = og.union_box(None, None, [0, 0, 0], [1, 1, 1])
        lower, upper = og.union_box(lower, upper, [-1, 0.5, 0.5], [0.5, 2, 0.5])
        self.assertEqual((lower, upper), ([-1.0, 0.0, 0.0], [1.0, 2.0, 1.0]))


class TrackerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.table = table()
        self.executed = [
            {"kind": "remove", "object_id": "Chair|1", "executed": True},
            {"kind": "move", "object_id": "Mug|2", "executed": True, "point": xyz(4.0, 0.9, 4.0)},
        ]

    def test_presence_flips_after_the_window_and_positions_follow_the_private_record(self) -> None:
        tracker = og.EpisodeTruthTracker(self.table, executed_interventions=self.executed, window=[2, 3])
        self.assertEqual(tracker.intervened_ids(), {"Chair|1", "Mug|2"})
        # frame 0: both seen at their initial positions
        truth = tracker.update(0, private_record(0, {"Chair|1": xyz(3.0, 0.0, 2.0), "Mug|2": xyz(1.0, 0.9, 1.0), "door|4": xyz(0, 0, 0)}))
        self.assertTrue(truth["Chair|1"]["present"] and truth["Mug|2"]["present"] and truth["Wall|9"]["present"])
        self.assertEqual(truth["Mug|2"]["position_source"], "private_record")
        self.assertEqual([round(v, 9) for v in truth["Mug|2"]["centroid_m"]], [0.5, -0.55, 1.5])
        self.assertIsNone(truth["Wall|9"]["aabb_min_m"])
        self.assertNotIn("door|4", truth)
        # frames 1..3: nothing seen; inside the window everything is still present at its last position
        for index in (1, 2, 3):
            truth = tracker.update(index, private_record(index, {}))
            self.assertTrue(truth["Chair|1"]["present"])
            self.assertEqual(truth["Mug|2"]["position_source"], "private_record")
        # frame 4 (after the window): the chair is gone, the mug sits at its placement point
        truth = tracker.update(4, private_record(4, {}))
        self.assertFalse(truth["Chair|1"]["present"])
        self.assertNotIn("aabb_min_m", truth["Chair|1"])
        self.assertEqual(truth["Mug|2"]["position_source"], "placement_point")
        self.assertEqual([round(v, 9) for v in truth["Mug|2"]["centroid_m"]], [3.5, -0.55, 4.5])
        # frame 5: the mug is seen again, the private record wins
        truth = tracker.update(5, private_record(5, {"Mug|2": xyz(4.02, 0.9, 4.01)}))
        self.assertEqual(truth["Mug|2"]["position_source"], "private_record")
        self.assertEqual([round(v, 9) for v in truth["Mug|2"]["centroid_m"]], [3.52, -0.55, 4.51])
        with self.assertRaises(og.LeanObjectGeometryError):
            tracker.update(7, private_record(7, {}))

    def test_interventions_need_a_window_and_a_known_object(self) -> None:
        with self.assertRaises(og.LeanObjectGeometryError) as caught:
            og.EpisodeTruthTracker(self.table, executed_interventions=self.executed, window=None)
        self.assertEqual(str(caught.exception), "interventions_without_window")
        with self.assertRaises(og.LeanObjectGeometryError) as caught:
            og.EpisodeTruthTracker(self.table, executed_interventions=[{"kind": "remove", "object_id": "Ghost|0"}], window=[0, 1])
        self.assertEqual(str(caught.exception), "intervened_object_not_in_table:Ghost|0")
        tracker = og.EpisodeTruthTracker(self.table, executed_interventions=[], window=None)
        self.assertEqual(tracker.update(0, private_record(0, {}))["Chair|1"]["position_source"], "initial")


class ResidualTests(unittest.TestCase):
    CALIBRATION = {"fx": 112.0, "fy": 112.0, "cx": 111.5, "cy": 111.5}
    POSE = {"position_m": [0.25, 1.5, -0.75], "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0]}
    GEOMETRY = PublicGeometryConfig(
        depth_convention="ai2thor_linear01_camera_axis_z_m", minimum_depth_m=0.05, maximum_depth_m=20.0,
        absolute_minimum_valid_depth_points=32, minimum_valid_depth_fraction=0.25)

    def test_private_mask_backprojection_lands_in_the_s1_03_fragment_frame(self) -> None:
        mask = np.zeros((48, 48), dtype=bool)
        mask[10:30, 12:36] = True
        depth = np.full((48, 48), 2.0, dtype=np.float32)
        depth[15:20, 20:25] = 1.5
        points = og.backproject_mask(mask, depth, self.CALIBRATION, self.POSE, minimum_depth_m=0.05, maximum_depth_m=20.0)
        lower, upper = fc.fragment_aabb(mask, depth, self.CALIBRATION, self.POSE, self.GEOMETRY)
        self.assertEqual(points.shape, (int(mask.sum()), 3))
        self.assertEqual([float(v) for v in points.min(axis=0)], lower)
        self.assertEqual([float(v) for v in points.max(axis=0)], upper)
        self.assertEqual(og.containment_fraction(points, lower, upper, margin_m=0.0), 1.0)
        self.assertEqual(og.containment_fraction(points, [u + 1.0 for u in upper], [u + 2.0 for u in upper]), 0.0)
        self.assertIsNone(og.containment_fraction(points[:0], lower, upper))

    def test_drift_reports_a_non_intervened_object_that_moved_and_skips_intervened_ones(self) -> None:
        built = table()
        records = [
            private_record(0, {"Chair|1": xyz(3.0, 0.0, 2.0), "Mug|2": xyz(1.0, 0.9, 1.0)}),
            private_record(1, {"Chair|1": xyz(3.0, 0.0, 2.02), "Mug|2": xyz(1.0, 0.9, 1.0), "door|4": xyz(9, 9, 9)}),
        ]
        report = og.drift_report(built, records, intervened_ids=[])
        self.assertEqual(report["objects_observed"], 2)
        self.assertAlmostEqual(report["max_drift_m"], 0.02)
        self.assertEqual(report["objects_over_tolerance"], ["Chair|1"])
        report = og.drift_report(built, records, intervened_ids=["Chair|1"])
        self.assertEqual(report["objects_observed"], 1)
        self.assertEqual(report["objects_over_tolerance"], [])
        self.assertEqual(report["max_drift_m"], 0.0)


if __name__ == "__main__":
    unittest.main()
