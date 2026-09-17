import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from vsmt.d210_place_memory import build_route_plan, validate_contract
from vsmt.d211_p0_smoke import (
    D211Error,
    build_sealed_route_batch,
    seal_public_route_evidence,
    seal_reachable_scan,
    seal_route_execution_binding,
    seal_scenario_receipt,
    validate_d211_contract,
)


ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "ops/vsmt"
if str(OPS) not in sys.path:
    sys.path.insert(0, str(OPS))

from vm04_d211_raw_smoke import run_raw_smoke_core  # noqa: E402


class FakeEvent:
    def __init__(self, success=True, value=0):
        self.metadata = {
            "lastActionSuccess": success,
            "errorMessage": "" if success else "blocked",
            "fov": 90.0,
            "agent": {
                "position": {"x": float(value), "y": 0.9, "z": 2.0},
                "rotation": {"x": 0.0, "y": 90.0, "z": 0.0},
                "cameraHorizon": 0.0,
            },
            "cameraPosition": {
                "x": float(value), "y": 1.575, "z": 2.0,
            },
            "objects": [{
                "objectId": "Cup|1", "objectType": "Cup",
                "position": {"x": 1.0, "y": 0.8, "z": 2.0},
                "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
                "visible": True, "isInteractable": True,
                "pickupable": True, "moveable": True,
                "isPickedUp": False, "isMoving": False,
                "parentReceptacles": ["Table|1"],
                "receptacleObjectIds": None,
            }, {
                "objectId": "Table|1", "objectType": "Table",
                "position": {"x": 1.0, "y": 0.0, "z": 2.0},
                "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
                "visible": True, "isInteractable": False,
                "pickupable": False, "moveable": False,
                "isPickedUp": False, "isMoving": False,
                "parentReceptacles": None,
                "receptacleObjectIds": ["Cup|1"],
            }],
        }
        self.frame = np.full((4, 6, 3), value, dtype=np.uint8)
        self.depth_frame = np.full((4, 6), 1.0 + value, dtype=np.float32)
        self.instance_masks = {
            "Cup|1": np.ones((4, 6), dtype=np.bool_),
        }


class FakeController:
    def __init__(self, fail_registered_index=None):
        self.requests = []
        self.registered_index = 0
        self.fail_registered_index = fail_registered_index

    def step(self, **request):
        self.requests.append(dict(request))
        if request["action"] == "TeleportFull":
            return FakeEvent(True, 0)
        index = self.registered_index
        self.registered_index += 1
        success = index != self.fail_registered_index
        return FakeEvent(success, index + 1)


