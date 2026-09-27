"""D-224 / S2-05 tests: the read-only attribution export v2 (ruling 79-2) on hand-made label rows.

The window phase follows the evaluator (after the window means frame_index > window_end, so the window's last
frame is still before), and a gone(moved) label is filed by whether its object has a fragment this frame, whether
another entity carries the object within delta on the committed memory, and how far the entity sits.  CPU only.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import lean_s2_05_attribution_export as export  # noqa: E402


def row(frame_index: int) -> dict:
    return {
        "frame_index": frame_index,
        "targets": {"f1": {"status": "labelled", "key": "Mug|1"}, "f2": {"status": "unlabelled", "key": None}},
        "existence_labels": {
            "e1": {"status": "gone", "key": "Mug|1", "reason": "moved", "displacement_m": 0.8},
            "e2": {"status": "gone", "key": "Book|2", "reason": "moved", "displacement_m": 2.5},
            "e3": {"status": "gone", "key": "Cup|3", "reason": "absent"},
            "e4": {"status": "present", "key": "Mug|1", "reason": None, "displacement_m": 0.1},
            "e5": {"status": "identity_ambiguous", "key": None, "reason": "no_strict_majority"},
        },
        "wrongly_absent_objects": ["Book|2"],
        "truth_in_scope": ["Book|2", "Mug|1"],
        "stale_entities": ["e3", "e9"],
        "decomposition": {"existence": {"candidates": 5, "correct": 2}},
        "node_prf1": {"matched": 1, "predicted": 3, "truth": 2},
        "node_prf1_iou": {"matched": 0, "predicted": 3, "truth": 2},
    }


class AttributionExportV2Tests(unittest.TestCase):
    def test_the_window_phase_is_the_evaluators(self) -> None:
        self.assertEqual(export.phase_of(10, 10), export.PHASE_BEFORE)
        self.assertEqual(export.phase_of(11, 10), export.PHASE_AFTER)
        self.assertEqual(export.phase_of(500, None), export.PHASE_BEFORE)

    def test_displacement_bins(self) -> None:
        self.assertEqual([export.displacement_bin(v) for v in (0.6, 0.75, 0.9, 1.5, 3.0, None)],
                         ["0.5-0.75", "0.5-0.75", "0.75-1.0", "1.0-2.0", ">2.0", "unknown"])

    def test_a_row_is_filed_by_class_phase_fragment_carrier_and_distance(self) -> None:
        intervened = {"Cup|3": "remove", "Book|2": "move"}
        counters = export.new_counters()
        export.tally_row(row(11), intervened, 10, counters)
        after = export.PHASE_AFTER
        self.assertEqual(dict(counters["gone_moved_split"]), {
            ("never_intervened", after, "yes", "yes", "0.75-1.0"): 1,  # the mug is seen and carried: e1 is a leftover
            ("move", after, "no", "no", ">2.0"): 1,                    # the book is unseen and nobody carries it
        })
        self.assertEqual(counters["existence"][("gone", "absent", "remove", after)], 1)
        self.assertEqual(counters["existence"][("identity_ambiguous", "no_strict_majority", "no_key", after)], 1)
        self.assertEqual(sum(counters["existence"].values()), 5)
        self.assertEqual(dict(counters["absent"]), {("move", after): 1})
        self.assertEqual(dict(counters["in_scope"]), {("move", after): 1, ("never_intervened", after): 1})
        self.assertEqual(dict(counters["stale"]), {("remove", after): 1, ("key_not_in_frame_labels", after): 1})
        self.assertEqual(counters["node"], {"matched": 1, "predicted": 3, "truth": 2})
        self.assertEqual(counters["decomposition"]["existence"]["candidates"], 5)

    def test_the_last_window_frame_is_before(self) -> None:
        counters = export.new_counters()
        export.tally_row(row(10), {}, 10, counters)
        self.assertTrue(all(key[1] == export.PHASE_BEFORE for key in counters["gone_moved_split"]))
        self.assertTrue(all(key[1] == export.PHASE_BEFORE for key in counters["absent"]))


if __name__ == "__main__":
    unittest.main()
