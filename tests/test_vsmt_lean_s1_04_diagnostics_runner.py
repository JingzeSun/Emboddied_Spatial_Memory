"""The S1-04 diagnostics runner's model-free parts: labelling cache fragments from recovered masks
and private instance images (every mask re-digested from its pixels first), the frame and episode
seals recomputed from the loaded cache bytes, the fragment-versus-truth IoU rows with the proxy
column, the labelled-fragment arrays round trip that feeds the ReID stage (including an episode
with no labelled fragment), the hold-out frozen on cache membership, the rerun guards, the
divergence handling of the ReID stage, aggregation over per-episode diagnostics files, and the
authorization guard.  No model, simulator or cache root; the ReID stage is exercised with the
training and projection calls stubbed.
"""

from __future__ import annotations

import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import lean_s1_03_cache as cache_runner  # noqa: E402
import lean_s1_04_diagnostics as diag  # noqa: E402
from vsmt import lean_frontend_cache as fc  # noqa: E402
from vsmt import lean_frontend_diagnostics as fd  # noqa: E402
from vsmt import lean_reid_head as rh  # noqa: E402

CONTRACT_PATH = PROJECT_ROOT / "configs" / "vsmt" / "lean_s1_04_frontend_diagnostics_v1.json"
H = W = 16
ASSETS = {"vits14": "b" * 64, "vitb14": "c" * 64}


def unit(vector) -> list[float]:
    array = np.asarray(vector, dtype=np.float64)
    return (array / np.linalg.norm(array)).tolist()


def synthetic_episode(frames: int = 3, labels_of: dict | None = None):
    """Two fragments per frame on objects, one half on the chair half on background; digests are real."""

    rng = np.random.default_rng(7)
    cache_frames, masks_by_frame, records, images = [], [], [], []
    mapping = labels_of if labels_of is not None else {"Chair|1": 1, "Mug|2": 2}
    for t in range(frames):
        labels = np.zeros((H, W), dtype=np.uint16)
        labels[2:10, 2:10] = 1   # chair
        labels[12:16, 0:4] = 2   # mug
        chair_mask = np.zeros((H, W), dtype=bool); chair_mask[3:9, 3:9] = True          # fully on the chair
        mug_mask = np.zeros((H, W), dtype=bool); mug_mask[10:16, 0:4] = True            # 16 of 24 px on the mug
        half_mask = np.zeros((H, W), dtype=bool); half_mask[8:12, 8:12] = True          # 8 of 16 px on the chair: no majority
        masks = [chair_mask, mug_mask, half_mask]
        shas = [fc.mask_sha256_of(mask) for mask in masks]
        fragments = []
        for n, (sha, mask) in enumerate(zip(shas, masks)):
            fragments.append({"fragment_id": f"f{t}:{n}", "descriptor_vits14": unit(rng.normal(size=8)),
                              "descriptor_vitb14": unit(rng.normal(size=12)), "centroid_m": [float(n), 0.0, float(t)],
                              "aabb_min_m": [n - 0.2, -0.2, t - 0.2], "aabb_max_m": [n + 0.2, 0.2, t + 0.2],
                              "pixel_count": int(mask.sum()), "mask_sha256": sha})
        cache_frames.append({"tick": t + 1, "fragments": fragments})
        masks_by_frame.append({"masks": np.stack(masks), "mask_sha256": shas})
        records.append({"observation_index": t, "object_id_to_entity_id": dict(mapping)})
        images.append(labels)
    return cache_frames, masks_by_frame, records, images


