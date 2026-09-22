"""The S1-04 diagnostics runner's model-free parts: labelling cache fragments from recovered masks
and private instance images (digest check first), the fragment-versus-truth IoU rows with the
proxy column, the labelled-fragment arrays round trip that feeds the ReID stage, aggregation over
per-episode diagnostics files, and the authorization guard.  No model, simulator or cache root.
"""

from __future__ import annotations

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

import lean_s1_04_diagnostics as diag  # noqa: E402
from vsmt import lean_frontend_diagnostics as fd  # noqa: E402

CONTRACT_PATH = PROJECT_ROOT / "configs" / "vsmt" / "lean_s1_04_frontend_diagnostics_v1.json"
H = W = 16


def unit(vector) -> list[float]:
    array = np.asarray(vector, dtype=np.float64)
    return (array / np.linalg.norm(array)).tolist()


def synthetic_episode(frames: int = 3):
    """Two fragments per frame: one on the chair (majority), one half on the mug half on background."""

    rng = np.random.default_rng(7)
    cache_frames, masks_by_frame, records, images = [], [], [], []
    for t in range(frames):
        labels = np.zeros((H, W), dtype=np.uint16)
        labels[2:10, 2:10] = 1   # chair
        labels[12:16, 0:4] = 2   # mug
        chair_mask = np.zeros((H, W), dtype=bool); chair_mask[3:9, 3:9] = True          # fully on the chair
        mug_mask = np.zeros((H, W), dtype=bool); mug_mask[10:16, 0:4] = True            # 16 of 24 px on the mug
        half_mask = np.zeros((H, W), dtype=bool); half_mask[8:12, 8:12] = True          # 8 of 16 px on the chair: no majority
        shas = ["a" * 64, "b" * 64, "c" * 64]
        fragments = []
        for n, (sha, mask) in enumerate(zip(shas, (chair_mask, mug_mask, half_mask))):
            fragments.append({"fragment_id": f"f{t}:{n}", "descriptor_vits14": unit(rng.normal(size=8)),
                              "descriptor_vitb14": unit(rng.normal(size=12)), "centroid_m": [float(n), 0.0, float(t)],
                              "aabb_min_m": [n - 0.2, -0.2, t - 0.2], "aabb_max_m": [n + 0.2, 0.2, t + 0.2],
                              "pixel_count": int(mask.sum()), "mask_sha256": sha})
        cache_frames.append({"tick": t + 1, "fragments": fragments})
        masks_by_frame.append({"masks": np.stack([chair_mask, mug_mask, half_mask]), "mask_sha256": shas})
        records.append({"observation_index": t, "object_id_to_entity_id": {"Chair|1": 1, "Mug|2": 2}})
        images.append(labels)
    return cache_frames, masks_by_frame, records, images


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
            results.append({"episode_id": "procthor10k-0.1.2-train-00003", "status": "failed", "reason": "fragment_masks_missing"})
            report = diag.aggregate(results, root)
            self.assertEqual(report["episodes_used"], 2)
            self.assertEqual(report["fragment_truth_iou"]["truth"]["count"], 2)
            self.assertEqual(report["recall_curve_by_set"]["vits14"]["episodes"], 2)
            self.assertEqual(set(report["per_house"]), {"procthor10k-0.1.2-train-00001", "procthor10k-0.1.2-train-00002"})
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
