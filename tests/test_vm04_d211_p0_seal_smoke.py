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
    seal_route_execution_binding,
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
        }
        self.frame = np.full((4, 6, 3), value, dtype=np.uint8)
        self.depth_frame = np.full((4, 6), 1.0 + value, dtype=np.float32)


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
            ROOT / "configs/vsmt/vm04_d211_p0_seal_single_smoke_v1.json"
        ).read_text(encoding="utf-8")), base_contract=cls.base)

    def route(self, slot, count=4):
        pattern = ["MoveAhead", "RotateRight", "MoveAhead", "RotateLeft"]
        return build_route_plan(
            slot=slot,
            action_names=[pattern[index % len(pattern)] for index in range(count)],
            keyframe_observation_indices=[0, count], contract=self.base)

    def binding(self, route):
        return seal_route_execution_binding(
            route_plan=route,
            initial_pose={"x_m": 1.0, "y_m": 0.9, "z_m": 2.0,
                          "yaw_deg": 90.0, "horizon_deg": 0.0},
            reachable_scan_sha256="a" * 64,
            public_rgbd_route_evidence_sha256="b" * 64,
            contract=self.overlay, base_contract=self.base)

    def test_authorization_opens_only_seal_and_one_smoke(self):
        auth = self.overlay["authorization"]
        self.assertTrue(auth["source_house_binding_authorized"])
        self.assertTrue(auth["twelve_route_sealing_authorized"])
        self.assertTrue(auth["single_slot_raw_smoke_authorized"])
        self.assertFalse(auth["twelve_slot_raw_generation_authorized"])
        self.assertFalse(auth["adapter_materialization_authorized"])
        self.assertFalse(auth["private_evaluation_authorized"])
        self.assertIsNone(self.overlay["expected_reviewed_code_commit"])

    def test_two_source_houses_are_fixed_to_audited_record_digests(self):
        houses = self.overlay["source_binding"]["houses"]
        self.assertEqual(["train:004270", "train:008243"],
                         [row["source_house_id"] for row in houses])
        self.assertEqual(64, len(houses[0]["source_record_sha256"]))
        self.assertFalse(self.overlay["source_binding"]
                         ["replacement_after_route_or_smoke_failure_allowed"])

    def test_route_binding_requires_axis_aligned_start(self):
        route = self.route(0)
        with self.assertRaisesRegex(D211Error, "axis-aligned"):
            seal_route_execution_binding(
                route_plan=route,
                initial_pose={"x_m": 1.0, "y_m": 0.9, "z_m": 2.0,
                              "yaw_deg": 45.0, "horizon_deg": 0.0},
                reachable_scan_sha256="a" * 64,
                public_rgbd_route_evidence_sha256="b" * 64,
                contract=self.overlay, base_contract=self.base)

    def test_twelve_route_batch_seals_public_private_and_start_bindings(self):
        rows = []
        for slot in range(12):
            route = self.route(slot)
            rows.append({"route_plan": route,
                         "execution_binding": self.binding(route)})
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
        binding = self.binding(route)
        controller = FakeController()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "smoke"
            receipt = run_raw_smoke_core(
                controller, route_plan=route, execution_binding=binding,
                d211_contract=self.overlay, base_contract=self.base,
                output_root=root,
                source_record_sha256=self.overlay["source_binding"]["houses"]
                [0]["source_record_sha256"],
                public_manifest_sha256="c" * 64,
                episode_id="d210:p0:" + "1" * 24)
            self.assertEqual("raw_smoke_complete", receipt["status"])
            self.assertEqual(5, receipt["observation_count"])
            self.assertEqual(4, receipt["completed_registered_action_count"])
            self.assertEqual(5, len(controller.requests))
            self.assertEqual(90.0, controller.requests[2]["degrees"])
            self.assertFalse((root / "private").exists())
            calibration = json.loads((root / "public/raw/frame_0000/"
                                      "sensor-calibration.json").read_text())
            self.assertNotIn("pose", calibration)
            self.assertFalse(calibration["contains_camera_or_agent_pose"])
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

    def test_failed_action_keeps_completed_prefix_and_stops(self):
        route = self.route(0)
        binding = self.binding(route)
        controller = FakeController(fail_registered_index=1)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "smoke"
            receipt = run_raw_smoke_core(
                controller, route_plan=route, execution_binding=binding,
                d211_contract=self.overlay, base_contract=self.base,
                output_root=root,
                source_record_sha256=self.overlay["source_binding"]["houses"]
                [0]["source_record_sha256"],
                public_manifest_sha256="c" * 64,
                episode_id="d210:p0:" + "2" * 24)
            self.assertEqual("raw_smoke_failure", receipt["status"])
            self.assertEqual(2, receipt["observation_count"])
            self.assertEqual(1, receipt["completed_registered_action_count"])
            actions = json.loads((root / "provenance/action-receipts.json")
                                 .read_text())["receipts"]
            self.assertEqual(3, len(actions))  # setup + success + failed action
            self.assertFalse(actions[-1]["success"])
            self.assertEqual(3, len(controller.requests))

    def test_raw_core_rejects_any_nonregistered_smoke_slot(self):
        route = self.route(1)
        binding = self.binding(route)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "only the D-211 registered"):
                run_raw_smoke_core(
                    FakeController(), route_plan=route,
                    execution_binding=binding, d211_contract=self.overlay,
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
        self.assertFalse(report["twelve_slot_raw_generation_authorized"])

    def test_seal_rejects_before_reading_external_bundle_or_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            completed = subprocess.run([
                sys.executable,
                str(ROOT / "ops/vsmt/vm04_d211_p0_stage.py"),
                "seal-routes", "--route-bundle", str(root / "missing.json"),
                "--output-root", str(root / "sealed"),
                "--reviewed-code", "f" * 40,
            ], cwd=ROOT, check=False, capture_output=True, text=True)
            self.assertNotEqual(0, completed.returncode)
            self.assertIn("not executable", completed.stderr)
            self.assertFalse((root / "sealed").exists())


if __name__ == "__main__":
    unittest.main()
