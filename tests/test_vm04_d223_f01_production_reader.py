from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.d223_f01_production_reader import (  # noqa: E402
    D223F01Error,
    F01ProductionReader,
    assert_real_f01_authorized,
    identical_method_cache_views,
    validate_episode_cache,
    validate_f01_contract,
    validate_frame_cache,
    validate_public_input_manifest,
)


CONTRACT_PATH = (
    ROOT / "configs/vsmt/vm04_d223_f01_production_reader_v1.json")
STAGE_PATH = ROOT / "ops/vsmt/vm04_d223_f01_production_reader.py"


def contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def seal(value: dict, field: str) -> dict:
    result = json.loads(canonical_json(value))
    result[field] = hashlib.sha256(
        canonical_json(result).encode("utf-8")).hexdigest()
    return result


def pose_belief(index: int) -> dict:
    return seal({
        "schema_version": "vsmt-vm04-d210-continuous-pose-belief-v1",
        "observation_index": index,
        "frame": "episode_relative_observation_zero_origin",
        "mean_x_y_z_yaw": [0.0, 0.0, float(index) * 0.25, 0.0],
        "covariance_diagonal": [0.01, 0.01, 0.01, 0.01],
        "source_id": "fixture.causal.odometry.v1",
        "is_world_pose": False,
        "defines_place_identity": False,
    }, "belief_sha256")


class Generator:
    def __init__(self) -> None:
        self.inputs: list[np.ndarray] = []

    def generate(self, rgb: np.ndarray):
        self.inputs.append(rgb.copy())
        mask = np.zeros((224, 224), dtype=np.bool_)
        mask[70:98, 84:112] = True
        return [{"segmentation": mask, "ignored_score": 0.99}]


class Extractor:
    def __init__(self) -> None:
        self.inputs: list[np.ndarray] = []

    def __call__(self, rgb: np.ndarray) -> np.ndarray:
        self.inputs.append(rgb.copy())
        tokens = np.zeros((16, 16, 384), dtype=np.float32)
        tokens[..., 0] = 1.0
        return tokens


def materialized_episode():
    generator, extractor = Generator(), Extractor()
    reader = F01ProductionReader(
        contract=contract(), sam_generator=generator,
        patch_token_extractor=extractor,
        frozen_assets_receipt_sha256="e" * 64,
        proposal_generator_code_sha256="f" * 64)
    rgb = np.zeros((224, 224, 3), dtype=np.uint8)
    rgb[..., 1] = 31
    depth = np.full((224, 224), 2.0, dtype=np.float32)
    frame = reader.read_frame(
        observation_index=0, decision_time_s=0.0,
        rgb_uint8=rgb, depth_m_float32=depth,
        rgb_source_sha256="a" * 64, depth_source_sha256="b" * 64,
        camera_intrinsics={"fx": 112.0, "fy": 112.0,
                           "cx": 111.5, "cy": 111.5},
        causal_episode_relative_camera_pose={
            "position_m": [0.0, 0.0, 0.0],
            "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
            "is_world_pose": False,
            "source_id": "fixture.causal.odometry.v1"},
        continuous_pose_belief=pose_belief(0),
        incoming_transition_action_summary=None)
    episode = reader.seal_episode(episode_public_id="public-episode-000")
    return frame, episode, generator, extractor, rgb