def sealed_cache_frame(tick: int, seed: int) -> dict:
    """A cache frame in the sealed shape with its seal computed the way ``build_frame`` does."""

    rng = np.random.default_rng(seed)
    frame = {
        "frame_digest": "a" * 64, "tick": tick, "camera_position_m": [0.0, 1.5, float(tick)], "camera_forward": [0.0, 0.0, 1.0],
        "fragments": [{"fragment_id": f"fragment:{n:04d}", "descriptor_vits14": unit(rng.normal(size=8)),
                       "descriptor_vitb14": unit(rng.normal(size=12)), "centroid_m": [float(n), 0.0, 1.0],
                       "aabb_min_m": [0.0, 0.0, 0.0], "aabb_max_m": [1.0, 1.0, 1.0], "pixel_count": 300,
                       "depth_valid_ratio": 1.0, "supported_by": None, "mask_sha256": "d" * 64} for n in range(2)],
        "surfaces": [], "free_space": [], "visibility": [],
    }
    frame["frame_seal"] = {
        "payload_sha256": fc.sha(fc.frame_seal_payload(frame, frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256,
                                                       descriptor_asset_sha256s=ASSETS)),
        "frontend_config_sha256": fc.D223_FRONTEND_CONFIG_SHA256,
    }
    return frame


def write_cache_episode(cache_dir: Path, frames: list[dict], mask_source: str = fc.MASK_SOURCE_SAM2) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    for index, frame in enumerate(frames):
        (cache_dir / f"{index:04d}{cache_runner.FRAME_FILE_SUFFIX}").write_bytes(gzip.compress(json.dumps(frame).encode("utf-8")))
    sealed = fc.seal_episode(frames, frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256, mask_source=mask_source)
    (cache_dir / "episode_seal.json").write_text(json.dumps(sealed), encoding="utf-8")
    (cache_dir / "receipt.json").write_text(json.dumps({"status": "succeeded"}), encoding="utf-8")


class LabelFramesTests(unittest.TestCase):
    def test_labels_follow_the_strict_majority_and_digests_are_checked_first(self) -> None:
        cache_frames, masks, records, images = synthetic_episode()
        labelled = diag.label_frames(cache_frames, masks, records, images)
        self.assertEqual([f["object"] for f in labelled[0]["fragments"]], ["Chair|1", "Mug|2", None])
        self.assertEqual(set(labelled[0]["fragments"][0]), {"fragment_id", "object", "descriptor_vits14", "descriptor_vitb14",
                                                             "centroid_m", "aabb_min_m", "aabb_max_m", "pixel_count"})
        masks[1]["mask_sha256"] = list(reversed(masks[1]["mask_sha256"]))
        with self.assertRaises(diag.DiagnosticsFailure) as caught:
            diag.label_frames(cache_frames, masks, records, images)
        self.assertEqual(caught.exception.reason, "fragment_masks_missing")
        with self.assertRaises(diag.DiagnosticsFailure):
            diag.label_frames(cache_frames[:2], masks[:2], records[:2], images[:1])

    def test_mask_pixels_are_re_digested_so_a_changed_mask_under_a_kept_digest_is_refused(self) -> None:
        cache_frames, masks, records, images = synthetic_episode()
        # move the chair fragment's pixels onto the mug while keeping the stored digest string: the
        # label would flip from the chair to the mug if only the strings were compared
        tampered = np.zeros((H, W), dtype=bool)
        tampered[12:16, 0:4] = True
        masks[0]["masks"] = np.stack([tampered, masks[0]["masks"][1], masks[0]["masks"][2]])
        with self.assertRaises(diag.DiagnosticsFailure) as caught:
            diag.label_frames(cache_frames, masks, records, images)
        self.assertEqual(caught.exception.reason, "fragment_masks_missing")
        self.assertIn("pixels", caught.exception.detail)
        # a mask file with fewer masks than sealed fragments is refused too
        cache_frames, masks, records, images = synthetic_episode()
        masks[2]["masks"] = masks[2]["masks"][:2]
        with self.assertRaises(diag.DiagnosticsFailure):
            diag.label_frames(cache_frames, masks, records, images)

    def test_arrays_round_trip_and_only_labelled_fragments_enter(self) -> None:
        cache_frames, masks, records, images = synthetic_episode()
        labelled = diag.label_frames(cache_frames, masks, records, images)
        arrays = diag.labelled_arrays(labelled)
        self.assertEqual(arrays["descriptor_vits14"].shape, (6, 8))
        self.assertEqual(arrays["descriptor_vitb14"].shape, (6, 12))
        self.assertEqual(sorted(set(arrays["object"].tolist())), ["Chair|1", "Mug|2"])
        frames = diag.frames_from_arrays(arrays, "vitb14")
        self.assertEqual(len(frames), 3)
        self.assertEqual([f["object"] for f in frames[0]["fragments"]], ["Chair|1", "Mug|2"])
        self.assertEqual(len(frames[0]["fragments"][0]["descriptor"]), 12)
        direct = diag.descriptor_frames(labelled, "vitb14")
        self.assertEqual([x["object"] for x in direct[0]["fragments"] if x["object"]], [x["object"] for x in frames[0]["fragments"]])
        np.testing.assert_allclose(direct[0]["fragments"][0]["descriptor"], frames[0]["fragments"][0]["descriptor"], atol=1e-6)

    def test_an_episode_without_a_labelled_fragment_is_a_defined_empty_result_not_a_malformed_plane(self) -> None:
        cache_frames, masks, records, images = synthetic_episode(labels_of={"Chair|1": 7, "Mug|2": 8})  # no label present
        labelled = diag.label_frames(cache_frames, masks, records, images)
        self.assertEqual([f["object"] for f in labelled[0]["fragments"]], [None, None, None])
        arrays = diag.labelled_arrays(labelled)
        self.assertEqual(arrays["descriptor_vits14"].shape, (0, fc.DESCRIPTOR_DIMENSIONS["vits14"]))
        self.assertEqual(arrays["descriptor_vitb14"].shape, (0, fc.DESCRIPTOR_DIMENSIONS["vitb14"]))
        self.assertEqual(arrays["centroid_m"].shape, (0, 3))
        self.assertEqual(int(arrays["frame_count"][0]), 3)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "labelled_fragments.npz"
            np.savez_compressed(path, **arrays)
            back = dict(np.load(path))
        frames = diag.frames_from_arrays(back, "vits14")
        self.assertEqual(len(frames), 3)
        self.assertEqual(sum(len(f["fragments"]) for f in frames), 0)
        self.assertEqual(fd.separation_statistics(frames)["pairs"], 0)
        self.assertEqual(fd.recall_curve(frames)["decisions_total"], 0)
        self.assertEqual(diag.iou_rows(labelled, [{}] * 3, {}, {}), [])


