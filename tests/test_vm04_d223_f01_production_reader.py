from __future__ import annotations

import hashlib
import inspect
import io
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
    BORDER_POLICY_EXECUTION_CONSTANT,
    D223F01Error,
    F01ProductionReader,
    SAM_FROZEN_ASSET_BYTES,
    SAM_RECORDED_DEFAULTS,
    assert_real_f01_authorized,
    build_observation_zero_compat_input,
    build_l2_proposal_config,
    identical_method_cache_views,
    resolve_generator_arguments,
    select_first_d217_public_train_sample,
    validate_d224_supersession,
    validate_episode_cache,
    validate_f01_contract,
    validate_frame_cache,
    validate_public_input_manifest,
)


CONTRACT_PATH = (
    ROOT / "configs/vsmt/vm04_d223_f01_production_reader_v1.json")
STAGE_PATH = ROOT / "ops/vsmt/vm04_d223_f01_production_reader.py"
D224_PATH = (
    ROOT / "configs/vsmt/vm04_d224_frozen_sam2_asset_acquisition_v1.json")
D215_PATH = ROOT / "configs/vsmt/vm04_d215_frontend_freeze_v1.json"


def contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def d224() -> dict:
    return json.loads(D224_PATH.read_text(encoding="utf-8"))


def d215_file_sha256() -> str:
    return hashlib.sha256(D215_PATH.read_bytes()).hexdigest()


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
        self.assertFalse(report["d217_compatibility_input_built"])
        self.assertFalse(report["outputs_written"])


