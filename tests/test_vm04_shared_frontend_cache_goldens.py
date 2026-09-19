"""Byte-preservation goldens for both shared front-end cache profiles.

D-214 and D-223/F-01 compose their caches from the same public geometry
primitives but seal two deliberately different schemas.  Neither module's own
tests pin an output digest, so a refactor of the shared core could silently
change sealed bytes while every structural assertion still passed.  This
module pins the digests themselves.

A failure here means sealed cache bytes moved.  That is only ever acceptable
as an explicit, separately reasoned schema decision -- never as a side effect
of extracting or parameterizing shared code.  D-214's bytes additionally
explain already executed receipts, so they must not move at all.
"""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests import test_vm04_d214_shared_rgbd_frontend as d214_fixtures
from tests import test_vm04_d223_f01_production_reader as f01_fixtures


D214_FRAME_ZERO_SHA256 = (
    "1efd0da1a0f737ea0aee9869ece6b7cc7b9722e8e18943efd2a75e71f2c6eab1")
D214_FRAME_ONE_SHA256 = (
    "f8c3c70edff2bfa93255c7c4d04b388bfa31293e7f8250a3f28bf1ef79838048")
D214_EPISODE_SHA256 = (
    "82beccf72b9084862b9688740978f11c10e9be1d291a471249ae09a7899e6f6c")
D214_PLACE_ZERO_SHA256 = (
    "f907600eb620ab95f893ddafe224b44dd27fd9689bcf18ccf42cc642b3e99ce5")

F01_FRAME_ZERO_SHA256 = (
    "7b23372304103960542c8ccebdafba53033a6a3b0b12a666e1127a5321033472")
F01_EPISODE_SHA256 = (
    "b269d8594eb5e8bd827b0107975b1b7b77c8ab5d5a3cf4e0abffc62c57437a05")
F01_PLACE_ZERO_SHA256 = (
    "2d8516b3e7487856f4783bd49bae256bcdb9a13a2d7530a6e9d9cf9e0ccb3e1a")


class SharedFrontendCacheGoldenTests(unittest.TestCase):
    def test_d214_legacy_profile_seals_its_frozen_digests(self):
        first = d214_fixtures.frame(0)
        second = d214_fixtures.frame(
            1, role="bottleneck", descriptor_axis=1, x=2.0)
        episode = d214_fixtures.episode([first, second])
        self.assertEqual(D214_FRAME_ZERO_SHA256, first["frame_cache_sha256"])
        self.assertEqual(D214_FRAME_ONE_SHA256, second["frame_cache_sha256"])
        self.assertEqual(D214_EPISODE_SHA256, episode["episode_cache_sha256"])
        self.assertEqual(
            D214_PLACE_ZERO_SHA256,
            first["place_observation"]["place_observation_sha256"])

    def test_d214_place_observation_still_carries_structural_probabilities(self):
        place = d214_fixtures.frame(0)["place_observation"]
        self.assertEqual(
            {"basin", "bottleneck", "unknown"},
            set(place["structural_role_probabilities"]))

    def test_f01_production_profile_seals_its_digests(self):
        frame, episode, _generator, _extractor, _rgb = (
            f01_fixtures.materialized_episode())
        self.assertEqual(F01_FRAME_ZERO_SHA256, frame["frame_cache_sha256"])
        self.assertEqual(F01_EPISODE_SHA256, episode["episode_cache_sha256"])
        self.assertEqual(
            F01_PLACE_ZERO_SHA256,
            frame["place_observation"]["place_observation_sha256"])

    def test_f01_place_observation_carries_no_structural_field(self):
        place = f01_fixtures.materialized_episode()[0]["place_observation"]
        self.assertFalse(
            [key for key in place if "structural" in key or "semantic" in key])

    def test_the_two_profiles_do_not_share_a_schema_or_a_digest(self):
        d214_frame = d214_fixtures.frame(0)
        f01_frame = f01_fixtures.materialized_episode()[0]
        self.assertNotEqual(
            d214_frame["schema_version"], f01_frame["schema_version"])
        self.assertNotEqual(
            d214_frame["frame_cache_sha256"], f01_frame["frame_cache_sha256"])
        self.assertNotEqual(set(d214_frame), set(f01_frame))


if __name__ == "__main__":
    unittest.main()