class SealVerificationTests(unittest.TestCase):
    def test_the_frame_seals_are_recomputed_from_the_loaded_bytes(self) -> None:
        frames = [sealed_cache_frame(1, 1), sealed_cache_frame(2, 2)]
        with tempfile.TemporaryDirectory() as directory:
            cache_dir = Path(directory) / "procthor10k-0.1.2-train-00001"
            write_cache_episode(cache_dir, frames)
            loaded, seal = diag.load_cache_episode(cache_dir, ASSETS)
            self.assertEqual([f["tick"] for f in loaded], [1, 2])
            self.assertEqual(seal["episode_frame_count"], 2)
            # a descriptor changed on disk while the frame seal string (and so the episode seal) is kept
            tampered = json.loads(json.dumps(frames[0]))
            tampered["fragments"][0]["descriptor_vits14"] = unit(np.arange(1, 9))
            (cache_dir / f"0000{cache_runner.FRAME_FILE_SUFFIX}").write_bytes(gzip.compress(json.dumps(tampered).encode("utf-8")))
            with self.assertRaises(diag.DiagnosticsFailure) as caught:
                diag.load_cache_episode(cache_dir, ASSETS)
            self.assertEqual(caught.exception.reason, "cache_missing_or_unsealed")
            self.assertIn("frame_seal_mismatch", caught.exception.detail)
            # restored bytes pass again; other registered asset digests do not
            write_cache_episode(cache_dir, frames)
            diag.load_cache_episode(cache_dir, ASSETS)
            with self.assertRaises(diag.DiagnosticsFailure):
                diag.load_cache_episode(cache_dir, {"vits14": "b" * 64, "vitb14": "e" * 64})
            # a frame file removed: the count no longer matches the seal
            (cache_dir / f"0001{cache_runner.FRAME_FILE_SUFFIX}").unlink()
            with self.assertRaises(diag.DiagnosticsFailure):
                diag.load_cache_episode(cache_dir, ASSETS)

    def test_ruling_72_the_seal_is_recomputed_with_its_declared_source_and_an_entry_refuses_the_other(self) -> None:
        import lean_s2_04_evaluate_episode as s2_04
        frames = [sealed_cache_frame(1, 1), sealed_cache_frame(2, 2)]
        with tempfile.TemporaryDirectory() as directory:
            cache_dir = Path(directory) / "procthor10k-0.1.2-train-00001"
            write_cache_episode(cache_dir, frames, mask_source=fc.MASK_SOURCE_INSTANCE)
            _, seal = diag.load_cache_episode(cache_dir, ASSETS)
            self.assertEqual(seal["mask_source"], fc.MASK_SOURCE_INSTANCE)
            s2_04.verify_cache_episode(cache_dir, ASSETS, mask_source=fc.MASK_SOURCE_INSTANCE)
            s2_04.verify_cache_episode(cache_dir, ASSETS)                    # a diagnostic that names no source reads either
            with self.assertRaises(diag.DiagnosticsFailure) as caught:     # mixing: a sam2 run over an instance cache
                s2_04.verify_cache_episode(cache_dir, ASSETS, mask_source=fc.MASK_SOURCE_SAM2)
            self.assertIn("mask source", caught.exception.detail)
            # an instance seal relabelled as sam2 by dropping the source no longer matches its payload
            relabelled = {k: v for k, v in seal.items() if k != "mask_source"}
            (cache_dir / "episode_seal.json").write_text(json.dumps(relabelled), encoding="utf-8")
            for load in (lambda: diag.load_cache_episode(cache_dir, ASSETS),
                         lambda: s2_04.verify_cache_episode(cache_dir, ASSETS, mask_source=fc.MASK_SOURCE_SAM2)):
                with self.assertRaises(diag.DiagnosticsFailure) as caught:
                    load()
                self.assertEqual(caught.exception.detail, "episode seal mismatch")
            # a sam2 cache refuses an instance run the same way
            write_cache_episode(cache_dir, frames)
            with self.assertRaises(diag.DiagnosticsFailure):
                s2_04.verify_cache_episode(cache_dir, ASSETS, mask_source=fc.MASK_SOURCE_INSTANCE)
            s2_04.verify_cache_episode(cache_dir, ASSETS, mask_source=fc.MASK_SOURCE_SAM2)

    def test_the_registered_descriptor_asset_digests_are_the_s1_01_registry_values(self) -> None:
        digests = diag.registered_descriptor_asset_sha256s()
        self.assertEqual(set(digests), set(fc.DESCRIPTOR_SETS))
        registry = {row["asset_id"]: row for row in
                    json.loads(cache_runner.ASSET_REGISTRY_PATH.read_text(encoding="utf-8"))["asset_registry"]}
        for name, asset_id in cache_runner.DESCRIPTOR_ASSET_IDS.items():
            self.assertEqual(digests[name], registry[asset_id]["sha256"])


