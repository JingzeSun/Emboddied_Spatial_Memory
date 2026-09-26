"""The ruling-75 evidence-ceiling diagnostic's model-free parts: strict-majority ownership, the ideal memory keeping
each object's latest frame (points and box union), and the two rules read on the fixture's rendered depth views."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt", PROJECT_ROOT / "tests"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import lean_s2_05_evidence_ceiling as ceiling  # noqa: E402
from test_vsmt_lean_runner import depth_view, fragment_row, front_face_points, unit  # noqa: E402

BOX = ([-0.1, -0.1, 1.9], [0.1, 0.1, 2.1])


class OwnershipTests(unittest.TestCase):
    def test_only_a_strict_majority_owns_a_fragment(self) -> None:
        owners = ceiling.owners_of({"f:a": {"overlap": {"Mug|1": 0.8, "Book|2": 0.1}},
                                    "f:b": {"overlap": {"Mug|1": 0.5, "Book|2": 0.5}},
                                    "f:c": {"overlap": {}}})
        self.assertEqual(owners, {"f:a": "Mug|1", "f:b": None, "f:c": None})


class IdealMemoryTests(unittest.TestCase):
    def test_the_latest_frame_replaces_and_same_frame_fragments_union(self) -> None:
        memory = ceiling.IdealMemory()
        a = fragment_row("f:1", descriptor=unit(1), centroid=[0.0, 0.0, 2.0])
        b = fragment_row("f:2", descriptor=unit(1), centroid=[0.4, 0.0, 2.0])
        memory.observe(1, [a, b], {"f:1": "Mug|1", "f:2": "Mug|1"}, {"f:1": [[0.0, 0.0, 1.9]], "f:2": [[0.4, 0.0, 1.9]]})
        mug = memory.entities["Mug|1"]
        self.assertEqual((mug["tick"], len(mug["points"]), mug["aabb_min_m"][0], mug["aabb_max_m"][0]), (1, 2, -0.1, 0.5))
        self.assertAlmostEqual(mug["centroid_m"][0], 0.2)
        c = fragment_row("f:3", descriptor=unit(1), centroid=[1.0, 0.0, 2.0])
        memory.observe(2, [c], {"f:3": "Mug|1"}, {"f:3": [[1.0, 0.0, 1.9]]})
        self.assertEqual((memory.entities["Mug|1"]["tick"], memory.entities["Mug|1"]["points"]), (2, [[1.0, 0.0, 1.9]]))
        memory.observe(3, [c], {"f:3": None}, {"f:3": []})       # an unowned fragment changes nothing
        self.assertEqual(memory.entities["Mug|1"]["tick"], 2)


class RuleTests(unittest.TestCase):
    def test_surface_points_are_clean_where_the_grid_sees_only_a_front_layer(self) -> None:
        memory = ceiling.IdealMemory()
        row = fragment_row("f:1", descriptor=unit(1), centroid=[0.0, 0.0, 2.0])
        memory.observe(1, [row], {"f:1": "Mug|1"}, {"f:1": front_face_points(*BOX)})
        present = ceiling.ratios_by_rule(memory, ["Mug|1"], depth_view("f" * 64, [BOX]), 4)
        self.assertEqual(present["surface"]["Mug|1"], {"should_be_visible_ratio": 1.0, "free_space_coverage_ratio": 0.0})
        self.assertEqual(present["grid"]["Mug|1"]["should_be_visible_ratio"], 16 / 64)
        gone = ceiling.ratios_by_rule(memory, ["Mug|1"], depth_view("f" * 64, []), 4)
        for rule in ceiling.RULES:
            self.assertEqual(gone[rule]["Mug|1"]["free_space_coverage_ratio"], 1.0, rule)


if __name__ == "__main__":
    unittest.main()
