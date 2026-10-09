"""Parity with the frozen pipeline on one released episode (needs downloaded data; skipped otherwise).

Set ``VSMT_DATA`` to the ``--dest`` of ``ops/vsmt/hf_fetch.py`` after restoring, from T0, ``weights/sam2/VSMT-lean.tar``
and ``reid/reid_head_vitb14_154776d.json``, and, from T1, the raw and SAM 2.1 cache tars of
``validation/.../procthor10k-0.1.2-train-02318``.  The raw-path test also loads DINOv2 (``VSMT_MEMORY_CACHE``).

1. Replaying the sealed cache through ``VSMTMemory`` gives the same per-frame seal chain as the audit runner's reading
   path (``ops/vsmt``) with ``lean_runner.run_episode``, in the same process: the package adds no decision of its own.
2. Building frames from the public RGB-D and the cache's masks reproduces the cache's fragment geometry bit for bit, its
   DINOv2 descriptors to float32 rounding (the cache was computed on a GPU) and the camera's forward vector to float64
   rounding (``numpy.linalg.norm`` rounds differently across numpy builds).

Bit identity holds within one environment; across CPUs and library versions the decisions may differ in a few near-ties
(docs/REPRODUCE.md, determinism boundary).
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

import numpy as np

from vsmt_memory import _repo
from vsmt_memory.episodes import HfEpisode
from vsmt_memory.memory import ARM, VSMTMemory, frozen_policy
from vsmt_memory.weights import load_pretrained

EPISODE = "procthor10k-0.1.2-train-02318"
DATA = Path(os.environ["VSMT_DATA"]) if os.environ.get("VSMT_DATA") else None
FRAMES = int(os.environ.get("VSMT_PARITY_FRAMES", "60"))


def episode(front: str = "sam2") -> HfEpisode:
    return HfEpisode(DATA / "vsmt_outputs/s3-02-3f6ef1d/validation" / EPISODE,
                     DATA / f"vsmt_caches/s3-02-{front}-3f6ef1d/validation" / EPISODE)


@unittest.skipUnless(DATA and (DATA / "vsmt_caches/s3-02-sam2-3f6ef1d/validation" / EPISODE).is_dir(),
                     "VSMT_DATA with the parity episode is not set")
class ParityTests(unittest.TestCase):
    def test_cache_replay_equals_the_audit_runners_reading_path(self) -> None:
        self.check_replay("sam2")

    def test_instance_mask_replay_with_the_released_head(self) -> None:
        """The instance-mask front end, with the ReID head of the T0 addendum (``reproduce/fetch_extras.py``)."""

        if not (DATA / "vsmt_caches/s3-02-instance-3f6ef1d/validation" / EPISODE).is_dir():
            self.skipTest("the instance-mask cache of the parity episode is not restored")
        self.check_replay("instance")

    def check_replay(self, front: str) -> None:
        ops = str(_repo.REPO_ROOT / "ops" / "vsmt")
        if ops not in sys.path:
            sys.path.insert(0, ops)
        import lean_s1_03_cache as cache_runner
        import lean_s2_01_runner as s2_01
        import lean_s2_04_evaluate_episode as s2_04
        import lean_s2_05_node_audit as node_audit
        from vsmt import lean_assignment as la
        from vsmt import lean_runner as lr

        policy, missing = s2_01.gather_policy()
        self.assertEqual(missing, [])
        self.assertEqual(lr.validate_policy(policy), frozen_policy())

        weights = load_pretrained(front, 7, restored_root=DATA)
        ep = episode(front)
        self.assertEqual(ep.mask_source, weights.mask_source)
        reader = s2_04.episode_depth_reader(ep.raw_dir, ep.cache_dir)

        def frames():
            for index in range(FRAMES):
                frame = cache_runner.load_cache_frame(ep.cache_dir / f"{index:04d}{cache_runner.FRAME_FILE_SUFFIX}")
                frame[lr.PUBLIC_DEPTH_VIEW_KEY] = reader(index, frame)
                yield frame

        memory = VSMTMemory(weights, episode_id=EPISODE)
        receipts = [step["receipt"] for step in lr.run_episode(
            frames(), episode_id=EPISODE, arm=ARM, config={"tau_r": weights.tau_r}, policy=policy,
            descriptor=la.SELECTED_DESCRIPTOR, projector=memory.projector, scorer=memory.scorer)]
        folded = []
        for index in range(FRAMES):
            result = memory.step_cache_frame(ep.cache_frame(index))
            folded += [row["folded_entity_id"] for row in result.maintenance.get("dedup", [])]
        self.assertEqual(memory.trajectory_sha256(), node_audit.trajectory_sha256(receipts))
        live = {entity.entity_id for entity in memory.entities()}
        self.assertTrue(all(memory.resolve(entity_id) in live for entity_id in folded))
        self.assertEqual(memory.memory["memory_digest"], receipts[-1]["memory_digest_after"])

    def test_raw_rgbd_path_reproduces_the_cache_fragments(self) -> None:
        from vsmt_memory.frontend import DinoV2Extractor, build_frame
        from vsmt_memory.weights import default_cache_dir

        ep = episode()
        extractor = DinoV2Extractor(cache_dir=default_cache_dir())
        worst = 0.0
        for index in range(0, ep.frame_count, max(1, ep.frame_count // 10)):
            frame = ep.public_frame(index)
            built = build_frame(tick=index + 1, rgb=frame["rgb"], depth_m=frame["depth_m"], intrinsics=frame["intrinsics"],
                                pose=frame["pose"], masks=frame["masks"], patch_tokens=extractor, strict=True)
            cached = ep.cache_frame(index)
            np.testing.assert_allclose(built.cache_frame["camera_forward"], cached["camera_forward"], rtol=0, atol=1e-12)
            self.assertEqual([f["mask_sha256"] for f in built.cache_frame["fragments"]],
                             [f["mask_sha256"] for f in cached["fragments"]])
            for mine, theirs in zip(built.cache_frame["fragments"], cached["fragments"]):
                for key in ("fragment_id", "centroid_m", "aabb_min_m", "aabb_max_m", "pixel_count", "depth_valid_ratio"):
                    self.assertEqual(mine[key], theirs[key], f"frame {index} {mine['fragment_id']} {key}")
                worst = max(worst, float(np.abs(np.subtract(mine["descriptor_vitb14"], theirs["descriptor_vitb14"])).max()))
        self.assertLess(worst, 1e-5)


if __name__ == "__main__":
    unittest.main()