class IoURowsTests(unittest.TestCase):
    def test_rows_only_for_present_boxed_objects_with_the_proxy_as_a_column(self) -> None:
        cache_frames, masks, records, images = synthetic_episode(frames=1)
        labelled = diag.label_frames(cache_frames, masks, records, images)
        truth = [{"Chair|1": {"present": True, "aabb_min_m": [-0.2, -0.2, -0.2], "aabb_max_m": [0.2, 0.2, 0.2]},
                  "Mug|2": {"present": False}}]
        proxies = {"Chair|1": ([-0.1, -0.1, -0.1], [0.1, 0.1, 0.1])}
        meta = {"Chair|1": {"pickupable": False, "receptacle": True}, "Mug|2": {"pickupable": True, "receptacle": False}}
        rows = diag.iou_rows(labelled, truth, proxies, meta)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["iou_truth"], 1.0)
        self.assertAlmostEqual(rows[0]["iou_proxy"], 0.125)
        self.assertTrue(rows[0]["receptacle"])
        stats = fd.iou_statistics(rows)
        self.assertFalse(stats["median_below_gate"])


class HoldoutTests(unittest.TestCase):
    def test_membership_is_frozen_on_the_cache_and_a_failed_house_is_a_gap_in_its_own_group(self) -> None:
        cached = [f"procthor10k-0.1.2-train-{i:05d}" for i in range(43) if i != 20]
        split = rh.holdout_split(cached, seed=20260920)
        lost_training, lost_selection = split["training_houses"][3], split["selection_houses"][5]
        succeeded = [h for h in cached if h not in (lost_training, lost_selection)]
        status = diag.holdout_status(split, succeeded)
        self.assertEqual(status["training_houses"], split["training_houses"])          # unchanged by the failures
        self.assertEqual(status["selection_houses"], split["selection_houses"])
        self.assertEqual(status["training_houses_failed_diagnostics"], [lost_training])
        self.assertEqual(status["selection_houses_failed_diagnostics"], [lost_selection])
        self.assertEqual(len(status["training_houses_used"]), 29)
        self.assertEqual(len(status["selection_houses_used"]), 11)
        self.assertNotIn(lost_selection, status["training_houses_used"])               # no backfill across groups
        self.assertEqual(set(status["training_houses_used"]) & set(status["selection_houses_used"]), set())
        self.assertEqual(status["membership_rule"], diag.HOLDOUT_MEMBERSHIP_RULE)
        # the split of the full cache differs from a split of the succeeded subset: that is the point
        resplit = rh.holdout_split(succeeded, seed=20260920)
        self.assertNotEqual(resplit["training_houses"], status["training_houses_used"])


