from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path
import tempfile
import unittest


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

    def test_current_config_opens_registered_audit_pipeline(self) -> None:
        value = OPS.load_config()
        self.assertTrue(value["implementation_authorized"])
        self.assertTrue(value["source_inventory_authorized"])
        self.assertTrue(value["generation_authorized"])
        self.assertTrue(value["private_audit_authorized"])
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
