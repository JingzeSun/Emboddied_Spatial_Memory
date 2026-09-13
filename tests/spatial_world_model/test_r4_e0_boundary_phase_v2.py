"""Pure contract tests for the D-118 E0-v2 phase audit helpers."""

import json
from pathlib import Path
import unittest

from ops.spatial_history.r4_e0_boundary_phase_v2 import (
    boundary_support, geometry_signature, summarize, v1_audit_view,
)
from spatial_world_model.public_geometry import recover_openings as recover_v1
from spatial_world_model.public_geometry_v2 import recover_openings as recover_v2
from tests.spatial_world_model.test_public_geometry import opening


ROOT = Path(__file__).resolve().parents[2]
V1 = json.loads((ROOT / "configs/spatial_history/public_geometry_parallel_v1.json").read_text())
V2 = json.loads((ROOT / "configs/spatial_history/public_geometry_boundary_v2.json").read_text())


class BoundaryPhaseHelpersTests(unittest.TestCase):
    def test_strict_candidate_geometry_matches_v1_after_schema_projection(self):
        history = [opening()]
        first = recover_v1(history, V1["public_sensor_spec"], V1["extractor"])
        second = recover_v2(history, V2["public_sensor_spec"], V2["extractor"])
        self.assertEqual(geometry_signature(first), geometry_signature(second))
        projected = v1_audit_view(second)
        self.assertEqual(projected["schema_version"], "public-openings-v1")
        self.assertNotIn("evidence_counts", projected)

    def test_boundary_support_lists_only_explicit_b_pixels(self):
        history = [opening()]
        width = history[0]["width"]
        for v in range(3, 7):
            history[0]["depth_m"][v * width + 9] = 1.00025
        prediction = recover_v2(history, V2["public_sensor_spec"], V2["extractor"])
        support = boundary_support(prediction)
        self.assertEqual(len(support), 4)
        self.assertEqual({tuple(item["pixel"]) for item in support}, {(9, v) for v in range(3, 7)})
        self.assertEqual({item["boundary_kind"] for item in support}, {"x_right"})

    def test_summary_rejects_wrong_fixed_census(self):
        assessment = {"accepted": True}
        row = {"v1_assessment": assessment, "v2_assessment": assessment,
               "v2_boundary_support": [], "v1_accepted_geometry_exactly_preserved": True}
        result = summarize([row])
        self.assertFalse(result["accepted"])
        self.assertIn("v1_accepted_census", result["failed_checks"])


if __name__ == "__main__":
    unittest.main()