class RerunGuardTests(unittest.TestCase):
    def test_existing_weights_are_refused_without_resume_and_reused_with_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(diag.reid_weights_plan(root, resume=False), {"reuse": [], "train": ["vitb14", "vits14"]})
            (root / diag.REID_WEIGHTS_NAME.format(set_name="vits14")).write_text("{}", encoding="utf-8")
            with self.assertRaises(diag.RerunRefused):
                diag.reid_weights_plan(root, resume=False)
            self.assertEqual(diag.reid_weights_plan(root, resume=True), {"reuse": ["vits14"], "train": ["vitb14"]})

    def test_the_resume_plan_the_runner_reuses_keeps_failed_episodes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for episode_id, status in (("e-succ", "succeeded"), ("e-fail", "failed")):
                (root / episode_id).mkdir()
                (root / episode_id / "receipt.json").write_text(json.dumps({"status": status}), encoding="utf-8")
            (root / "e-partial").mkdir()
            plan = cache_runner.resume_plan(root, ["e-succ", "e-fail", "e-partial", "e-new"])
            self.assertEqual(plan, {"kept_succeeded": ["e-succ"], "kept_failed": ["e-fail"], "redo": ["e-partial", "e-new"]})


def _house_arrays(seed: int, frames: int = 4) -> dict:
    """Labelled arrays of one house: two objects per frame, separable 8/12-d descriptors."""

    rng = np.random.default_rng(seed)
    bases = {"A": rng.normal(size=12), "B": rng.normal(size=12)}
    rows = []
    for t in range(frames):
        for n, key in enumerate(sorted(bases)):
            rows.append({"fragment_id": f"f{t}:{n}", "object": key,
                         "descriptor_vits14": unit(bases[key][:8] + rng.normal(scale=0.1, size=8)),
                         "descriptor_vitb14": unit(bases[key] + rng.normal(scale=0.1, size=12)),
                         "centroid_m": [float(n), 0.0, float(t)], "aabb_min_m": [0, 0, 0], "aabb_max_m": [1, 1, 1], "pixel_count": 9})
    labelled = [{"tick": t + 1, "fragments": [r for r in rows if r["fragment_id"].startswith(f"f{t}:")]} for t in range(frames)]
    return diag.labelled_arrays(labelled)


