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
ENTRY = PROJECT_ROOT / "ops/vsmt/vm04_two_house_audit.py"
SPEC = importlib.util.spec_from_file_location("vm04_two_house_audit", ENTRY)
assert SPEC is not None and SPEC.loader is not None
OPS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OPS)
WORKER_ENTRY = PROJECT_ROOT / "ops/vsmt/vm04_two_house_worker.py"
WORKER_SPEC = importlib.util.spec_from_file_location("vm04_two_house_worker", WORKER_ENTRY)
assert WORKER_SPEC is not None and WORKER_SPEC.loader is not None
WORKER = importlib.util.module_from_spec(WORKER_SPEC)
WORKER_SPEC.loader.exec_module(WORKER)
PARALLEL_ENTRY = PROJECT_ROOT / "ops/vsmt/vm04_public_seal_parallel.py"
PARALLEL_SPEC = importlib.util.spec_from_file_location(
    "vm04_public_seal_parallel", PARALLEL_ENTRY
)
assert PARALLEL_SPEC is not None and PARALLEL_SPEC.loader is not None
PARALLEL = importlib.util.module_from_spec(PARALLEL_SPEC)
PARALLEL_SPEC.loader.exec_module(PARALLEL)


class TwoHouseOpsTests(unittest.TestCase):
    def test_source_inventory_reads_explicit_author_train_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "train.json"
            source.write_text(json.dumps({"train": [
                {"id": "house-a", "rooms": []},
                {"id": "house-b", "rooms": []},
            ]}), encoding="utf-8")
            license_path = root / "LICENSE"
            license_path.write_text("test license", encoding="utf-8")
            rows, licenses = OPS.inventory_source_rows(
                root, [Path("train.json")], [license_path],
            )
            self.assertEqual([row["house_id"] for row in rows], ["house-a", "house-b"])
            self.assertEqual(rows[0]["source_locator"], {
                "relative_path": "train.json", "index": 0,
            })
            self.assertEqual(licenses[0]["name"], "LICENSE")

    def test_missing_source_ids_receive_stable_train_ordinals(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "train.jsonl"
            source.write_text('{"rooms": []}\n{"rooms": [1]}\n', encoding="utf-8")
            license_path = root / "LICENSE"
            license_path.write_text("license", encoding="utf-8")
            rows, _ = OPS.inventory_source_rows(
                root, [source], [license_path],
            )
            self.assertEqual(
                [row["house_id"] for row in rows],
                ["train:000000", "train:000001"],
            )

    def test_source_path_may_not_escape_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as other:
            root = Path(directory)
            outside = Path(other) / "train.json"
            outside.write_text("[]", encoding="utf-8")
            license_path = root / "LICENSE"
            license_path.write_text("license", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "escapes"):
                OPS.inventory_source_rows(root, [outside], [license_path])
            train = root / "train.json"
            train.write_text("[]", encoding="utf-8")
            outside_license = Path(other) / "LICENSE"
            outside_license.write_text("license", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "license file escapes"):
                OPS.inventory_source_rows(root, [train], [outside_license])
            validation = root / "val.json"
            validation.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "author-train"):
                OPS.inventory_source_rows(root, [validation], [license_path])

    def test_json_write_is_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            OPS.write_new_json(path, {"value": 1})
            with self.assertRaises(FileExistsError):
                OPS.write_new_json(path, {"value": 2})
            self.assertEqual(json.loads(path.read_text()), {"value": 1})

    def test_v2_config_blocks_generation_until_slot_rules_are_reviewed(self) -> None:
        value = OPS.load_config()
        self.assertEqual(value["version"], "vsmt-vm04-l1-two-house-audit-proposal-v2")
        self.assertEqual(value["generator_initial_viewpoint"]["selection_rule"],
                         WORKER.SLOT_VIEWPOINT_SELECTION_RULE)
        self.assertEqual(OPS.STAGE_ID, "vsmt-vm04-two-house-audit-v2")
        self.assertTrue(value["implementation_authorized"])
        self.assertTrue(value["source_inventory_authorized"])
        self.assertFalse(value["generation_authorized"])
        self.assertFalse(value["private_audit_authorized"])
        self.assertFalse(value["training_authorized"])
        self.assertFalse(value["confirmation_authorized"])

    def test_capacity_resource_stop_is_fail_closed_before_dispatch(self) -> None:
        value = OPS.load_config()
        probe = OPS.capacity_probe(
            free_bytes=0, visible_cpu_count=2, requested_workers=2,
            predicted_wall_seconds=1.0, predicted_stage_bytes=1, config=value,
        )
        self.assertFalse(probe["ready"])
        self.assertFalse(probe["generation_started"])
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            (stage / "byte.bin").write_bytes(b"x")
            value["resource_and_worker_proposal"]["maximum_stage_bytes"] = 0
            with self.assertRaisesRegex(OPS.ResourceLimitReached, "stage byte"):
                OPS._resource_checkpoint(stage, value, started=OPS.time.monotonic())

    def test_worker_resource_stop_keeps_remaining_fixed_slots(self) -> None:
        source = WORKER_ENTRY.read_text(encoding="utf-8")
        self.assertIn('"status": "not_started"', source)
        self.assertIn('"reason": "family_resource_stop"', source)
        self.assertIn("break", source)

    def test_fixed_entry_lists_every_stage_in_order(self) -> None:
        source = ENTRY.read_text(encoding="utf-8")
        for name in (
            "contracts", "inventory", "select", "capacity", "generate",
            "materialize", "public-seal", "private-eval", "verify", "export",
        ):
            self.assertIn(f'"{name}"', source)
        self.assertNotIn("reviewed command implementation is incomplete", source)

    def test_public_seal_function_does_not_open_private_plan(self) -> None:
        source = inspect.getsource(OPS.run_public_seal)
        self.assertNotIn("private/episode_plan.json", source)
        self.assertNotIn("materialized/private", source)
        self.assertIn("range(25)", source)
        self.assertNotIn("range(32)", source)

    def test_parallel_recovery_uses_all_twelve_workers_without_wall_timeout(self) -> None:
        config = PARALLEL.load_recovery_config()
        parallel = config["parallel_public_seal"]
        self.assertEqual(parallel["requested_workers"], 12)
        self.assertIsNone(parallel["maximum_wall_clock_seconds"])
        self.assertFalse(parallel["wall_clock_timeout_allowed"])
        self.assertEqual(PARALLEL.choose_worker_count(12, 48, 12), 12)
        with self.assertRaisesRegex(RuntimeError, "only 11 CPUs"):
            PARALLEL.choose_worker_count(12, 48, 11)

    def test_parallel_public_worker_is_public_only_and_atomically_promoted(self) -> None:
        source = inspect.getsource(PARALLEL.run_public_profile_task)
        self.assertIn('"materialized/public"', source)
        self.assertNotIn("materialized/private", source)
        self.assertNotIn("private/episode_plan", source)
        self.assertIn("_promote_attempt", source)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attempt = root / "attempt"
            final = root / "completed/task"
            attempt.mkdir()
            (attempt / "value.json").write_text("{}", encoding="utf-8")
            PARALLEL._promote_attempt(attempt, final)
            self.assertFalse(attempt.exists())
            self.assertEqual((final / "value.json").read_text(encoding="utf-8"), "{}")

    def test_parallel_private_open_occurs_only_after_public_marker_check(self) -> None:
        source = inspect.getsource(PARALLEL.run_parallel_private_evaluation)
        marker_position = source.index('_marker(stage, "public-seal")')
        dispatch_position = source.index("_run_worker_pool")
        self.assertLess(marker_position, dispatch_position)
        self.assertIn("public seal changed before private opening", source)

    def test_recovery_downstream_accepts_explicit_source_stage_code(self) -> None:
        verify_source = inspect.getsource(OPS.run_verify)
        export_source = inspect.getsource(OPS.run_export)
        for source in (verify_source, export_source):
            self.assertIn("source_stage_reviewed_code or commit", source)
            self.assertIn('"source_stage_reviewed_code": stage_code', source)

    def test_parallel_pool_records_worker_exits_and_progress(self) -> None:
        source = inspect.getsource(PARALLEL._run_worker_pool)
        self.assertIn("multiprocessing.get_context", source)
        self.assertIn('get_context("spawn")', source)
        self.assertIn('row["exit_code"] = process.exitcode', source)
        self.assertIn("_PROGRESS", source)

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
        self.assertEqual(source.count("discover_initial_viewpoint(search_controller)"), 1)
        self.assertLess(source.index("discover_initial_viewpoint(search_controller)"),
                        source.index("for row_index, public in enumerate(ordered_rows)"))
        self.assertIn("slot_initial_viewpoint(ranked_poses", source)

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
                    WORKER.run_episode({}, assignment, root, 100000, start_pose)
            attempts = json.loads((root / "private/intervention-attempts.json").read_text())
            self.assertEqual(attempts["actions"][0]["diagnostic"]["error_code"],
                             "UnsupportedAction")
            self.assertTrue((root / "private/intervention-capability-audit.json").exists())
            self.assertFalse((root / "public/intervention-attempts.json").exists())
            self.assertTrue(fake.stopped)

    def test_worker_artifact_chain_rejects_changed_private_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            family = stage / "execution/family"
            episode = family / "episodes/opaque"
            private = episode / "private"
            private.mkdir(parents=True)
            viewpoints = family / "initial_viewpoints.json"
            OPS.write_new_json(viewpoints, {
                "selection_rule": WORKER.SLOT_VIEWPOINT_SELECTION_RULE,
                "eligible_pose_count": 0, "ranked_poses": [],
            })
            capability = private / "intervention-capability-audit.json"
            attempts = private / "intervention-attempts.json"
            OPS.write_new_json(capability, {"program": "BIRTH"})
            OPS.write_new_json(attempts, {"target_instance_ids": ["object|1"],
                                              "actions": [{"error_code": "E"}]})
            failure = episode / "raw.failure.json"
            OPS.write_new_json(failure, {
                "family_viewpoints_sha256": OPS.sha256(viewpoints),
                "capability_audit_sha256": OPS.sha256(capability),
                "private_intervention_attempts_sha256": OPS.sha256(attempts),
            })
            worker = family / "worker.receipt.json"
            OPS.write_new_json(worker, {
                "schema_version": "vsmt-vm04-two-house-family-worker-receipt-v2",
                "initial_viewpoint_receipt_sha256": OPS.sha256(viewpoints),
                "viewpoint_receipts": [], "target_set_recorded_count": 1,
                "repeated_target_set_count": 0,
                "episodes": [{"episode_id": "opaque", "status": "failed",
                              "failure_sha256": OPS.sha256(failure)}],
            })
            generation = {"family_receipts": [{"family_id": "family",
                                                "sha256": OPS.sha256(worker)}]}
            OPS.verify_worker_artifact_chain(stage, generation)
            attempts.write_text('{"target_instance_ids":["object|2"]}')
            with self.assertRaisesRegex(RuntimeError, "private action diagnostic digest"):
                OPS.verify_worker_artifact_chain(stage, generation)

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

    def test_birth_and_split_construction_have_positive_and_negative_cases(self) -> None:
        def crosswalk(mapping):
            return {"entity_region_to_private_instance_ids": mapping}

        raw = [{"objects": {}} for _ in range(32)]
        birth = [crosswalk({}) for _ in range(24)] + [
            crosswalk({"region:new": ["target"]}) for _ in range(8)
        ]
        self.assertEqual(
            OPS.assess_private_construction(
                program="BIRTH", target_ids=["target"], crosswalks=birth,
                raw_mappings=raw, target_node_ids=[],
            ),
            (True, None),
        )
        birth[3] = crosswalk({"region:leak": ["target"]})
        self.assertFalse(OPS.assess_private_construction(
            program="BIRTH", target_ids=["target"], crosswalks=birth,
            raw_mappings=raw, target_node_ids=[],
        )[0])

        split = [crosswalk({"region:joined": ["left", "right"]}) for _ in range(24)]
        split.extend([
            crosswalk({"region:left": ["left"], "region:right": ["right"]})
            for _ in range(8)
        ])
        self.assertEqual(OPS.assess_private_construction(
            program="SPLIT", target_ids=["left", "right"], crosswalks=split,
            raw_mappings=raw, target_node_ids=["node:joined"],
        ), (True, None))

    def test_strict_reference_selects_only_one_exact_sealed_candidate(self) -> None:
        evidence = "evidence:target"
        candidate = {
            "program": {
                "template": "BIND", "evidence_refs": [evidence],
                "operations": [{
                    "op_type": "CLOSE_NODE_VERSION",
                    "arguments": {"node_id": "node:target"},
                }],
            }
        }
        key, count = OPS.strict_reference_key(
            {"candidates": [candidate]}, program="BIND",
            target_node_ids=["node:target"], current_evidence_refs={evidence},
            incident_edge_ids=set(), target_node_version_id="version:target",
        )
        self.assertEqual(count, 1)
        self.assertEqual(key, OPS.canonical_candidate_key(candidate)[0])
        sentinel, count = OPS.strict_reference_key(
            {"candidates": [candidate, candidate]}, program="BIND",
            target_node_ids=["node:target"], current_evidence_refs={evidence},
            incident_edge_ids=set(), target_node_version_id="version:target",
        )
        self.assertEqual(count, 2)
        self.assertNotEqual(sentinel, key)


if __name__ == "__main__":
    unittest.main()