def sha(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def d217_source_arrays() -> dict:
    observation_ids = [hashlib.sha256(
        f"observation-{index}".encode("utf-8")).hexdigest()
        for index in range(32)]
    rgb = np.zeros((32, 224, 224, 3), dtype=np.uint8)
    rgb[0, ..., 1] = 37
    depth = np.full((32, 224, 224), 2.0, dtype=np.float32)
    intrinsics = np.tile(
        np.asarray([112.0, 112.0, 111.5, 111.5], dtype=np.float64), (32, 1))
    return {
        "rgb_uint8": rgb,
        "depth_m_float32": depth,
        "camera_intrinsics_float64": intrinsics,
        "observation_ids": np.asarray(observation_ids),
    }


def d217_source_receipt(
    *, rank: int, npz_sha256: str = "b" * 64, arrays: dict | None = None,
) -> dict:
    values = arrays or d217_source_arrays()
    return seal({
        "schema_version": "vsmt-vm04-d217-public-rgbd-house-v1",
        "split": "train",
        "sample_rank": rank,
        "public_house_ref": "d217-public-house-fixture",
        "observation_count": 32,
        "observation_ids_sha256": sha(
            [str(item) for item in values["observation_ids"].tolist()]),
        "rgbd_npz_sha256": npz_sha256,
        "contains_house_world_pose_grid_instance_scenario_teacher_or_future":
            False,
    }, "public_receipt_sha256")


def write_d217_sample(public_root: Path, rank: int) -> Path:
    sample = public_root / "train" / f"sample_{rank:04d}"
    sample.mkdir(parents=True)
    arrays = d217_source_arrays()
    npz_path = sample / "rgbd.npz"
    np.savez(npz_path, **arrays)
    digest = hashlib.sha256(npz_path.read_bytes()).hexdigest()
    (sample / "receipt.json").write_text(
        canonical_json(d217_source_receipt(
            rank=rank, npz_sha256=digest, arrays=arrays)) + "\n",
        encoding="utf-8")
    return sample


class D223F01D217CompatibilityInputTests(unittest.TestCase):
    """The D-217 adapter is an input mode of F-01, not a separate stage.

    These are the load-bearing guarantees: the contract freezes the selection
    policy, the selector never skips a broken earlier sample, source digests and
    the public/private boundary flag are verified, the bundle is deterministic
    and carries a single origin-pose frame, and nothing identifying the source
    house reaches the method-visible manifest.
    """

    def test_contract_freezes_the_adapter_and_keeps_execution_closed(self):
        value = validate_f01_contract(contract())
        adapter = value["compatibility_input_adapter"]
        self.assertEqual("train", adapter["source_split"])
        self.assertEqual(0, adapter["selected_observation_index"])
        self.assertEqual(
            "fail_do_not_skip",
            adapter["selected_sample_incomplete_or_malformed_policy"])
        self.assertTrue(adapter["diagnostic_compatibility_only"])
        self.assertFalse(
            adapter["eligible_for_formal_data_p04_p08_or_paper_results"])
        self.assertFalse(adapter["private_root_or_sidecar_read_allowed"])
        if value["status"] == (
                "implementation_pending_review_all_execution_closed"):
            self.assertFalse(any(value["authorization"].values()))

    def test_selector_takes_the_lowest_existing_public_train_rank(self):
        with tempfile.TemporaryDirectory() as temporary:
            public_root = Path(temporary) / "public"
            write_d217_sample(public_root, 9)
            expected = write_d217_sample(public_root, 3)
            (public_root / "calibration" / "sample_0000").mkdir(parents=True)
            (Path(temporary) / "private" / "train").mkdir(parents=True)
            selected, receipt, arrays = (
                select_first_d217_public_train_sample(public_root))
            self.assertEqual(expected, selected)
            self.assertEqual(3, receipt["sample_rank"])
            self.assertEqual((32, 224, 224, 3), arrays["rgb_uint8"].shape)

    def test_selector_does_not_skip_a_malformed_earlier_sample(self):
        with tempfile.TemporaryDirectory() as temporary:
            public_root = Path(temporary) / "public"
            malformed = public_root / "train" / "sample_0002"
            malformed.mkdir(parents=True)
            (malformed / "receipt.json").write_text("{}", encoding="utf-8")
            write_d217_sample(public_root, 7)
            with self.assertRaisesRegex(
                    D223F01Error, "incomplete or has extra files"):
                select_first_d217_public_train_sample(public_root)

    def test_source_validation_rejects_a_private_flag_or_array_drift(self):
        arrays = d217_source_arrays()
        receipt = d217_source_receipt(rank=3, arrays=arrays)
        receipt[
            "contains_house_world_pose_grid_instance_scenario_teacher_or_future"
        ] = True
        receipt = seal({key: value for key, value in receipt.items()
                        if key != "public_receipt_sha256"},
                       "public_receipt_sha256")
        with self.assertRaisesRegex(D223F01Error, "identity changed"):
            build_observation_zero_compat_input(
                source_receipt=receipt, source_arrays=arrays,
                frontend_config_sha256="c" * 64)

        arrays = d217_source_arrays()
        receipt = d217_source_receipt(rank=3, arrays=arrays)
        arrays["extra"] = np.asarray([1])
        with self.assertRaisesRegex(D223F01Error, "NPZ fields"):
            build_observation_zero_compat_input(
                source_receipt=receipt, source_arrays=arrays,
                frontend_config_sha256="c" * 64)

    def test_input_is_deterministic_with_one_origin_pose_frame(self):
        arrays = d217_source_arrays()
        receipt = d217_source_receipt(rank=3, arrays=arrays)
        first = build_observation_zero_compat_input(
            source_receipt=receipt, source_arrays=arrays,
            frontend_config_sha256="c" * 64)
        second = build_observation_zero_compat_input(
            source_receipt=receipt, source_arrays=arrays,
            frontend_config_sha256="c" * 64)
        self.assertEqual(first, second)
        npz_bytes, manifest, _provenance = first
        validate_public_input_manifest(manifest)
        self.assertEqual(1, manifest["frame_count"])
        row = manifest["rows"][0]
        self.assertEqual(
            [0.0, 0.0, 0.0],
            row["causal_episode_relative_camera_pose"]["position_m"])
        self.assertEqual(
            [0.0, 0.0, 0.0, 0.0],
            row["continuous_pose_belief"]["mean_x_y_z_yaw"])
        self.assertEqual(
            [0.0, 0.0, 0.0, 0.0],
            row["continuous_pose_belief"]["covariance_diagonal"])
        self.assertIsNone(row["incoming_transition_action_summary"])
        with np.load(io.BytesIO(npz_bytes), allow_pickle=False) as output:
            self.assertEqual({"rgb_uint8", "depth_m_float32"},
                             set(output.files))
            np.testing.assert_array_equal(
                arrays["rgb_uint8"][:1], output["rgb_uint8"])
            np.testing.assert_array_equal(
                arrays["depth_m_float32"][:1], output["depth_m_float32"])

    def test_method_manifest_is_anonymous_and_provenance_is_diagnostic(self):
        arrays = d217_source_arrays()
        receipt = d217_source_receipt(rank=3, arrays=arrays)
        _npz, manifest, provenance = build_observation_zero_compat_input(
            source_receipt=receipt, source_arrays=arrays,
            frontend_config_sha256="c" * 64)
        encoded = canonical_json(manifest)
        self.assertNotIn("public_house_ref", encoded)
        self.assertNotIn(receipt["public_house_ref"], encoded)
        self.assertNotIn(str(arrays["observation_ids"][0]), encoded)
        self.assertNotIn("sample_rank", encoded)
        self.assertEqual(3, provenance["selected_sample_rank"])
        self.assertTrue(provenance["compatibility_only"])
        self.assertFalse(
            provenance["formal_data_p04_p08_or_paper_eligible"])
        self.assertFalse(provenance["private_input_read"])
        self.assertFalse(provenance["calibration_or_audit_input_read"])


class FakeGenerator:
    """The SAM2AutomaticMaskGenerator signature at the pinned commit."""

    def __init__(
        self, model, points_per_side=32, points_per_batch=64,
        pred_iou_thresh=0.8, stability_score_thresh=0.95,
        stability_score_offset=1.0, mask_threshold=0.0, box_nms_thresh=0.7,
        crop_n_layers=0, crop_nms_thresh=0.7, crop_overlap_ratio=512 / 1500,
        crop_n_points_downscale_factor=1, point_grids=None,
        min_mask_region_area=0, output_mode="binary_mask", use_m2m=False,
        multimask_output=True, **kwargs,
    ) -> None:
        self.arguments = dict(kwargs)


class DriftedGenerator:
    """The same signature with one default moved, as a library bump would."""

    def __init__(
        self, model, points_per_side=32, points_per_batch=64,
        pred_iou_thresh=0.8, stability_score_thresh=0.95,
        stability_score_offset=1.0, mask_threshold=0.0, box_nms_thresh=0.7,
        crop_n_layers=0, crop_nms_thresh=0.7, crop_overlap_ratio=512 / 1500,
        crop_n_points_downscale_factor=1, point_grids=None,
        min_mask_region_area=0, output_mode="binary_mask", use_m2m=False,
        multimask_output=False, **kwargs,
    ) -> None:
        self.arguments = dict(kwargs)


class D223F01FrozenGeneratorArgumentTests(unittest.TestCase):
    """Nothing that changes which masks come back may rest on a library default.

    D-215 froze ten generator arguments.  Six more affect the returned masks --
    ``multimask_output`` most of all, since it is why one grid point can yield
    several proposals and therefore what the 64-proposal ceiling bounds.  The
    contract records those six at their pinned-commit values, and the reader
    passes all of them explicitly.
    """

    def test_contract_records_every_remaining_generator_argument(self):
        sam = validate_f01_contract(contract())["assets"]["sam2"]
        recorded = sam["automatic_mask_generator_recorded_defaults"]
        self.assertEqual(SAM_RECORDED_DEFAULTS, recorded)
        self.assertEqual(
            "sam2/automatic_mask_generator.py::SAM2AutomaticMaskGenerator.__init__",
            sam["automatic_mask_generator_argument_source"])
        self.assertTrue(sam["automatic_mask_generator_recorded_defaults_note"])

    def test_recorded_defaults_never_restate_a_d215_frozen_value(self):
        sam = validate_f01_contract(contract())["assets"]["sam2"]
        self.assertFalse(
            set(sam["automatic_mask_generator"]) & set(SAM_RECORDED_DEFAULTS))

    def test_resolved_arguments_cover_the_full_pinned_signature(self):
        sam = validate_f01_contract(contract())["assets"]["sam2"]
        arguments = resolve_generator_arguments(sam, FakeGenerator)
        parameters = inspect.signature(FakeGenerator.__init__).parameters
        expected = {name for name, item in parameters.items()
                    if name not in {"self", "model"}
                    and item.kind is not inspect.Parameter.VAR_KEYWORD}
        self.assertEqual(expected, set(arguments))
        self.assertTrue(arguments["multimask_output"])
        self.assertEqual(1.0, arguments["box_nms_thresh"])

    def test_a_drifted_library_default_is_refused(self):
        sam = validate_f01_contract(contract())["assets"]["sam2"]
        with self.assertRaisesRegex(D223F01Error, "multimask_output drifted"):
            resolve_generator_arguments(sam, DriftedGenerator)

    def test_an_argument_the_constructor_does_not_name_is_refused(self):
        sam = json.loads(canonical_json(
            validate_f01_contract(contract())["assets"]["sam2"]))
        sam["automatic_mask_generator_recorded_defaults"][
            "multimask_ouput"] = True
        with self.assertRaisesRegex(D223F01Error, "does not name"):
            resolve_generator_arguments(sam, FakeGenerator)

    def test_border_policy_name_maps_onto_the_executed_constant(self):
        value = validate_f01_contract(contract())
        sam = value["assets"]["sam2"]
        self.assertEqual("retain_if_minimum_visible_pixels_met",
                         sam["border_truncation_policy"])
        self.assertEqual(BORDER_POLICY_EXECUTION_CONSTANT,
                         sam["border_truncation_policy_execution_constant"])
        config = build_l2_proposal_config(
            value, generator_code_sha256="a" * 64)
        self.assertEqual(BORDER_POLICY_EXECUTION_CONSTANT,
                         config.border_truncation_policy)


class D224AssetAcquisitionSupersessionTests(unittest.TestCase):
    """D-215 closed the download and dependency bits and its bytes are
    hash-bound by d216, d217 and d218, so F-01 may only acquire the frozen
    SAM2 assets under a by-reference supersession, never by editing D-215."""

    def test_d215_bytes_and_closed_bits_are_untouched(self):
        value = json.loads(D215_PATH.read_text(encoding="utf-8"))
        self.assertFalse(value["authorization"]["server_asset_download"])
        self.assertFalse(value["authorization"]["dependency_install"])
        self.assertEqual(
            validate_f01_contract(contract())["bindings"]["d215_file_sha256"],
            d215_file_sha256())

    def test_supersession_is_by_reference_over_exactly_two_bits(self):
        core = d224()["supersession_core"]
        self.assertEqual(
            ["authorization.server_asset_download",
             "authorization.dependency_install"],
            core["supersedes"]["d215_clauses_replaced"])
        self.assertTrue(
            core["supersedes"]["predecessor_bytes_must_not_change"])
        self.assertTrue(
            core["supersedes"]["supersession_is_by_reference_not_by_rewrite"])
        self.assertEqual(
            d215_file_sha256(),
            core["frozen_predecessor_bindings"]["d215_file_sha256"])

    def test_f01_binds_the_core_digest_and_the_digest_matches(self):
        bindings = validate_f01_contract(contract())["bindings"]
        self.assertEqual(
            bindings["d224_supersession_core_sha256"],
            validate_d224_supersession(
                d224(),
                expected_d215_file_sha256=bindings["d215_file_sha256"]))

    def test_core_digest_survives_opening_and_reclosing_the_bits(self):
        opened = d224()
        opened["status"] = opened["activation_policy"]["active_status"]
        for name in opened["activation_policy"]["active_true_authorizations"]:
            opened["authorization"][name] = True
        self.assertEqual(
            d224()["supersession_core_sha256"],
            validate_d224_supersession(
                opened, expected_d215_file_sha256=d215_file_sha256()))

    def test_expected_assets_restate_the_frozen_pins_exactly(self):
        expected = d224()["supersession_core"]["expected_assets"]
        for name, value in SAM_FROZEN_ASSET_BYTES.items():
            self.assertEqual(value, expected[name])
        sam = validate_f01_contract(contract())["assets"]["sam2"]
        self.assertEqual(sam["repository_commit"],
                         expected["sam2_repository_commit"])
        self.assertEqual(sam["checkpoint_sha256"],
                         expected["sam2_checkpoint_sha256"])
        self.assertEqual(sam["checkpoint_bytes"],
                         expected["sam2_checkpoint_bytes"])
        self.assertEqual(sam["official_model_config_sha256"],
                         expected["sam2_official_model_config_sha256"])

    def test_a_retargeted_or_widened_supersession_is_refused(self):
        for mutate, pattern in (
            (lambda value: value["supersession_core"]["supersedes"][
                "d215_clauses_replaced"].append(
                    "authorization.private_evaluation"),
             "exactly the two D-215 bits"),
            (lambda value: value["supersession_core"][
                "frozen_predecessor_bindings"].__setitem__(
                    "d215_file_sha256", "0" * 64),
             "different D-215 bytes"),
            (lambda value: value["supersession_core"][
                "expected_assets"].__setitem__(
                    "sam2_repository_commit", "b" * 40),
             "differ from the frozen pins"),
            (lambda value: value["supersession_core"][
                "digest_mismatch_policy"].__setitem__(
                    "may_try_a_mirror_or_reupload", True),
             "stop on a digest mismatch"),
        ):
            value = d224()
            mutate(value)
            with self.assertRaisesRegex(D223F01Error, pattern):
                validate_d224_supersession(
                    value, expected_d215_file_sha256=d215_file_sha256())

    def test_a_silently_edited_core_is_refused(self):
        value = d224()
        value["supersession_core"]["boundary_note"] = "anything else"
        with self.assertRaisesRegex(D223F01Error, "does not match its own"):
            validate_d224_supersession(
                value, expected_d215_file_sha256=d215_file_sha256())

    def test_acquisition_does_not_authorize_any_f01_or_downstream_run(self):
        value = d224()
        self.assertEqual(
            {"sam2_repository_clone", "sam2_checkpoint_download",
             "sam2_import_dependency_install"},
            set(value["activation_policy"]["active_true_authorizations"]))
        for name in ("f01_real_asset_verification_and_loading",
                     "f01_production_cache_generation",
                     "p04_p08_qualification", "route_or_raw_generation",
                     "private_evaluation", "training", "audit_rerun",
                     "f02_and_all_downstream_stages"):
            self.assertIn(name, value["supersession_core"]["does_not_authorize"])
        for name in value["activation_policy"]["must_remain_false"]:
            self.assertFalse(value["authorization"][name])


if __name__ == "__main__":
    unittest.main()