class ReIDStageTests(unittest.TestCase):
    HOUSES = [f"procthor10k-0.1.2-train-{i:05d}" for i in range(3)]

    def _root(self, directory: str) -> Path:
        root = Path(directory)
        for i, house in enumerate(self.HOUSES):
            (root / house).mkdir()
            np.savez_compressed(root / house / "labelled_fragments.npz", **_house_arrays(i))
        return root

    def _split(self) -> dict:
        return {"training_houses": self.HOUSES[:2], "selection_houses": self.HOUSES[2:], "training_shortfall": 28,
                "selection_shortfall": 11, "houses_beyond_the_holdout": [], "order": "s0_02_house_split_rank", "seed": 1}

    def _contract(self) -> dict:
        return {"reid_training": {"temperature": 0.07, "epochs": 2, "batch_fragments": 8, "learning_rate": 0.01,
                                  "seed": 1, "output_dimension": 4, "selection_rule_threshold": 0.05}}

    def _results(self) -> list[dict]:
        return [{"episode_id": house, "status": "succeeded"} for house in self.HOUSES]

    def test_a_diverged_training_writes_no_weights_and_leaves_the_selection_rule(self) -> None:
        original = diag.rh.train_head
        diag.rh.train_head = lambda *a, **k: {"diverged": True, "loss_curve": [float("nan")], "weights": {"sha256": "x"}, "head": None}
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = self._root(directory)
                report = diag.reid_stage(self._results(), root, contract=self._contract(), split=self._split(), device="cpu", resume=False)
                self.assertEqual(report["failed_sets"], ["vits14", "vitb14"])
                for name in diag.DESCRIPTOR_KEYS:
                    entry = report["by_set"][name]
                    self.assertEqual((entry["status"], entry["reason"], entry["weights_written"]), ("failed", "training_diverged", False))
                    self.assertFalse((root / diag.REID_WEIGHTS_NAME.format(set_name=name)).exists())
                    self.assertNotIn("selection_houses_separation_projection", entry)
                    self.assertIsNotNone(entry["selection_houses_separation_frozen"]["median"])
                    self.assertIsNotNone(entry["selection_houses_recall_curve_frozen"])
                rule = report["selection_rule"]
                self.assertEqual(rule["status"], "computed")
                self.assertEqual(rule["chosen"], rule["best_frozen"])
                self.assertIsNone(rule["projection_gain_over_best_frozen"])
                self.assertEqual(rule["projections_excluded_after_divergence"], ["vits14", "vitb14"])
                self.assertEqual(report["holdout"]["training_houses_used"], self.HOUSES[:2])
        finally:
            diag.rh.train_head = original

    def test_a_converged_training_scores_separation_and_the_recall_curve_on_the_selection_houses_for_both(self) -> None:
        original_train, original_project = diag.rh.train_head, diag.rh.project_frames

        def fake_train(descriptors, classes, **kwargs):
            payload = {"schema_version": rh.WEIGHTS_SCHEMA_VERSION, "input_dimension": int(descriptors.shape[1]),
                       "output_dimension": kwargs["output_dimension"], "weight": [], "bias": [], "training": {}, "sha256": "w" * 64}
            return {"diverged": False, "loss_curve": [1.0, 0.5], "weights": payload, "head": "fake-head"}

        def fake_project(frames, head, *, source_key, target_key="reid_projection"):
            return [{**f, "fragments": [{**x, target_key: list(x[source_key])} for x in f["fragments"]]} for f in frames]

        diag.rh.train_head, diag.rh.project_frames = fake_train, fake_project
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = self._root(directory)
                report = diag.reid_stage(self._results(), root, contract=self._contract(), split=self._split(), device="cpu", resume=False)
                self.assertEqual(report["failed_sets"], [])
                for name in diag.DESCRIPTOR_KEYS:
                    entry = report["by_set"][name]
                    self.assertEqual(entry["status"], "succeeded")
                    self.assertTrue((root / entry["weights_file"]).exists())
                    self.assertEqual(entry["training_houses_used"], 2)
                    self.assertEqual(entry["selection_houses_used"], 1)
                    # identity projection: the projected numbers equal the frozen ones on the same houses
                    self.assertEqual(entry["selection_houses_separation_projection"], entry["selection_houses_separation_frozen"])
                    frozen, projected = entry["selection_houses_recall_curve_frozen"], entry["selection_houses_recall_curve_projection"]
                    self.assertEqual(frozen["grid_points"], projected["grid_points"])
                    self.assertEqual(frozen["episodes"], 1)
                    self.assertGreater(frozen["decisions_total"], 0)
                self.assertEqual(report["selection_rule"]["status"], "computed")
                self.assertAlmostEqual(report["selection_rule"]["projection_gain_over_best_frozen"], 0.0)
                self.assertEqual(report["selection_rule"]["chosen"], report["selection_rule"]["best_frozen"])
                # a second call without --resume refuses to retrain over the written weights
                with self.assertRaises(diag.RerunRefused):
                    diag.reid_stage(self._results(), root, contract=self._contract(), split=self._split(), device="cpu", resume=False)
        finally:
            diag.rh.train_head, diag.rh.project_frames = original_train, original_project


