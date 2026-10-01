"""Tests of the S1 generator's worker ops/vsmt/vm04_two_house_worker.py (the live helper of lean_s1_02a_pilot.py).

Kept from the earlier two-house ops tests when the superseded audit and parallel-seal drivers were removed (user, 2026-10-01):
target ranking from mask geometry only, anonymous view support, the initial viewpoint scan, the family scan before dispatch,
private diagnostics kept apart, the legacy-house upgrade, the authored agent pose and the predeclared intervention schedule.
"""
from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKER_ENTRY = PROJECT_ROOT / "ops/vsmt/vm04_two_house_worker.py"
WORKER_SPEC = importlib.util.spec_from_file_location("vm04_two_house_worker", WORKER_ENTRY)
assert WORKER_SPEC is not None and WORKER_SPEC.loader is not None
WORKER = importlib.util.module_from_spec(WORKER_SPEC)
WORKER_SPEC.loader.exec_module(WORKER)


class TwoHouseWorkerTests(unittest.TestCase):
    def test_worker_resource_stop_keeps_remaining_fixed_slots(self) -> None:
        source = WORKER_ENTRY.read_text(encoding="utf-8")
        self.assertIn('"status": "not_started"', source)
        self.assertIn('"reason": "family_resource_stop"', source)
        self.assertIn("break", source)

    def test_worker_target_ranking_uses_mask_geometry_not_private_id(self) -> None:
        import numpy as np

        left = np.zeros((224, 224), dtype=np.bool_)
        right = np.zeros((224, 224), dtype=np.bool_)
        left[10:24, 10:24] = True
        right[10:24, 40:54] = True
        first = WORKER.rank_visible_instance_ids({"private-z": left, "private-a": right})
        second = WORKER.rank_visible_instance_ids({"renamed-a": left, "renamed-z": right})
        self.assertEqual(first, ["private-z", "private-a"])
        self.assertEqual(second, ["renamed-a", "renamed-z"])

    def test_worker_target_ranking_can_require_physical_object_ids(self) -> None:
        import numpy as np

        ceiling = np.zeros((224, 224), dtype=np.bool_)
        object_mask = np.zeros((224, 224), dtype=np.bool_)
        ceiling[:20, :20] = True
        object_mask[40:60, 40:60] = True
        ranked = WORKER.rank_visible_instance_ids(
            {"ceiling|0": ceiling, "object|1": object_mask},
            {"object|1"},
        )
        self.assertEqual(ranked, ["object|1"])

    def test_target_ranking_hashes_only_geometry_ties_without_changing_order(self) -> None:
        import numpy as np

        left = np.zeros((32, 32), dtype=np.bool_)
        right = np.zeros((32, 32), dtype=np.bool_)
        left[:14, :14] = True
        right[16:30, 16:30] = True
        with patch.object(WORKER.hashlib, "sha256",
                          side_effect=AssertionError("untied masks need no digest")):
            self.assertEqual(WORKER.rank_visible_instance_ids(
                {"left": left, "right": right}
            ), ["left", "right"])
        shifted = np.zeros((32, 32), dtype=np.bool_)
        shifted[0, 0] = True
        shifted[1:14, 0:15] = True  # 196 pixels, same first index as left
        self.assertEqual(int(np.count_nonzero(shifted)), 196)
        pairs = []
        for name, mask in (("left", left), ("shifted", shifted)):
            payload = WORKER.canonical_json([32, 32] +
                                             mask.reshape(-1).astype(int).tolist())
            pairs.append((WORKER.hashlib.sha256(payload.encode()).hexdigest(), name))
        self.assertEqual(WORKER.rank_visible_instance_ids(
            {"left": left, "shifted": shifted}
        ), [name for _, name in sorted(pairs)])

    def test_intervention_capability_audit_is_private_and_non_mutating(self) -> None:
        audit = WORKER.audit_intervention_capabilities(
            "REPLACE",
            ["obj-a", "obj-b"],
            {"obj-a": {"position": {}, "isInteractable": True}},
        )
        self.assertEqual(audit["required_target_count"], 2)
        self.assertEqual(audit["objects"][0]["object_id"], "obj-a")
        self.assertTrue(audit["objects"][0]["present_in_metadata_objects"])
        self.assertFalse(audit["objects"][1]["present_in_metadata_objects"])

    def test_relink_audit_records_planned_pose_without_claiming_collision_check(self) -> None:
        audit = WORKER.audit_intervention_capabilities(
            "RELINK", ["obj-a"],
            {"obj-a": {"position": {"x": 1, "y": 2, "z": 3}}},
        )
        self.assertEqual(
            audit["relink_pose_audit"]["planned_position"],
            {"x": 1.5, "y": 2.0, "z": 3.0},
        )
        self.assertFalse(audit["relink_pose_audit"]["collision_or_reachability_checked"])

    def test_anonymous_view_support_ignores_ids_and_small_masks(self) -> None:
        import numpy as np

        first = np.zeros((32, 32), dtype=np.bool_)
        second = np.zeros((32, 32), dtype=np.bool_)
        small = np.zeros((32, 32), dtype=np.bool_)
        first[:14, :14] = True
        second[14:28, 14:28] = True
        small[:13, :13] = True
        self.assertEqual(
            WORKER.anonymous_mask_support({"a": first, "b": second, "c": small}),
            (2, 392),
        )
        self.assertEqual(
            WORKER.anonymous_mask_support({"renamed-z": first, "renamed-y": second}),
            (2, 392),
        )
        self.assertEqual(
            WORKER.anonymous_mask_support(
                {"a": first, "b": second, "c": small}, {"b", "c"}
            ),
            (1, 196),
        )

    def test_initial_viewpoint_prefers_support_then_lexicographic_pose(self) -> None:
        rows = [
            {"position": {"x": 1, "y": 0, "z": 0}, "rotation_y_degrees": 0,
             "eligible_anonymous_mask_count": 3,
             "total_eligible_anonymous_mask_pixels": 700},
            {"position": {"x": 0, "y": 0, "z": 0}, "rotation_y_degrees": 90,
             "eligible_anonymous_mask_count": 3,
             "total_eligible_anonymous_mask_pixels": 700},
            {"position": {"x": -1, "y": 0, "z": 0}, "rotation_y_degrees": 0,
             "eligible_anonymous_mask_count": 2,
             "total_eligible_anonymous_mask_pixels": 900},
        ]
        self.assertEqual(
            WORKER.select_initial_viewpoint(rows)["position"]["x"], 0,
        )

    def test_initial_viewpoint_scans_sorted_positions_and_cardinal_yaws(self) -> None:
        import numpy as np

        mask = np.ones((14, 14), dtype=np.bool_)

        class FakeController:
            def __init__(self):
                self.teleports = []

            def step(self, **action):
                if action["action"] == "GetReachablePositions":
                    return SimpleNamespace(metadata={
                        "lastActionSuccess": True,
                        "actionReturn": [
                            {"x": 1, "y": 0, "z": 0},
                            {"x": 0, "y": 0, "z": 0},
                        ],
                    })
                self.teleports.append((action["x"], action["rotation"]["y"]))
                count = 3 if action["x"] == 1 and action["rotation"]["y"] == 90 else 2
                return SimpleNamespace(
                    metadata={
                        "lastActionSuccess": True,
                        "objects": [
                            {"objectId": "id-%s" % index}
                            for index in range(count)
                        ],
                    },
                    instance_masks={"id-%s" % index: mask for index in range(count)},
                )

        controller = FakeController()
        poses = WORKER.discover_initial_viewpoint(controller)
        pose = WORKER.slot_initial_viewpoint(poses, 0)
        self.assertEqual(pose["position"]["x"], 1.0)
        self.assertEqual(pose["rotation_y_degrees"], 90)
        self.assertNotEqual(pose, WORKER.slot_initial_viewpoint(poses, 1))
        with self.assertRaisesRegex(RuntimeError, "lacks a distinct eligible pose"):
            WORKER.slot_initial_viewpoint(poses, len(poses))
        self.assertEqual(controller.teleports, [
            (x, yaw) for x in (0.0, 1.0) for yaw in (0, 90, 180, 270)
        ])

    def test_family_scan_precedes_slot_dispatch(self) -> None:
        source = inspect.getsource(WORKER.main)
        scan_call = "discover_initial_viewpoint(\n                search_controller, collect_private_targets=True"
        self.assertEqual(source.count(scan_call), 1)
        self.assertLess(source.index(scan_call),
                        source.index("for row_index, public in enumerate(ordered_rows)"))
        self.assertIn("start_pose = slot_initial_viewpoint(", source)
        self.assertIn("ranked_poses, int(public[\"slot\"]), selected_indices", source)

    def test_scan_only_separates_private_targets_and_skips_episode_dispatch(self) -> None:
        source = inspect.getsource(WORKER.main)
        self.assertIn('"private/viewpoint-target-audit.json"', source)
        self.assertLess(source.index("if arguments.scan_only:"),
                        source.index("for row_index, public in enumerate(ordered_rows)"))
        self.assertIn("private_viewpoint_target_audit_sha256", source)

    def test_greedy_spacing_does_not_claim_maximum_possible_yield(self) -> None:
        ranked = [{"position": {"x": x, "y": 0.0, "z": 0.0}}
                  for x in (0.0, -0.75, 0.75)]
        selected = WORKER.select_spaced_viewpoint_indices(ranked, 1.0)
        self.assertEqual(selected, [0])
        self.assertGreater(abs(-0.75 - 0.75), 1.0)

    def test_private_id_renaming_changes_only_scan_diagnostic(self) -> None:
        import numpy as np

        first = np.zeros((32, 32), dtype=np.bool_)
        second = np.zeros((32, 32), dtype=np.bool_)
        first[:14, :14] = True
        second[16:30, 16:30] = True

        class FakeController:
            def __init__(self, prefix):
                self.prefix = prefix

            def step(self, **action):
                if action["action"] == "GetReachablePositions":
                    return SimpleNamespace(metadata={"lastActionSuccess": True,
                        "actionReturn": [{"x": 0, "y": 0, "z": 0},
                                         {"x": 1, "y": 0, "z": 0}]})
                masks = {self.prefix + "1": first, self.prefix + "2": second}
                return SimpleNamespace(
                    metadata={"lastActionSuccess": True,
                              "objects": [{"objectId": key} for key in masks]},
                    instance_masks=masks,
                )

        public_a, private_a = WORKER.discover_initial_viewpoint(
            FakeController("a"), collect_private_targets=True
        )
        public_b, private_b = WORKER.discover_initial_viewpoint(
            FakeController("b"), collect_private_targets=True
        )
        self.assertEqual(public_a, public_b)
        self.assertEqual(WORKER.select_spaced_viewpoint_indices(public_a, 1.0),
                         WORKER.select_spaced_viewpoint_indices(public_b, 1.0))
        self.assertNotEqual(private_a, private_b)

    def test_failed_intervention_keeps_private_action_diagnostic(self) -> None:
        import numpy as np

        mask = np.ones((14, 14), dtype=np.bool_)

        class FakeController:
            def __init__(self):
                self.stopped = False

            def step(self, **action):
                if action["action"] == "TeleportFull":
                    return SimpleNamespace(metadata={
                        "lastActionSuccess": True,
                        "objects": [{"objectId": "object|1", "position": {}}],
                    }, instance_masks={"object|1": mask})
                return SimpleNamespace(metadata={
                    "lastActionSuccess": False, "errorMessage": "disabled failed",
                    "errorCode": "UnsupportedAction",
                })

            def stop(self):
                self.stopped = True

        fake = FakeController()
        assignment = {"episode_id": "opaque", "family_id": "family", "slot": 0,
                      "program": "BIRTH", "replicate": 0}
        start_pose = {"position": {"x": 0, "y": 0, "z": 0},
                      "rotation_y_degrees": 0, "horizon_degrees": 0,
                      "standing": True}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(WORKER, "make_controller", return_value=fake):
                with self.assertRaisesRegex(RuntimeError, "setup intervention failed"):
                    WORKER.run_episode({}, assignment, root, 100000, start_pose,
                                       "0" * 64)
            attempts = json.loads((root / "private/intervention-attempts.json").read_text())
            self.assertEqual(attempts["actions"][0]["diagnostic"]["error_code"],
                             "UnsupportedAction")
            self.assertTrue((root / "private/intervention-capability-audit.json").exists())
            self.assertFalse((root / "public/intervention-attempts.json").exists())
            self.assertTrue(fake.stopped)

    def test_legacy_house_upgrade_is_deterministic_and_does_not_mutate_source(self) -> None:
        source = {
            "metadata": {"schema": "0.0.1"},
            "proceduralParameters": {
                "ceilingMaterial": "White", "ceilingColor": {"r": 1},
            },
            "rooms": [{"floorMaterial": "Wood", "ceilings": []}],
            "walls": [{
                "id": "wall|exterior|0", "material": "Brick", "color": {"r": 0},
            }],
            "windows": [{
                "assetId": "window-a",
                "boundingBox": {
                    "min": {"x": 1, "y": 2, "z": 0},
                    "max": {"x": 3, "y": 6, "z": 0},
                },
                "assetOffset": {"x": 0.5, "y": 0.25, "z": 0},
            }],
            "doors": [],
            "objects": [],
        }
        frozen = json.loads(json.dumps(source))
        assets = {"window-a": {"boundingBox": {"x": 2, "y": 4, "z": 0.1}}}
        first = WORKER.upgrade_house_schema_v1(source, assets)
        second = WORKER.upgrade_house_schema_v1(source, assets)
        self.assertEqual(source, frozen)
        self.assertEqual(first, second)
        self.assertEqual(first["metadata"]["schema"], "1.0.0")
        self.assertEqual(first["rooms"][0]["floorMaterial"], {"name": "Wood"})
        self.assertEqual(first["walls"][0]["roomId"], "exterior")
        self.assertEqual(first["windows"][0]["holePolygon"][0]["x"], 1)
        self.assertEqual(first["windows"][0]["assetPosition"], {
            "x": 2.5, "y": 4.25, "z": 0,
        })

    def test_house_agent_bootstrap_uses_authored_pose(self) -> None:
        class FakeController:
            def __init__(self):
                self.action = None

            def step(self, **action):
                self.action = action
                return SimpleNamespace(metadata={"lastActionSuccess": True})

        controller = FakeController()
        event = WORKER.bootstrap_house_agent(controller, {"metadata": {"agent": {
            "position": {"x": 1, "y": 0.95, "z": 2},
            "rotation": {"x": 0, "y": 270, "z": 0},
            "horizon": 30, "standing": True,
        }}})
        self.assertTrue(event.metadata["lastActionSuccess"])
        self.assertEqual(controller.action, {
            "action": "TeleportFull", "x": 1.0, "y": 0.95, "z": 2.0,
            "rotation": {"x": 0.0, "y": 270.0, "z": 0.0},
            "horizon": 30.0, "standing": True, "forceAction": True,
        })

    def test_worker_intervention_schedule_is_predeclared(self) -> None:
        objects = {
            "a": {"position": {"x": 1.0, "y": 0.5, "z": 2.0},
                  "rotation": {"x": 0, "y": 0, "z": 0}},
            "b": {"position": {"x": 2.0, "y": 0.5, "z": 2.0}},
        }
        self.assertEqual(
            WORKER.intervention_actions("RETRACT", 22, ["a"], objects),
            [{"action": "DisableObject", "objectId": "a"}],
        )
        relink = WORKER.intervention_actions("RELINK", 24, ["a"], objects)
        self.assertEqual(relink[0]["position"]["x"], 1.5)
        self.assertEqual(
            WORKER.intervention_actions("REPLACE", -1, ["a", "b"], objects),
            [{"action": "DisableObject", "objectId": "b"}],
        )
        self.assertEqual(
            WORKER.intervention_actions("REPLACE", 24, ["a", "b"], objects),
            [{"action": "EnableObject", "objectId": "b"}],
        )

    def test_every_frame_has_a_predeclared_registered_public_action(self) -> None:
        first = [WORKER.registered_agent_action(0, index) for index in range(32)]
        second = [WORKER.registered_agent_action(1, index) for index in range(32)]
        self.assertTrue(all(
            action[0]["action"] in {"RotateLeft", "RotateRight"}
            and action[0]["degrees"] == 0.25 and len(action[1]) == 2
            for action in first + second
        ))
        self.assertEqual(first[0][0]["action"], "RotateRight")
        self.assertEqual(second[0][0]["action"], "RotateLeft")


if __name__ == "__main__":
    unittest.main()