class D223F01ProductionReaderTests(unittest.TestCase):
    def test_contract_state_machine_and_e06_is_not_loaded(self):
        value = validate_f01_contract(contract())
        self.assertFalse(value["assets"]["e06_structural_estimator_loaded"])
        if value["status"] == "implementation_pending_review_all_execution_closed":
            self.assertFalse(any(value["authorization"].values()))
            with self.assertRaisesRegex(D223F01Error, "closed pending review"):
                assert_real_f01_authorized(value)
        else:
            enabled = {name for name, flag in value["authorization"].items()
                       if flag}
            self.assertEqual(
                enabled,
                set(value["activation_policy"]["active_true_authorizations"]))
            assert_real_f01_authorized(value)

        active = contract()
        active["status"] = "frozen_real_f01_single_episode_reader"
        for name in active["activation_policy"]["active_true_authorizations"]:
            active["authorization"][name] = True
        validated_active = validate_f01_contract(active)
        assert_real_f01_authorized(validated_active)

    def test_contract_rejects_asset_drift_and_downstream_opening(self):
        changed = contract()
        changed["assets"]["sam2"]["automatic_mask_generator"][
            "pred_iou_thresh"] = 0.81
        with self.assertRaisesRegex(D223F01Error, "asset policy"):
            validate_f01_contract(changed)
        changed = contract()
        changed["closed_downstream"]["training_run"] = True
        with self.assertRaisesRegex(D223F01Error, "closed downstream"):
            validate_f01_contract(changed)

    def test_reader_signature_excludes_restricted_and_structural_inputs(self):
        names = set(inspect.signature(F01ProductionReader.read_frame).parameters)
        forbidden = {
            "scenario_id", "house_id", "route_index", "world_pose",
            "reachable_grid", "instance_mask", "object_id", "teacher",
            "future", "structural_role_probabilities",
            "structural_model_receipt_sha256", "semantic_probabilities",
        }
        self.assertFalse(names & forbidden)
        self.assertEqual(names, {
            "self", "observation_index", "decision_time_s", "rgb_uint8",
            "depth_m_float32", "rgb_source_sha256", "depth_source_sha256",
            "camera_intrinsics", "causal_episode_relative_camera_pose",
            "continuous_pose_belief", "incoming_transition_action_summary",
        })

    def test_public_rgbd_materializes_nonsemantic_shared_cache(self):
        frame, episode, generator, extractor, rgb = materialized_episode()
        validate_frame_cache(frame)
        validate_episode_cache(episode)
        encoded = canonical_json(episode).lower()
        self.assertNotIn("semantic", encoded)
        self.assertNotIn("structural", encoded)
        self.assertNotIn("scenario", encoded)
        self.assertNotIn("persistent_entity", encoded)
        self.assertEqual(len(frame["fragment_observations"]), 1)
        self.assertTrue(frame["surface_observations"])
        self.assertTrue(frame["free_space_observations"])
        self.assertTrue(frame["visibility_observations"])
        self.assertFalse(frame["place_observation"]["identity_assigned"])
        self.assertFalse(frame["place_observation"]["metric_grid_identity_used"])
        self.assertEqual(len(generator.inputs), 1)
        self.assertEqual(len(extractor.inputs), 1)
        np.testing.assert_array_equal(generator.inputs[0], rgb)
        np.testing.assert_array_equal(extractor.inputs[0], rgb)

    def test_five_methods_receive_identical_independent_cache_views(self):
        _frame, episode, _generator, _extractor, _rgb = materialized_episode()
        views = identical_method_cache_views(episode)
        self.assertEqual(list(views), ["VSMT", "TAF", "ELU", "WFR", "LOW"])
        self.assertEqual(len({canonical_json(value)
                              for value in views.values()}), 1)
        views["VSMT"]["frames"][0]["public_only"] = False
        self.assertTrue(views["TAF"]["frames"][0]["public_only"])

    def test_frame_rejects_cross_collection_kind_even_when_resealed(self):
        frame, _episode, _generator, _extractor, _rgb = materialized_episode()
        frame["fragment_observations"][0]["structure_kind"] = "surface"
        frame["fragment_observations"][0]["proposal_source_id"] = (
            "l1.public_depth.planar_surface.v1")
        frame["frame_cache_sha256"] = hashlib.sha256(
            canonical_json({key: value for key, value in frame.items()
                            if key != "frame_cache_sha256"}).encode("utf-8")
        ).hexdigest()
        with self.assertRaisesRegex(D223F01Error, "changed structure kind"):
            validate_frame_cache(frame)

    def test_frame_revalidates_public_volume_geometry(self):
        frame, _episode, _generator, _extractor, _rgb = materialized_episode()
        frame["visibility_observations"][0]["halfspaces_world"][0][
            "normal"] = [2.0, 0.0, 0.0]
        frame["frame_cache_sha256"] = hashlib.sha256(
            canonical_json({key: value for key, value in frame.items()
                            if key != "frame_cache_sha256"}).encode("utf-8")
        ).hexdigest()
        with self.assertRaisesRegex(D223F01Error, "not unit length"):
            validate_frame_cache(frame)

    def test_manifest_rejects_recursive_private_smuggling(self):
        row = {
            "observation_index": 0, "decision_time_s": 0.0,
            "rgb_source_sha256": "a" * 64,
            "depth_source_sha256": "b" * 64,
            "camera_intrinsics": {"fx": 112.0, "fy": 112.0,
                                  "cx": 111.5, "cy": 111.5},
            "causal_episode_relative_camera_pose": {
                "position_m": [0.0, 0.0, 0.0],
                "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
                "is_world_pose": False,
                "source_id": "fixture.causal.odometry.v1"},
            "continuous_pose_belief": pose_belief(0),
            "incoming_transition_action_summary": None,
        }
        manifest = seal({
            "schema_version": "vsmt-vm04-d223-f01-public-episode-input-v1",
            "episode_public_id": "public-episode-000", "frame_count": 1,
            "arrays_npz_sha256": "c" * 64, "rows": [row],
            "restricted_information_used": False,
        }, "manifest_sha256")
        validate_public_input_manifest(manifest)
        row["camera_intrinsics"]["nested"] = {"instance_mask": "leak"}
        smuggled = seal({key: value for key, value in manifest.items()
                        if key != "manifest_sha256"}, "manifest_sha256")
        smuggled["rows"] = [row]
        smuggled = seal({key: value for key, value in smuggled.items()
                        if key != "manifest_sha256"}, "manifest_sha256")
        with self.assertRaisesRegex(D223F01Error, "forbidden field"):
            validate_public_input_manifest(smuggled)

    def test_closed_stage_rejects_before_opening_external_paths(self):
        if contract()["status"] != (
                "implementation_pending_review_all_execution_closed"):
            self.skipTest("checked-in F-01 contract is active")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "must-not-exist"
            result = subprocess.run([
                sys.executable, str(STAGE_PATH), "run",
                "--input-root", str(Path(temporary) / "missing-input"),
                "--output-root", str(output),
                "--dino-repository", str(Path(temporary) / "missing-dino"),
                "--dino-checkpoint", str(Path(temporary) / "missing-dino.pt"),
                "--sam-repository", str(Path(temporary) / "missing-sam"),
                "--sam-checkpoint", str(Path(temporary) / "missing-sam.pt"),
            ], cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("closed pending review", result.stderr)
            self.assertFalse(output.exists())

    def test_check_cli_is_read_only_and_reports_closed_execution(self):
        result = subprocess.run(
            [sys.executable, str(STAGE_PATH), "check"], cwd=ROOT,
            capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        checked_contract = contract()
        if checked_contract["status"] == (
                "implementation_pending_review_all_execution_closed"):
            self.assertFalse(any(report["authorization"].values()))
        else:
            self.assertEqual(
                {name for name, flag in report["authorization"].items() if flag},
                set(checked_contract["activation_policy"]
                    ["active_true_authorizations"]))
        self.assertFalse(report["real_assets_opened"])
        self.assertFalse(report["real_public_inputs_opened"])
        self.assertFalse(report["compatibility_bundle_generated"])
        self.assertFalse(report["outputs_written"])


if __name__ == "__main__":
    unittest.main()