class AggregateTests(unittest.TestCase):
    def test_pooled_report_over_two_episode_files(self) -> None:
        cache_frames, masks, records, images = synthetic_episode()
        labelled = diag.label_frames(cache_frames, masks, records, images)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            results = []
            for episode_id in ("procthor10k-0.1.2-train-00001", "procthor10k-0.1.2-train-00002"):
                (root / episode_id).mkdir()
                data = {"episode_id": episode_id, "frames": 3, "episode_seal_sha256": "e" * 64, "fragments": 9,
                        "fragments_labelled": 6, "add_objects": [], "separation": {}, "recall_curve": {},
                        "fragment_truth_iou_rows": [{"iou_truth": 0.4, "iou_proxy": 0.5, "pickupable": True, "receptacle": False}]}
                for name in diag.DESCRIPTOR_KEYS:
                    frames = diag.descriptor_frames(labelled, name)
                    data["separation"][name] = fd.separation_statistics(frames)
                    data["recall_curve"][name] = fd.recall_curve(frames)
                (root / episode_id / "diagnostics.json").write_text(json.dumps(data), encoding="utf-8")
                results.append({"episode_id": episode_id, "status": "succeeded", "fragments": 9, "fragments_labelled": 6})
            empty_id = "procthor10k-0.1.2-train-00004"
            (root / empty_id).mkdir()
            empty_frames = diag.descriptor_frames(diag.label_frames(*synthetic_episode(labels_of={"Chair|1": 7})), "vits14")
            (root / empty_id / "diagnostics.json").write_text(json.dumps({
                "episode_id": empty_id, "frames": 3, "episode_seal_sha256": "f" * 64, "fragments": 9, "fragments_labelled": 0,
                "add_objects": [], "fragment_truth_iou_rows": [],
                "separation": {name: fd.separation_statistics(empty_frames) for name in diag.DESCRIPTOR_KEYS},
                "recall_curve": {name: fd.recall_curve(empty_frames) for name in diag.DESCRIPTOR_KEYS}}), encoding="utf-8")
            results.append({"episode_id": empty_id, "status": "succeeded", "fragments": 9, "fragments_labelled": 0})
            results.append({"episode_id": "procthor10k-0.1.2-train-00003", "status": "failed", "reason": "fragment_masks_missing"})
            report = diag.aggregate(results, root)
            self.assertEqual(report["episodes_used"], 3)
            self.assertEqual(report["episodes_with_zero_labelled_fragments"], [empty_id])
            self.assertFalse(report["per_house"][empty_id]["diagnostics_defined"])
            self.assertIsNone(report["per_house"][empty_id]["separation_median"]["vits14"])
            self.assertEqual(report["fragment_truth_iou"]["truth"]["count"], 2)
            self.assertEqual(report["recall_curve_by_set"]["vits14"]["episodes"], 3)
            self.assertEqual(set(report["per_house"]), {"procthor10k-0.1.2-train-00001", "procthor10k-0.1.2-train-00002", empty_id})
            self.assertEqual(report["separation_by_set"]["vitb14"]["count"], 2 * data["separation"]["vitb14"]["pairs"])


class GuardTests(unittest.TestCase):
    def test_every_bit_the_runner_needs_was_opened_by_name_and_the_values_are_frozen(self) -> None:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        for name in diag.REQUIRED_AUTHORIZATION + ("reid_adapter_head_training",):
            self.assertIs(contract["authorization"][name], True, name)
            self.assertIn(name, contract["activation_policy"]["active_true_authorizations"])
        self.assertEqual([name for name in fd.REID_VALUE_SLOTS if contract["reid_training"][name] is None], [])


if __name__ == "__main__":
    unittest.main()