class D211P0SealSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = validate_contract(json.loads((
            ROOT / "configs/vsmt/vm04_d210_dual_layer_p0_v1.json"
        ).read_text(encoding="utf-8")))
        cls.overlay = validate_d211_contract(json.loads((
            ROOT / "configs/vsmt/vm04_d211_p0_seal_single_smoke_v2.json"
        ).read_text(encoding="utf-8")), base_contract=cls.base)

    def route(self, slot):
        scenario = self.base["slot_plan"][slot]["scenario_id"]
        routes = {
            "P01": ["MoveAhead"] * 6 + ["RotateRight"] +
                   ["MoveAhead"] * 6 + ["RotateLeft"] +
                   ["MoveAhead"] * 6,
            "P02": (["MoveAhead"] * 4 + ["RotateRight"] +
                    ["MoveAhead"] * 4 + ["MoveBack"] * 4 +
                    ["RotateLeft"] + ["MoveBack"] * 4),
            "P03": (["MoveAhead"] * 4 + ["RotateRight"]) * 4,
            "P04": ["MoveAhead"] * 6,
            "P05": ["RotateRight", "RotateRight"],
            "P06": (["MoveAhead"] * 4 + ["RotateRight"] +
                    ["MoveAhead"] * 4 + ["MoveBack"] * 4 +
                    ["RotateRight", "RotateRight"] + ["MoveAhead"] * 4),
            "P07": (["RotateRight"] + ["MoveAhead"] * 2 +
                    ["RotateLeft"] + ["MoveAhead"] * 2 +
                    ["RotateLeft"] + ["MoveAhead"] * 2 +
                    ["RotateLeft"] + ["MoveAhead"] * 2 +
                    ["RotateRight", "RotateRight"] +
                    ["RotateLeft"] + ["MoveAhead"] * 2 +
                    ["RotateLeft"] + ["MoveAhead"] * 2 +
                    ["RotateLeft"] + ["MoveAhead"] * 2 +
                    ["RotateLeft"] + ["MoveAhead"] * 2),
            "P08": ["MoveAhead"] * 8,
        }
        actions = routes[scenario]
        return build_route_plan(
            slot=slot,
            action_names=actions,
            keyframe_observation_indices=[0, len(actions)], contract=self.base)

    def row(self, route):
        slot = route["slot"]
        house_slot = route["house_slot"]
        source_house_id = self.overlay["source_binding"]["houses"][house_slot][
            "source_house_id"]
        scan = seal_reachable_scan(
            house_slot=house_slot, source_house_id=source_house_id,
            raw_positions=[{"x": x * .25, "y": .9, "z": z * .25}
                           for x in range(-20, 21) for z in range(-20, 21)],
            contract=self.overlay, base_contract=self.base)
        n = route["planned_action_count"]
        indices = [0, n]
        scenario = route["scenario_id"]
        if scenario == "P08":
            indices = [0, 4, 8]
        observations = []
        for index in indices:
            role = "unknown"
            refs = []
            if scenario == "P08":
                role = "corridor" if index == 4 else "room"
                refs = [] if index == 4 else [f"region:{index}"]
            descriptor = [1.0, 0.0] if scenario == "P04" else [1.0, index + 1.0]
            observations.append({
                "observation_index": index,
                "rgb_sha256": ("a" if index == 0 else "b") * 64,
                "depth_sha256": ("c" if index == 0 else "d") * 64,
                "calibration_sha256": "e" * 64,
                "place_descriptor": descriptor,
                "public_region_role": role,
                "visible_entity_region_refs": refs,
            })
        evidence = seal_public_route_evidence(
            route_plan=route, observations=observations,
            base_contract=self.base)
        annotations = {
            "P01": {"bend_observation_indices": [7, 14],
                    "frontier_observation_index": n},
            "P02": {"turnaround_observation_index": n // 2,
                    "return_observation_index": n},
            "P03": {"loop_anchor_observation_indices": [0, n]},
            "P04": {"alias_observation_indices": [0, n]},
            "P05": {"same_place_observation_indices": [0, n]},
            "P06": {"junction_observation_indices": [4, 13],
                    "branch_endpoint_observation_indices": [9, 19]},
            "P07": {"loop_observation_ranges": [[0, 14], [14, n]]},
            "P08": {"room_anchor_observation_indices": [0, 8],
                    "corridor_observation_indices": [4]},
        }[scenario]
        semantic = seal_scenario_receipt(
            route_plan=route,
            initial_pose={"x_m": 0.0, "y_m": 0.9, "z_m": 0.0,
                          "yaw_deg": 0.0, "horizon_deg": 0.0},
            public_route_evidence=evidence, annotations=annotations,
            contract=self.overlay, base_contract=self.base)
        binding = seal_route_execution_binding(
            route_plan=route,
            initial_pose={"x_m": 0, "y_m": .9, "z_m": 0,
                          "yaw_deg": 0, "horizon_deg": 0},
            reachable_scan=scan, public_route_evidence=evidence,
            scenario_receipt=semantic,
            contract=self.overlay, base_contract=self.base)
        return {"route_plan": route, "reachable_scan": scan,
                "public_route_evidence": evidence,
                "scenario_receipt": semantic,
                "execution_binding": binding}

    def test_authorization_opens_only_seal_and_one_smoke(self):
        auth = self.overlay["authorization"]
        self.assertTrue(auth["source_house_binding_authorized"])
        self.assertTrue(auth["twelve_route_sealing_authorized"])
        self.assertTrue(auth["single_slot_raw_smoke_authorized"])
        self.assertTrue(auth["private_simulator_pose_capture_authorized"])
        self.assertTrue(auth[
            "private_instance_and_entity_truth_capture_authorized"])
        self.assertFalse(auth["twelve_slot_raw_generation_authorized"])
        self.assertFalse(auth["adapter_materialization_authorized"])
        self.assertFalse(auth["private_evaluation_authorized"])
        self.assertIsNone(self.overlay[
            "expected_reviewed_implementation_commit"])

    def test_two_source_houses_are_fixed_to_audited_record_digests(self):
        houses = self.overlay["source_binding"]["houses"]
        self.assertEqual(["train:004270", "train:008243"],
                         [row["source_house_id"] for row in houses])
        self.assertEqual(64, len(houses[0]["source_record_sha256"]))
        self.assertFalse(self.overlay["source_binding"]
                         ["replacement_after_route_or_smoke_failure_allowed"])

    def test_route_binding_requires_axis_aligned_start(self):
        route = self.route(0)
        row = self.row(route)
        with self.assertRaisesRegex(D211Error, "axis-aligned"):
            seal_route_execution_binding(
                route_plan=route,
                initial_pose={"x_m": 1.0, "y_m": 0.9, "z_m": 2.0,
                              "yaw_deg": 45.0, "horizon_deg": 0.0},
                reachable_scan=row["reachable_scan"],
                public_route_evidence=row["public_route_evidence"],
                scenario_receipt=row["scenario_receipt"],
                contract=self.overlay, base_contract=self.base)

    def test_binding_normalizes_integer_pose_before_digest(self):
        row = self.row(self.route(0))
        self.assertEqual(0.0, row["execution_binding"]["initial_pose"]["x_m"])

    def test_fake_digest_or_same_route_for_every_scenario_is_rejected(self):
        row = self.row(self.route(0))
        fake = dict(row["execution_binding"])
        fake["reachable_scan_sha256"] = "f" * 64
        with self.assertRaisesRegex(D211Error, "evidence digests"):
            from vsmt.d211_p0_smoke import validate_route_execution_binding
            validate_route_execution_binding(
                fake, route_plan=row["route_plan"],
                reachable_scan=row["reachable_scan"],
                public_route_evidence=row["public_route_evidence"],
                scenario_receipt=row["scenario_receipt"],
                contract=self.overlay, base_contract=self.base)

    def test_p03_rejects_an_exact_inverse_route(self):
        inverse_actions = (["MoveAhead"] * 4 + ["RotateRight"] +
                           ["MoveAhead"] * 4 + ["MoveBack"] * 4 +
                           ["RotateLeft"] + ["MoveBack"] * 4)
        route = build_route_plan(
            slot=2, action_names=inverse_actions,
            keyframe_observation_indices=[0, len(inverse_actions)],
            contract=self.base)
        evidence = seal_public_route_evidence(
            route_plan=route, observations=[{
                "observation_index": index, "rgb_sha256": "a" * 64,
                "depth_sha256": "b" * 64, "calibration_sha256": "c" * 64,
                "place_descriptor": [1.0, 1.0],
                "public_region_role": "unknown",
                "visible_entity_region_refs": [],
            } for index in (0, len(inverse_actions))],
            base_contract=self.base)
        with self.assertRaisesRegex(D211Error, "alternate"):
            seal_scenario_receipt(
                route_plan=route,
                initial_pose={"x_m": 0, "y_m": .9, "z_m": 0,
                              "yaw_deg": 0, "horizon_deg": 0},
                public_route_evidence=evidence,
                annotations={"loop_anchor_observation_indices":
                             [0, len(inverse_actions)]},
                contract=self.overlay, base_contract=self.base)

    def test_missing_reachable_endpoint_is_rejected(self):
        route = self.route(0)
        row = self.row(route)
        scan = dict(row["reachable_scan"])
        scan["cells"] = [cell for cell in scan["cells"] if cell != [26, 32]]
        from vsmt.d211_p0_smoke import _payload_sha
        scan["reachable_scan_sha256"] = _payload_sha(
            scan, "reachable_scan_sha256")
        with self.assertRaisesRegex(D211Error, "not reachable"):
            seal_route_execution_binding(
                route_plan=route,
                initial_pose={"x_m": 0, "y_m": .9, "z_m": 0,
                              "yaw_deg": 0, "horizon_deg": 0},
                reachable_scan=scan,
                public_route_evidence=row["public_route_evidence"],
                scenario_receipt=row["scenario_receipt"],
                contract=self.overlay, base_contract=self.base)

    def test_twelve_route_batch_seals_public_private_and_start_bindings(self):
        rows = []
        for slot in range(12):
            route = self.route(slot)
            rows.append(self.row(route))
        public, private, bindings = build_sealed_route_batch(
            rows=rows, contract=self.overlay, base_contract=self.base)
        self.assertEqual(12, public["episode_count"])
        self.assertEqual(12, private["episode_count"])
        self.assertEqual(12, bindings["binding_count"])
        self.assertTrue(all("source_house_id" not in row
                            for row in public["episodes"]))
        self.assertFalse(bindings[
            "route_replacement_after_smoke_outcome_allowed"])

    def test_successful_smoke_saves_observation_zero_and_every_action(self):
        route = self.route(0)
        row = self.row(route)
        binding = row["execution_binding"]
        controller = FakeController()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "smoke"
            receipt = run_raw_smoke_core(
                controller, route_plan=route, execution_binding=binding,
                d211_contract=self.overlay,
                reachable_scan=row["reachable_scan"],
                public_route_evidence=row["public_route_evidence"],
                scenario_receipt=row["scenario_receipt"],
                base_contract=self.base,
                output_root=root,
                source_record_sha256=self.overlay["source_binding"]["houses"]
                [0]["source_record_sha256"],
                public_manifest_sha256="c" * 64,
                episode_id="d210:p0:" + "1" * 24)
            self.assertEqual("raw_smoke_complete", receipt["status"])
            self.assertEqual(21, receipt["observation_count"])
            self.assertEqual(20, receipt["completed_registered_action_count"])
            self.assertEqual(21, len(controller.requests))
            self.assertEqual(90.0, controller.requests[7]["degrees"])
            self.assertTrue((root / "private/simulator-poses.json").is_file())
            self.assertTrue((root / "private/scene-truth.manifest.json").is_file())
            self.assertTrue((root / "private/raw/frame_0000/instance-masks.npz").is_file())
            calibration = json.loads((root / "public/raw/frame_0000/"
                                      "sensor-calibration.json").read_text())
            self.assertNotIn("pose", calibration)
            self.assertFalse(calibration["contains_camera_or_agent_pose"])
            self.assertAlmostEqual(2.0, calibration["fx"])
            self.assertAlmostEqual(2.0, calibration["fy"])
            manifest = json.loads((root / "public/raw-smoke.manifest.json")
                                  .read_text())
            self.assertFalse(manifest["adapter_materialized"])
            self.assertFalse(manifest["private_evaluation_performed"])
            provenance_text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in (root / "provenance").glob("*.json"))
            self.assertNotIn('"x_m"', provenance_text)
            self.assertNotIn('"z_m"', provenance_text)
            self.assertIn('"initial_pose_copied_to_raw_smoke":false',
                          provenance_text)
            private_poses = json.loads((
                root / "private/simulator-poses.json").read_text())
            self.assertEqual(21, private_poses["observation_count"])
            self.assertTrue(all(row["candidate_or_model_reader_allowed"] is False
                                for row in private_poses["poses"]))
            self.assertEqual(
                manifest["frames"][0]["frame_sha256"],
                private_poses["poses"][0]["public_frame_sha256"])
            self.assertNotIn("agent_world_pose", provenance_text)
            self.assertNotIn("Cup|1", provenance_text)
            private_state = json.loads((root / "private/raw/frame_0000/"
                                        "entity-state.json").read_text())
            self.assertEqual("Cup|1", private_state[
                "private_mask_to_simulator_object_id"][0])
            self.assertFalse(private_state["candidate_or_model_reader_allowed"])
            self.assertEqual(21, len(list((root / "provenance/action-journal")
                                         .glob("*.json"))))

    def test_failed_action_keeps_completed_prefix_and_stops(self):
        route = self.route(0)
        row = self.row(route)
        binding = row["execution_binding"]
        controller = FakeController(fail_registered_index=1)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "smoke"
            receipt = run_raw_smoke_core(
                controller, route_plan=route, execution_binding=binding,
                d211_contract=self.overlay,
                reachable_scan=row["reachable_scan"],
                public_route_evidence=row["public_route_evidence"],
                scenario_receipt=row["scenario_receipt"],
                base_contract=self.base,
                output_root=root,
                source_record_sha256=self.overlay["source_binding"]["houses"]
                [0]["source_record_sha256"],
                public_manifest_sha256="c" * 64,
                episode_id="d210:p0:" + "2" * 24)
            self.assertEqual("raw_smoke_failure", receipt["status"])
            self.assertEqual(2, receipt["observation_count"])
            self.assertEqual(1, receipt["completed_registered_action_count"])
            self.assertEqual(2, receipt["private_simulator_pose_count"])
            actions = json.loads((root / "provenance/action-receipts.json")
                                 .read_text())["receipts"]
            self.assertEqual(3, len(actions))  # setup + success + failed action
            self.assertFalse(actions[-1]["success"])
            self.assertEqual(3, len(controller.requests))

    def test_raw_core_rejects_any_nonregistered_smoke_slot(self):
        route = self.route(1)
        row = self.row(route)
        binding = row["execution_binding"]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "only the D-211 registered"):
                run_raw_smoke_core(
                    FakeController(), route_plan=route,
                    execution_binding=binding, d211_contract=self.overlay,
                    reachable_scan=row["reachable_scan"],
                    public_route_evidence=row["public_route_evidence"],
                    scenario_receipt=row["scenario_receipt"],
                    base_contract=self.base,
                    output_root=Path(directory) / "smoke",
                    source_record_sha256=self.overlay["source_binding"]["houses"]
                    [0]["source_record_sha256"],
                    public_manifest_sha256="c" * 64,
                    episode_id="d210:p0:" + "3" * 24)

    def test_stage_check_is_closed_pending_reviewed_commit(self):
        completed = subprocess.run(
            [sys.executable, str(ROOT / "ops/vsmt/vm04_d211_p0_stage.py"),
             "check"], cwd=ROOT, check=True, capture_output=True, text=True)
        report = json.loads(completed.stdout)
        self.assertFalse(report["execution_authorized"])
        self.assertEqual(0, report["raw_smoke_slot"])
        self.assertTrue(report[
            "private_simulator_pose_capture_authorized"])
        self.assertFalse(report["twelve_slot_raw_generation_authorized"])

    def test_seal_rejects_before_reading_external_bundle_or_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            completed = subprocess.run([
                sys.executable,
                str(ROOT / "ops/vsmt/vm04_d211_p0_stage.py"),
                "seal-routes", "--route-bundle", str(root / "missing.json"),
                "--output-root", str(root / "sealed"),
                "--reviewed-implementation", "f" * 40,
            ], cwd=ROOT, check=False, capture_output=True, text=True)
            self.assertNotEqual(0, completed.returncode)
            self.assertIn("not executable", completed.stderr)
            self.assertFalse((root / "sealed").exists())


if __name__ == "__main__":
    unittest.main()
