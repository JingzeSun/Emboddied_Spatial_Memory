"""D-224 / S2-05 tests: the direction-B position-gate probe on hand-made sealed frames.

A wrong bind 1.5 m from the chosen entity with disjoint boxes is outside a 0.5 m gate and, re-solved, goes to the
correct entity (repaired); a teacher-correct bind 3 m away is blocked and falls to its birth column; a near correct
bind is untouched; a 10 m gate changes nothing.  The box clause lets an overlapping box through regardless of
distance.  Read-only, CPU, seconds.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt", PROJECT_ROOT / "tests"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import direction_b_probe as probe  # noqa: E402
import test_vsmt_lean_model as helpers  # noqa: E402
from vsmt import lean_assignment as la  # noqa: E402


def sealed_frame() -> tuple[dict, dict[str, str]]:
    objects = {**helpers.OBJECTS, "vase": (helpers.unit(4), [-1.0, 0.0, 4.0])}  # mug [0,0,2], book [1,0,2], lamp [-1,0,2.5], vase 1.5 m behind the lamp
    memory, ids = helpers.memory_with(objects)
    mug, book, lamp = objects["mug"][0], objects["book"][0], objects["lamp"][0]
    fragments = [helpers.fragment("f:mug", descriptor=mug, centroid=[0.02, 0.0, 2.0]),
                 helpers.fragment("f:book", descriptor=book, centroid=[4.0, 0.0, 2.0]),      # the book seen 3 m away
                 helpers.fragment("f:lamp", descriptor=lamp, centroid=[-1.0, 0.0, 2.5])]
    frame = helpers.frame_with(*fragments, tick=2, geometry={ids[n]: (1.0, 0.0) for n in objects}, seed="probe")
    stage_a = la.build_assignment_inputs(frame, memory, birth_neighbourhood_radius_m=helpers.BIRTH_RADIUS, **helpers.RECALL)
    targets = {"f:mug": {"status": "labelled", "target": ids["mug"]}, "f:book": {"status": "labelled", "target": ids["book"]},
               "f:lamp": {"status": "labelled", "target": ids["lamp"]}}
    return {"stage_a": stage_a, "targets": targets}, ids


def logits_for(record: dict, ids: dict[str, str], *, lamp_to_vase: float = 5.0, lamp_to_lamp: float = 3.0) -> tuple[dict, dict]:
    association = {f"{r['fragment_id']}|{r['entity_id']}": -5.0 for r in record["stage_a"]["association_rows"]}
    association[f"f:mug|{ids['mug']}"] = 6.0
    association[f"f:book|{ids['book']}"] = 6.0
    association[f"f:lamp|{ids['vase']}"] = lamp_to_vase   # the student prefers the unclaimed vase entity, 1.5 m away, for the lamp fragment
    association[f"f:lamp|{ids['lamp']}"] = lamp_to_lamp
    birth = {f: -2.0 for f in record["stage_a"]["rows"]}
    return association, birth


class GateTests(unittest.TestCase):
    def test_gate_rule(self) -> None:
        self.assertTrue(probe.gate_allows(0.4, 0.0, 0.5))
        self.assertFalse(probe.gate_allows(0.6, 0.0, 0.5))
        self.assertTrue(probe.gate_allows(3.0, 0.01, 0.5))            # overlapping boxes pass regardless of distance
        self.assertFalse(probe.gate_allows(3.0, 0.01, 0.5, box_clause=False))

    def test_wrong_far_bind_is_repaired_and_correct_far_bind_is_blocked(self) -> None:
        record, ids = sealed_frame()
        association, birth = logits_for(record, ids)
        self.assertIn(f"f:book|{ids['book']}", association)  # the far book entity is recalled through the global channel
        tally = probe.empty_tally([0.5, 10.0])
        probe.frame_outcomes(record, association, birth, [0.5, 10.0], tally)
        self.assertEqual(tally["decisions"], 3)
        self.assertEqual(tally["outcomes"], {"correct_bind": 2, "wrong_bind": 1})
        near = tally["per_tolerance"]["0.5"]
        self.assertEqual((near["wrong_bind_outside_gate"], near["wrong_bind_repaired"], near["wrong_bind_still_wrong"]), (1, 1, 0))
        self.assertEqual(near["wrong_bind_regated_to"]["active"], 1)
        self.assertEqual(near["correct_bind_outside_gate"], 1)
        self.assertEqual(near["correct_bind_blocked_to"]["birth"], 1)
        self.assertEqual(near["inside_gate_decisions_changed"], 0)
        far = tally["per_tolerance"]["10.0"]
        self.assertEqual(far["gated_cells"], 0)
        self.assertEqual((far["wrong_bind_outside_gate"], far["correct_bind_outside_gate"]), (0, 0))
        self.assertEqual(sum(v for k, v in tally["histogram"].items() if k.startswith("wrong_bind|[1.0,2.0)|iou_zero")), 1)
        self.assertIn(f"f:lamp|{ids['vase']}", association)
        self.assertEqual(sum(v for k, v in tally["histogram"].items() if k.startswith("correct_bind|[2.0,4.0)")), 1)

    def test_merge_and_summary_shares(self) -> None:
        record, ids = sealed_frame()
        association, birth = logits_for(record, ids)
        a = probe.empty_tally([0.5])
        probe.frame_outcomes(record, association, birth, [0.5], a)
        b = probe.empty_tally([0.5])
        probe.frame_outcomes(record, association, birth, [0.5], b)
        probe.merge_tallies(a, b)
        self.assertEqual(a["decisions"], 6)
        self.assertEqual(a["per_tolerance"]["0.5"]["wrong_bind_repaired"], 2)
        run = {"arm": "VSMT-lean", "label": "A7", "tolerances_m": [0.5], "pooled": a}
        summary = probe.summarise([run, {**run, "label": "A19"}])
        arm = summary["per_arm"]["VSMT-lean"]
        self.assertEqual(arm["labels"], ["A7", "A19"])
        self.assertAlmostEqual(arm["per_tolerance"]["0.5"]["wrong_repaired_share"], 1.0)
        self.assertAlmostEqual(arm["per_tolerance"]["0.5"]["correct_blocked_share"], 0.5)


if __name__ == "__main__":
    unittest.main()
